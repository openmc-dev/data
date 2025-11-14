#!/usr/bin/env python3

import argparse
import ssl
from pathlib import Path
from urllib.parse import urljoin

from openmc.deplete import Chain

from utils import download, extract

URLS = {
    'neutron': {
        'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/ftp/JENDL/',
        'compressed_files': [
            'jendl5-n.tar.gz',
            'jendl5-n_upd1.tar.gz',
            'jendl5-n_upd6.tar.gz',
            'jendl5-n_upd7.tar.gz',
            'jendl5-n_upd10.tar.gz',
            'jendl5-n_upd11.tar.gz',
            'jendl5-n_upd12.tar.gz',
            'jendl5-n_upd14.tar.gz',
        ],
        'endf_files': 'jendl5-n/*.dat',
        'errata': ['jendl5-n_upd1/*.dat', 'jendl-n_upd6/*.dat', '*.dat'],
    },
    'decay': {
        'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/ftp/JENDL/',
        'compressed_files': [
            'jendl5-dec_upd5.tar.gz',
            'jendl5-dec_upd15.tar.gz',
        ],
        'endf_files': 'jendl5-dec_upd5/*.dat',
        'errata': ['jendl5-dec_upd15/*.dat'],
    },
    'nfy': {
        'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/ftp/JENDL/',
        'compressed_files': ['jendl5-fpy_upd8.tar.gz'],
        'endf_files': 'jendl5-fpy_upd8/*.dat'
    }
}



# Parse command line arguments
parser = argparse.ArgumentParser(prog="generate_jeff_chain",
    description="Generates a OpenMC chain file from JENDL nuclear data files",
)
parser.add_argument('-r', '--release', choices=['5'],
                    default='5', help="The nuclear data library release "
                    "version. The only currently supported option is 5.")
parser.add_argument(
    "-d",
    "--destination",
    type=Path,
    default=None,
    help="filename of the chain file xml file produced. If left as None then "
    "the filename will follow this format 'chain_jendl_{release}.xml'",
)
parser.add_argument(
    "--neutron",
    type=Path,
    default=[],
    nargs="+",
    help="Path to neutron endf files, if not provided, neutron files will be downloaded.",
)
parser.add_argument(
    "--decay",
    type=Path,
    default=[],
    nargs="+",
    help="Path to decay data files, if not provided, decay files will be downloaded.",
)
parser.add_argument(
    "--nfy",
    type=Path,
    default=[],
    nargs="+",
    help="Path to neutron fission product yield files, if not provided, fission yield files will be downloaded.",
)
args = parser.parse_args()

def main():

    library_name = 'jendl'

    cwd = Path.cwd()

    # DOWNLOAD NEUTRON DATA
    endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))
    download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))
    neutron_files = args.neutron
    if not neutron_files:
        details = URLS['neutron']

        for f in details['compressed_files']:
            # Establish connection to URL
            downloaded_file = download(
                urljoin(details['base_url'], f),
                context=ssl._create_unverified_context(),
                output_path=download_path
            )

            extract(downloaded_file, extraction_dir=endf_files_dir)

        for erratum in details["errata"]:
            files = endf_files_dir.rglob(erratum)
            for p in files:
                p.rename((endf_files_dir / details["endf_files"]).parent / p.name)
        neutron_files = endf_files_dir.glob(details['endf_files'])

    decay_files = args.decay
    if not decay_files:
        details = URLS['decay']
        for file in details['compressed_files']:
            downloaded_file = download(
                url=urljoin(details['base_url'], file),
                output_path=download_path
            )

            extract(downloaded_file, extraction_dir=endf_files_dir)

        for erratum in details["errata"]:
            files = endf_files_dir.rglob(erratum)
            for p in files:
                p.rename((endf_files_dir / details["endf_files"]).parent / p.name)

        decay_files = list(endf_files_dir.rglob(details["endf_files"]))

    nfy_files = args.nfy
    if not nfy_files:
        details = URLS['nfy']
        for file in details['compressed_files']:
            downloaded_file = download(
                url=urljoin(details['base_url'], file),
                output_path=download_path
            )

            extract(downloaded_file, extraction_dir=endf_files_dir)
        nfy_files = list(endf_files_dir.rglob(details["endf_files"]))

    # check files exist
    for flist, ftype in [(decay_files, "decay"), (neutron_files, "neutron"),
                         (nfy_files, "neutron fission product yield")]:
        if not flist:
            raise FileNotFoundError(f"No {ftype} endf files found in {endf_files_dir}")

    chain = Chain.from_endf(decay_files, nfy_files, neutron_files)

    if args.destination is None:
        args.destination = f'chain_{library_name}{args.release}.xml'
    chain.export_to_xml(args.destination)
    print(f'Chain file written to {args.destination}')


if __name__ == '__main__':
    main()
