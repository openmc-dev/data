#!/usr/bin/env python3

import argparse
from pathlib import Path
import tempfile

from openmc.deplete import Chain
import openmc.data

from utils import download, extract

URLS = [
    'https://data.oecd-nea.org/records/bh7jn-rm903/files/JEFF33-n.tgz?download=1',
    'https://data.oecd-nea.org/records/qfhqd-s0y84/files/JEFF33-rdd.zip?download=1',
    'https://data.oecd-nea.org/records/nhfqy-hvz09/files/JEFF33-nfy.asc?download=1',
]


def main(chain_path, endf_path=None):
    if endf_path is not None:
        endf_path = Path(endf_path)
    elif all(Path(lib).is_dir() for lib in ("neutrons", "decay", "nfy")):
        endf_path = Path(".")
    else:
        # Create directories for decay and nfy data
        Path('decay').mkdir(exist_ok=True)
        Path('nfy').mkdir(exist_ok=True)

        # Download and extract tar files
        for url in URLS:
            basename = download(url)
            if basename.suffix == '.tgz':
                extract(basename)
            elif basename.suffix == '.zip':
                extract(basename, extraction_dir='decay')

        # Rename extracted directories and move JEFF33-nfy.asc into the nfy directory
        Path('endf6').rename('neutrons')
        Path('JEFF33-nfy.asc').rename(Path('nfy') / 'JEFF33-nfy.asc')

        endf_path = Path.cwd()

    decay_files = list((endf_path / "decay").glob("*.ASC"))
    neutron_files = list((endf_path / "neutrons").glob("*.jeff33"))
    nfy_file = (endf_path / "nfy") / "JEFF33-nfy.asc"

    # Create temporary file with TPID line and append nfy_file content
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_f:
        temp_f.write(" "*69 + "1 0  0    0\n")
        temp_f.write(nfy_file.read_text())
        temp_path = Path(temp_f.name)

    try:
        # Get evaluations from the patched file
        nfy_evals = openmc.data.endf.get_evaluations(temp_path)
    finally:
        # Clean up temporary file
        temp_path.unlink()

    chain = Chain.from_endf(decay_files, nfy_evals, neutron_files)
    chain.export_to_xml(chain_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--chain-path', default='chain_jeff33.xml')
    parser.add_argument('--endf-path', type=Path, default=None)
    args = parser.parse_args()

    main(args.chain_path, args.endf_path)
