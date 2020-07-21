import argparse
import json

import openmc.deplete

parser = argparse.ArgumentParser()
parser.add_argument('chain_in')
parser.add_argument('branching_ratios')
parser.add_argument('chain_out')
args = parser.parse_args()

# Load existing chain
chain = openmc.deplete.Chain.from_xml(args.chain_in)

# Set branching ratios
with open(args.branching_ratios) as fh:
    br = json.load(fh)
chain.set_branch_ratios(br, strict=False)

# Export to new XML file
chain.export_to_xml(args.chain_out)
