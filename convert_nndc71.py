#!/usr/bin/env python

"""
Download ENDF/B-VII.1 incident neutron ACE data and incident photon ENDF data
from NNDC and convert it to an HDF5 library for use with OpenMC. This data is
used for OpenMC's regression test suite.
"""

import argparse
import glob
import hashlib
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from string import digits

import openmc.data
from openmc._utils import download

# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"

class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=CustomFormatter
)

parser.add_argument('-d', '--destination', type=Path, default='nndc-b7.1-hdf5',
                    help='Directory to create new library in')
parser.add_argument('--download', action='store_true',
                    help='Download tarball from NNDC-BNL')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download tarball from NNDC-BNL')
parser.add_argument('--extract', action='store_true',
                    help='Extract compressed files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract compressed file if it has already been extracted')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('-p', '--particles', choices=['neutron', 'photon'], nargs='+',
                    default=['neutron', 'photon'], help="Incident particles to include")   
parser.set_defaults(download=True, extract=True)
args = parser.parse_args()

library_name = 'nndc'
release = 'b7.1'
ace_files_dir = Path('-'.join([library_name, release, 'ace']))
endf_files_dir = Path('-'.join([library_name, release, 'endf']))

# This dictionary contains all the unique information about each release. This can be exstened to accommodated new releases
release_details = {
    'b7.1': 
        {
        'neutron': 
            {
            'base_url': 'http://www.nndc.bnl.gov/endf/b7.1/aceFiles/',
            'compressed_files': ['ENDF-B-VII.1-neutron-293.6K.tar.gz',
                                'ENDF-B-VII.1-tsl.tar.gz'],
            'checksums': ['9729a17eb62b75f285d8a7628ace1449',
                        'e17d827c92940a30f22f096d910ea186'],
            'file_type': 'ace',   
            'ace_files': ace_files_dir.rglob('[aA-zZ]*.ace'),
            'sab_files': ace_files_dir.rglob('*.acer'),
            'compressed_file_size': 497,
            'uncompressed_file_size': 0.1
            },
        'photon': 
            {
            'base_url': 'http://www.nndc.bnl.gov/endf/b7.1/zips/',
            'compressed_files': ['ENDF-B-VII.1-photoat.zip', 
                                 'ENDF-B-VII.1-atomic_relax.zip'],
            'file_type': 'endf',   
            'photo_file': endf_files_dir.joinpath('photoat').rglob('*.endf'),
            'atom_file': endf_files_dir.joinpath('atomic_relax').rglob('*.endf'),
            'compressed_file_size': 9,
            'uncompressed_file_size': 0.1
            }
        }
    
}


compressed_file_size, uncompressed_file_size = 0, 0
for p in ('neutron', 'photon'): 
    compressed_file_size += release_details[release][p]['compressed_file_size']
    uncompressed_file_size += release_details[release][p]['uncompressed_file_size']

download_warning = """
WARNING: This script will download up to {} MB of data. Extracting and
processing the data may require as much as {} MB of additional free disk
space. This script downloads ENDF/B-VII.1 incident neutron ACE data and 
incident photon ENDF data from NNDC and convert it to an HDF5 library 
for use with OpenMC. This data is used for OpenMC's regression test suite.
""".format(compressed_file_size, uncompressed_file_size)


# ==============================================================================
# DOWNLOAD FILES FROM NNDC SITE

if args.download:
    for particle in args.particles:
        print(download_warning)
        for f in release_details[release][particle]['compressed_files']:
            # Establish connection to URL
            url = release_details[release][particle]['base_url'] + f
            downloaded_file = download(url)


# ==============================================================================
# VERIFY MD5 CHECKSUMS

if args.download:
    print('Verifying MD5 checksums...')
    for particle in args.particles:
        if 'checksums' in release_details[release].keys():
            for f, checksum in zip(release_details[release]['compressed_files'], 
                                    release_details[release]['checksums']):
                downloadsum = hashlib.md5(open(f, 'rb').read()).hexdigest()
                print(downloadsum,f)
            if downloadsum != checksum:
                raise IOError("MD5 checksum for {} does not match. If this is your first "
                            "time receiving this message, please re-run the script. "
                            "Otherwise, please contact OpenMC developers by emailing "
                            "openmc-users@googlegroups.com.".format(f))


# ==============================================================================
# EXTRACT FILES FROM TGZ

if args.extract:
    for particle in args.particles:

        if release_details[release][particle]['file_type'] == 'ace':
            extraction_dir = ace_files_dir
        elif release_details[release][particle]['file_type'] == 'endf':
            extraction_dir = endf_files_dir

        for f in release_details[release][particle]['compressed_files']:
            # Extract files

            if f.endswith('.zip'):
                with zipfile.ZipFile(f, 'r') as zipf:
                    print('Extracting {}...'.format(f))
                    zipf.extractall(extraction_dir)
            else:
                with tarfile.open(f, 'r') as tgz:
                    print('Extracting {}...'.format(f))
                    tgz.extractall(path = extraction_dir)


# ==============================================================================
# FIX ZAID ASSIGNMENTS FOR VARIOUS S(A,B) TABLES

def fix_zaid(table, old, new):
    filename = ace_files_dir / table
    with open(filename, 'r') as fh:
        text = fh.read()
    text = text.replace(old, new, 1)
    with open(filename, 'w') as fh:
        fh.write(text)

if 'neutrons' in args.particles:
    print('Fixing ZAIDs for S(a,b) tables')
    fix_zaid('bebeo.acer', '8016', '   0')
    fix_zaid('obeo.acer', '4009', '   0')


# ==============================================================================
# GENERATE HDF5 LIBRARY

# Create output directory if it doesn't exist
for particle in args.particles:
    particle_destination = args.destination / particle
    particle_destination.mkdir(parents=True, exist_ok=True)


library = openmc.data.DataLibrary()

for particle in args.particles: 
    if particle == 'neutron':
        for filename in sorted(release_details[release][particle]['sab_files']):

            print('Converting: ' , filename)
            table = openmc.data.ace.get_table(filename)
            data = openmc.data.ThermalScattering.from_ace(table)
            # Export HDF5 file
            h5_file = args.destination.joinpath(particle, data.name + '.h5')
            data.export_to_hdf5(h5_file, 'w', libver=args.libver)
            
            # Register with library
            library.register_file(h5_file)

        for filename in sorted(release_details[release][particle]['ace_files']):
        
            print('Converting: ' , filename)
            data = openmc.data.IncidentNeutron.from_ace(filename)

            # Export HDF5 file
            h5_file = args.destination.joinpath(particle, data.name + '.h5')
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
            h5_file = args.destination.joinpath(particle, data.name + '.h5')
            data.export_to_hdf5(h5_file, 'w', libver=args.libver)

            # Register with library
            library.register_file(h5_file)
        

# Write cross_sections.xml
library.export_to_xml(args.destination / 'cross_sections.xml')
print('written ',args.destination / 'cross_sections.xml')