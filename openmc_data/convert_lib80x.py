#!/usr/bin/env python3

"""
Convert ENDF/B-VIII.0 ACE data from LANL into an HDF5 library
that can be used by OpenMC. This assumes that you have a directory containing
subdirectories 'Lib80x' and 'ENDF80SaB'.
"""

import argparse
from collections import defaultdict
from pathlib import Path
import sys

import openmc.data


# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"



class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=Path('lib80x_hdf5'),
                    help='Directory to create new library in')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('datadir', type=Path,
                    help='Directory containing Lib80x and ENDF80SaB/ENDF80SaB2')

args = parser.parse_args()


def main():

    assert args.datadir.is_dir()
    # Get a list of all ACE files
    lib80x = list(args.datadir.glob('Lib80x/**/*.80?nc'))
    if (args.datadir / 'ENDF80SaB2').is_dir():
        thermal_dir = args.datadir / 'ENDF80SaB2'
    else:
        thermal_dir = args.datadir / 'ENDF80SaB'
    lib80sab = list(thermal_dir.glob('**/*.??t'))

    # Find and fix B10 ACE files
    b10files = list(args.datadir.glob('Lib80x/**/5010.80?nc'))
    nxs1_position = 523
    for filename in b10files:
        with open(filename, 'r+') as fh:
            # Read NXS(1)
            fh.seek(nxs1_position)
            nxs1 = int(fh.read(5))

            # Increase length to match actual length of XSS, but make sure this
            # isn't done twice by checking the current length
            if nxs1 < 86870:
                fh.seek(nxs1_position)
                fh.write(str(nxs1 + 53))

    # Group together tables for the same nuclide
    tables = defaultdict(list)
    for p in sorted(lib80x + lib80sab):
        tables[p.stem].append(p)

    # Create output directory if it doesn't exist
    args.destination.mkdir(parents=True, exist_ok=True)

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

    # Write cross_sections.xml
    library.export_to_xml(args.destination / 'cross_sections.xml')


if __name__ == '__main__':
    main()
