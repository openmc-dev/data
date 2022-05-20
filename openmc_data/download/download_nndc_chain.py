#!/usr/bin/env python3

"""
Downloads preprocessed a chain file in xml format for use with OpenMc depletion
simulations.
"""

import argparse
from pathlib import Path
from urllib.parse import urljoin

from openmc_data.urls_xml import all_chain_release_details
from openmc_data.utils import download


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
parser.add_argument(
    "-f",
    "--filename",
    type=Path,
    default=None,
    help="Filename for the xml chain file",
)
parser.add_argument(
    "-r",
    "--release",
    choices=["b7.1"],
    default="b7.1",
    help="The nuclear data library release version. The currently supported "
         "options are b7.1",
)

parser.set_defaults()
args = parser.parse_args()


def main():

    library_name = 'nndc'
    details = all_chain_release_details[library_name][args.release]["chain"]

    cwd = Path.cwd()

    if args.filename is None:
        args.filename = Path("-".join(["chain", library_name, args.release])+".xml")
    print(args.filename)

    download(
        details["url"],
        output_path=args.destination,
        output_filename=args.filename,
    )


if __name__ == "__main__":
    main()
