#!/usr/bin/env python3

import argparse
from pathlib import Path

from openmc.deplete import Chain
import openmc.data

from utils import download, extract, fix_missing_tpid

URLS = [
    'https://data.oecd-nea.org/records/e9ajn-a3p20/files/JEFF40-Evaluations-Neutron-593.zip?download=1',
    'https://data.oecd-nea.org/records/trtwt-k2828/files/nf_Fission_Yields_JEFF-40.txt?download=1',
    'https://data.oecd-nea.org/records/tw0c6-t1386/files/Radioactive_Decay_Data_JEFF-40.txt?download=1',
]


def main(chain_path, endf_path=None):
    decay_file = 'Radioactive_Decay_Data_JEFF-40.txt'
    nfy_file = 'nf_Fission_Yields_JEFF-40.txt'

    if endf_path is not None:
        endf_path = Path(endf_path)
    elif all(Path(lib).is_dir() for lib in ("neutrons", "decay", "nfy")):
        endf_path = Path(".")
    else:
        # Create directories for decay and nfy data
        Path('neutrons').mkdir(exist_ok=True)
        Path('decay').mkdir(exist_ok=True)
        Path('nfy').mkdir(exist_ok=True)

        # Download and extract zip files
        for url in URLS:
            basename = download(url)
            if basename.suffix == '.zip':
                extract(basename, extraction_dir='neutrons')

        # Rename extracted directories and move files into the appropriate directories
        Path(nfy_file).rename(Path('nfy') / nfy_file)
        Path(decay_file).rename(Path('decay') / decay_file)

        endf_path = Path.cwd()

    neutron_files = list((endf_path / "neutrons").glob("*.jeff"))
    decay_path = (endf_path / "decay") / decay_file
    nfy_path = (endf_path / "nfy") / nfy_file

    # Get evaluations from the single files; note that FPY file need TPID fix
    with fix_missing_tpid(nfy_path) as nfy_path_fixed:
        nfy_evals = openmc.data.endf.get_evaluations(nfy_path_fixed)
    decay_evals = openmc.data.endf.get_evaluations(decay_path)

    chain = Chain.from_endf(decay_evals, nfy_evals, neutron_files)
    chain.export_to_xml(chain_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--chain-path', default='chain_jeff40.xml')
    parser.add_argument('--endf-path', type=Path, default=None)
    args = parser.parse_args()

    main(args.chain_path, args.endf_path)
