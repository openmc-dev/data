import argparse
from pathlib import Path
import openmc.deplete


parser = argparse.ArgumentParser()
parser.add_argument('chain_in', type=Path)
parser.add_argument('chain_out', type=Path)
args = parser.parse_args()


def main():

    chain_full = openmc.deplete.Chain.from_xml(args.chain_in)
    stable = [
        nuc.name
        for nuc in chain_full.nuclides
        if nuc.half_life is None or nuc.half_life > 1e15
    ]

    chain_reduced = chain_full.reduce(stable)
    chain_reduced.export_to_xml(args.chain_out)
