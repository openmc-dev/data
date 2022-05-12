#!/usr/bin/env python

"""
Writes a depletion chain XML file from a depletion chain XML file and branching
ratios
"""

import argparse
import json

import openmc.deplete

class CustomFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    pass

parser = argparse.ArgumentParser(description=__doc__, formatter_class=CustomFormatter)
parser.add_argument('chain_in')
parser.add_argument('branching_ratios')
parser.add_argument('chain_out')
args = parser.parse_args()


def main():

    # Load existing chain
    chain = openmc.deplete.Chain.from_xml(args.chain_in)

    # Set branching ratios
    with open(args.branching_ratios) as fh:
        br = json.load(fh)
    chain.set_branch_ratios(br, strict=False)

    # Export to new XML file
    chain.export_to_xml(args.chain_out)


if __name__ == "__main__":
    main()
