#!/usr/bin/env python3

import argparse
from pathlib import Path
import shutil
import sys

import numpy as np
import openmc.data


def library_in_list(lib, lib_list):
    """Returns whether the given nuclide library is present in the given list of libraries.

    Does this by checking whether libraries have the same type and material list.
    """
    for lib_in_list in lib_list:
        if isinstance(lib_in_list, type(lib)):
            if lib['type'] == lib_in_list['type'] \
               and np.array_equal(lib['materials'], lib_in_list['materials']):
                return True
    return False


description = """
Script to combine nuclide files from multiple OpenMC HDF5 libraries into a single library.

"""
class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass

parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path,
                    help='Directory to create new library in', required=True)
parser.add_argument('-l', '--libraries', type=Path,
                    help='List of data libraries to create', required=True, nargs='+')
parser.add_argument('-n', '--no-copy', dest='copy', action='store_true',
                    help='Don\'t copy library files, just create a cross_sections.xml file')
args = parser.parse_args()

read_libraries = []

# Error check arguments
if args.destination.exists():
    if not args.destination.is_dir():
        print(f'Error: Destination {args.destination.resolve()} should be a directory')
        sys.exit()
    if len(list(args.destination.glob('*'))) > 0:
        print(f'Error: Destination {args.destination.resolve()} is not empty')
        sys.exit()

# Parse cross_sections.xml from each library
for lib_dir in args.libraries:
    lib_cross_sections_file = lib_dir / 'cross_sections.xml'
    if not lib_cross_sections_file.exists():
        print(f'Error: Unable to find cross_sections.xml file in {lib_dir.resolve()}')
        sys.exit()
    parsed_library = openmc.data.DataLibrary.from_xml(lib_cross_sections_file)
    read_libraries.append(parsed_library)

i = 1
print(f'Creating library in {args.destination.resolve()}'
      + ' from the following nuclides in order of preference:')
for lib_dir in args.libraries:
    print(f'{i}) {lib_dir.resolve()}')
    i += 1
if args.copy:
    print('Original library files will not be copied into the destination folder')

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

combined_library = openmc.data.DataLibrary()

# Copy all of library 1 to new library
for library in read_libraries[0].libraries:
    source_file = Path(library['path'])
    destination_file = source_file
    source_path = source_file.relative_to(args.libraries[0])
    if not args.copy:
        destination_file = args.destination / source_file.name
        shutil.copy(source_file, args.destination)
    print(f'Adding {source_path} from {args.libraries[0].resolve()}')
    combined_library.register_file(destination_file)

# For each other libraries, check library and add if not already present
for lib_num in range(1, len(read_libraries)):
    for library in read_libraries[lib_num].libraries:
        if not library_in_list(library, combined_library.libraries):
            source_file = Path(library['path'])
            destination_file = source_file
            source_path = source_file.relative_to(args.libraries[lib_num])
            if not args.copy:
                destination_file = args.destination / source_file.name
                if destination_file.exists():
                    print(f'Error: Library file {destination_file.name} already'
                          + ' exists in the combined library')
                    sys.exit()
                shutil.copy(source_file, args.destination)
            print(f'Adding {source_path} from {args.libraries[lib_num].resolve()}')
            combined_library.register_file(destination_file)

# Write cross_sections.xml
combined_library_path = args.destination / 'cross_sections.xml'
combined_library.export_to_xml(combined_library_path)
