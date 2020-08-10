#!/usr/bin/env python3

"""
Download JEFF 3.2 ACE data from OECD/NEA and convert it to a multi-temperature
HDF5 library for use with OpenMC.
"""

import argparse
import tarfile
import zipfile
from collections import defaultdict
from pathlib import Path
from string import digits
from urllib.parse import urljoin

import openmc.data
from utils import download


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=None,
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
parser.add_argument('-r', '--release', choices=['3.2'],
                    default='3.2', help="The nuclear data library release version. "
                    "The currently supported options are 3.2")
parser.add_argument('-t', '--temperatures',
                    choices=['293', '400', '500', '600', '700', '800', '900',
                             '1000', '1200', '1500', '1800'],
                    default=['293', '400', '500', '600', '700', '800', '900',
                             '1000', '1200', '1500', '1800'],
                    help="Temperatures to download in Kelvin", nargs='+')
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
# the destination is decided after the release is know to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '3.2': {
        'base_url': 'https://www.oecd-nea.org/dbforms/data/eva/evatapes/jeff_32/Processed/',
        'compressed_files': [f'JEFF32-ACE-{t}K.zip' if t == '800' else f'JEFF32-ACE-{t}K.tar.gz' for t in args.temperatures]
                  +['TSLs.tar.gz'],
        'neutron_files': ace_files_dir.rglob('*.ACE'),
        'metastables': ace_files_dir.rglob('*M.ACE'),
        'sab_files': ace_files_dir.glob('ANNEX_6_3_STLs/*/*.ace'),
        'redundant': ace_files_dir.glob('ACEs_293K/*-293.ACE'),
        'compressed_file_size': 9,
        'uncompressed_file_size': 40
    }
}

download_warning = """
WARNING: This script will download up to {} GB of data. Extracting and
processing the data may require as much as {} GB of additional free disk
space. Note that if you don't need all 11 temperatures, you can used the
--temperature argument to download only the temperatures you want.
""".format(release_details[args.release]['compressed_file_size'],
           release_details[args.release]['uncompressed_file_size'])

# ==============================================================================
# DOWNLOAD FILES FROM OECD SITE

if args.download:
    print(download_warning)
    for f in release_details[args.release]['compressed_files']:
        download(urljoin(release_details[args.release]['base_url'], f),
                 output_path=download_path)

# ==============================================================================
# EXTRACT FILES FROM TGZ

if args.extract:
    for f in release_details[args.release]['compressed_files']:
        # Extract files
        if f.endswith('.zip'):
            with zipfile.ZipFile(download_path / f, 'r') as zipf:
                print('Extracting {}...'.format(f))
                zipf.extractall(ace_files_dir)

        else:
            suffix = 'ACEs_293K' if '293' in f else ''
            with tarfile.open(download_path / f, 'r') as tgz:
                print('Extracting {}...'.format(f))
                tgz.extractall(ace_files_dir / suffix)

            # Remove thermal scattering tables from 293K data since they are
            # redundant
            if '293' in f:
                for path in release_details[args.release]['redundant']:
                    print(f'removing {path}')
                    path.unlink()


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

# Group together tables for same nuclide
tables = defaultdict(list)
for filename in sorted(neutron_files):
    name = filename.stem
    tables[name].append(filename)

# Sort temperatures from lowest to highest
for name, filenames in sorted(tables.items()):
    filenames.sort(key=lambda x: int(
        x.parts[-2].split('_')[1][:-1]))

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

for name, filenames in sorted(tables.items()):
    # Convert first temperature for the table
    print('Converting: ' + str(filenames[0]))
    data = openmc.data.IncidentNeutron.from_ace(filenames[0])

    # For each higher temperature, add cross sections to the existing table
    for filename in filenames[1:]:
        print(f'Adding: {filename}')
        data.add_temperature_from_ace(filename)

    # Export HDF5 file
    h5_file = args.destination / f'{data.name}.h5'
    print('Writing {}...'.format(h5_file))
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)

    # Register with library
    library.register_file(h5_file)

# ==============================================================================
# GENERATE HDF5 LIBRARY -- S(A,B) FILES

# Group together tables for same nuclide
tables = defaultdict(list)
for filename in sorted(release_details[args.release]['sab_files']):
    name = filename.name.split('-')[0]
    tables[name].append(filename)

# Sort temperatures from lowest to highest
for name, filenames in sorted(tables.items()):
    filenames.sort(key=lambda x: int(
        x.name.split('-')[1].split('.')[0]))

for name, filenames in sorted(tables.items()):
    # Convert first temperature for the table
    print(f'Converting: {filenames[0]}')

    # Take numbers out of table name, e.g. lw10.32t -> lw.32t
    table = openmc.data.ace.get_table(filenames[0])
    name, xs = table.name.split('.')
    table.name = '.'.join((name.strip(digits), xs))
    data = openmc.data.ThermalScattering.from_ace(table)

    # For each higher temperature, add cross sections to the existing table
    for filename in filenames[1:]:
        print(f'Adding: {filename}')
        table = openmc.data.ace.get_table(filename)
        name, xs = table.name.split('.')
        table.name = '.'.join((name.strip(digits), xs))
        data.add_temperature_from_ace(table)

    # Export HDF5 file
    h5_file = args.destination / f'{data.name}.h5'
    print('Writing {}...'.format(h5_file))
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)

    # Register with library
    library.register_file(h5_file)

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')
