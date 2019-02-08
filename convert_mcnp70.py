#!/usr/bin/env python3

import argparse
from collections import defaultdict
from pathlib import Path
import sys

import openmc.data


# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"

description = """
Convert ENDF/B-VII.0 ACE data from the MCNP5/6 distribution into an HDF5 library
that can be used by OpenMC. This assumes that you have a directory containing
files named endf70[a-k], endf70sab, and mcplib84.

"""


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=Path('mcnp_endfb70'),
                    help='Directory to create new library in')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('mcnpdata', type=Path,
                    help="Directory containing endf70[a-k], endf70sab, and mcplib")
args = parser.parse_args()
assert args.mcnpdata.is_dir()

# Get a list of all neutron ACE files
endf70 = args.mcnpdata.glob('endf70[a-k]')

# Create output directory if it doesn't exist
(args.destination / 'photon').mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

for path in sorted(endf70):
    print(f'Loading data from {path}...')
    lib = openmc.data.ace.Library(path)

    # Group together tables for the same nuclide
    tables = defaultdict(list)
    for table in lib.tables:
        zaid, xs = table.name.split('.')
        tables[zaid].append(table)

    for zaid, tables in sorted(tables.items()):
        # Convert first temperature for the table
        print(f'Converting: {tables[0].name}')
        data = openmc.data.IncidentNeutron.from_ace(tables[0], 'mcnp')

        # For each higher temperature, add cross sections to the existing table
        for table in tables[1:]:
            print(f'Adding: {table.name}')
            data.add_temperature_from_ace(table, 'mcnp')

        # Export HDF5 file
        h5_file = args.destination / f'{data.name}.h5'
        print(f'Writing {h5_file}...')
        data.export_to_hdf5(h5_file, 'w', libver=args.libver)

        # Register with library
        library.register_file(h5_file)

# Handle S(a,b) tables
endf70sab = args.mcnpdata / 'endf70sab'
if endf70sab.exists():
    lib = openmc.data.ace.Library(endf70sab)

    # Group together tables for the same nuclide
    tables = defaultdict(list)
    for table in lib.tables:
        name, xs = table.name.split('.')
        tables[name].append(table)

    for zaid, tables in sorted(tables.items()):
        # Convert first temperature for the table
        print(f'Converting: {tables[0].name}')
        data = openmc.data.ThermalScattering.from_ace(tables[0])

        # For each higher temperature, add cross sections to the existing table
        for table in tables[1:]:
            print(f'Adding: {table.name}')
            data.add_temperature_from_ace(table)

        # Export HDF5 file
        h5_file = args.destination / f'{data.name}.h5'
        print(f'Writing {h5_file}...')
        data.export_to_hdf5(h5_file, 'w', libver=args.libver)

        # Register with library
        library.register_file(h5_file)

# Handle photoatomic data
mcplib = args.mcnpdata / 'mcplib84'
if mcplib.exists():
    lib = openmc.data.ace.Library(mcplib)

    for table in lib.tables:
        # Convert first temperature for the table
        print(f'Converting: {table.name}')
        data = openmc.data.IncidentPhoton.from_ace(table)

        # Export HDF5 file
        h5_file = args.destination / 'photon' / f'{data.name}.h5'
        print(f'Writing {h5_file}...')
        data.export_to_hdf5(h5_file, 'w', libver=args.libver)

        # Register with library
        library.register_file(h5_file)

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')
