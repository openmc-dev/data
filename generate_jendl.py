#!/usr/bin/env python3

"""
Download JENDL 4.0 or JENDL-5 ENDF data from JAEA and convert it to a HDF5 library for
use with OpenMC.
"""

import argparse
import ssl
from multiprocessing import Pool
from pathlib import Path
from shutil import rmtree
from urllib.parse import urljoin

import openmc.data
from utils import download, process_neutron, process_thermal, extract, update_zsymam


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=CustomFormatter
    )
    parser.add_argument('-d', '--destination', type=Path, default=None,
                        help='Directory to create new library in')
    parser.add_argument('--download', action='store_true',
                        help='Download files from JAEA')
    parser.add_argument('--no-download', dest='download', action='store_false',
                        help='Do not download files from JAEA')
    parser.add_argument('--extract', action='store_true',
                        help='Extract tar/zip files')
    parser.add_argument('--no-extract', dest='extract', action='store_false',
                        help='Do not extract tar/zip files')
    parser.add_argument('--libver', choices=['earliest', 'latest'],
                        default='latest', help="Output HDF5 versioning. Use "
                        "'earliest' for backwards compatibility or 'latest' for "
                        "performance")
    parser.add_argument('-r', '--release', choices=['5'], default='5',
                        help="The nuclear data library release version. "
                        "The currently supported options are 5")
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


    library_name = 'jendl'

    cwd = Path.cwd()

    endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))
    download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))
    # the destination is decided after the release is known
    # to avoid putting the release in a folder with a misleading name
    if args.destination is None:
        args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

    # This dictionary contains all the unique information about each release.
    # This can be exstened to accommodated new releases
    release_details = {
        '5':{
            'neutron': {
                'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/ftp/JENDL/',
                'compressed_files': [
                    'jendl5-n.tar.gz',
                    'jendl5-n_upd1.tar.gz',
                    'jendl5-n_upd6.tar.gz',
                    'jendl5-n_upd7.tar.gz',
                    'jendl5-n_upd10.tar.gz',
                    'jendl5-n_upd11.tar.gz',
                    'jendl5-n_upd12.tar.gz',
                    'jendl5-n_upd14.tar.gz',
                ],
                'endf_dir': 'jendl5-n',
                'patterns': ['n_???-*-???.dat', 'n_???-*-???m?.dat'],
                'pattern_errata': ['jendl5-n_upd1/*.dat', 'jendl-n_upd6/*.dat', '*.dat'],
            },
            'thermal': {
                'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/ftp/JENDL/',
                'compressed_files': [
                    'jendl5-tsl.tar.gz',
                    'jendl5-tsl_upd16.tar.gz',
                ],
                'endf_dir': 'jendl5-tsl',
                'pattern': '*.dat',
                'sab_files': [
                    # Hydrogen (H-1) compounds
                    ('n_001-H-001.dat', 'tsl_HinC5O2H8.dat'),
                    ('n_001-H-001.dat', 'tsl_HinCH2.dat'),
                    ('n_001-H-001.dat', 'tsl_HinH2O.dat'),
                    ('n_001-H-001.dat', 'tsl_HinIceIh.dat'),
                    ('n_001-H-001.dat', 'tsl_HinLiquidBenzene.dat'),
                    ('n_001-H-001.dat', 'tsl_HinLiquidEthanol.dat'),
                    ('n_001-H-001.dat', 'tsl_HinLiquidMesitylene.dat'),
                    ('n_001-H-001.dat', 'tsl_HinLiquidMethane.dat'),
                    ('n_001-H-001.dat', 'tsl_HinLiquidM-Xylene.dat'),
                    ('n_001-H-001.dat', 'tsl_HinLiquidToluene.dat'),
                    ('n_001-H-001.dat', 'tsl_HinLiquidTriphenylmethane.dat'),
                    ('n_001-H-001.dat', 'tsl_HinOrthoH.dat'),
                    ('n_001-H-001.dat', 'tsl_HinParaH.dat'),
                    ('n_001-H-001.dat', 'tsl_HinSolidBenzene.dat'),
                    ('n_001-H-001.dat', 'tsl_HinSolidEthanol.dat'),
                    ('n_001-H-001.dat', 'tsl_HinSolidMesitylene.dat'),
                    ('n_001-H-001.dat', 'tsl_HinSolidMethane.dat'),
                    ('n_001-H-001.dat', 'tsl_HinSolidM-Xylene.dat'),
                    ('n_001-H-001.dat', 'tsl_HinSolidToluene.dat'),
                    ('n_001-H-001.dat', 'tsl_HinSolidTriphenylmethane.dat'),
                    ('n_001-H-001.dat', 'tsl_HinYH2.dat'),
                    ('n_001-H-001.dat', 'tsl_HinZrH.dat'),
                    # Deuterium (H-2) compounds
                    ('n_001-H-002.dat', 'tsl_DinD2O.dat'),
                    ('n_001-H-002.dat', 'tsl_DinOrthoD.dat'),
                    ('n_001-H-002.dat', 'tsl_DinParaD.dat'),
                    # Beryllium (Be-9) compounds
                    ('n_004-Be-009.dat', 'tsl_Be-metal.dat'),
                    ('n_004-Be-009.dat', 'tsl_BeinBeO.dat'),
                    # Carbon (C-12) compounds
                    ('n_006-C-012.dat', 'tsl_CinLiquidBenzene.dat'),
                    ('n_006-C-012.dat', 'tsl_CinLiquidEthanol.dat'),
                    ('n_006-C-012.dat', 'tsl_CinLiquidMesitylene.dat'),
                    ('n_006-C-012.dat', 'tsl_CinLiquidMethane.dat'),
                    ('n_006-C-012.dat', 'tsl_CinLiquidM-Xylene.dat'),
                    ('n_006-C-012.dat', 'tsl_CinLiquidToluene.dat'),
                    ('n_006-C-012.dat', 'tsl_CinLiquidTriphenylmethane.dat'),
                    ('n_006-C-012.dat', 'tsl_CinSiC.dat'),
                    ('n_006-C-012.dat', 'tsl_CinSolidBenzene.dat'),
                    ('n_006-C-012.dat', 'tsl_CinSolidEthanol.dat'),
                    ('n_006-C-012.dat', 'tsl_CinSolidMesitylene.dat'),
                    ('n_006-C-012.dat', 'tsl_CinSolidMethane.dat'),
                    ('n_006-C-012.dat', 'tsl_CinSolidM-Xylene.dat'),
                    ('n_006-C-012.dat', 'tsl_CinSolidToluene.dat'),
                    ('n_006-C-012.dat', 'tsl_CinSolidTriphenylmethane.dat'),
                    ('n_006-C-012.dat', 'tsl_crystalline-graphite.dat'),
                    ('n_006-C-012.dat', 'tsl_reactor-graphite-10P.dat'),
                    ('n_006-C-012.dat', 'tsl_reactor-graphite-30P.dat'),
                    # Nitrogen (N-14) compounds
                    ('n_007-N-014.dat', 'tsl_NinUN.dat'),
                    # Oxygen (O-16) compounds
                    ('n_008-O-016.dat', 'tsl_OinBeO.dat'),
                    ('n_008-O-016.dat', 'tsl_OinD2O.dat'),
                    ('n_008-O-016.dat', 'tsl_OinH2O.dat'),
                    ('n_008-O-016.dat', 'tsl_OinIceIh.dat'),
                    ('n_008-O-016.dat', 'tsl_OinLiquidEthanol.dat'),
                    ('n_008-O-016.dat', 'tsl_OinSolidEthanol.dat'),
                    ('n_008-O-016.dat', 'tsl_OinUO2.dat'),
                    # Aluminum (Al-27)
                    ('n_013-Al-027.dat', 'tsl_013_Al_027.dat'),
                    # Silicon (Si-28) compounds
                    ('n_014-Si-028.dat', 'tsl_SiinSiC.dat'),
                    ('n_014-Si-028.dat', 'tsl_SiO2-alpha.dat'),
                    ('n_014-Si-028.dat', 'tsl_SiO2-beta.dat'),
                    # Iron (Fe-56)
                    ('n_026-Fe-056.dat', 'tsl_026_Fe_056.dat'),
                    # Yttrium (Y-89) compounds
                    ('n_039-Y-089.dat', 'tsl_YinYH2.dat'),
                    # Zirconium (Zr-90) compounds
                    ('n_040-Zr-090.dat', 'tsl_ZrinZrH.dat'),
                    # Uranium (U-238) compounds
                    ('n_092-U-238.dat', 'tsl_UinUN.dat'),
                    ('n_092-U-238.dat', 'tsl_UinUO2.dat'),
                ],
                'pattern_errata': ['*.dat'],
            },
            'photon': {
                'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/ftp/JENDL/',
                'compressed_files': [
                    'jendl5-pa.tar.gz',
                    'jendl5-ar.tar.gz',
                ],
                'pattern_photoatomic': 'jendl5-pa/*.dat',
                'pattern_atomic_relax': 'jendl5-ar/*.dat',
            }
        }
    }

    # ==============================================================================
    # DOWNLOAD FILES FROM WEBSITE

    if args.download:
        for particle in args.particles:
            details = release_details[args.release][particle]
            for f in details['compressed_files']:
                download(
                    urljoin(details['base_url'], f),
                    context=ssl._create_unverified_context(),
                    output_path=download_path / particle
            )

    # ==============================================================================
    # EXTRACT FILES FROM TGZ
    if args.extract:
        for particle in args.particles:
            details = release_details[args.release][particle]
            extraction_dir = endf_files_dir / particle
            for f in details['compressed_files']:
                extract(download_path / particle / f, extraction_dir)

        if args.cleanup and download_path.exists():
            rmtree(download_path)

    # ==============================================================================
    # HANDLE ERRATA FILES

    for particle in args.particles:
        details = release_details[args.release][particle]
        if "pattern_errata" in details:
            destination_dir = endf_files_dir / particle / details["endf_dir"]
            for pattern in details["pattern_errata"]:
                files = (endf_files_dir / particle).rglob(pattern)
                for p in files:
                    p.rename(destination_dir / p.name)

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
            neutron_dir = endf_files_dir / particle / details["endf_dir"]
            for pattern in details['patterns']:
                for filename in neutron_dir.glob(pattern):
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
        neutron_details = release_details[args.release]['neutron']
        thermal_details = release_details[args.release]['thermal']
        neutron_dir = endf_files_dir / 'neutron' / neutron_details["endf_dir"]
        thermal_dir = endf_files_dir / 'thermal' / thermal_details["endf_dir"]

        # Patch liquid/solid evaluations to have unique ZSYMAM fields
        update_thermal_list = [
            ("tsl_CinLiquidBenzene.dat", "c(c6h6)l"),
            ("tsl_CinLiquidEthanol.dat", "c(c2h6o)l"),
            ("tsl_CinLiquidM-Xylene.dat", "c(m-c8h10)l"),
            ("tsl_CinLiquidMesitylene.dat", "c(c9h12)l"),
            ("tsl_CinLiquidMethane.dat", "c(ch4)l"),
            ("tsl_CinLiquidToluene.dat", "c(c7h8)l"),
            ("tsl_CinLiquidTriphenylmethane.dat", "c(c19h16)l"),
            ("tsl_CinSolidBenzene.dat", "c(c6h6)s"),
            ("tsl_CinSolidEthanol.dat", "c(c2h6o)s"),
            ("tsl_CinSolidM-Xylene.dat", "c(m-c8h10)s"),
            ("tsl_CinSolidMesitylene.dat", "c(c9h12)s"),
            ("tsl_CinSolidMethane.dat", "c(ch4)s"),
            ("tsl_CinSolidToluene.dat", "c(c7h8)s"),
            ("tsl_CinSolidTriphenylmethane.dat", "c(c19h16)s"),
            ("tsl_HinLiquidBenzene.dat", "h(c6h6)l"),
            ("tsl_HinLiquidEthanol.dat", "h(c2h6o)l"),
            ("tsl_HinLiquidM-Xylene.dat", "h(m-c8h10)l"),
            ("tsl_HinLiquidMesitylene.dat", "h(c9h12)l"),
            ("tsl_HinLiquidMethane.dat", "h(ch4)l"),
            ("tsl_HinLiquidToluene.dat", "h(c7h8)l"),
            ("tsl_HinLiquidTriphenylmethane.dat", "h(c19h16)l"),
            ("tsl_HinSolidBenzene.dat", "h(c6h6)s"),
            ("tsl_HinSolidEthanol.dat", "h(c2h6o)s"),
            ("tsl_HinSolidM-Xylene.dat", "h(m-c8h10)s"),
            ("tsl_HinSolidMesitylene.dat", "h(c9h12)s"),
            ("tsl_HinSolidMethane.dat", "h(ch4)s"),
            ("tsl_HinSolidToluene.dat", "h(c7h8)s"),
            ("tsl_HinSolidTriphenylmethane.dat", "h(c19h16)s"),
            ("tsl_OinLiquidEthanol.dat", "o(c2h6o)l"),
            ("tsl_OinSolidEthanol.dat", "o(c2h6o)s"),
        ]
        for filename, zsymam in update_thermal_list:
            update_zsymam(thermal_dir / filename, zsymam)


        with Pool() as pool:
            results = []
            for path_neutron, path_thermal in thermal_details['sab_files']:
                func_args = (neutron_dir / path_neutron, thermal_dir / path_thermal,
                             args.destination / 'thermal', args.libver)
                r = pool.apply_async(process_thermal, func_args)
                results.append(r)

            for r in results:
                r.wait()

        for p in sorted((args.destination / 'thermal').glob('*.h5'), key=sort_key):
            library.register_file(p)

    # =========================================================================
    # INCIDENT PHOTON DATA

    if 'photon' in args.particles:
        particle = 'photon'
        details = release_details[args.release][particle]
        photo_files = (endf_files_dir / particle).rglob(details['pattern_photoatomic'])
        atom_files = (endf_files_dir / particle).rglob(details['pattern_atomic_relax'])
        for photo_path, atom_path in zip(sorted(photo_files), sorted(atom_files)):
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
