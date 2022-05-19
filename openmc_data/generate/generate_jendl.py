#!/usr/bin/env python3

"""
Download JENDL 4.0 data from JAEA and convert it to a HDF5 library for
use with OpenMC.
"""

import argparse
import ssl
from multiprocessing import Pool
from pathlib import Path
from urllib.parse import urljoin

import openmc.data
from openmc_data import download, extract, process_neutron, state_download_size, all_release_details


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
                    help='Download files from JAEA')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download files from JAEA')
parser.add_argument('--extract', action='store_true',
                    help='Extract tar/zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract tar/zip files')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='latest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['4.0'], default='4.0',
                    help="The nuclear data library release version. "
                    "The only option currently supported is 4.0")
parser.add_argument('--cleanup', action='store_true',
                    help="Remove download directories when data has "
                    "been processed")
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                    help="Do not remove download directories when data has "
                    "been processed")
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()


def main():

    library_name = 'jendl'

    cwd = Path.cwd()

    endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))
    download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))
    # the destination is decided after the release is known
    # to avoid putting the release in a folder with a misleading name
    if args.destination is None:
        args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

    # This dictionary contains all the unique information about each release.
    # This can be exstened to accommodated new releases
    details = all_release_details[library_name][args.release]['neutron']

    # ==============================================================================
    # DOWNLOAD FILES FROM WEBSITE

    if args.download:
        state_download_size(details['compressed_file_size'], details['uncompressed_file_size'], 'GB')
        for f in details['compressed_files']:
            # Establish connection to URL
            download(urljoin(details['base_url'], f),
                    context=ssl._create_unverified_context(),
                    output_path=download_path)

    # ==============================================================================
    # EXTRACT FILES FROM TGZ
    if args.extract:
        extract(
            compressed_files=[download_path/ f for f in details['compressed_files']],
            extraction_dir=endf_files_dir,
            del_compressed_file=args.cleanup
        )


    # ==============================================================================
    # GENERATE HDF5 LIBRARY -- NEUTRON FILES

    # Get a list of all ENDF files
    neutron_files = endf_files_dir.glob(details['endf_files'])

    # Create output directory if it doesn't exist
    args.destination.mkdir(parents=True, exist_ok=True)

    library = openmc.data.DataLibrary()


    with Pool() as pool:
        results = []
        for filename in sorted(neutron_files):
            func_args = (filename, args.destination, args.libver)
            r = pool.apply_async(process_neutron, func_args)
            results.append(r)

        for r in results:
            r.wait()

    # Register with library
    for p in sorted((args.destination).glob('*.h5')):
        library.register_file(p)

    # Write cross_sections.xml
    library.export_to_xml(args.destination / 'cross_sections.xml')


if __name__ == '__main__':
    main()
