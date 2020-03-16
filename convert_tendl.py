#!/usr/bin/env python3

"""
Download TENDL 2019/2017/2015 ACE files from PSI and
convert them to HDF5 libraries for use with OpenMC.
"""

import argparse
import sys
import tarfile
from pathlib import Path
from shutil import rmtree
from urllib.parse import urljoin

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
parser.add_argument('-d', '--destination', type=Path, default=None,
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download files from PSI')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download files from PSI')
parser.add_argument('--extract', action='store_true',
                    help='Extract tar/zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract tar/zip files')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='latest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['2015', '2017', '2019'],
                    default='2019', help="The nuclear data library release "
                    "version. The currently supported options are 2015, "
                    "2017, and 2019.")
parser.add_argument('--cleanup', action='store_true',
                    help="Remove download directories when data has "
                    "been processed")
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                    help="Do not remove download directories when data has "
                    "been processed")
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()

library_name = 'tendl'

cwd = Path.cwd()

ace_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'ace']))
download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))
# the destination is decided after the release is known
# to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release.
# This can be exstened to accommodated new releases
release_details = {
    '2015': {
        'base_url': 'https://tendl.web.psi.ch/tendl_2015/tar_files/',
        'compressed_files': ['ACE-n.tgz'],
        'neutron_files': ace_files_dir.glob('neutron_file/*/*/lib/endf/*-n.ace'),
        'metastables': ace_files_dir.glob('neutron_file/*/*/lib/endf/*m-n.ace'),
        'compressed_file_size': '5.1 GB',
        'uncompressed_file_size': '40 GB'
    },
    '2017': {
        'base_url': 'https://tendl.web.psi.ch/tendl_2017/tar_files/',
        'compressed_files': ['tendl17c.tar.bz2'],
        'neutron_files': ace_files_dir.glob('ace-17/*'),
        'metastables': ace_files_dir.glob('ace-17/*m'),
        'compressed_file_size': '2.1 GB',
        'uncompressed_file_size': '14 GB'
    },
    '2019': {
        'base_url': 'https://tendl.web.psi.ch/tendl_2019/tar_files/',
        'compressed_files': ['tendl19c.tar.bz2'],
        'neutron_files': ace_files_dir.glob('tendl19c/*'),
        'metastables': ace_files_dir.glob('tendl19c/*m'),
        'compressed_file_size': '2.3 GB',
        'uncompressed_file_size': '10.1 GB'
    }
}

download_warning = """
WARNING: This script will download {} of data.
Extracting and processing the data requires {} of additional free disk space.
""".format(release_details[args.release]['compressed_file_size'],
           release_details[args.release]['uncompressed_file_size'])

# ==============================================================================
# DOWNLOAD FILES FROM WEBSITE

if args.download:
    print(download_warning)
    for f in release_details[args.release]['compressed_files']:
        # Establish connection to URL
        download(urljoin(release_details[args.release]['base_url'], f),
                 output_path=download_path)

# ==============================================================================
# EXTRACT FILES FROM TGZ

if args.extract:
    for f in release_details[args.release]['compressed_files']:
        with tarfile.open(download_path / f, 'r') as tgz:
            print(f'Extracting {f}...')
            tgz.extractall(path=ace_files_dir)

    if args.cleanup and download_path.exists():
        rmtree(download_path)

# ==============================================================================
# CHANGE ZAID FOR METASTABLES

metastables = release_details[args.release]['metastables']
for path in metastables:
    print('    Fixing {} (ensure metastable)...'.format(path))
    text = open(path, 'r').read()
    mass_first_digit = int(text[3])
    if mass_first_digit <= 2:
        text = text[:3] + str(mass_first_digit + 4) + text[4:]
        open(path, 'w').write(text)

# ==============================================================================
# GENERATE HDF5 LIBRARY -- NEUTRON FILES

# Get a list of all ACE files
neutron_files = release_details[args.release]['neutron_files']

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

for filename in sorted(neutron_files):

    # this is a fix for the TENDL-2017 release where the B10 ACE file which has an error on one of the values
    if library_name == 'tendl' and args.release == '2017' and filename.name == 'B010':
        text = open(filename, 'r').read()
        if text[423:428] == '86843':
            print('Manual fix for incorrect value in ACE file')
            # see OpenMC user group issue for more details
            text = ''.join(text[:423])+'86896'+''.join(text[428:])
            open(filename, 'w').write(text)

    print(f'Converting: {filename}')
    data = openmc.data.IncidentNeutron.from_ace(filename)

    # Export HDF5 file
    h5_file = args.destination / f'{data.name}.h5'
    print('Writing {}...'.format(h5_file))
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)

    # Register with library
    library.register_file(h5_file)

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')
