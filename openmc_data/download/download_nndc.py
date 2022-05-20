#!/usr/bin/env python3

"""
Downloads preprocessed ENDF HDF5 files and cross_sections.xml from openmc.org
for use with OpenMC.
"""

import argparse
from pathlib import Path
from urllib.parse import urljoin

from openmc_data.urls_h5 import all_h5_release_details
from openmc_data.utils import download, extract, state_download_size


class CustomFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    pass


parser = argparse.ArgumentParser(description=__doc__, formatter_class=CustomFormatter)
parser.add_argument(
    "-d",
    "--destination",
    type=Path,
    default=None,
    help="Directory to create new library in",
)
parser.add_argument("--download", action="store_true", help="Download files from PSI")
parser.add_argument(
    "--no-download",
    dest="download",
    action="store_false",
    help="Do not download files from PSI",
)
parser.add_argument("--extract", action="store_true", help="Extract tar/zip files")
parser.add_argument(
    "--no-extract",
    dest="extract",
    action="store_false",
    help="Do not extract tar/zip files",
)
parser.add_argument(
    "-r",
    "--release",
    choices=["b7.1"],
    default="b7.1",
    help="The nuclear data library release version. The currently supported "
         "options are b7.1",
)
parser.add_argument(
    "--cleanup",
    action="store_true",
    help="Remove download directories when data has " "been processed",
)
parser.add_argument(
    "--no-cleanup",
    dest="cleanup",
    action="store_false",
    help="Do not remove download directories when data has " "been processed",
)
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()


def main():

    library_name = 'nndc'
    details = all_h5_release_details[library_name][args.release]["neutron-photon"]

    cwd = Path.cwd()

    download_path = cwd.joinpath("-".join([library_name, args.release, "download"]))

    if args.destination is None:
        args.destination = Path("-".join([library_name, args.release, "hdf5"]))

    if args.download:
        state_download_size(
            details['compressed_file_size'],
            details['uncompressed_file_size'],
            'GB'
        )
        download(
            urljoin(details["base_url"], details["compressed_files"][0]),
            output_path=download_path,
        )

    if args.extract:
        extract(
            compressed_files=[
                download_path / f for f in details["compressed_files"]
            ],
            extraction_dir=args.destination,
            del_compressed_file=args.cleanup,
        )


if __name__ == "__main__":
    main()
