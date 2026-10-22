#!/usr/bin/env python3

"""
Generate an HDF5 library for OpenMC based on the JEFF 4.0 nuclear data library.
Because JEFF does not distribute photoatomic or atomic relaxation data, these
are obtained from ENDF/B-VIII.1.
"""


import argparse
from multiprocessing import Pool
from pathlib import Path
from shutil import rmtree

import openmc.data
from utils import download, extract, process_neutron, process_thermal

# Directory-based JEFF-4.0 thermal evaluations.
DIRECTORY_TSL = {
    'PuO2': ('O16', 'Pu238', 'Pu239', 'Pu240', 'Pu241', 'Pu242'),
    'ThO2': ('O16', 'Th232'),
    'UO2':  ('O16', 'U238'),
    'Zy4':  ('Sn112', 'Sn114', 'Sn115', 'Sn116', 'Sn117', 'Sn118', 'Sn119', 'Sn120', 'Sn122', 'Sn124',
             'Zr90', 'Zr91', 'Zr92', 'Zr94', 'Zr96')}


def directory_tsl_args(neutron_dir, thermal_dir, output_dir, libver):
    """Yield arguments for directory-based JEFF-4.0 TSL evaluations."""
    for material, nuclides in DIRECTORY_TSL.items():
        material_dir = thermal_dir / f'tsl_{material}'

        burnup_dirs = []
        if material == 'Zy4':
            burnup_dirs = sorted(
                (material_dir / 'Burnup').glob('[0-9]*GWdt'),
                key=lambda path: int(path.name[:-4]),
            )
            if not burnup_dirs:
                raise FileNotFoundError('No Zy4 burnup evaluations found')

        for nuclide in nuclides:
            symbol = nuclide.rstrip('0123456789')
            Z, A, _ = openmc.data.zam(nuclide)
            path_neutron = (
                neutron_dir / f'n_{Z}-{symbol}-{A:03d}g.jeff'
            )

            evaluations = [
                ('', sorted(
                    material_dir.glob(
                        f'[0-9]*K/'
                        f'tsl_{nuclide}_{material}_[0-9]*K.jeff'
                    ),
                    key=lambda path: int(path.parent.name[:-1]),
                ))
            ]
            evaluations.extend(
                (f'_{path.name}', [
                    path / f'tsl_{nuclide}_{material}.jeff'
                ])
                for path in burnup_dirs
            )

            if nuclide == 'O16':
                table_name = f'o{material.lower()}'
            elif nuclide == 'U238' and material == 'UO2':
                table_name = 'uuo2'
            else:
                table_name = (
                    f'{nuclide.lower()}{material.lower()}'[:6]
                )

            isotope_specific = (
                material == 'Zy4' or (material == 'PuO2' and symbol == 'Pu')
            )
            name_part = nuclide if isotope_specific else symbol
            name = f'c_{name_part}_in_{material}'

            for suffix, paths_thermal in evaluations:
                missing = [p for p in paths_thermal if not p.is_file()]
                if not paths_thermal or missing:
                    raise FileNotFoundError(
                        f'No TSL evaluations found for '
                        f'{nuclide} in {material}{suffix}'
                    )

                yield (
                    path_neutron,
                    paths_thermal,
                    output_dir,
                    libver,
                    name + suffix,
                    table_name,
                    1000*Z + A,
                    nuclide,
                    material != 'Zy4',
                )


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=CustomFormatter
    )

    parser.add_argument('-d', '--destination', type=Path,
                        help='Directory to create new library in')
    parser.add_argument('--download', action='store_true',
                        help='Download archive files')
    parser.add_argument('--no-download', dest='download', action='store_false',
                        help='Do not download archive files')
    parser.add_argument('--extract', action='store_true',
                        help='Extract archive files')
    parser.add_argument('--no-extract', dest='extract', action='store_false',
                        help='Do not extract archive files')
    parser.add_argument('--libver', choices=['earliest', 'latest'],
                        default='earliest', help="Output HDF5 versioning. Use "
                        "'earliest' for backwards compatibility or 'latest' for "
                        "performance")
    parser.add_argument('-r', '--release', choices=['4.0'],
                        default='4.0', help="The nuclear data library release "
                        "version. The currently supported options are 4.0")
    parser.add_argument('-p', '--particles', choices=['neutron', 'thermal', 'photon'],
                        nargs='+', default=['neutron', 'thermal', 'photon'],
                        help="Incident particles to include")
    parser.add_argument('--cleanup', action='store_true',
                        help="Remove download directories when data has "
                        "been processed")
    parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                        help="Do not remove download directories when data has "
                        "been processed")
    parser.add_argument('--temperatures', type=float,
                        default=[250.0, 293.6, 600.0, 900.0, 1200.0, 2500.0],
                        help="Temperatures in Kelvin", nargs='+')
    parser.set_defaults(download=True, extract=True, cleanup=False)
    args = parser.parse_args()


    def sort_key(path):
        if path.name.startswith('c_'):
            # Ensure that thermal scattering gets sorted after neutron data
            return (1000, path)
        else:
            return openmc.data.zam(path.stem)


    library_name = 'jeff'

    cwd = Path.cwd()

    endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))
    neutron_dir = endf_files_dir / 'neutron'
    thermal_dir = endf_files_dir / 'thermal'
    download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))
    # the destination is decided after the release is known
    # to avoid putting the release in a folder with a misleading name
    if args.destination is None:
        args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

    # This dictionary contains all the unique information about each release. This
    # can be extended to accommodate new releases
    release_details = {
        '4.0': {
            'neutron': {
                'base_url': 'https://data.oecd-nea.org/records/e9ajn-a3p20/files/',
                'compressed_files': [
                    'JEFF40-Evaluations-Neutron-593.zip?download=1'
                ],
                'checksums': ['51d00ee7bf1491d428f9b30a9782e41d'],
                'file_type': 'endf',
                'endf_files': neutron_dir.rglob('*.jeff'),
            },
            'thermal': {
                'base_url': 'https://data.oecd-nea.org/records/scmva-nqh68/files/',
                'compressed_files': ['JEFF40-Evaluations-TSL.zip?download=1'],
                'checksums': ['13d22cd59f83368885ab2d86300b470a'],
                'file_type': 'endf',
                'sab_files': [
                    # Hydrogen (H-1) compounds
                    ('n_1-H-001g.jeff', 'tsl_H_Benzene.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_C5O2H8.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_C8H8.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_CaH2.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_CaO2H2.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_CH2.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_CH4-liquid.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_CH4-solid.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_H2O.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_HF.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_Ice.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_KOH.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_LiH.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_Mesitylene.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_MgH2.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_MgOH2.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_NaMgH3.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_NaOH.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_ortho-H.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_para-H.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_ParaffinicOil.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_SrH2.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_Toluene.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_UH3.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_YH2.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_ZrH.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_ZrH15.jeff'),
                    ('n_1-H-001g.jeff', 'tsl_H_ZrH2.jeff'),
                    # Deuterium (H-2) compounds
                    ('n_1-H-002g.jeff', 'tsl_D_7LiD.jeff'),
                    ('n_1-H-002g.jeff', 'tsl_D_D2O.jeff'),
                    ('n_1-H-002g.jeff', 'tsl_D_MgD2.jeff'),
                    ('n_1-H-002g.jeff', 'tsl_D_ortho-D.jeff'),
                    ('n_1-H-002g.jeff', 'tsl_D_para-D.jeff'),
                    # Lithium (Li-7) compounds
                    ('n_3-Li-007g.jeff', 'tsl_7Li_7LiD.jeff'),
                    ('n_3-Li-007g.jeff', 'tsl_Li_FLiBe.jeff'),
                    ('n_3-Li-007g.jeff', 'tsl_Li_LiF.jeff'),
                    ('n_3-Li-007g.jeff', 'tsl_Li_LiH.jeff'),
                    # Beryllium (Be-9) compounds
                    ('n_4-Be-009g.jeff', 'tsl_Be_Be.jeff'),
                    ('n_4-Be-009g.jeff', 'tsl_Be_Be2C.jeff'),
                    ('n_4-Be-009g.jeff', 'tsl_Be_BeF2.jeff'),
                    ('n_4-Be-009g.jeff', 'tsl_Be_BeO.jeff'),
                    ('n_4-Be-009g.jeff', 'tsl_Be_FLiBe.jeff'),
                    # Carbon (C-12) compounds
                    ('n_6-C-012g.jeff', 'tsl_C_Be2C.jeff'),
                    ('n_6-C-012g.jeff', 'tsl_C_C5O2H8.jeff'),
                    ('n_6-C-012g.jeff', 'tsl_C_C8H8.jeff'),
                    ('n_6-C-012g.jeff', 'tsl_C_CF2.jeff'),
                    ('n_6-C-012g.jeff', 'tsl_C_CH2.jeff'),
                    ('n_6-C-012g.jeff', 'tsl_C_Diamond.jeff'),
                    ('n_6-C-012g.jeff', 'tsl_C_Graphite.jeff'),
                    ('n_6-C-012g.jeff', 'tsl_C_UC.jeff'),
                    ('n_6-C-012g.jeff', 'tsl_C_ZrC.jeff'),
                    # Nitrogen (N-14) compounds
                    ('n_7-N-014g.jeff', 'tsl_N_GaN.jeff'),
                    ('n_7-N-014g.jeff', 'tsl_N_UN.jeff'),
                    # Oxygen (O-16) compounds
                    ('n_8-O-016g.jeff', 'tsl_O_Al2O3.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_BeO.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_C5O2H8.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_CaO2H2.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_D20.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_Ge3Bi4O12.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_KOH.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_MgO.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_MgOH2.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_NaOH.jeff'),
                    ('n_8-O-016g.jeff', 'tsl_O_Y3Al5O12.jeff'),
                    # Fluorine (F-19) compounds
                    ('n_9-F-019g.jeff', 'tsl_F_BeF2.jeff'),
                    ('n_9-F-019g.jeff', 'tsl_F_CF2.jeff'),
                    ('n_9-F-019g.jeff', 'tsl_F_FLiBe.jeff'),
                    ('n_9-F-019g.jeff', 'tsl_F_LiF.jeff'),
                    ('n_9-F-019g.jeff', 'tsl_F_MgF2.jeff'),
                    # Sodium (Na-23) compounds
                    ('n_11-Na-023g.jeff', 'tsl_Na_Na.jeff'),
                    ('n_11-Na-023g.jeff', 'tsl_Na_NaI.jeff'),
                    ('n_11-Na-023g.jeff', 'tsl_Na_NaMgH3.jeff'),
                    ('n_11-Na-023g.jeff', 'tsl_Na_NaOH.jeff'),
                    # Magnesium (Mg-24) compounds
                    ('n_12-Mg-024g.jeff', 'tsl_Mg_Mg.jeff'),
                    ('n_12-Mg-024g.jeff', 'tsl_Mg_MgD2.jeff'),
                    ('n_12-Mg-024g.jeff', 'tsl_Mg_MgF2.jeff'),
                    ('n_12-Mg-024g.jeff', 'tsl_Mg_MgH2.jeff'),
                    ('n_12-Mg-024g.jeff', 'tsl_Mg_MgO.jeff'),
                    ('n_12-Mg-024g.jeff', 'tsl_Mg_MgOH2.jeff'),
                    ('n_12-Mg-024g.jeff', 'tsl_Mg_NaMgH3.jeff'),
                    # Aluminum (Al-27) compounds
                    ('n_13-Al-027g.jeff', 'tsl_Al_Al.jeff'),
                    ('n_13-Al-027g.jeff', 'tsl_Al_Al2O3.jeff'),
                    ('n_13-Al-027g.jeff', 'tsl_Al_Y3Al5O12.jeff'),
                    # Silicon (Si-28) compounds
                    ('n_14-Si-028g.jeff', 'tsl_Si_Si.jeff'),
                    # Sulfur (S-32) compounds
                    ('n_16-S-032g.jeff', 'tsl_S_ZnS.jeff'),
                    # Potassium (K-39) compounds
                    ('n_19-K-039g.jeff', 'tsl_K_K.jeff'),
                    ('n_19-K-039g.jeff', 'tsl_K_KOH.jeff'),
                    # Calcium (Ca-40) compounds
                    ('n_20-Ca-040g.jeff', 'tsl_Ca_Ca.jeff'),
                    ('n_20-Ca-040g.jeff', 'tsl_Ca_CaH2.jeff'),
                    ('n_20-Ca-040g.jeff', 'tsl_Ca_CaO2H2.jeff'),
                    # Titanium (Ti-48) compounds
                    ('n_22-Ti-048g.jeff', 'tsl_Ti_Ti.jeff'),
                    # Vanadium (V-51) compounds
                    ('n_23-V-051g.jeff', 'tsl_V_V.jeff'),
                    # Chromium (Cr-52) compounds
                    ('n_24-Cr-052g.jeff', 'tsl_Cr_Cr.jeff'),
                    # Iron (Fe-56) compounds
                    ('n_26-Fe-056g.jeff', 'tsl_Fe_Fe-alpha.jeff'),
                    ('n_26-Fe-056g.jeff', 'tsl_Fe_Fe-gamma.jeff'),
                    # Nickel (Ni-58) compounds
                    ('n_28-Ni-058g.jeff', 'tsl_Ni_Ni.jeff'),
                    # Copper (Cu-63) compounds
                    ('n_29-Cu-063g.jeff', 'tsl_Cu_Cu.jeff'),
                    # Zinc (Zn-64) compounds
                    ('n_30-Zn-064g.jeff', 'tsl_Zn_Zn.jeff'),
                    ('n_30-Zn-064g.jeff', 'tsl_Zn_ZnS.jeff'),
                    # Gallium (Ga-69) compounds
                    ('n_31-Ga-069g.jeff', 'tsl_Ga_GaN.jeff'),
                    ('n_31-Ga-069g.jeff', 'tsl_Ga_GaSe.jeff'),
                    # Germanium (Ge-74) compounds
                    ('n_32-Ge-074g.jeff', 'tsl_Ge_Ge.jeff'),
                    ('n_32-Ge-074g.jeff', 'tsl_Ge_Ge3Bi4O12.jeff'),
                    ('n_32-Ge-074g.jeff', 'tsl_Ge_GeTe.jeff'),
                    # Selenium (Se-80) compounds
                    ('n_34-Se-080g.jeff', 'tsl_Se_GaSe.jeff'),
                    # Strontium (Sr-88) compounds
                    ('n_38-Sr-088g.jeff', 'tsl_Sr_SrH2.jeff'),
                    # Yttrium (Y-89) compounds
                    ('n_39-Y-089g.jeff', 'tsl_Y_Y3Al5O12.jeff'),
                    ('n_39-Y-089g.jeff', 'tsl_Y_YH2.jeff'),
                    # Zirconium (Zr-90) compounds
                    ('n_40-Zr-090g.jeff', 'tsl_Zr_Zr.jeff'),
                    ('n_40-Zr-090g.jeff', 'tsl_Zr_ZrC.jeff'),
                    ('n_40-Zr-090g.jeff', 'tsl_Zr_ZrH15.jeff'),
                    ('n_40-Zr-090g.jeff', 'tsl_Zr_ZrH2.jeff'),
                    # Niobium (Nb-93) compounds
                    ('n_41-Nb-093g.jeff', 'tsl_Nb_Nb.jeff'),
                    # Molybdenum (Mo-98) compounds
                    ('n_42-Mo-098g.jeff', 'tsl_Mo_Mo.jeff'),
                    # Palladium (Pd-106) compounds
                    ('n_46-Pd-106g.jeff', 'tsl_Pd_Pd.jeff'),
                    # Silver (Ag-107) compounds
                    ('n_47-Ag-107g.jeff', 'tsl_Ag_Ag.jeff'),
                    # Tin (Sn-120) compounds
                    ('n_50-Sn-120g.jeff', 'tsl_Sn_Sn.jeff'),
                    # Tellurium (Te-130) compounds
                    ('n_52-Te-130g.jeff', 'tsl_Te_GeTe.jeff'),
                    # Iodine (I-127) compounds
                    ('n_53-I-127g.jeff', 'tsl_I_NaI.jeff'),
                    # Tungsten (W-184) compounds
                    ('n_74-W-184g.jeff', 'tsl_W_W.jeff'),
                    # Platinum (Pt-195) compounds
                    ('n_78-Pt-195g.jeff', 'tsl_Pt_Pt.jeff'),
                    # Gold (Au-197) compounds
                    ('n_79-Au-197g.jeff', 'tsl_Au_Au.jeff'),
                    # Lead (Pb-208) compounds
                    ('n_82-Pb-208g.jeff', 'tsl_Pb_Pb.jeff'),
                    # Bismuth (Bi-209) compounds
                    ('n_83-Bi-209g.jeff', 'tsl_Bi_Bi.jeff'),
                    ('n_83-Bi-209g.jeff', 'tsl_Bi_Ge3Bi4O12.jeff'),
                    # Uranium (U-238) compounds
                    ('n_92-U-238g.jeff', 'tsl_U_U.jeff'),
                    ('n_92-U-238g.jeff', 'tsl_U_UC.jeff'),
                    ('n_92-U-238g.jeff', 'tsl_U_UN.jeff'),
                ],
            },
            'photon': {
                'base_url': 'https://www.nndc.bnl.gov/endf-releases/releases/B-VIII.1/',
                'compressed_files': [
                    'photoat/photoat-version.VIII.1.tar.gz',
                    'atomic_relax/atomic_relax-version.VIII.1.tar.gz',
                ],
                'checksums': [
                    '6d5f4830f6290d6c618803a8391ba0cf',
                    '70e9ca0c481236499b7a3e0a490f4ef2',
                ],
                'file_type': 'endf',
                'photo_files': endf_files_dir.joinpath('photon').rglob('photoat*.endf'),
                'atom_files': endf_files_dir.joinpath('photon').rglob('atom*.endf'),
            },
        }
    }

    # ==============================================================================
    # DOWNLOAD FILES

    if args.download:
        for particle in args.particles:
            details = release_details[args.release][particle]
            for i, f in enumerate(details['compressed_files']):
                url = details['base_url'] + f
                if 'checksums' in details.keys():
                    checksum = details['checksums'][i]
                    download(url, output_path=download_path / particle, checksum=checksum)
                else:
                    download(url, output_path=download_path / particle)

    # ==============================================================================
    # EXTRACT FILES FROM ARCHIVES

    if args.extract:
        for particle in args.particles:
            if release_details[args.release][particle]['file_type'] == 'wmp':
                extraction_dir = args.destination / particle
            elif release_details[args.release][particle]['file_type'] == 'endf':
                extraction_dir = endf_files_dir / particle

            for f in release_details[args.release][particle]['compressed_files']:
                fname = Path(f).name
                extract(download_path / particle / fname.rstrip('?download=1'), extraction_dir)

        if args.cleanup and download_path.exists():
            rmtree(download_path)

    # =========================================================================
    # PROCESS INCIDENT NEUTRON DATA

    # Create output directory if it doesn't exist
    for particle in args.particles:
        particle_destination = args.destination / particle
        particle_destination.mkdir(parents=True, exist_ok=True)

    library = openmc.data.DataLibrary()

    if 'neutron' in args.particles:
        particle = 'neutron'
        with Pool() as pool:
            details = release_details[args.release][particle]
            results = []
            for filename in details['endf_files']:
                func_args = (filename, args.destination / particle, args.libver,
                             args.temperatures)
                r = pool.apply_async(process_neutron, func_args)
                results.append(r)

            for r in results:
                r.wait()

        for p in sorted((args.destination / particle).glob('*.h5'), key=sort_key):
            library.register_file(p)

    # =========================================================================
    # PROCESS THERMAL SCATTERING DATA

    if 'thermal' in args.particles:
        particle = 'thermal'
        with Pool() as pool:
            details = release_details[args.release][particle]
            results = []
            for path_neutron, path_thermal in details['sab_files']:
                func_args = (neutron_dir / path_neutron, thermal_dir / path_thermal,
                             args.destination / particle, args.libver)
                r = pool.apply_async(process_thermal, func_args)
                results.append(r)
            # special treatment for directory organized tsl (PuO2, ThO2, UO2, Zy4)
            for func_args in directory_tsl_args(
                    neutron_dir,
                    thermal_dir,
                    args.destination / particle,
                    args.libver):
                r = pool.apply_async(process_thermal, func_args)
                results.append(r)

            for r in results:
                r.wait()

        for p in sorted((args.destination / particle).glob('*.h5'), key=sort_key):
            library.register_file(p)

    # =========================================================================
    # INCIDENT PHOTON DATA

    if 'photon' in args.particles:
        particle = 'photon'
        details = release_details[args.release][particle]
        for photo_path, atom_path in zip(sorted(details['photo_files']),
                                        sorted(details['atom_files'])):
            # Generate instance of IncidentPhoton
            print('Converting:', photo_path.name, atom_path.name)
            data = openmc.data.IncidentPhoton.from_endf(photo_path, atom_path)

            # Export HDF5 file
            h5_file = args.destination / particle / f'{data.name}.h5'
            data.export_to_hdf5(h5_file, 'w', libver=args.libver)

            # Register with library
            library.register_file(h5_file)

    # Write cross_sections.xml
    library.export_to_xml(args.destination / 'cross_sections.xml')


if __name__ == '__main__':
    main()
