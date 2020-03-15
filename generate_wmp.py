#!/usr/bin/env python3

"""
Downloads windowed multipole data from the MIT Github repository for 
temperature-dependent cross section lookups on-the-fly.
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

parser.add_argument('-d', '--destination', type=Path, default='wmp-1.1-hdf5',
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download tarball from MIT Github')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download tarball from MIT Github')
parser.add_argument('--extract', action='store_true',
                    help='Extract compressed files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract compressed file if it has already been extracted')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('--cleanup', action='store_true',
                    help="Remove download directories when data has "
                    "been processed")
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                    help="Do not remove download directories when data has "
                    "been processed")
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()

library_name = 'wmp'
release = '1.1'

cwd = Path.cwd()

download_path = cwd.joinpath('-'.join([library_name, release, 'download']))

# This dictionary contains all the unique information about each release. This
# can be exstened to accommodated new releases
release_details = {
    '1.1': {
            'base_url': 'https://github.com/mit-crpg/WMP_Library/releases/download/v1.1/',
            'compressed_files': ['WMP_Library_v1.1.tar.gz'],
            'compressed_file_size': 12,
            'uncompressed_file_size': 17
            }
}

download_warning = """
WARNING: This script will download {} of data.
Extracting and processing the data requires {} of additional free disk space.
""".format(release_details[release]['compressed_file_size'],
           release_details[release]['uncompressed_file_size'])

# ==============================================================================
# DOWNLOAD FILES FROM MIT GITHUB SITE

if args.download:
    print(download_warning) 
    for f in release_details[release]['compressed_files']:
        # Establish connection to URL
        url = release_details[release]['base_url'] + f
        download(url, output_path=download_path)


# ==============================================================================
# EXTRACT FILES FROM TGZ

if args.extract:
    for f in release_details[release]['compressed_files']:
        with tarfile.open(download_path / Path(f), 'r') as tgz:
            tgz.extractall(path=args.destination)

    if args.cleanup and download_path.exists():
        rmtree(download_path)  


# ==============================================================================
# GENERATE HDF5 LIBRARY

library = openmc.data.DataLibrary()

# Add multipole data to library
for h5_file in Path(args.destination).rglob('*.h5'):
    library.register_file(h5_file)

# Write cross_sections.xml
print('Writing ', args.destination / 'cross_sections.xml')
library.export_to_xml(args.destination / 'cross_sections.xml')
