#!/usr/bin/env python3

import argparse
from pathlib import Path

from openmc.deplete import Chain

from utils import download, extract

URLS = [
    'https://www.nndc.bnl.gov/endf-releases/releases/B-VIII.1/neutrons/neutrons-version.VIII.1.tar.gz',
    'https://www.nndc.bnl.gov/endf-releases/releases/B-VIII.1/decay/decay-version.VIII.1.tar.gz',
    'https://www.nndc.bnl.gov/endf-releases/releases/B-VIII.1/nfy/nfy-version.VIII.1.tar.gz'
]


def main(chain_path, endf_path=None):
    if endf_path is not None:
        endf_path = Path(endf_path)
    elif all(Path(lib).is_dir() for lib in ("neutrons", "decay", "nfy")):
        endf_path = Path(".")
    else:
        # Download and extract archives
        for url in URLS:
            basename = download(url)
            extract(basename)

        # Rename extracted directories
        Path('decay-version.VIII.1').rename('decay')
        Path('neutrons-version.VIII.1').rename('neutrons')
        Path('nfy-version.VIII.1').rename('nfy')
        endf_path = Path.cwd()

    decay_files = list((endf_path / "decay").glob("*endf"))
    neutron_files = list((endf_path / "neutrons").glob("*endf"))
    nfy_files = list((endf_path / "nfy").glob("*endf"))

    # check files exist
    for flist, ftype in [(decay_files, "decay"), (neutron_files, "neutron"),
                         (nfy_files, "neutron fission product yield")]:
        if not flist:
            raise FileNotFoundError(f"No {ftype} endf files found in {endf_path}")

    chain = Chain.from_endf(decay_files, nfy_files, neutron_files)
    chain.export_to_xml(chain_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--chain-path', default='chain_endfb81.xml')
    parser.add_argument('--endf-path', type=Path, default=None)
    args = parser.parse_args()

    main(args.chain_path, args.endf_path)
