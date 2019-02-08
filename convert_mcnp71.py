#!/usr/bin/env python3

import argparse
from collections import defaultdict
from pathlib import Path
import sys

import openmc.data


# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"

description = """
Convert ENDF/B-VII.1 ACE data from the MCNP6 distribution into an HDF5 library
that can be used by OpenMC. This assumes that you have a directory containing
subdirectories 'endf71x' and 'ENDF71SaB'. If the 'mcplib84' photoatomic library
is present in the data directory, it will also be converted.

"""


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=Path('mcnp_endfb71'),
                    help='Directory to create new library in')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('mcnpdata', type=Path,
                    help='Directory containing endf71x and ENDF71SaB')
args = parser.parse_args()
assert args.mcnpdata.is_dir()

# Get a list of all ACE files
endf71x = list(args.mcnpdata.glob('endf71x/*/*.71?nc'))
endf71sab = list(args.mcnpdata.glob('ENDF71SaB/*.??t'))

# There's a bug in H-Zr at 1200 K
endf71sab.remove(args.mcnpdata / 'ENDF71SaB' / 'h-zr.27t')

# Group together tables for the same nuclide
tables = defaultdict(list)
for p in sorted(endf71x + endf71sab):
    tables[p.stem].append(p)

# Create output directory if it doesn't exist
(args.destination / 'photon').mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

for name, paths in sorted(tables.items()):
    # Convert first temperature for the table
    p = paths[0]
    print(f'Converting: {p}')
    if p.name.endswith('t'):
        data = openmc.data.ThermalScattering.from_ace(p)
    else:
        data = openmc.data.IncidentNeutron.from_ace(p, 'mcnp')

    # For each higher temperature, add cross sections to the existing table
    for p in paths[1:]:
        print(f'Adding: {p}')
        if p.name.endswith('t'):
            data.add_temperature_from_ace(p)
        else:
            data.add_temperature_from_ace(p, 'mcnp')

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
