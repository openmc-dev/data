#!/usr/bin/env python3

import argparse
from pathlib import Path
import shutil

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
parser.add_argument('-d', '--destination', type=Path, default=None,
                    help='Directory to output new library in')
parser.add_argument('-o', '--outputfilename', type=str, default='cross_sections.xml',
                    help='Output filename')
parser.add_argument('-l', '--libraries', type=Path,
                    help='List of data library .xml files to combine', nargs='+')
parser.set_defaults(copy=True)
args = parser.parse_args()


def main():

    read_libraries = []
    copy = True

    # Error check arguments
    if args.destination is None:
        copy = False
        args.destination = Path('.')
    else:
        if args.destination.exists():
            if not args.destination.is_dir():
                raise NotADirectoryError(f'Destination {args.destination.resolve()} should be a directory')
            if any(args.destination.iterdir()):
                raise OSError(f'Destination {args.destination.resolve()} is not empty')

    # Parse library .xml files
    if args.libraries is None:
        raise OSError('No input libraries specified')
    for lib_cross_sections_file in args.libraries:
        parsed_library = openmc.data.DataLibrary.from_xml(lib_cross_sections_file)
        read_libraries.append(parsed_library)

    print(f'Creating library {args.destination.resolve() / args.outputfilename}'
        ' from the following libraries in order of preference:')
    for i, lib_dir in enumerate(args.libraries):
        print(f'{i + 1}) {lib_dir.resolve()}')

    # Create output directory if it doesn't exist
    if copy:
        print('Original library files will be copied into the destination folder')
        args.destination.mkdir(parents=True, exist_ok=True)

    combined_library = openmc.data.DataLibrary()

    # Copy all of library 1 to new library
    for library in read_libraries[0].libraries:
        source_file = Path(library['path'])
        destination_file = source_file
        if copy:
            destination_file = args.destination / source_file.name
            shutil.copy(source_file, args.destination)
        print(f'Adding {source_file.name} from {args.libraries[0].resolve()}')
        combined_library.register_file(destination_file)

    # For each other libraries, check library and add if not already present
    for lib_num in range(1, len(read_libraries)):
        for library in read_libraries[lib_num].libraries:
            if not library_in_list(library, combined_library.libraries):
                source_file = Path(library['path'])
                destination_file = source_file
                if copy:
                    destination_file = args.destination / source_file.name
                    if destination_file.exists():
                        raise FileExistsError(f'Library file {destination_file.name} already'
                                            ' exists in the combined library')
                    shutil.copy(source_file, args.destination)
                print(f'Adding {source_file.name} from {args.libraries[lib_num].resolve()}')
                combined_library.register_file(destination_file)

    # Write .xml file
    combined_library_path = args.destination / args.outputfilename
    combined_library.export_to_xml(combined_library_path)


if __name__ == '__main__':
    main()
