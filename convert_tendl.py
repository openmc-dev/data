#!/usr/bin/env python3

"""
Download TENDL 2017 or TENDL 2015 ACE data from PSI and convert it to a HDF5 library for
use with OpenMC.
"""

import argparse
import glob
import os
import sys
import tarfile
import pathlib
from pathlib import Path

import openmc.data
from openmc._utils import download


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
                    help='Download tarball from PSI')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download tarball from PSI')
parser.add_argument('--extract', action='store_true',
                    help='Extract compressed files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract compressed file if it has already been extracted')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='latest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-r', '--release', choices=['2015', '2017'],
                    default='2017', help="The nuclear data library release version. "
                    "The currently supported options are 2015 and 2017")
parser.add_argument('-p', '--particles', choices=['neutron', 'photon'], nargs='+',
                    default=['neutron', 'photon'], help="Incident particles to include")   
parser.set_defaults(download=True, extract=True)
args = parser.parse_args()



library_name = 'tendl' #this could be added as an argument to allow different libraries to be downloaded
ace_files_dir = Path('-'.join([library_name, args.release, 'ace']))

# the destination is decided after the release is know to avoid putting the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    '2015': 
        {
        'neutron':
            {
            'base_url': 'https://tendl.web.psi.ch/tendl_2015/tar_files/',
            'compressed_files': ['ACE-n.tgz'],
            # 'ace_files': ace_files_dir.rglob('neutron_file', '*', '*', 'lib', 'endf', '*-n.ace'),
            # 'metastables': ace_files_dir.rglob('neutron_file', '*', '*', 'lib', 'endf', '*m-n.ace'),
            'compressed_file_size': 50000,
            'uncompressed_file_size': 40000
            },
        'photon':
            {
            'base_url': 'https://tendl.web.psi.ch/tendl_2015/tar_files/',
            'compressed_files': ['ACE-g.tgz'],
            'compressed_file_size': 0,
            'uncompressed_file_size': 0
            },
        },
    '2017': 
        {
        'neutron':
            {
            'base_url': 'https://tendl.web.psi.ch/tendl_2017/tar_files/',
            'compressed_files': ['tendl17c.tar.bz2'],
            # 'ace_files': ace_files_dir.rglob('ace-17/*'),
            # 'metastables': ace_files_dir.rglob('ace-17/*m'),
            'compressed_file_size': 2100,
            'uncompressed_file_size': 14000
            },
        'photon':
            {
            'base_url': 'https://tendl.web.psi.ch/tendl_2017/tar_files/',
            'compressed_files': ['TENDL-283-g.tgz'],
            'compressed_file_size': 0,
            'uncompressed_file_size': 0
            }
        }
}

compressed_file_size, uncompressed_file_size = 0, 0
for p in args.particles: 
    compressed_file_size += release_details[args.release][p]['compressed_file_size']
    uncompressed_file_size += release_details[args.release][p]['uncompressed_file_size']

download_warning = """
WARNING: This script will download up to {} MB of data. Extracting and
processing the data may require as much as {} MB of additional free disk
space.
""".format(compressed_file_size, uncompressed_file_size)


# ==============================================================================
# DOWNLOAD FILES FROM WEBSITE

if args.download:
    for particle in args.particles:
        print(download_warning)
        for f in release_details[args.release][particle]['compressed_files']:
            # Establish connection to URL
            url = release_details[args.release][particle]['base_url'] + f
            downloaded_file = download(url)

# ==============================================================================
# EXTRACT FILES FROM TGZ

if args.extract:
    for particle in args.particles:
        for f in release_details[args.release][particle]['compressed_files']:
            for f in release_details[args.release]['compressed_files']:
                # Extract files
                with tarfile.open(f, 'r') as tgz:
                    print('Extracting {}...'.format(f))
                    tgz.extractall(path = ace_files_dir)

input()

# ==============================================================================
# CHANGE ZAID FOR METASTABLES

metastables = glob.glob(release_details[args.release]['metastables'])
for path in metastables:
    print('    Fixing {} (ensure metastable)...'.format(path))
    text = open(path, 'r').read()
    mass_first_digit = int(text[3])
    if mass_first_digit <= 2:
        text = text[:3] + str(mass_first_digit + 4) + text[4:]
        open(path, 'w').write(text)

# ==============================================================================
# GENERATE HDF5 LIBRARY -- NEUTRON FILES

# Create output directory if it doesn't exist
args.destination.mkdir(parents=True, exist_ok=True)

library = openmc.data.DataLibrary()

for particle in args.particles: 
    if particle == 'neutron':
        for filename in sorted(release_details[release][particle]['ace_files']):
        
            # this is a fix for the TENDL-2017 release where the B10 ACE file which has an error on one of the values
            if library_name == 'tendl' and args.release == '2017' and os.path.basename(filename) == 'B010':
                text = open(filename, 'r').read()
                if text[423:428] == '86843':
                    print('Manual fix for incorrect value in ACE file') # see OpenMC user group issue for more details
                    text = ''.join(text[:423])+'86896'+''.join(text[428:])
                    open(filename, 'w').write(text)

            print('Converting: ' + filename)
            data = openmc.data.IncidentNeutron.from_ace(filename)

            # Export HDF5 file
            h5_file = args.destination.joinpath(data.name + '.h5')
            print('Writing {}...'.format(h5_file))
            data.export_to_hdf5(h5_file, 'w', libver=args.libver)

            # Register with library
            library.register_file(h5_file)

    elif particle == 'photon':
        for photo_file, atom_file in zip(sorted(release_details[release][particle]['photo_file']),
                                         sorted(release_details[release][particle]['atom_file'])):
    
            print('Converting: ' , photo_file, atom_file)
            
            # Generate instance of IncidentPhoton
            data = openmc.data.IncidentPhoton.from_endf(photo_file, atom_file)

            # Export HDF5 file
            h5_file = args.destination.joinpath(data.name + '.h5')
            data.export_to_hdf5(h5_file, 'w', libver=args.libver)

            # Register with library
            library.register_file(h5_file)

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')

