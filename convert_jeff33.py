#!/usr/bin/env python

import argparse
from pathlib import Path
import tarfile
import sys

import openmc.data
from openmc._utils import download


# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"

description = """
Convert JEFF 3.3 ACE data distributed by OECD/NEA into an HDF5 library
that can be used by OpenMC. It will download an 1.3 GB archive containing
all the ACE files, extract it, convert them, and write HDF5 files into a
destination directory.

"""

class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=description,
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
parser.set_defaults(download=True, extract=True)
args = parser.parse_args()

ace_files_dir = Path('jeff-3.3-ace')

# Download JEFF 3.3 library
filename = 'JEFF33-n_tsl-ace.tgz'
url = f'http://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/{filename}'
if args.download:
    download(url)

# Extract tar file
if args.extract:
    with tarfile.open(filename, 'r') as tgz:
        print(f'Extracting {filename}...')
        tgz.extractall(path=ace_files_dir)

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
