#!/usr/bin/env python3

import argparse
from pathlib import Path
from zipfile import ZipFile

from openmc.deplete import Chain

from utils import download

URLS = [
    'https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_neutrons.zip',
    'https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_decay.zip',
    'https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_nfy.zip'
]


def main(chain_path, release, endf_path=None):
    if endf_path is not None:
        endf_path = Path(endf_path)
    elif all(Path(lib).is_dir() for lib in ("neutrons", "decay", "nfy")):
        endf_path = Path(".")
    else:
        # Download and extract zip files
        for url in URLS:
            basename = download(url)
            with ZipFile(basename, 'r') as zf:
                print(f'Extracting {basename}...')
                zf.extractall()

        # Rename extracted directories
        Path('ENDF-B-VIII.0_decay').rename('decay')
        Path('ENDF-B-VIII.0_neutrons').rename('neutrons')
        Path('ENDF-B-VIII.0_nfy').rename('nfy')
        endf_path = Path.cwd()

    decay_files = list((endf_path / "decay").glob("*endf"))
    neutron_files = list((endf_path / "neutrons").glob("*endf"))
    nfy_files = list((endf_path / "nfy").glob("*endf"))

    # check files exist
    for flist, ftype in [(decay_files, "decay"), (neutron_files, "neutron"),
                         (nfy_files, "neutron fission product yield")]:
        if not flist:
            raise IOError(f"No {ftype} endf files found in {endf_path}")

    chain = Chain.from_endf(decay_files, nfy_files, neutron_files)
    chain.export_to_xml(chain_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--chain-path', default='chain_endfb80.xml')
    parser.add_argument('--endf-path', type=Path, default=None)
    args = parser.parse_args()

    main(args.chain_path, args.endf_path)
