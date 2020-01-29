#!/usr/bin/env python3

import argparse
from pathlib import Path
import sys
import zipfile

import openmc.data
from openmc._utils import download

description = """
Download CENDL 3.1 data from OECD NEA and convert it to a HDF5 library for
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
parser.add_argument('-r', '--release', choices=['3.1'],
                    default='3.1', help="The nuclear data library release version. "
                    "The only option currently supported is 3.1")
args = parser.parse_args()



library_name = 'cendl' #this could be added as an argument to allow different libraries to be downloaded
endf_files_dir = Path('-'.join([library_name, args.release, 'endf']))
# the destination is decided after the release is known to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '3.1': {
        'base_url': 'https://www.oecd-nea.org/dbforms/data/eva/evatapes/cendl_31/',
        'files': ['CENDL-31.zip'],
        'neutron_files': endf_files_dir.glob('*.C31'),
        'metastables': endf_files_dir.glob('*m.C31'),
        'compressed_file_size': '0.03 GB',
        'uncompressed_file_size': '0.4 GB'
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
# EXTRACT FILES FROM ZIP

for f in release_details[args.release]['files']:
    if f not in files_complete:
        continue

    # Extract files

    with zipfile.ZipFile(f) as zf:
        print('Extracting {0}...'.format(f))
        zf.extractall(path=endf_files_dir)


# ==============================================================================
# GENERATE HDF5 LIBRARY -- NEUTRON FILES

# Get a list of all ENDF files
neutron_files = release_details[args.release]['neutron_files']

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

for filename in sorted(neutron_files):

    # this is a fix for the CENDL 3.1 release where the 22-Ti-047.C31 and 5-B-010.C31 files contain non-ASCII characters
    if library_name == 'cendl' and args.release == '3.1' and filename.name in  ['22-Ti-047.C31','5-B-010.C31']:
        print('Manual fix for incorrect value in ENDF file')
        text = open(filename, 'rb').read().decode('utf-8','ignore').split('\r\n')
        if filename.name == '22-Ti-047.C31':
            text[205] = ' 8) YUAN Junqian,WANG Yongchang,etc.               ,16,(1),57,92012228 1451  205'
        if filename.name == '5-B-010.C31':
            text[203] = '21)   Day R.B. and Walt M.  Phys.rev.117,1330 (1960)               525 1451  203'
        open(filename, 'w').write('\r\n'.join(text))

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
