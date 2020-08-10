#!/usr/bin/env python3

"""
Download ENDF/B-VII.1 incident neutron ENDF data and incident photon ENDF data
from NNDC and convert it to an HDF5 library for use with OpenMC. This data is
used for OpenMC's regression test suite.
"""

import argparse
import sys
import tarfile
import zipfile
from multiprocessing import Pool
from pathlib import Path
from shutil import rmtree

import openmc.data
from utils import download, process_neutron, process_thermal

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
                    default=Path('endf-b7.1-hdf5'),
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
parser.add_argument('-p', '--particles', choices=['neutron', 'photon', 'wmp'],
                    nargs='+', default=['neutron', 'photon', 'wmp'],
                    help="Incident particles to include")
parser.add_argument('--cleanup', action='store_true',
                    help="Remove download directories when data has "
                    "been processed")
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                    help="Do not remove download directories when data has "
                    "been processed")
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()


def sort_key(path):
    if path.name.startswith('c_'):
        # Ensure that thermal scattering gets sorted after neutron data
        return (1000, path)
    else:
        return openmc.data.zam(path.stem)


library_name = 'endf'
release = 'b7.1'

cwd = Path.cwd()

wmp_files_dir = args.destination / 'wmp'
endf_files_dir = cwd.joinpath('-'.join([library_name, release, 'endf']))
neutron_dir = endf_files_dir / 'neutrons'
thermal_dir = endf_files_dir / 'thermal_scatt'
download_path = cwd.joinpath('-'.join([library_name, release, 'download']))

temperatures = [250.0, 293.6, 600.0, 900.0, 1200.0, 2500.0]

# This dictionary contains all the unique information about each release. This
# can be extended to accommodate new releases
release_details = {
    'b7.1': {
        'neutron': {
            'base_url': 'http://www.nndc.bnl.gov/endf/b7.1/zips/',
            'compressed_files': ['ENDF-B-VII.1-neutrons.zip',
                                 'ENDF-B-VII.1-thermal_scatt.zip'],
            'checksums': ['e5d7f441fc4c92893322c24d1725e29c',
                          'fe590109dde63b2ec5dc228c7b8cab02'],
            'file_type': 'endf',
            'endf_files': endf_files_dir.rglob('n-*.endf'),
            'sab_files': [
                (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinH2O.endf'),
                (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinCH2.endf'),
                (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinZrH.endf'),
                (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-ortho-H.endf'),
                (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-para-H.endf'),
                (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-benzine.endf'),
                (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-l-CH4.endf'),
                (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-s-CH4.endf'),
                (neutron_dir / 'n-001_H_002.endf', thermal_dir / 'tsl-DinD2O.endf'),
                (neutron_dir / 'n-001_H_002.endf', thermal_dir / 'tsl-ortho-D.endf'),
                (neutron_dir / 'n-001_H_002.endf', thermal_dir / 'tsl-para-D.endf'),
                (neutron_dir / 'n-004_Be_009.endf', thermal_dir / 'tsl-BeinBeO.endf'),
                (neutron_dir / 'n-004_Be_009.endf', thermal_dir / 'tsl-Be-metal.endf'),
                (neutron_dir / 'n-006_C_000.endf', thermal_dir / 'tsl-graphite.endf'),
                (neutron_dir / 'n-008_O_016.endf', thermal_dir / 'tsl-OinBeO.endf'),
                (neutron_dir / 'n-008_O_016.endf', thermal_dir / 'tsl-OinUO2.endf'),
                (neutron_dir / 'n-013_Al_027.endf', thermal_dir / 'tsl-013_Al_027.endf'),
                (neutron_dir / 'n-026_Fe_056.endf', thermal_dir / 'tsl-026_Fe_056.endf'),
                (neutron_dir / 'n-014_Si_028.endf', thermal_dir / 'tsl-SiO2.endf'),
                (neutron_dir / 'n-040_Zr_090.endf', thermal_dir / 'tsl-ZrinZrH.endf'),
                (neutron_dir / 'n-092_U_238.endf', thermal_dir / 'tsl-UinUO2.endf')
            ],
            'compressed_file_size': 226,
            'uncompressed_file_size': 916
        },
        'photon': {
            'base_url': 'http://www.nndc.bnl.gov/endf/b7.1/zips/',
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
    }
}

compressed_file_size, uncompressed_file_size = 0, 0
for r in release:
    for p in args.particles:
        compressed_file_size += release_details[release][p]['compressed_file_size']
        uncompressed_file_size += release_details[release][p]['uncompressed_file_size']

download_warning = """
WARNING: This script will download up to {} MB of data. Extracting and
processing the data may require as much as {} MB of additional free disk
space. This script downloads ENDF/B-VII.1 incident neutron ACE data and
incident photon ENDF data from NNDC and convert it to an HDF5 library
for use with OpenMC.
""".format(compressed_file_size, uncompressed_file_size)


# ==============================================================================
# DOWNLOAD FILES FROM NNDC SITE

if args.download:
    print(download_warning)
    for particle in args.particles:
        details = release_details[release][particle]
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

        if release_details[release][particle]['file_type'] == 'wmp':
            extraction_dir = wmp_files_dir
        elif release_details[release][particle]['file_type'] == 'endf':
            extraction_dir = endf_files_dir

        for f in release_details[release][particle]['compressed_files']:

            # Extract files different depending on compression method
            if f.endswith('.zip'):
                with zipfile.ZipFile(download_path / particle / f, 'r') as zipf:
                    print(f'Extracting {f}...')
                    zipf.extractall(extraction_dir)
            else:
                with tarfile.open(download_path / particle / f, 'r') as tgz:
                    print(f'Extracting {f}...')
                    # extract files ignoring the internal folder structure
                    for member in tgz.getmembers():
                        if member.isreg():
                            member.name = Path(member.name).name
                            tgz.extract(member, path=extraction_dir)

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
        details = release_details[release][particle]
        results = []
        for filename in details['endf_files']:
            func_args = (filename, args.destination / particle, args.libver,
                         temperatures)
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
    details = release_details[release][particle]
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
    for h5_file in Path(wmp_files_dir).rglob('*.h5'):
        library.register_file(h5_file)

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')
