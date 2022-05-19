#!/usr/bin/env python3

"""
Convert ENDF/B-VII.1 ACE data from the MCNP6 distribution into an HDF5 library
that can be used by OpenMC. This assumes that you have a directory containing
subdirectories 'endf71x' and 'ENDF71SaB'. Optionally, if a recent photoatomic
library (e.g., eprdata14) is available, it can also be converted using the
--photon argument.
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
parser.add_argument('-d', '--destination', type=Path, default=Path('mcnp_endfb71'),
                    help='Directory to create new library in')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-p', '--photon', type=Path,
                    help='Path to photoatomic data library (eprdata12 or later)')
parser.add_argument('mcnpdata', type=Path,
                    help='Directory containing endf71x and ENDF71SaB')
args = parser.parse_args()


def main():

    # Check arguments to make sure they're valid
    assert args.mcnpdata.is_dir(), 'mcnpdata argument must be a directory'
    if args.photon is not None:
        assert args.photon.is_file(), 'photon argument must be an existing file'

    # Get a list of all ACE files
    endf71x = list(args.mcnpdata.glob('endf71x/*/*.7??nc'))
    endf71sab = list(args.mcnpdata.glob('ENDF71SaB/*.??t'))

    # Check for fixed H1 files and remove old ones if present
    hydrogen = args.mcnpdata / 'endf71x' / 'H'
    if (hydrogen / '1001.720nc').is_file():
        for i in range(10, 17):
            endf71x.remove(hydrogen / f'1001.7{i}nc')

    # There's a bug in H-Zr at 1200 K
    thermal = args.mcnpdata / 'ENDF71SaB'
    endf71sab.remove(thermal / 'h-zr.27t')

    # Check for updated TSL files and remove old ones if present
    checks = [
        ('sio2', 10, range(20, 37)),
        ('u-o2', 30, range(20, 28)),
        ('zr-h', 30, range(20, 28))
    ]
    for material, good, bad in checks:
        if (thermal / f'{material}.{good}t').is_file():
            for suffix in bad:
                f = thermal / f'{material}.{suffix}t'
                if f.is_file():
                    endf71sab.remove(f)

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
    if args.photon is not None:
        lib = openmc.data.ace.Library(args.photon)

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


if __name__ == '__main__':
    main()
