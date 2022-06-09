#!/usr/bin/env python3

"""
Generate a depletion chain based on TENDL 2019 data. Note that TENDL 2019 does
not contain any decay or fission product yield (FPY) sublibraries, so these must
be borrowed from another library. The --lib flag for this script indicates what
library should be used for decay and FPY evaluations and defaults to JEFF 3.3.
"""

import json
import tarfile
from argparse import ArgumentParser
from pathlib import Path
from urllib.parse import urljoin
from zipfile import ZipFile
import openmc_data

import openmc.data
import openmc.deplete as dep

from openmc_data.utils import download, extract

# Parse command line arguments
parser = ArgumentParser()
parser.add_argument('--lib', choices=('jeff33', 'endf80'), default='jeff33',
                    help='Library to use for decay and fission product yields')
parser.add_argument('-r', '--release', choices=['2019', '2021'],
                    default='2021', help="The nuclear data library release "
                    "version. The currently supported options are 2019, "
                    "and 2021.")
parser.add_argument(
    "-d",
    "--destination",
    type=Path,
    default=None,
    help="filename of the chain file xml file produced. If left as None then "
    "the filename will follow this format 'chain_tendl_{release}_{lib}.xml'",
)
args = parser.parse_args()


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

    library_name = 'tendl'

    cwd = Path.cwd()

    endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))
    download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))

    neutron_dir = endf_files_dir / "neutrons"
    decay_dir = endf_files_dir / "decay"
    nfy_dir = endf_files_dir / "nfy"

    # This dictionary contains all the unique information about each release.
    # This can be extended to accommodated new releases
    release_details = {
        '2019': {
            'base_url': 'https://tendl.web.psi.ch/tendl_2019/tar_files/',
            'compressed_files': ['TENDL-n.tgz'],
            'transport_nuclides': 'depletion/tendl2019_nuclides.json',
            'neutron_files': endf_files_dir.glob('tendl19c/*'),
        },
        '2021': {
            'base_url': 'https://tendl.web.psi.ch/tendl_2021/tar_files/',
            'compressed_files': ['TENDL-n.tgz'],
            'transport_nuclides': 'depletion/tendl2021_nuclides.json',
            'neutron_files': endf_files_dir.glob('tendl21c/*'),
        }
    }

    DECAY_LIB = {
        'jeff33': 'https://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/JEFF33-rdd.zip',
        'endf80': 'https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_decay.zip',
    }
    NFY_LIB = {
        'jeff33': 'https://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/JEFF33-nfy.asc',
        'endf80': 'https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_nfy.zip',
    }


    # ==========================================================================
    # Incident neutron data
    for f in release_details[args.release]['compressed_files']:
        downloaded_file = download(
            url=urljoin(release_details[args.release]['base_url'], f),
            output_path=download_path
        )

        extract(downloaded_file, neutron_dir)

    # Get list of transport nuclides in TENDL-2019
    with open(Path(openmc_data.__path__[0])/release_details[args.release]['transport_nuclides'], 'r') as fh:
        transport_nuclides = set(json.load(fh))

    neutron_files = [
        p
        for p in release_details[args.release]['neutron_files']
        if p.name[2:-6] in transport_nuclides  # filename is n-XXNNN.tendl
    ]

    # ==========================================================================
    # Decay and fission product yield data

    decay_zip = download(DECAY_LIB[args.lib], output_path=download_path)
    nfy_file = download(NFY_LIB[args.lib], output_path=download_path)

    extract(decay_zip, decay_dir)
    if args.lib == 'jeff33':
        decay_files = list(decay_dir.glob('*.ASC'))

        nfy_file_fixed = fix_jeff33_nfy(nfy_file)
        nfy_files = openmc.data.endf.get_evaluations(nfy_file_fixed)

    elif args.lib == 'endf80':
        decay_files = list(decay_dir.rglob('*.endf'))

        extract(nfy_file, nfy_dir)
        nfy_files = list(nfy_dir.rglob('*.endf'))

    chain = dep.Chain.from_endf(
        decay_files, nfy_files, neutron_files,
        reactions=dep.chain.REACTIONS.keys()
    )

    if args.destination is None:
        args.destination=f'chain_{library_name}_{args.release}_{args.lib}.xml'

    chain.export_to_xml(args.destination)
    print(f'Chain file written to {args.destination}')


if __name__ == "__main__":
    main()
