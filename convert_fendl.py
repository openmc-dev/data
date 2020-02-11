#!/usr/bin/env python3

import argparse
from pathlib import Path
import ssl
import subprocess
import sys
import zipfile
from urllib.parse import urljoin

import openmc.data
from openmc._utils import download

description = """
Download FENDL 3.1d or FENDL 3.1c ACE data from the IAEA and convert it to a HDF5 library for
use with OpenMC.

"""


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=None,
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download files from IAEA-NDS')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download files from IAEA-NDS')
parser.add_argument('--extract', action='store_true',
                    help='Extract tar/zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract tar/zip files')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['3.1a', '3.1d'],
                    default='3.1d', help="The nuclear data library release version. "
                    "The currently supported options are 3.1a and 3.1d")
parser.set_defaults(download=True, extract=True)
args = parser.parse_args()


# this could be added as an argument to allow different libraries to be downloaded
library_name = 'fendl'
ace_files_dir = Path('-'.join([library_name, args.release, 'ace']))
# the destination is decided after the release is know to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '3.1a': {
        'base_url': 'https://www-nds.iaea.org/fendl31/data/neutron/',
        'files': ['fendl31a-neutron-ace.zip'],
        'neutron_files': ace_files_dir.glob('*'),
        'compressed_file_size': '0.4 GB',
        'uncompressed_file_size': '3 GB'
    },
    '3.1d': {
        'base_url': 'https://www-nds.iaea.org/fendl/data/neutron/',
        'files': ['fendl31d-neutron-ace.zip'],
        'neutron_files': ace_files_dir.joinpath('fendl31d_ACE').glob('*'),
        'compressed_file_size': '0.5 GB',
        'uncompressed_file_size': '3 GB'
    }
}

download_warning = """
WARNING: This script will download {} of data.
Extracting and processing the data requires {} of additional free disk space.
""".format(release_details[args.release]['compressed_file_size'],
           release_details[args.release]['uncompressed_file_size'])

# ==============================================================================
# DOWNLOAD FILES FROM IAEA SITE

if args.download:
    print(download_warning)
    for f in release_details[args.release]['files']:
        download(urljoin(release_details[args.release]['base_url'], f),
                    as_browser=True, context=ssl._create_unverified_context())

# ==============================================================================
# EXTRACT FILES FROM TGZ
if args.extract:
    for f in release_details[args.release]['files']:
        # Extract files, the fendl release was compressed using type 9 zip format
        # unfortunatly which is incompatible with the standard python zipfile library
        # therefore the following system command is used

        subprocess.call(['unzip', '-o', f, '-d', ace_files_dir])

# ==============================================================================
# GENERATE HDF5 LIBRARY -- NEUTRON FILES

# Get a list of all ACE files, excluding files ending with _ which are old incorrect files kept in the release for backwards compatability
neutron_files = [
    f
    for f in release_details[args.release]['neutron_files']
    if not f.name.endswith('_') and not f.name.endswith('.xsd')
]

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

for filename in sorted(neutron_files):

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
