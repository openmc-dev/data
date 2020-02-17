#!/usr/bin/env python3

import argparse
from pathlib import Path
import ssl
import subprocess
import sys
import zipfile
from urllib.parse import urljoin
from textwrap import dedent
from os import chdir

import openmc.data
from openmc._utils import download

description = """
Download FENDL 3.1d or FENDL 3.1c ACE data from the IAEA and convert it to a HDF5 library for
use with OpenMC.

"""


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=None,
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download files from IAEA-NDS')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download files from IAEA-NDS')
parser.add_argument('--extract', action='store_true',
                    help='Extract tar/zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract tar/zip files')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['3.1a', '3.1d', '3.0', '2.1'],
                    default='3.1d', help="The nuclear data library release version. "
                    "The currently supported options are 3.1d, 3.1a, 3.0 and "
                    "2.1")
parser.set_defaults(download=True, extract=True)
args = parser.parse_args()


# this could be added as an argument to allow different libraries to be downloaded
library_name = 'fendl'
cwd = Path.cwd()  

ace_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'ace']))
zip_path = cwd.joinpath('-'.join([library_name, args.release, 'zips']))
# the destination is decided after the release is know to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '3.1a': {
        'base_url': 'https://www-nds.iaea.org/fendl31/data/neutron/',
        'files': ['fendl31a-neutron-ace.zip'],
        'neutron_files': ace_files_dir.glob('*'),
        'compressed_file_size': '0.4 GB',
        'uncompressed_file_size': '3 GB'
    },
    '3.1d': {
        'base_url': 'https://www-nds.iaea.org/fendl/data/neutron/',
        'files': ['fendl31d-neutron-ace.zip'],
        'neutron_files': ace_files_dir.joinpath('fendl31d_ACE').glob('*'),
        'compressed_file_size': '0.5 GB',
        'uncompressed_file_size': '3 GB'
    },
    '3.0': {
        'base_url': 'https://www-nds.iaea.org/fendl30/data/neutron/',
        'files': ['fendl30-neutron-ace.zip'],
        'neutron_files': ace_files_dir.joinpath('ace').glob('*.ace'),
        'compressed_file_size': '0.4 GB',
        'uncompressed_file_size': '2.2 GB'
    },
    '2.1': {
        'base_url': 'https://www-nds.iaea.org/fendl21/fendl21mc/',
        'files': ['H001mc.zip',  'H002mc.zip',  'H003mc.zip',  'He003mc.zip', 
                  'He004mc.zip', 'Li006mc.zip', 'Li007mc.zip', 'Be009mc.zip',
                  'B010mc.zip',  'B011mc.zip',  'C012mc.zip',  'N014mc.zip', 
                  'N015mc.zip',  'O016mc.zip',  'F019mc.zip',  'Na023mc.zip',
                  'Mg000mc.zip', 'Al027mc.zip', 'Si028mc.zip', 'Si029mc.zip',
                  'Si030mc.zip', 'P031mc.zip',  'S000mc.zip',  'Cl035mc.zip', 
                  'Cl037mc.zip', 'K000mc.zip',  'Ca000mc.zip', 'Ti046mc.zip', 
                  'Ti047mc.zip', 'Ti048mc.zip', 'Ti049mc.zip', 'Ti050mc.zip', 
                  'V000mc.zip',  'Cr050mc.zip', 'Cr052mc.zip', 'Cr053mc.zip', 
                  'Cr054mc.zip', 'Mn055mc.zip', 'Fe054mc.zip', 'Fe056mc.zip', 
                  'Fe057mc.zip', 'Fe058mc.zip', 'Co059mc.zip', 'Ni058mc.zip', 
                  'Ni060mc.zip', 'Ni061mc.zip', 'Ni062mc.zip', 'Ni064mc.zip', 
                  'Cu063mc.zip', 'Cu065mc.zip', 'Ga000mc.zip', 'Zr000mc.zip', 
                  'Nb093mc.zip', 'Mo092mc.zip', 'Mo094mc.zip', 'Mo095mc.zip', 
                  'Mo096mc.zip', 'Mo097mc.zip', 'Mo098mc.zip', 'Mo100mc.zip', 
                  'Sn000mc.zip', 'Ta181mc.zip', 'W182mc.zip',  'W183mc.zip',  
                  'W184mc.zip',  'W186mc.zip',  'Au197mc.zip', 'Pb206mc.zip', 
                  'Pb207mc.zip', 'Pb208mc.zip', 'Bi209mc.zip'],
        'neutron_files': ace_files_dir.glob('*.ace'),
        'compressed_file_size': '0.4 GB',
        'uncompressed_file_size': '2.2 GB'
    }
}

download_warning = """
WARNING: This script will download {} of data.
Extracting and processing the data requires {} of additional free disk space.
""".format(release_details[args.release]['compressed_file_size'],
           release_details[args.release]['uncompressed_file_size'])

# ==============================================================================
# DOWNLOAD FILES FROM IAEA SITE

if args.download:
    print(download_warning)

    if args.release == '2.1':
        # Older releases have ace files in individual zip files. Create a 
        # a directory to hold them.
        zip_path.mkdir(exist_ok=True) 
        chdir(zip_path)

    for f in release_details[args.release]['files']:
        download(urljoin(release_details[args.release]['base_url'], f),
                    as_browser=True, context=ssl._create_unverified_context())
    chdir(cwd)

# ==============================================================================
# EXTRACT FILES FROM TGZ
if args.extract:
    if args.release == '2.1':
        chdir(zip_path)

    for f in release_details[args.release]['files']:
        # Extract files, the fendl release was compressed using type 9 zip format
        # unfortunatly which is incompatible with the standard python zipfile library
        # therefore the following system command is used

        subprocess.call(['unzip', '-o', f, '-d', ace_files_dir])
    chdir(cwd)

# ==============================================================================
# GENERATE HDF5 LIBRARY -- NEUTRON FILES

# Get a list of all ACE files, excluding files ending with _ which are old incorrect files kept in the release for backwards compatability
neutron_files = [
    f
    for f in release_details[args.release]['neutron_files']
    if not f.name.endswith('_') and not f.name.endswith('.xsd')
]

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

warn_k39 = False 

for filename in sorted(neutron_files):

    # Check for Inf values in K-39 ace file for FENDL-3.0
    if args.release == '3.0' and filename.name == '19K_039.ace':
        # Check for the error in case user has provided a fixed version.
        if 'Inf' in open(filename, 'r').read():
            ace_error_warning = """
            WARNING: {} contains 'Inf' values within the XSS array which 
            prevent conversion to a hdf5 file format. This is a known issue
            in FENDL-3.0. {} has not been added to the cross section library 
            """.format(filename, filename.name)
            ace_error_warning = dedent(ace_error_warning)
            warn_k39 = True
            continue
    
    print(f'Converting: {filename}')
    data = openmc.data.IncidentNeutron.from_ace(filename)

    # Export HDF5 file
    h5_file = args.destination / f'{data.name}.h5'
    print('Writing {}...'.format(h5_file))
    data.export_to_hdf5(h5_file, 'w', libver=args.libver)

    # Register with library
    library.register_file(h5_file)

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')

if warn_k39:
    print(ace_error_warning)

