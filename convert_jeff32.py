#!/usr/bin/env python3

import argparse
import glob
import os
import tarfile
import zipfile
from collections import defaultdict
from string import digits
from urllib.parse import urljoin

import openmc.data
from openmc._utils import download

description = """
Download JEFF 3.2 ACE data from OECD/NEA and convert it to a multi-temperature
HDF5 library for use with OpenMC.

"""

download_warning = """
WARNING: This script will download approximately 9 GB of data. Extracting and
processing the data may require as much as 40 GB of additional free disk
space. Note that if you don't need all 11 temperatures, you can modify the
'files' list in the script to download only the data you want.
"""

class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass

parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', default='jeff-3.2-hdf5',
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download files from OECD-NEA')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download files from OECD-NEA')
parser.add_argument('--extract', action='store_true',
                    help='Extract tar/zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract tar/zip files')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='latest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.set_defaults(download=True, extract=True)
args = parser.parse_args()

print(download_warning)

base_url = 'https://www.oecd-nea.org/dbforms/data/eva/evatapes/jeff_32/Processed/'
files = ['JEFF32-ACE-293K.tar.gz',
         'JEFF32-ACE-400K.tar.gz',
         'JEFF32-ACE-500K.tar.gz',
         'JEFF32-ACE-600K.tar.gz',
         'JEFF32-ACE-700K.tar.gz',
         'JEFF32-ACE-800K.zip',
         'JEFF32-ACE-900K.tar.gz',
         'JEFF32-ACE-1000K.tar.gz',
         'JEFF32-ACE-1200K.tar.gz',
         'JEFF32-ACE-1500K.tar.gz',
         'JEFF32-ACE-1800K.tar.gz',
         'TSLs.tar.gz']

# ==============================================================================
# DOWNLOAD FILES FROM OECD SITE

if args.download:
    for f in files:
        download(urljoin(base_url, f))

# ==============================================================================
# EXTRACT FILES FROM TGZ

if args.extract:
    for f in files:
        # Extract files
        if f.endswith('.zip'):
            with zipfile.ZipFile(f, 'r') as zipf:
                print('Extracting {}...'.format(f))
                zipf.extractall('jeff-3.2')

        else:
            suffix = 'ACEs_293K' if '293' in f else ''
            with tarfile.open(f, 'r') as tgz:
                print('Extracting {}...'.format(f))
                tgz.extractall(os.path.join('jeff-3.2', suffix))

            # Remove thermal scattering tables from 293K data since they are
            # redundant
            if '293' in f:
                for path in glob.glob(os.path.join('jeff-3.2', 'ACEs_293K', '*-293.ACE')):
                    os.remove(path)

# ==============================================================================
# CHANGE ZAID FOR METASTABLES

metastables = glob.glob(os.path.join('jeff-3.2', '**', '*M.ACE'))
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
neutron_files = glob.glob(os.path.join('jeff-3.2', '*', '*.ACE'))

# Group together tables for same nuclide
tables = defaultdict(list)
for filename in sorted(neutron_files):
    dirname, basename = os.path.split(filename)
    name = basename.split('.')[0]
    tables[name].append(filename)

# Sort temperatures from lowest to highest
for name, filenames in sorted(tables.items()):
    filenames.sort(key=lambda x: int(
        x.split(os.path.sep)[1].split('_')[1][:-1]))

# Create output directory if it doesn't exist
if not os.path.isdir(args.destination):
    os.mkdir(args.destination)

library = openmc.data.DataLibrary()

for name, filenames in sorted(tables.items()):
    # Convert first temperature for the table
    print('Converting: ' + filenames[0])
    data = openmc.data.IncidentNeutron.from_ace(filenames[0])

    # For each higher temperature, add cross sections to the existing table
    for filename in filenames[1:]:
        print('Adding: ' + filename)
        data.add_temperature_from_ace(filename)

    # Export HDF5 file
    h5_file = os.path.join(args.destination, data.name + '.h5')
    print('Writing {}...'.format(h5_file))
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)

    # Register with library
    library.register_file(h5_file)

# ==============================================================================
# GENERATE HDF5 LIBRARY -- S(A,B) FILES

sab_files = glob.glob(os.path.join('jeff-3.2', 'ANNEX_6_3_STLs', '*', '*.ace'))

# Group together tables for same nuclide
tables = defaultdict(list)
for filename in sorted(sab_files):
    dirname, basename = os.path.split(filename)
    name = basename.split('-')[0]
    tables[name].append(filename)

# Sort temperatures from lowest to highest
for name, filenames in sorted(tables.items()):
    filenames.sort(key=lambda x: int(
        os.path.split(x)[1].split('-')[1].split('.')[0]))

for name, filenames in sorted(tables.items()):
    # Convert first temperature for the table
    print('Converting: ' + filenames[0])

    # Take numbers out of table name, e.g. lw10.32t -> lw.32t
    table = openmc.data.ace.get_table(filenames[0])
    name, xs = table.name.split('.')
    table.name = '.'.join((name.strip(digits), xs))
    data = openmc.data.ThermalScattering.from_ace(table)

    # For each higher temperature, add cross sections to the existing table
    for filename in filenames[1:]:
        print('Adding: ' + filename)
        table = openmc.data.ace.get_table(filename)
        name, xs = table.name.split('.')
        table.name = '.'.join((name.strip(digits), xs))
        data.add_temperature_from_ace(table)

    # Export HDF5 file
    h5_file = os.path.join(args.destination, data.name + '.h5')
    print('Writing {}...'.format(h5_file))
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)

    # Register with library
    library.register_file(h5_file)

# Write cross_sections.xml
libpath = os.path.join(args.destination, 'cross_sections.xml')
library.export_to_xml(libpath)
