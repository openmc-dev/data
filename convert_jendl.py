#!/usr/bin/env python3

import argparse
import glob
import os
import sys
import tarfile
import zipfile
from collections import defaultdict
from string import digits
from urllib.request import urlopen

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
parser.add_argument('-d', '--destination', default=None,
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
endf_files_dir = '-'.join([library_name, args.release, 'endf'])
# the destination is decided after the release is known to avoid putting the release in a folder with a misleading name
if args.destination == None:
    args.destination = '-'.join([library_name, args.release, 'hdf5'])

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '4.0': {
        'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/ftp/JENDL/',
        'files': ['jendl40-or-up_20160106.tar.gz'],
        'neutron_files': os.path.join(endf_files_dir, 'jendl40-or-up_20160106', '*.dat'),
        'metastables': os.path.join(endf_files_dir, 'jendl40-or-up_20160106', '*m.dat'),
        'compressed_file_size': '0.2 GB',
        'uncompressed_file_size': '? GB'
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

block_size = 16384

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

    suffix = ''
    with tarfile.open(f, 'r') as tgz:
        print('Extracting {0}...'.format(f))
        tgz.extractall(path=os.path.join(endf_files_dir, suffix))


# ==============================================================================
# GENERATE HDF5 LIBRARY -- NEUTRON FILES

# Get a list of all ACE files
neutron_files = glob.glob(release_details[args.release]['neutron_files'])

# Create output directory if it doesn't exist
if not os.path.isdir(args.destination):
    os.mkdir(args.destination)

library = openmc.data.DataLibrary()

for filename in sorted(neutron_files):

    # this is a fix for the TENDL-2017 release where the B10 ACE file which has an error on one of the values
    if library_name == 'tendl' and args.release == '2017' and os.path.basename(filename) == 'B010':
        text = open(filename, 'r').read()
        if text[423:428] == '86843':
            print('Manual fix for incorrect value in ACE file') # see OpenMC user group issue for more details
            text = ''.join(text[:423])+'86896'+''.join(text[428:])
            open(filename, 'w').write(text)

    print('Converting: ' + filename)
    data = openmc.data.IncidentNeutron.from_njoy(filename)

    # Export HDF5 file
    h5_file = os.path.join(args.destination, data.name + '.h5')
    print('Writing {}...'.format(h5_file))
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)

    # Register with library
    library.register_file(h5_file)

# Write cross_sections.xml
libpath = os.path.join(args.destination, 'cross_sections.xml')
library.export_to_xml(libpath)
