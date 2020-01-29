#!/usr/bin/env python3

import argparse
from pathlib import Path
import ssl
import sys
import tarfile

import openmc.data
from openmc._utils import download

description = """
Download JENDL 4.0 data from JAEA and convert it to a HDF5 library for
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
parser.add_argument('-r', '--release', choices=['4.0'],
                    default='4.0', help="The nuclear data library release version. "
                    "The only option currently supported is 4.0")
args = parser.parse_args()



library_name = 'jendl' #this could be added as an argument to allow different libraries to be downloaded
endf_files_dir = Path('-'.join([library_name, args.release, 'endf']))
# the destination is decided after the release is known to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '4.0': {
        'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/ftp/JENDL/',
        'files': ['jendl40-or-up_20160106.tar.gz'],
        'neutron_files': endf_files_dir.joinpath('jendl40-or-up_20160106').glob('*.dat'),
        'metastables': endf_files_dir.joinpath('jendl40-or-up_20160106').glob('*m.dat'),
        'compressed_file_size': '0.2 GB',
        'uncompressed_file_size': '2 GB'
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
    downloaded_file = download(url, 
                               context=ssl._create_unverified_context())
    files_complete.append(downloaded_file)

# ==============================================================================
# EXTRACT FILES FROM TGZ

for f in release_details[args.release]['files']:
    if f not in files_complete:
        continue

    # Extract files

    with tarfile.open(f, 'r') as tgz:
        print('Extracting {0}...'.format(f))
        tgz.extractall(path=endf_files_dir)


# ==============================================================================
# GENERATE HDF5 LIBRARY -- NEUTRON FILES

# Get a list of all ACE files
neutron_files = release_details[args.release]['neutron_files']

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

for filename in sorted(neutron_files):

    print('Converting: ' + str(filename))
    data = openmc.data.IncidentNeutron.from_njoy(filename)

    # Export HDF5 file
    h5_file = args.destination / f'{data.name}.h5'
    print('Writing {}...'.format(h5_file))
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)

    # Register with library
    library.register_file(h5_file)

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')
