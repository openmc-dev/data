#!/usr/bin/env python3

import os
from argparse import ArgumentParser
from pathlib import Path
from zipfile import ZipFile

import openmc.deplete

from openmc_data.utils import download


URLS = [
    'https://www.nndc.bnl.gov/endf-b7.1/zips/ENDF-B-VII.1-neutrons.zip',
    'https://www.nndc.bnl.gov/endf-b7.1/zips/ENDF-B-VII.1-decay.zip',
    'https://www.nndc.bnl.gov/endf-b7.1/zips/ENDF-B-VII.1-nfy.zip'
]

# Parse command line arguments
parser = ArgumentParser()
parser.add_argument(
    "-d",
    "--destination",
    type=Path,
    default='chain_endfb71.xml',
    help="filename of the chain file xml file produced.",
)
args = parser.parse_args()


def main():
    endf_dir = os.environ.get("OPENMC_ENDF_DATA")
    if endf_dir is not None:
        endf_dir = Path(endf_dir)
    elif all(os.path.isdir(lib) for lib in ("neutrons", "decay", "nfy")):
        endf_dir = Path(".")
    else:
        for url in URLS:
            basename = download(url)
            with ZipFile(basename, 'r') as zf:
                print('Extracting {}...'.format(basename))
                zf.extractall()
        endf_dir = Path(".")

    decay_files = list((endf_dir / "decay").glob("*endf"))
    neutron_files = list((endf_dir / "neutrons").glob("*endf"))
    nfy_files = list((endf_dir / "nfy").glob("*endf"))

    # Remove erroneous Be7 evaluation that can cause problems
    decay_files.remove(endf_dir / "decay" / "dec-004_Be_007.endf")
    neutron_files.remove(endf_dir / "neutrons" / "n-004_Be_007.endf")

    # check files exist
    for flist, ftype in [(decay_files, "decay"), (neutron_files, "neutron"),
                         (nfy_files, "neutron fission product yield")]:
        if not flist:
            raise IOError("No {} endf files found in {}".format(ftype, endf_dir))

    chain = openmc.deplete.Chain.from_endf(decay_files, nfy_files, neutron_files)

    chain.export_to_xml(args.destination)


if __name__ == '__main__':
    main()
