#!/usr/bin/env python3

import os
from argparse import ArgumentParser
from pathlib import Path
from urllib.parse import urljoin

import openmc.deplete

from openmc_data.utils import download, extract



# Parse command line arguments
parser = ArgumentParser()
parser.add_argument('-r', '--release', choices=['vii.1', 'viii.0'],
                    default='viii.0', help="The nuclear data library release "
                    "version. The currently supported options are vii.1, "
                    "viii.0")
parser.add_argument(
    "-d",
    "--destination",
    type=Path,
    default=None,
    help="filename of the chain file xml file produced. If left as None then "
    "the filename will follow this format 'chain_endf_{release}.xml'",
)
args = parser.parse_args()


def main():

    library_name = 'endf'

    cwd = Path.cwd()

    endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))
    download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))

    neutron_dir = endf_files_dir / "neutrons"
    decay_dir = endf_files_dir / "decay"
    nfy_dir = endf_files_dir / "nfy"

    # This dictionary contains all the unique information about each release.
    # This can be extended to accommodated new releases
    release_details = {
        'vii.1': {
            'neutron': {
                'base_url': ['https://www.nndc.bnl.gov/endf-b7.1/zips/'],
                'compressed_files': ['ENDF-B-VII.1-neutrons.zip'],
            },
            'decay': {
                'base_url': ['https://www.nndc.bnl.gov/endf-b7.1/zips/'],
                'compressed_files': ['ENDF-B-VII.1-decay.zip']
            },
            'nfy':{
                'base_url': ['https://www.nndc.bnl.gov/endf-b7.1/zips/'],
                'compressed_files': ['ENDF-B-VII.1-nfy.zip']
            }
        },
        'viii.0': {
            'neutron': {
                'base_url': ['https://www.nndc.bnl.gov/endf-b8.0/zips/'],
                'compressed_files': ['ENDF-B-VIII.0_neutrons.zip'],
            },
            'decay': {
                'base_url': ['https://www.nndc.bnl.gov/endf-b8.0/zips/'],
                'compressed_files': ['ENDF-B-VIII.0_decay.zip']
            },
            'nfy':{
                'base_url': ['https://www.nndc.bnl.gov/endf-b8.0/zips/'],
                'compressed_files': ['ENDF-B-VIII.0_nfy.zip']
            }
        }
    }

    for file_type, extract_dir in zip(['neutron', 'decay', 'nfy'], [neutron_dir, decay_dir, nfy_dir]):
        details = release_details[args.release][file_type]
        for base_url, file in zip(details['base_url'], details['compressed_files']):
            downloaded_file = download(
                url=urljoin(base_url, file),
                output_path=download_path
            )

        extract(downloaded_file, extract_dir)

    neutron_files = list(neutron_dir.rglob("*endf"))
    decay_files = list(decay_dir.rglob("*endf"))
    nfy_files = list(nfy_dir.rglob("*endf"))

    if args.release == 'vii.1':
        # Remove erroneous Be7 evaluation from vii.1 that can cause problems
        decay_files.remove(decay_dir / "dec-004_Be_007.endf")
        neutron_files.remove(neutron_dir / "n-004_Be_007.endf")

    # check files exist
    for flist, ftype in [(decay_files, "decay"), (neutron_files, "neutron"),
                         (nfy_files, "neutron fission product yield")]:
        if not flist:
            raise IOError("No {} endf files found in {}".format(ftype, endf_files_dir))

    chain = openmc.deplete.Chain.from_endf(decay_files, nfy_files, neutron_files)

    if args.destination is None:
        args.destination=f'chain_{library_name}_{args.release}.xml'

    chain.export_to_xml(args.destination)
    print(f'Chain file written to {args.destination}')

if __name__ == '__main__':
    main()
