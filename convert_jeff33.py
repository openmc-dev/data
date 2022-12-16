#!/usr/bin/env python

"""
Convert JEFF 3.3 ACE data distributed by OECD/NEA into an HDF5 library that can
be used by OpenMC. It will download archives containing all the ACE files,
extract them, convert them, and write HDF5 files into a destination directory.
"""

import argparse
import tarfile
import sys
import os
from pathlib import Path
from shutil import rmtree
from urllib.parse import urljoin

import openmc.data

from utils import download


# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=Path('jeff-3.3-hdf5'),
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download tarball from OECD-NEA')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download tarball from OECD-NEA')
parser.add_argument('--extract', action='store_true',
                    help='Extract zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract .tgz file if it has already been extracted')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['3.3'],
                    default='3.3', help="The nuclear data library release version. "
                    "The only currently supported option is 3.3.")
parser.add_argument('--cleanup', action='store_true',
                    help="Remove download directories when data has "
                    "been processed")
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                    help="Do not remove download directories when data has "
                    "been processed")
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()

library_name = 'jeff'

cwd = Path.cwd()

ace_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'ace']))
download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))

# This dictionary contains all the unique information about each release. This
# can be extended to accommodate new releases
release_details = {
    '3.3': {
        'base_url': 'http://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/temperatures/',
        'compressed_files': [
            'ace_293.tar.gz',
            'ace_600.tar.gz',
            'ace_900.tar.gz',
            'ace_1200.tar.gz',
            'ace_1500.tar.gz',
            'ace_1800.tar.gz',
            'ace_tsl.tar.gz',
        ],
        'neutron_files': ace_files_dir.rglob('*-[A-Z]*.ace'),
        'thermal_files': (ace_files_dir / 'ace_tsl').glob('*.ace'),
        'metastables': ace_files_dir.rglob('*[0-9]m-*.ace'),
        'compressed_file_size': '7.7 GB',
        'uncompressed_file_size': '37 GB'
    }
}

details = release_details[args.release]

# ==============================================================================
# DOWNLOAD FILES FROM WEBSITE

download_warning = """
WARNING: This script will download {} of data.
Extracting and processing the data requires {} of additional free disk space.
""".format(details['compressed_file_size'], details['uncompressed_file_size'])

if args.download:
    print(download_warning)
    for f in details['compressed_files']:
        download(urljoin(details['base_url'], f), output_path=download_path)

# ==============================================================================
# EXTRACT FILES FROM TGZ

if args.extract:
    for f in details['compressed_files']:
        with tarfile.open(download_path / f, 'r') as tgz:
            print(f'Extracting {f}...')
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(tgz, path=ace_files_dir)

    if args.cleanup and download_path.exists():
        rmtree(download_path)

# ==============================================================================
# CONVERT INCIDENT NEUTRON FILES

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

lib = openmc.data.DataLibrary()


def key(p):
    """Return (temperature, atomic number, mass number, metastable)"""
    z, x, a, temp = p.stem.split('-')
    return int(temp), int(z), int(a[:-1]), a[-1]


for p in sorted((ace_files_dir / 'ace_293').glob('*.ace'), key=key):
    print(f'Converting: {p}')
    temp, z, a, m = key(p)

    data = openmc.data.IncidentNeutron.from_ace(p)
    if m == 'm' and not data.name.endswith('_m1'):
        # Correct metastable
        data.metastable = 1
        data.name += '_m1'

    for T in ('600', '900', '1200', '1500', '1800'):
        p_add = ace_files_dir / f'ace_{T}' / (p.stem.replace('293', T) + '.ace')
        print(f'Adding temperature: {p_add}')
        data.add_temperature_from_ace(p_add)

    h5_file = args.destination / f'{data.name}.h5'
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)
    lib.register_file(h5_file)

# ==============================================================================
# CONVERT THERMAL SCATTERING FILES

thermal_mats = [
    'al-sap',
    'be',
    'ca-cah2',
    'd-d2o',
    'graph',
    'h-cah2',
    'h-ch2',
    'h-h2o',
    'h-ice',
    'h-zrh',
    'mesi',
    'mg',
    'o-d2o',
    'orto-d',
    'orto-h',
    'o-sap',
    'para-d',
    'para-h',
    'sili',
    'tolu',
]


def thermal_temp(p):
    return int(p.stem.split('-')[-1])


thermal_dir = ace_files_dir / 'ace_tsl'

for mat in thermal_mats:
    for i, p in enumerate(sorted(thermal_dir.glob(f'{mat}*.ace'), key=thermal_temp)):
        if i == 0:
            print(f'Converting: {p}')
            data = openmc.data.ThermalScattering.from_ace(p)
        else:
            print(f'Adding temperature: {p}')
            data.add_temperature_from_ace(p)

    h5_file = args.destination / f'{data.name}.h5'
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)
    lib.register_file(h5_file)

lib.export_to_xml(args.destination / 'cross_sections.xml')
