#!/usr/bin/env python3

"""
Download FENDL-3.2 FENDL-3.1d, FENDL-3.1a, FENDL-3.0 or FENDL-2.1 ACE
data from the IAEA and convert it to a HDF5 library for use with OpenMC.
"""

import argparse
import ssl
import subprocess
import warnings
from pathlib import Path
from shutil import rmtree
from textwrap import dedent
from urllib.parse import urljoin

import openmc.data
from utils import download


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
parser.add_argument('-r', '--release', choices=['3.2','3.1d', '3.1a', '3.0',
                    '2.1'],  default='3.2', help="The nuclear data library "
                    "release version. The currently supported options are "
                    "3.2, 3.1d, 3.1a, 3.0 and 2.1")
parser.add_argument('-p', '--particles', choices=['neutron', 'photon'],
                    nargs='+', default=['neutron', 'photon'],
                    help="Incident particles to include")
parser.add_argument('--cleanup', action='store_true',
                    help="Remove download directories when data has "
                    "been processed")
parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                    help="Do not remove download directories when data has "
                    "been processed")
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()

# =============================================================================
# FUNCTIONS FOR DEALING WITH SPECIAL CASES
#
# Each of these functions should take a Path object which points to the file
# The function should return a bool which determines whether the file should be
# ignored.


def fendl30_k39(file_path):
    """ Function to check for k-39 error in FENDL-3.0"""
    if 'Inf' in open(file_path, 'r').read():
        ace_error_warning = """
        {} contains 'Inf' values within the XSS array
        which prevent conversion to a HDF5 file format. This is a known issue
        in FENDL-3.0. {} has not been added to the cross section library.
        """.format(file_path, file_path.name)
        err_msg = dedent(ace_error_warning)
        return {'skip_file': True, 'err_msg': err_msg}
    else:
        return {'skip_file': False}


def check_special_case(particle_details, script_step):
    """
    Helper function for checking if there are any special cases defined:
    Returns the special Cases relevant to a specific part of the script.
    If there are no special cases, return an empty dict
    """
    if 'special_cases' in particle_details:
        if script_step in particle_details['special_cases']:
            return particle_details['special_cases'][script_step]
    return {}


library_name = 'fendl'
cwd = Path.cwd()

ace_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'ace']))
endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))

download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))
# the destination is decided after the release is know to avoid putting
# the release in a folder with a misleading name
if args.destination is None:
    args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

# This dictionary contains all the unique information about each release.
# This can be extended to accommodate new releases
release_details = {
    '3.2': {
        'neutron': {
            'base_url': 'https://www-nds.iaea.org/fendl/data/neutron/',
            'compressed_files': ['fendl32-neutron-ace.zip'],
            'file_type': 'ace',
            'ace_files': ace_files_dir.joinpath('neutron/ace').glob('*[!.xsd]'),
            'compressed_file_size': 565,
            'uncompressed_file_size': 4226
        },
        'photon': {
            'base_url': 'https://www-nds.iaea.org/fendl/data/atom/',
            'compressed_files': ['fendl32-atom-endf.zip'],
            'file_type': 'endf',
            'photo_files': endf_files_dir.joinpath('atom/endf').rglob('*.endf'),
            'compressed_file_size': 4,
            'uncompressed_file_size': 33
        }
    },
    '3.1a': {
        'neutron': {
            'base_url': 'https://www-nds.iaea.org/fendl31/data/neutron/',
            'compressed_files': ['fendl31a-neutron-ace.zip'],
            'file_type': 'ace',
            'ace_files': ace_files_dir.glob('*.ace'),
            'compressed_file_size': 384,
            'uncompressed_file_size': 2250
        },
        'photon': {
            'base_url': 'https://www-nds.iaea.org/fendl31/data/atom/',
            'compressed_files': ['fendl30-atom-endf.zip'],
            'file_type': 'endf',
            'photo_files': endf_files_dir.joinpath('endf').glob('*.txt'),
            'compressed_file_size': 4,
            'uncompressed_file_size': 12
        }
    },
    '3.1d': {
        'neutron': {
            'base_url': 'https://www-nds.iaea.org/fendl31d/data/neutron/',
            'compressed_files': ['fendl31d-neutron-ace.zip'],
            'file_type': 'ace',
            'ace_files': ace_files_dir.joinpath('fendl31d_ACE').glob('*'),
            'compressed_file_size': 425,
            'uncompressed_file_size': 2290
        },
        'photon': {
            'base_url': 'https://www-nds.iaea.org/fendl31d/data/atom/',
            'compressed_files': ['fendl30-atom-endf.zip'],
            'file_type': 'endf',
            'photo_files': endf_files_dir.joinpath('endf').glob('*.txt'),
            'compressed_file_size': 4,
            'uncompressed_file_size': 12
        }
    },
    '3.0': {
        'neutron': {
            'base_url': 'https://www-nds.iaea.org/fendl30/data/neutron/',
            'compressed_files': ['fendl30-neutron-ace.zip'],
            'file_type': 'ace',
            'ace_files': ace_files_dir.joinpath('ace').glob('*.ace'),
            'compressed_file_size': 364,
            'uncompressed_file_size': 2200,
            'special_cases': {
                'process': {'19K_039.ace': fendl30_k39}
            }
        },
        'photon': {
            'base_url': 'https://www-nds.iaea.org/fendl30/data/atom/',
            'compressed_files': ['fendl30-atom-endf.zip'],
            'file_type': 'endf',
            'photo_files': endf_files_dir.joinpath('endf').glob('*.txt'),
            'compressed_file_size': 4,
            'uncompressed_file_size': 12
        }
    },
    '2.1': {
        'neutron': {
            'base_url': 'https://www-nds.iaea.org/fendl21/fendl21mc/',
            'compressed_files': ['H001mc.zip',  'H002mc.zip',  'H003mc.zip',  'He003mc.zip',
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
            'file_type': 'ace',
            'ace_files': ace_files_dir.glob('*.ace'),
            'compressed_file_size': 100,
            'uncompressed_file_size': 600
        },
        'photon': {
            'base_url': 'https://www-nds.iaea.org/fendl21/fendl21e/',
            'compressed_files': ['FENDLEP.zip'],
            'file_type': 'endf',
            'photo_files': endf_files_dir.glob('*.endf'),
            'compressed_file_size': 2,
            'uncompressed_file_size': 5
        }
    }
}

compressed_file_size = uncompressed_file_size = 0
for p in ('neutron', 'photon'):
    if p in args.particles:
        compressed_file_size += release_details[args.release][p]['compressed_file_size']
        uncompressed_file_size += release_details[args.release][p]['uncompressed_file_size']

download_warning = """
WARNING: This script will download {} MB of data.
Extracting and processing the data requires {} MB of additional free disk space.
""".format(compressed_file_size, uncompressed_file_size)

# Warnings to be printed at the end of the script.
output_warnings = []

# ==============================================================================
# DOWNLOAD FILES FROM IAEA SITE

if args.download:
    print(download_warning)

    for particle in args.particles:
        # Create a directory to hold the downloads
        particle_download_path = download_path / particle

        particle_details = release_details[args.release][particle]
        for f in particle_details['compressed_files']:
            download(urljoin(particle_details['base_url'], f),
                     as_browser=True, context=ssl._create_unverified_context(),
                     output_path=particle_download_path)


# ==============================================================================
# EXTRACT FILES FROM ZIP
if args.extract:
    for particle in args.particles:

        particle_details = release_details[args.release][particle]
        special_cases = check_special_case(particle_details, 'extract')

        if particle_details['file_type'] == "ace":
            extraction_dir = ace_files_dir
        elif particle_details['file_type'] == "endf":
            extraction_dir = endf_files_dir

        for f in particle_details['compressed_files']:
            # Check if file requires special handling
            if f in special_cases:
                ret = special_cases[f](Path(f))
                if 'err_msg' in ret:
                    output_warnings.append(ret['err_msg'])
                if ret['skip_file']:
                    continue

            # Extract files, the fendl release was compressed using type 9 zip format
            # unfortunatly which is incompatible with the standard python zipfile library
            # therefore the following system command is used
            subprocess.call(['unzip', '-o', download_path / particle / f, '-d', extraction_dir])

    if args.cleanup and download_path.exists():
        rmtree(download_path)


# ==============================================================================
# GENERATE HDF5 LIBRARY

library = openmc.data.DataLibrary()

for particle in args.particles:
    # Create output directories if it doesn't exist
    particle_destination = args.destination / particle
    particle_destination.mkdir(parents=True, exist_ok=True)

    particle_details = release_details[args.release][particle]

    # Get dictionary of special cases for particle
    special_cases = check_special_case(particle_details, 'process')

    if particle == 'neutron':
        # Get a list of all ACE files, excluding files ending with _ that are
        # old incorrect files kept in the release for backwards compatability
        neutron_files = [
            f
            for f in particle_details['ace_files']
            if not f.name.endswith('_') and not f.name.endswith('.xsd')
        ]

        for filename in sorted(neutron_files):
            # Handling for special cases
            if filename.name in special_cases:
                ret = special_cases[filename.name](filename)
                if 'err_msg' in ret:
                    output_warnings.append(ret['err_msg'])
                if ret['skip_file']:
                    continue

            print(f'Converting: {filename}')
            data = openmc.data.IncidentNeutron.from_ace(filename)

            # Export HDF5 file
            h5_file = particle_destination / f'{data.name}.h5'
            print(f'Writing {h5_file}...')
            data.export_to_hdf5(h5_file, 'w', libver=args.libver)

            # Register with library
            library.register_file(h5_file)

        # Remove the ace files if required
        if args.cleanup and ace_files_dir.exists():
            rmtree(ace_files_dir)

    elif particle == 'photon':
        for photo_path in sorted(particle_details['photo_files']):
            # Check if file requires special handling
            if photo_path.name in special_cases:
                ret = special_cases[photo_path.name](photo_path)
                if 'err_msg' in ret:
                    output_warnings.append(ret['err_msg'])
                if ret['skip_file']:
                    continue

            print(f'Converting: {photo_path}')
            evaluations = openmc.data.endf.get_evaluations(photo_path)
            for ev in evaluations:
                # Export HDF5 file
                data = openmc.data.IncidentPhoton.from_endf(ev)
                h5_file = particle_destination / f'{data.name}.h5'
                print(f'Writing {h5_file}...')
                data.export_to_hdf5(h5_file, 'w', libver=args.libver)

            # Register with library
            library.register_file(h5_file)

        # Remove the ENDF files if required
        if args.cleanup and endf_files_dir.exists():
            rmtree(endf_files_dir)

# Write cross_sections.xml
print('Writing ', args.destination / 'cross_sections.xml')
library.export_to_xml(args.destination / 'cross_sections.xml')

# Print any warnings
for warning in output_warnings:
    warnings.warn(warning)
