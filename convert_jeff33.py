#!/usr/bin/env python

"""
Convert JEFF 3.3 ACE data distributed by OECD/NEA into an HDF5 library
that can be used by OpenMC. It will download an 1.3 GB archive containing
all the ACE files, extract it, convert them, and write HDF5 files into a
destination directory.
"""

import argparse
import tarfile
import sys
import os
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
parser.add_argument('-d', '--destination', type=Path, default=Path('jeff-3.3-hdf5'),
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download tarball from OECD-NEA')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download tarball from OECD-NEA')
parser.add_argument('--extract', action='store_true',
                    help='Extract zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract .tgz file if it has already been extracted')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['3.3'],
                    default='3.3', help="The nuclear data library release version. "
                    "The only currently supported option is 3.3.")
parser.add_argument('--cleanup', action='store_true',
                    help="Remove download directories when data has "
                    "been processed")
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                    help="Do not remove download directories when data has "
                    "been processed")
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()

library_name = 'jeff'

cwd = Path.cwd()

ace_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'ace']))
download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '3.3': {
        'base_url': 'http://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/',
        'compressed_files': ['JEFF33-n_tsl-ace.tgz'],
        'neutron_files': sorted(ace_files_dir.rglob('*.[Aa][Cc][Ee]')),
        'metastables': ace_files_dir.glob('neutron_file/*/*/lib/endf/*m-n.ace'),
        'compressed_file_size': '1.3 GB',
        'uncompressed_file_size': '8.2 GB'
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

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

# Get a list of all ACE files
paths = sorted(ace_files_dir.rglob('*.[Aa][Cc][Ee]'))

lib = openmc.data.DataLibrary()
for p in sorted(paths):
    print(f'Converting: {p}')
    if 'jeff33' in str(p):
        data = openmc.data.IncidentNeutron.from_ace(p)
        if 'm.' in str(p):
            # Correct metastable
            data.metastable = 1
            data.name += '_m1'
    else:
        data = openmc.data.ThermalScattering.from_ace(p)

    h5_file = args.destination / f'{data.name}.h5'
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)
    lib.register_file(h5_file)

lib.export_to_xml(args.destination / 'cross_sections.xml')
