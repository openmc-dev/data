#!/usr/bin/env python3

"""
Download ENDF/B-VIII.0 or ENDF/B-VII.1 library for use in OpenMC by first
processing ENDF files using NJOY. The resulting library will contain incident
neutron, incident photon, and thermal scattering data.
"""


import argparse
import sys
import tarfile
import zipfile
from multiprocessing import Pool
from pathlib import Path
from shutil import rmtree, copy, copyfileobj

import openmc.data
from openmc_data import download, process_neutron, process_thermal, state_download_size

# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=CustomFormatter
)

parser.add_argument('-d', '--destination', type=Path,
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download zip files from NNDC')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download zip files from NNDC')
parser.add_argument('--extract', action='store_true',
                    help='Extract zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract zip files')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['vii.1', 'viii.0'],
                    default='viii.0', help="The nuclear data library release "
                    "version. The currently supported options are vii.1, "
                    "viii.0")
parser.add_argument('-p', '--particles', choices=['neutron', 'photon', 'wmp'],
                    nargs='+', default=['neutron', 'photon'],
                    help="Incident particles to include, wmp is not available "
                    "for release b8.0 at the moment")
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


def main():

    library_name = 'endfb'

    cwd = Path.cwd()

    endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))
    neutron_dir = endf_files_dir / 'neutron'
    thermal_dir = endf_files_dir / 'thermal_scatt'
    download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))
    # the destination is decided after the release is known
    # to avoid putting the release in a folder with a misleading name
    if args.destination is None:
        args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

    # This dictionary contains all the unique information about each release. This
    # can be extended to accommodate new releases
    release_details = {
        'vii.1': {
            'neutron': {
                'base_url': 'http://www.nndc.bnl.gov/endf-b7.1/zips/',
                'compressed_files': ['ENDF-B-VII.1-neutrons.zip',
                                    'ENDF-B-VII.1-thermal_scatt.zip'],
                'checksums': ['e5d7f441fc4c92893322c24d1725e29c',
                            'fe590109dde63b2ec5dc228c7b8cab02'],
                'file_type': 'endf',
                'endf_files': neutron_dir.rglob('n-*.endf'),
                'sab_files': [
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-HinH2O.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-HinCH2.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-HinZrH.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-ortho-H.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-para-H.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-benzine.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-l-CH4.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-s-CH4.endf'),
                    (neutron_dir / 'n-001_H_002.endf', neutron_dir / 'tsl-DinD2O.endf'),
                    (neutron_dir / 'n-001_H_002.endf', neutron_dir / 'tsl-ortho-D.endf'),
                    (neutron_dir / 'n-001_H_002.endf', neutron_dir / 'tsl-para-D.endf'),
                    (neutron_dir / 'n-004_Be_009.endf', neutron_dir / 'tsl-BeinBeO.endf'),
                    (neutron_dir / 'n-004_Be_009.endf', neutron_dir / 'tsl-Be-metal.endf'),
                    (neutron_dir / 'n-006_C_000.endf', neutron_dir / 'tsl-graphite.endf'),
                    (neutron_dir / 'n-008_O_016.endf', neutron_dir / 'tsl-OinBeO.endf'),
                    (neutron_dir / 'n-008_O_016.endf', neutron_dir / 'tsl-OinUO2.endf'),
                    (neutron_dir / 'n-013_Al_027.endf', neutron_dir / 'tsl-013_Al_027.endf'),
                    (neutron_dir / 'n-026_Fe_056.endf', neutron_dir / 'tsl-026_Fe_056.endf'),
                    (neutron_dir / 'n-014_Si_028.endf', neutron_dir / 'tsl-SiO2.endf'),
                    (neutron_dir / 'n-040_Zr_090.endf', neutron_dir / 'tsl-ZrinZrH.endf'),
                    (neutron_dir / 'n-092_U_238.endf', neutron_dir / 'tsl-UinUO2.endf')
                ],
                'compressed_file_size': 226,
                'uncompressed_file_size': 916
            },
            'photon': {
                'base_url': 'http://www.nndc.bnl.gov/endf-b7.1/zips/',
                'compressed_files': ['ENDF-B-VII.1-photoat.zip',
                                    'ENDF-B-VII.1-atomic_relax.zip'],
                'checksums': ['5192f94e61f0b385cf536f448ffab4a4',
                            'fddb6035e7f2b6931e51a58fc754bd10'],
                'file_type': 'endf',
                'photo_files': endf_files_dir.joinpath('photoat').rglob('*.endf'),
                'atom_files': endf_files_dir.joinpath('atomic_relax').rglob('*.endf'),
                'compressed_file_size': 9,
                'uncompressed_file_size': 45
            },
            'wmp': {
                'base_url': 'https://github.com/mit-crpg/WMP_Library/releases/download/v1.1/',
                'compressed_files': ['WMP_Library_v1.1.tar.gz'],
                'file_type': 'wmp',
                'compressed_file_size': 12,
                'uncompressed_file_size': 17
            }
        },
        'viii.0': {
            'neutron': {
                'base_url': 'https://www.nndc.bnl.gov/endf-b8.0/',
                'compressed_files': ['zips/ENDF-B-VIII.0_neutrons.zip',
                                    'zips/ENDF-B-VIII.0_thermal_scatt.zip',
                                    'erratafiles/n-005_B_010.endf'],
                'checksums': ['90c1b1a6653a148f17cbf3c5d1171859',
                            'ecd503d3f8214f703e95e17cc947062c',
                            'eaf71eb22258f759abc205a129d8715a'],
                'file_type': 'endf',
                'endf_files': neutron_dir.rglob('n-*.endf'),
                'sab_files': [
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-HinC5O2H8.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-HinH2O.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-HinCH2.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-HinZrH.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-HinIceIh.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-HinYH2.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-ortho-H.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-para-H.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-benzene.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-l-CH4.endf'),
                    (neutron_dir / 'n-001_H_001.endf', neutron_dir / 'tsl-s-CH4.endf'),
                    (neutron_dir / 'n-001_H_002.endf', neutron_dir / 'tsl-DinD2O.endf'),
                    (neutron_dir / 'n-001_H_002.endf', neutron_dir / 'tsl-ortho-D.endf'),
                    (neutron_dir / 'n-001_H_002.endf', neutron_dir / 'tsl-para-D.endf'),
                    (neutron_dir / 'n-004_Be_009.endf', neutron_dir / 'tsl-BeinBeO.endf'),
                    (neutron_dir / 'n-004_Be_009.endf', neutron_dir / 'tsl-Be-metal.endf'),
                    (neutron_dir / 'n-006_C_012.endf', neutron_dir / 'tsl-CinSiC.endf'),
                    (neutron_dir / 'n-006_C_012.endf', neutron_dir / 'tsl-crystalline-graphite.endf'),
                    (neutron_dir / 'n-006_C_012.endf', neutron_dir / 'tsl-reactor-graphite-10P.endf'),
                    (neutron_dir / 'n-006_C_012.endf', neutron_dir / 'tsl-reactor-graphite-30P.endf'),
                    (neutron_dir / 'n-007_N_014.endf', neutron_dir / 'tsl-NinUN.endf'),
                    (neutron_dir / 'n-008_O_016.endf', neutron_dir / 'tsl-OinBeO.endf'),
                    (neutron_dir / 'n-008_O_016.endf', neutron_dir / 'tsl-OinD2O.endf'),
                    (neutron_dir / 'n-008_O_016.endf', neutron_dir / 'tsl-OinIceIh.endf'),
                    (neutron_dir / 'n-008_O_016.endf', neutron_dir / 'tsl-OinUO2.endf'),
                    (neutron_dir / 'n-013_Al_027.endf', neutron_dir / 'tsl-013_Al_027.endf'),
                    (neutron_dir / 'n-026_Fe_056.endf', neutron_dir / 'tsl-026_Fe_056.endf'),
                    (neutron_dir / 'n-014_Si_028.endf', neutron_dir / 'tsl-SiinSiC.endf'),
                    (neutron_dir / 'n-014_Si_028.endf', neutron_dir / 'tsl-SiO2-alpha.endf'),
                    (neutron_dir / 'n-014_Si_028.endf', neutron_dir / 'tsl-SiO2-beta.endf'),
                    (neutron_dir / 'n-039_Y_089.endf', neutron_dir / 'tsl-YinYH2.endf'),
                    (neutron_dir / 'n-040_Zr_090.endf', neutron_dir / 'tsl-ZrinZrH.endf'),
                    (neutron_dir / 'n-092_U_238.endf', neutron_dir / 'tsl-UinUN.endf'),
                    (neutron_dir / 'n-092_U_238.endf', neutron_dir / 'tsl-UinUO2.endf')
                ],
                'compressed_file_size': 296+59+0.849,
                'uncompressed_file_size': 999999
            },
            'photon': {
                'base_url': 'https://www.nndc.bnl.gov/endf-b8.0/',
                'compressed_files': ['zips/ENDF-B-VIII.0_photoat.zip',
                                    'erratafiles/atomic_relax.tar.gz'],
                'checksums': ['d49f5b54be278862e1ce742ccd94f5c0',
                            '805f877c59ad22dcf57a0446d266ceea'],
                'file_type': 'endf',
                'photo_files': endf_files_dir.joinpath('photoat').rglob('*.endf'),
                'atom_files': endf_files_dir.joinpath('atom').rglob('*.endf'),
                'compressed_file_size': 1.2+35,
                'uncompressed_file_size': 999999
            }
        }
    }

    compressed_file_size, uncompressed_file_size = 0, 0
    for r in args.release:
        for p in args.particles:
            compressed_file_size += release_details[args.release][p]['compressed_file_size']
            uncompressed_file_size += release_details[args.release][p]['uncompressed_file_size']

    # ==============================================================================
    # DOWNLOAD FILES FROM NNDC SITE

    if args.download:
        state_download_size(compressed_file_size, uncompressed_file_size, 'MB')
        for particle in args.particles:
            details = release_details[args.release][particle]
            for i, f in enumerate(details['compressed_files']):
                url = details['base_url'] + f
                if 'checksums' in details.keys():
                    checksum = details['checksums'][i]
                    downloaded_file = download(url,
                                            output_path=download_path / particle,
                                            checksum=checksum)
                else:
                    downloaded_file = download(url,
                                            output_path=download_path / particle,
                                            )

    # ==============================================================================
    # EXTRACT FILES FROM TGZ

    if args.extract:
        for particle in args.particles:

            if release_details[args.release][particle]['file_type'] == 'wmp':
                extraction_dir = args.destination / 'wmp' / particle
            elif release_details[args.release][particle]['file_type'] == 'endf':
                extraction_dir = endf_files_dir / particle
            Path.mkdir(extraction_dir, parents=True, exist_ok=True)

            for f in release_details[args.release][particle]['compressed_files']:
                fname = Path(f).name
                # Extract files different depending on compression method
                if fname.endswith('.zip'):
                    print(f'Extracting {fname}...')
                    with zipfile.ZipFile(download_path / particle / fname) as zipf:
                        # Extracts files without folder structure in the zip file
                        for member in zipf.namelist():
                            filename = Path(member).name
                            # skip directories
                            if not filename:
                                continue
                            source = zipf.open(member)
                            target = open(extraction_dir / filename, "wb")
                            with source, target:
                                copyfileobj(source, target)
                elif fname.endswith('.tar.gz'):
                    with tarfile.open(download_path / particle / fname, 'r') as tgz:
                        print(f'Extracting {fname}...')
                        # extract files ignoring the internal folder structure
                        for member in tgz.getmembers():
                            if member.isreg():
                                member.name = Path(member.name).name
                                tgz.extract(member, path=extraction_dir)
                else:
                    # File is not compressed. Used for erratafiles. This ensures
                    # the n-005_B_010.endf erratafile overwrites the orginal
                    copy(download_path/particle/fname, extraction_dir/fname)

        if args.cleanup and download_path.exists():
            rmtree(download_path)

    # =========================================================================
    # PROCESS INCIDENT NEUTRON AND THERMAL SCATTERING DATA IN PARALLEL

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

                # Skip neutron evaluation that fails the processing stage
                if filename.name == 'n-000_n_001.endf':
                    continue

                func_args = (filename, args.destination / particle, args.libver,
                            args.temperatures)
                r = pool.apply_async(process_neutron, func_args)
                results.append(r)

            for path_neutron, path_thermal in details['sab_files']:
                func_args = (path_neutron, path_thermal,
                            args.destination / particle, args.libver)
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

    # =========================================================================
    # INCIDENT WMP NEUTRON DATA

    if 'wmp' in args.particles:
        for h5_file in Path(args.destination / 'wmp').rglob('*.h5'):
            library.register_file(h5_file)

    # Write cross_sections.xml
    library.export_to_xml(args.destination / 'cross_sections.xml')


if __name__ == '__main__':
    main()
