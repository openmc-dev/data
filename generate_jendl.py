#!/usr/bin/env python3

"""
Download JENDL 4.0 or JENDL-5 ENDF data from JAEA and convert it to a HDF5 library for
use with OpenMC.
"""

import argparse
import ssl
import tarfile
import gzip
from multiprocessing import Pool
from pathlib import Path
from shutil import rmtree, copyfileobj
from urllib.parse import urljoin

import openmc.data
from utils import download, process_neutron


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=None,
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download files from JAEA')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download files from JAEA')
parser.add_argument('--extract', action='store_true',
                    help='Extract tar/zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract tar/zip files')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='latest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['4.0', '5.0'], default='5.0',
                    help="The nuclear data library release version. "
                    "The currently supported options are 4.0, 5.0")
parser.add_argument('--cleanup', action='store_true',
                    help="Remove download directories when data has "
                    "been processed")
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                    help="Do not remove download directories when data has "
                    "been processed")
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()


library_name = 'jendl'

cwd = Path.cwd()

endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))
download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))
# the destination is decided after the release is known
# to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release.
# This can be exstened to accommodated new releases
release_details = {
    '4.0': {
        'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/ftp/JENDL/',
        'compressed_files': ['jendl40-or-up_20160106.tar.gz'],
        'endf_files': endf_files_dir.joinpath('jendl40-or-up_20160106').glob('*.dat'),
        'metastables': endf_files_dir.joinpath('jendl40-or-up_20160106').glob('*m.dat'),
        'compressed_file_size': '0.2 GB',
        'uncompressed_file_size': '2 GB'
    },
    '5.0':{
        'base_url': 'https://wwwndc.jaea.go.jp/ftpnd/',
        'compressed_files': ['ftp/JENDL/jendl5-n.tar.gz',
                             'jendl/jendl5-update/data/jendl5_upd6.tar.gz',
                             'jendl/jendl5-update/data/n_059-Pr-141.dat.gz'],
        'endf_files': endf_files_dir.glob('*.dat'),
        'metastables': endf_files_dir.glob('*m1.dat'),
        'compressed_file_size': '4.1 GB',
        'uncompressed_file_size': '16 GB'
    }
}

download_warning = """
WARNING: This script will download {} of data.
Extracting and processing the data requires {} of additional free disk space.
""".format(release_details[args.release]['compressed_file_size'],
           release_details[args.release]['uncompressed_file_size'])

# ==============================================================================
# DOWNLOAD FILES FROM WEBSITE

if args.download:
    print(download_warning)
    for f in release_details[args.release]['compressed_files']:
        # Establish connection to URL
        download(urljoin(release_details[args.release]['base_url'], f),
                 context=ssl._create_unverified_context(),
                 output_path=download_path)

# ==============================================================================
# EXTRACT FILES FROM TGZ
if args.extract:
    for f in release_details[args.release]['compressed_files']:
        fname = Path(f).parts[-1]
        if fname.endswith('.tar.gz'):
            with tarfile.open(download_path / fname, 'r') as tgz:
                print('Extracting {}...'.format(fname))
                # extract files ignoring internal folder structure
                for member in tgz.getmembers():
                    if member.isreg():
                        member.name = Path(member.name).name
                        tgz.extract(member, path=endf_files_dir)

        else:
            # get the file name
            filename = Path(download_path / fname)
            source = gzip.open(filename)
            target = open(endf_files_dir / filename.name.rsplit('.', 1)[0], 'wb')
            with source, target:
                copyfileobj(source, target)

    if args.cleanup and download_path.exists():
        rmtree(download_path)

# ==============================================================================
# GENERATE HDF5 LIBRARY -- NEUTRON FILES

# Get a list of all ENDF files
neutron_files = release_details[args.release]['endf_files']

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()


with Pool() as pool:
    results = []
    for filename in sorted(neutron_files):
        func_args = (filename, args.destination, args.libver)
        r = pool.apply_async(process_neutron, func_args)
        results.append(r)

    for r in results:
        r.wait()

# Register with library
for p in sorted((args.destination).glob('*.h5')):
    library.register_file(p)

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')
