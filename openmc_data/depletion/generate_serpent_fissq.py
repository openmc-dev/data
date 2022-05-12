#!/usr/bin/env python3

"""
Determine Q values equivalent to the defaults in Serpent
"""

from argparse import ArgumentParser
from pathlib import Path
import json

import openmc.data

# Get command line argument
parser = ArgumentParser()
parser.add_argument('dir', type=Path, help='Directory containing ENDF neutron sublibrary files')
parser.add_argument(
    "-d",
    "--destination",
    type=Path,
    default='serpent_fissq.json',
    help="filename of the heating values file produced",
)
args = parser.parse_args()


def main():

    # Get Q value for U235
    u235 = openmc.data.IncidentNeutron.from_endf(args.dir / 'n-092_U_235.endf')
    q_u235 = u235[18].q_value

    # Fixed heating value from Serpent
    # See http://serpent.vtt.fi/mediawiki/index.php/Input_syntax_manual#set_fissh
    heat_u235 = 202.27e6

    # Get Q values for all fissionable nuclides and scale by the ratio of the U235 Q
    # value and heating value
    serpent_fission_q = {}
    for path in args.dir.glob('*.endf'):
        nuc = openmc.data.IncidentNeutron.from_endf(path)
        if nuc.fission_energy is None:
            continue
        q = nuc[18].q_value
        serpent_fission_q[nuc.name] = heat_u235 * q / q_u235

    # Write heating values to JSON file
    with open(args.destination, 'w') as f:
        json.dump(serpent_fission_q, f, indent=2)
