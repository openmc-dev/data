#!/usr/bin/env python3

import glob
import os
from argparse import ArgumentParser
from pathlib import Path
from zipfile import ZipFile
from collections import defaultdict
from io import StringIO

try:
    import lxml.etree as ET
    _have_lxml = True
except ImportError:
    import xml.etree.ElementTree as ET
    _have_lxml = False

import openmc.data
import openmc.deplete
from openmc.deplete.chain import REACTIONS, replace_missing_fpy
from openmc.deplete.nuclide import Nuclide, FissionYieldDistribution

from .casl_chain import CASL_CHAIN, UNMODIFIED_DECAY_BR
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
    default='chain_casl.xml',
    help="filename of the chain file xml file produced.",
)
args = parser.parse_args()


def replace_missing_decay_product(product, decay_data, all_decay_data):
    # Determine atomic number, mass number, and metastable state
    Z, A, state = openmc.data.zam(product)
    symbol = openmc.data.ATOMIC_SYMBOL[Z]

    # Iterate until we find an existing nuclide in the chain
    while product not in decay_data:
        # If product has no decay data in the library, nothing further can be done
        if product not in all_decay_data:
            product = None
            break

        # If the current product is not in the chain but is stable, there's
        # nothing further we can do. Also, we only want to continue down the
        # decay chain if the half-life is short, so we also make a cutoff here
        # to terminate if the half-life is more than 1 day.
        decay_obj = all_decay_data[product]
        if decay_obj.nuclide['stable'] or decay_obj.half_life.n > 24*60*60:
            product = None
            break

        dominant_mode = max(decay_obj.modes, key=lambda x: x.branching_ratio)
        product = dominant_mode.daughter

    return product


def main():
    if os.path.isdir('./decay') and os.path.isdir('./nfy') and os.path.isdir('./neutrons'):
        endf_dir = '.'
    elif 'OPENMC_ENDF_DATA' in os.environ:
        endf_dir = os.environ['OPENMC_ENDF_DATA']
    else:
        for url in URLS:
            basename = download(url)
            with ZipFile(basename, 'r') as zf:
                print('Extracting {}...'.format(basename))
                zf.extractall()
        endf_dir = '.'

    decay_files = glob.glob(os.path.join(endf_dir, 'decay', '*.endf'))
    fpy_files = glob.glob(os.path.join(endf_dir, 'nfy', '*.endf'))
    neutron_files = glob.glob(os.path.join(endf_dir, 'neutrons', '*.endf'))

    # Create a Chain
    chain = openmc.deplete.Chain()

    print('Reading ENDF nuclear data from "{}"...'.format(os.path.abspath(endf_dir)))

    # Create dictionary mapping target to filename
    print('Processing neutron sub-library files...')
    reactions = {}
    for f in neutron_files:
        evaluation = openmc.data.endf.Evaluation(f)
        nuc_name = evaluation.gnd_name
        if nuc_name in CASL_CHAIN:
            reactions[nuc_name] = {}
            for mf, mt, nc, mod in evaluation.reaction_list:
                # Q value for each reaction is given in MF=3
                if mf == 3:
                    file_obj = StringIO(evaluation.section[3, mt])
                    openmc.data.endf.get_head_record(file_obj)
                    q_value = openmc.data.endf.get_cont_record(file_obj)[1]
                    reactions[nuc_name][mt] = q_value

    # Determine what decay and FPY nuclides are available
    print('Processing decay sub-library files...')
    decay_data = {}
    all_decay_data = {}
    for f in decay_files:
        decay_obj = openmc.data.Decay(f)
        nuc_name = decay_obj.nuclide['name']
        all_decay_data[nuc_name] = decay_obj
        if nuc_name in CASL_CHAIN:
            decay_data[nuc_name] = decay_obj

    for nuc_name in CASL_CHAIN:
        if nuc_name not in decay_data:
            print('WARNING: {} has no decay data!'.format(nuc_name))

    print('Processing fission product yield sub-library files...')
    fpy_data = {}
    for f in fpy_files:
        fpy_obj = openmc.data.FissionProductYields(f)
        name = fpy_obj.nuclide['name']
        if name in CASL_CHAIN:
            fpy_data[name] = fpy_obj

    print('Creating depletion_chain...')
    missing_daughter = []
    missing_rx_product = []
    missing_fpy = []

    for idx, parent in enumerate(sorted(decay_data, key=openmc.data.zam)):
        data = decay_data[parent]

        nuclide = Nuclide(parent)

        chain.nuclides.append(nuclide)
        chain.nuclide_dict[parent] = idx

        if not CASL_CHAIN[parent][0] and \
           not data.nuclide['stable'] and data.half_life.nominal_value != 0.0:
            nuclide.half_life = data.half_life.nominal_value
            nuclide.decay_energy = data.decay_energy.nominal_value
            sum_br = 0.0
            for mode in data.modes:
                decay_type = ','.join(mode.modes)
                if mode.daughter in decay_data:
                    target = mode.daughter
                else:
                    missing_daughter.append((parent, mode))
                    continue

                # Append decay mode
                br = mode.branching_ratio.nominal_value
                nuclide.add_decay_mode(decay_type, target, br)

            # Ensure sum of branching ratios is unity by slightly modifying last
            # value if necessary
            sum_br = sum(m.branching_ratio for m in nuclide.decay_modes)
            if sum_br != 1.0 and nuclide.decay_modes and parent not in UNMODIFIED_DECAY_BR:
                decay_type, target, br = nuclide.decay_modes.pop()
                br = 1.0 - sum(m.branching_ratio for m in nuclide.decay_modes)
                nuclide.add_decay_mode(decay_type, target, br)

        # If nuclide has incident neutron data, we need to list what
        # transmutation reactions are possible
        fissionable = False
        transmutation_reactions = ('(n,2n)', '(n,3n)', '(n,4n)', '(n,gamma)',
                                   '(n,p)', '(n,a)')
        if parent in reactions:
            reactions_available = reactions[parent].keys()
            for name in transmutation_reactions:
                mts, changes, _ = REACTIONS[name]
                if mts & reactions_available:
                    delta_A, delta_Z = changes
                    A = data.nuclide['mass_number'] + delta_A
                    Z = data.nuclide['atomic_number'] + delta_Z
                    daughter = '{}{}'.format(openmc.data.ATOMIC_SYMBOL[Z], A)

                    if daughter not in decay_data:
                        daughter = replace_missing_decay_product(
                            daughter, decay_data, all_decay_data)
                        if daughter is None:
                            missing_rx_product.append((parent, name, daughter))

                    # Store Q value -- use sorted order so we get summation
                    # reactions (e.g., MT=103) first
                    for mt in sorted(mts):
                        if mt in reactions[parent]:
                            q_value = reactions[parent][mt]
                            break
                    else:
                        q_value = 0.0

                    nuclide.add_reaction(name, daughter, q_value, 1.0)

            # Check for fission reactions
            if any(mt in reactions_available for mt in [18, 19, 20, 21, 38]):
                q_value = reactions[parent][18]
                nuclide.add_reaction('fission', None, q_value, 1.0)
                fissionable = True

        if fissionable:
            if parent in fpy_data:
                fpy = fpy_data[parent]
            else:
                nuclide._fpy = replace_missing_fpy(parent, fpy_data, decay_data)
                missing_fpy.append((parent, nuclide._fpy))
                continue

            if fpy.energies is not None:
                yield_energies = fpy.energies
            else:
                yield_energies = [0.0]

            yield_data = {}
            for E, table_yd, table_yc in zip(yield_energies, fpy.independent, fpy.cumulative):
                yields = defaultdict(float)
                for product in table_yd:
                    if product in decay_data:
                        # identifier
                        ifpy = CASL_CHAIN[product][2]
                        # 1 for independent
                        if ifpy == 1:
                            if product not in table_yd:
                                print('No independent fission yields found for {} in {}'.format(product, parent))
                            else:
                                yields[product] += table_yd[product].nominal_value
                        # 2 for cumulative
                        elif ifpy == 2:
                            if product not in table_yc:
                                print('No cumulative fission yields found for {} in {}'.format(product, parent))
                            else:
                                yields[product] += table_yc[product].nominal_value
                        # 3 for special treatment with weight fractions
                        elif ifpy == 3:
                            for name_i, weight_i, ifpy_i in CASL_CHAIN[product][3]:
                                if name_i not in table_yd:
                                    print('No fission yields found for {} in {}'.format(name_i, parent))
                                else:
                                    if ifpy_i == 1:
                                        yields[product] += weight_i * table_yd[name_i].nominal_value
                                    elif ifpy_i == 2:
                                        yields[product] += weight_i * table_yc[name_i].nominal_value

                yield_data[E] = yields

            nuclide.yield_data = FissionYieldDistribution(yield_data)

    # Replace missing FPY data
    for nuclide in chain.nuclides:
        if hasattr(nuclide, '_fpy'):
            nuclide.yield_data = chain[nuclide._fpy].yield_data

    # Display warnings
    if missing_daughter:
        print('The following decay modes have daughters with no decay data:')
        for parent, mode in missing_daughter:
            print('  {} -> {} ({})'.format(parent, mode.daughter, ','.join(mode.modes)))
        print('')

    if missing_rx_product:
        print('The following reaction products have no decay data:')
        for vals in missing_rx_product:
            print('{} {} -> {}'.format(*vals))
        print('')

    if missing_fpy:
        print('The following fissionable nuclides have no fission product yields:')
        for parent, replacement in missing_fpy:
            print('  {}, replaced with {}'.format(parent, replacement))
        print('')

    chain.export_to_xml(args.destination)


if __name__ == '__main__':
    main()
