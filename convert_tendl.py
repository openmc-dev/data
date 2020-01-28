#!/usr/bin/env python3

import argparse
from pathlib import Path
import sys
import tarfile

import openmc.data
from openmc._utils import download

description = """
Download TENDL 2017 or TENDL 2015 ACE data from PSI and convert it to a HDF5 library for
use with OpenMC.

"""


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-b', '--batch', action='store_true',
                    help='supresses standard in')
parser.add_argument('-d', '--destination', type=Path, default=None,
                    help='Directory to create new library in')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='latest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['2015', '2017'],
                    default='2017', help="The nuclear data library release version. "
                    "The currently supported options are 2015 and 2017")
args = parser.parse_args()



library_name = 'tendl' #this could be added as an argument to allow different libraries to be downloaded
ace_files_dir = Path('-'.join([library_name, args.release, 'ace']))
# the destination is decided after the release is know to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '2015': {
        'base_url': 'https://tendl.web.psi.ch/tendl_2015/tar_files/',
        'files': ['ACE-n.tgz'],
        'neutron_files': ace_files_dir.glob('neutron_file/*/*/lib/endf/*-n.ace'),
        'metastables': ace_files_dir.glob('neutron_file/*/*/lib/endf/*m-n.ace'),
        'compressed_file_size': '5.1 GB',
        'uncompressed_file_size': '40 GB'
    },
    '2017': {
        'base_url': 'https://tendl.web.psi.ch/tendl_2017/tar_files/',
        'files': ['tendl17c.tar.bz2'],
        'neutron_files': ace_files_dir.glob('ace-17/*'),
        'metastables': ace_files_dir.glob('ace-17/*m'),
        'compressed_file_size': '2.1 GB',
        'uncompressed_file_size': '14 GB'
    }
}

download_warning = """
WARNING: This script will download {} of data.
Extracting and processing the data requires {} of additional free disk space.

Are you sure you want to continue? ([y]/n)
""".format(release_details[args.release]['compressed_file_size'],
           release_details[args.release]['uncompressed_file_size'])

response = input(download_warning) if not args.batch else 'y'
if response.lower().startswith('n'):
    sys.exit()

# ==============================================================================
# DOWNLOAD FILES FROM WEBSITE

files_complete = []
for f in release_details[args.release]['files']:
    # Establish connection to URL
    url = release_details[args.release]['base_url'] + f
    downloaded_file = download(url)
    files_complete.append(downloaded_file)

# ==============================================================================
# EXTRACT FILES FROM TGZ

for f in release_details[args.release]['files']:
    if f not in files_complete:
        continue

    # Extract files
    with tarfile.open(f, 'r') as tgz:
        print('Extracting {0}...'.format(f))
        tgz.extractall(path=ace_files_dir)

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
            print('Manual fix for incorrect value in ACE file') # see OpenMC user group issue for more details
            text = ''.join(text[:423])+'86896'+''.join(text[428:])
            open(filename, 'w').write(text)

    print('Converting: ' + str(filename))
    data = openmc.data.IncidentNeutron.from_ace(filename)

    # Export HDF5 file
    h5_file = args.destination / f'{data.name}.h5'
    print('Writing {}...'.format(h5_file))
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)

    # Register with library
    library.register_file(h5_file)

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')
