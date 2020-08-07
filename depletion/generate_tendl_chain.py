#!/usr/bin/env python3

"""
Generate a depletion chain based on TENDL 2019 data. Note that TENDL 2019 does
not contain any decay or fission product yield (FPY) sublibraries, so these must
be borrowed from another library. The --lib flag for this script indicates what
library should be used for decay and FPY evaluations and defaults to JEFF 3.3.
"""

from argparse import ArgumentParser
import json
import os
from pathlib import Path
import tarfile
from zipfile import ZipFile

import openmc.deplete as dep
import openmc.data

from utils import download


NEUTRON_LIB = 'https://tendl.web.psi.ch/tendl_2019/tar_files/TENDL-n.tgz'
DECAY_LIB = {
    'jeff33': 'https://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/JEFF33-rdd.zip',
    'endf80': 'https://www.nndc.bnl.gov/endf/b8.0/zips/ENDF-B-VIII.0_decay.zip',
}
NFY_LIB = {
    'jeff33': 'https://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/JEFF33-nfy.asc',
    'endf80': 'https://www.nndc.bnl.gov/endf/b8.0/zips/ENDF-B-VIII.0_nfy.zip',
}


def extract(filename, path=".", verbose=True):
    # Determine function to open archive
    if Path(filename).suffix == '.zip':
        func = ZipFile
    else:
        func = tarfile.open

    # Open archive and extract files
    with func(filename, 'r') as fh:
        if verbose:
            print(f'Extracting {filename}...')
        fh.extractall(path)


def fix_jeff33_nfy(path):
    print(f'Fixing TPID in {path}...')
    new_path = path.with_name(path.name + '_fixed')
    if not new_path.exists():
        with path.open('r') as f:
            data = f.read()
        with new_path.open('w') as f:
            # Write missing TPID line
            f.write(" "*66 + "   1 0  0    0\n")
            f.write(data)
    return new_path


def main():
    # Parse command line arguments
    parser = ArgumentParser()
    parser.add_argument('--lib', choices=('jeff33', 'endf80'), default='jeff33',
                        help='Library to use for decay and fission product yields')
    args = parser.parse_args()

    # Setup output directories
    endf_dir = Path("tendl-download")
    neutron_dir = endf_dir / "neutrons"
    decay_dir = endf_dir / "decay"
    nfy_dir = endf_dir / "nfy"

    # ==========================================================================
    # Incident neutron data

    neutron_tgz = download(NEUTRON_LIB, output_path=endf_dir)
    extract(neutron_tgz, neutron_dir)

    # Get list of transport nuclides in TENDL-2019
    with open('tendl2019_nuclides.json', 'r') as fh:
        transport_nuclides = set(json.load(fh))

    neutron_files = [
        p
        for p in (endf_dir / "neutrons").glob("*.tendl")
        if p.name[2:-6] in transport_nuclides  # filename is n-XXNNN.tendl
    ]

    # ==========================================================================
    # Decay and fission product yield data

    decay_zip = download(DECAY_LIB[args.lib], output_path=endf_dir)
    nfy_file = download(NFY_LIB[args.lib], output_path=endf_dir)

    extract(decay_zip, decay_dir)
    if args.lib == 'jeff33':
        decay_files = list(decay_dir.glob('*.ASC'))

        nfy_file_fixed = fix_jeff33_nfy(nfy_file)
        nfy_files = openmc.data.endf.get_evaluations(nfy_file_fixed)

    elif args.lib == 'endf80':
        decay_files = list(decay_dir.glob('**/*.endf'))

        extract(nfy_file, nfy_dir)
        nfy_files = list(nfy_dir.glob('**/*.endf'))

    chain = dep.Chain.from_endf(
        decay_files, nfy_files, neutron_files,
        reactions=dep.chain.REACTIONS.keys()
    )
    chain.export_to_xml(f'chain_tendl2019_{args.lib}.xml')


if __name__ == '__main__':
    main()
