#!/usr/bin/env python

"""
Download ENDF/B-VII.1 incident neutron ACE data and incident photon ENDF data
from NNDC and convert it to an HDF5 library for use with OpenMC.
"""

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path
from shutil import rmtree

import openmc.data
from utils import download

# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=CustomFormatter
)

parser.add_argument('-d', '--destination', type=Path, default='nndc-b7.1-hdf5',
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download tarball from NNDC-BNL')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download tarball from NNDC-BNL')
parser.add_argument('--extract', action='store_true',
                    help='Extract compressed files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract compressed file if it has already been extracted')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-p', '--particles', choices=['neutron', 'photon'], nargs='+',
                    default=['neutron', 'photon'], help="Incident particles to include")
parser.add_argument('--cleanup', action='store_true',
                    help="Remove download directories when data has "
                    "been processed")
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                    help="Do not remove download directories when data has "
                    "been processed")
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()

library_name = 'nndc'
release = 'b7.1'

cwd = Path.cwd()

ace_files_dir = Path('-'.join([library_name, release, 'ace']))
endf_files_dir = Path('-'.join([library_name, release, 'endf']))
download_path = cwd.joinpath('-'.join([library_name, release, 'download']))

# This dictionary contains all the unique information about each release. This
# can be exstened to accommodated new releases
release_details = {
    'b7.1': {
        'neutron': {
            'base_url': 'http://www.nndc.bnl.gov/endf-b7.1/aceFiles/',
            'compressed_files': ['ENDF-B-VII.1-neutron-293.6K.tar.gz',
                                 'ENDF-B-VII.1-tsl.tar.gz'],
            'checksums': ['9729a17eb62b75f285d8a7628ace1449',
                          'e17d827c92940a30f22f096d910ea186'],
            'file_type': 'ace',
            'ace_files': ace_files_dir.rglob('[aA-zZ]*.ace'),
            'sab_files': ace_files_dir.rglob('*.acer'),
            'compressed_file_size': 497,
            'uncompressed_file_size': 1200
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
        }
    }
}

compressed_file_size, uncompressed_file_size = 0, 0
for p in ('neutron', 'photon'):
    compressed_file_size += release_details[release][p]['compressed_file_size']
    uncompressed_file_size += release_details[release][p]['uncompressed_file_size']

download_warning = """
WARNING: This script will download up to {} MB of data. Extracting and
processing the data may require as much as {} MB of additional free disk
space. This script downloads ENDF/B-VII.1 incident neutron ACE data and
incident photon ENDF data from NNDC and convert it to an HDF5 library
for use with OpenMC. This data is used for OpenMC's regression test suite.
""".format(compressed_file_size, uncompressed_file_size)


# ==============================================================================
# DOWNLOAD FILES FROM NNDC SITE

if args.download:
    print(download_warning)
    for particle in args.particles:
        particle_download_path = download_path / particle
        for f, checksum in zip(release_details[release][particle]['compressed_files'],
                               release_details[release][particle]['checksums']):
            # Establish connection to URL
            url = release_details[release][particle]['base_url'] + f
            downloaded_file = download(url, output_path=particle_download_path,
                                       checksum=checksum)


# ==============================================================================
# EXTRACT FILES FROM TGZ

if args.extract:
    for particle in args.particles:
        if release_details[release][particle]['file_type'] == 'ace':
            extraction_dir = ace_files_dir
        elif release_details[release][particle]['file_type'] == 'endf':
            extraction_dir = endf_files_dir

        for f in release_details[release][particle]['compressed_files']:

            # Extract files
            if f.endswith('.zip'):
                with zipfile.ZipFile(download_path / particle / f, 'r') as zipf:
                    print(f'Extracting {f}...')
                    zipf.extractall(extraction_dir)
            else:
                with tarfile.open(download_path / particle / f, 'r') as tgz:
                    print(f'Extracting {f}...')
                    tgz.extractall(path=extraction_dir)

    if args.cleanup and download_path.exists():
        rmtree(download_path)

# ==============================================================================
# FIX ZAID ASSIGNMENTS FOR VARIOUS S(A,B) TABLES

if 'neutron' in args.particles:
    print('Fixing ZAIDs for S(a,b) tables')
    fixes = [('bebeo.acer', '8016', '   0'),
             ('obeo.acer', '4009', '   0')]
    for table, old, new in fixes:
        filename = ace_files_dir / table
        with open(filename, 'r') as fh:
            text = fh.read()
        text = text.replace(old, new, 1)
        with open(filename, 'w') as fh:
            fh.write(text)

# ==============================================================================
# GENERATE HDF5 LIBRARY

# Create output directory if it doesn't exist
for particle in args.particles:
    particle_destination = args.destination / particle
    particle_destination.mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

for particle in args.particles:
    details = release_details[release][particle]
    if particle == 'neutron':
        for cls, files in [(openmc.data.IncidentNeutron, 'ace_files'),
                           (openmc.data.ThermalScattering, 'sab_files')]:
            for path in sorted(details[files]):
                print(f'Converting: {path.name}')
                data = cls.from_ace(path)
                # Export HDF5 file
                h5_file = args.destination.joinpath(particle, data.name + '.h5')
                data.export_to_hdf5(h5_file, 'w', libver=args.libver)

                # Register with library
                library.register_file(h5_file)

    elif particle == 'photon':
        for photo_path, atom_path in zip(sorted(details['photo_files']),
                                         sorted(details['atom_files'])):
            # Generate instance of IncidentPhoton
            print('Converting:', photo_path.name, atom_path.name)
            data = openmc.data.IncidentPhoton.from_endf(photo_path, atom_path)

            # Export HDF5 file
            h5_file = args.destination.joinpath(particle, data.name + '.h5')
            data.export_to_hdf5(h5_file, 'w', libver=args.libver)

            # Register with library
            library.register_file(h5_file)

# Write cross_sections.xml
print('Writing ', args.destination / 'cross_sections.xml')
library.export_to_xml(args.destination / 'cross_sections.xml')
