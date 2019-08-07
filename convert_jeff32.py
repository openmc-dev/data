#!/usr/bin/env python3

import argparse
import glob
import os
import sys
import tarfile
import zipfile
from collections import defaultdict
from string import digits

import openmc.data
from openmc._utils import download

description = """
Download JEFF 3.2 ACE data from OECD/NEA and convert it to a multi-temperature
HDF5 library for use with OpenMC.

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
parser.add_argument('-d', '--destination', default='jeff-3.2-hdf5',
                    help='Directory to create new library in')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='latest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['3.2'],
                    default='3.2', help="The nuclear data library release version. "
                    "The currently supported options are 3.2")
parser.add_argument('-t', '--temperatures', 
                    choices=['293', '400', '500', '600', '700', '800', '900', 
                             '1000', '1200', '1500', '1800'],
                    default=['293', '400', '500', '600', '700', '800', '900',
                             '1000', '1200', '1500', '1800'], 
                    help="Temperatures to download in Kelvin", nargs='+',)    
args = parser.parse_args()


library_name = 'jeff'
ace_files_dir = '-'.join([library_name, args.release, 'ace'])
# the destination is decided after the release is know to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = '-'.join([library_name, args.release, 'hdf5'])

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '3.2':{
        'base_url': 'https://www.oecd-nea.org/dbforms/data/eva/evatapes/jeff_32/Processed/',
        'files':['JEFF32-ACE-'+temperature+'K.tar.gz' for temperature in args.temperatures]+['TSLs.tar.gz'],
        'neutron_files': os.path.join(ace_files_dir, '*', '*.ACE'),
        'metastables': os.path.join(ace_files_dir, '**', '*M.ACE'),
        'sab_files': os.path.join(ace_files_dir, 'ANNEX_6_3_STLs', '*', '*.ace'),
        'redundant': os.path.join(ace_files_dir, 'ACEs_293K', '*-293.ACE'),
        'compressed_file_size': '9 GB',
        'uncompressed_file_size': '40 GB'
    }
}

download_warning = """
WARNING: This script will download approximately {} of data. Extracting and
processing the data may require as much as {} of additional free disk
space.

Are you sure you want to continue? ([y]/n)
""".format(release_details[args.release]['compressed_file_size'],
           release_details[args.release]['uncompressed_file_size'])


response = input(download_warning) if not args.batch else 'y'
if response.lower().startswith('n'):
    sys.exit()

# ==============================================================================
# DOWNLOAD FILES FROM OECD SITE

files_complete = []
for f in release_details[args.release]['files']:
    # Establish connection to URL
    url = release_details[args.release]['base_url'] + f
    downloaded_file = download(url)
    files_complete.append(f)

# ==============================================================================
# EXTRACT FILES FROM TGZ

for f in release_details[args.release]['files']:
    if f not in files_complete:
        continue

    # Extract files
    if f.endswith('.zip'):
        with zipfile.ZipFile(f, 'r') as zipf:
            print('Extracting {}...'.format(f))
            zipf.extractall(ace_files_dir)

    else:
        suffix = 'ACEs_293K' if '293' in f else ''
        with tarfile.open(f, 'r') as tgz:
            print('Extracting {}...'.format(f))
            tgz.extractall(os.path.join(ace_files_dir, suffix))

        # Remove thermal scattering tables from 293K data since they are
        # redundant
        if '293' in f:
            for path in glob.glob(release_details[args.release]['redundant']):
                print('deleting',path)
                os.remove(path)


# ==============================================================================
# CHANGE ZAID FOR METASTABLES

metastables = glob.glob(release_details[args.release]['metastables'])
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
neutron_files = glob.glob(release_details[args.release]['neutron_files'])

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

sab_files = glob.glob(release_details[args.release]['sab_files'])

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
