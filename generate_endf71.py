#!/usr/bin/env python3

import argparse
import os
import shutil
import sys
import tarfile
import tempfile
import warnings
import zipfile
from multiprocessing import Pool
from pathlib import Path
from urllib.parse import urljoin

import openmc.data
from _utils import download

# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"

description = """
Generate ENDF/B-VII.1 HDF5 library for use in OpenMC by first processing ENDF
files using NJOY. The resulting library will contain incident neutron, incident
photon, and thermal scattering data. Windowed multipole data is also included
for temperature-dependent cross section lookups on-the-fly.

"""

temperatures = [250.0, 293.6, 600.0, 900.0, 1200.0, 2500.0]

class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=Path('endfb71_hdf5'),
                    help='Directory to create new library in')
parser.add_argument('--libver', choices=['earliest', 'latest'],
                    default='earliest', help="Output HDF5 versioning. Use "
                    "'earliest' for backwards compatibility or 'latest' for "
                    "performance")
parser.add_argument('--download', action='store_true',
                    help='Download zip files from NNDC')
parser.add_argument('--no-download', dest='download', action='store_false',
                    help='Do not download zip files from NNDC')
parser.add_argument('--use-tmpdir', dest='tmpdir', action='store_true',
                    help='Use temporary directory while processing')
parser.add_argument('--no-use-tmpdir', dest='tmpdir', action='store_false',
                    help='Do not use temporary directory while processing')
parser.add_argument('--extract', action='store_true',
                    help='Extract zip files')
parser.add_argument('--no-extract', dest='extract', action='store_false',
                    help='Do not extract zip files')
parser.set_defaults(download=True, extract=True, tmpdir=True)
args = parser.parse_args()


def process_neutron(path, output_dir):
    """Process ENDF neutron sublibrary file into HDF5 and write into a
    specified output directory."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            data = openmc.data.IncidentNeutron.from_njoy(
                path, temperatures=temperatures
            )
    except Exception as e:
        print(path, e)
        raise
    data.export_to_hdf5(output_dir / f'{data.name}.h5', 'w', libver=args.libver)
    print(f'Finished {path}')


def process_thermal(path_neutron, path_thermal, output_dir):
    """Process ENDF thermal scattering sublibrary file into HDF5 and write into a
    specified output directory."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            data = openmc.data.ThermalScattering.from_njoy(
                path_neutron, path_thermal
            )
    except Exception as e:
        print(path_neutron, path_thermal, e)
        raise
    data.export_to_hdf5(output_dir / f'{data.name}.h5', 'w', libver=args.libver)
    print(f'Finished {path_thermal}')


def sort_key(path):
    if path.name.startswith('c_'):
        # Ensure that thermal scattering gets sorted after neutron data
        return (1000, path)
    else:
        return openmc.data.zam(path.stem)


base_endf = 'http://www.nndc.bnl.gov/endf/b7.1/zips/'
files = [
    (base_endf, 'ENDF-B-VII.1-neutrons.zip', 'e5d7f441fc4c92893322c24d1725e29c'),
    (base_endf, 'ENDF-B-VII.1-photoat.zip', '5192f94e61f0b385cf536f448ffab4a4'),
    (base_endf, 'ENDF-B-VII.1-atomic_relax.zip', 'fddb6035e7f2b6931e51a58fc754bd10'),
    (base_endf, 'ENDF-B-VII.1-thermal_scatt.zip', 'fe590109dde63b2ec5dc228c7b8cab02')
]
wmp_version = '1.1'
wmp_base = f'https://github.com/mit-crpg/WMP_Library/releases/download/v{wmp_version}/'
wmp_filename = f'WMP_Library_v{wmp_version}.tar.gz'


neutron_dir = Path('neutrons')
thermal_dir = Path('thermal_scatt')
thermal_paths = [
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinH2O.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinCH2.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinZrH.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-ortho-H.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-para-H.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-benzine.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-l-CH4.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-s-CH4.endf'),
    (neutron_dir / 'n-001_H_002.endf', thermal_dir / 'tsl-DinD2O.endf'),
    (neutron_dir / 'n-001_H_002.endf', thermal_dir / 'tsl-ortho-D.endf'),
    (neutron_dir / 'n-001_H_002.endf', thermal_dir / 'tsl-para-D.endf'),
    (neutron_dir / 'n-004_Be_009.endf', thermal_dir / 'tsl-BeinBeO.endf'),
    (neutron_dir / 'n-004_Be_009.endf', thermal_dir / 'tsl-Be-metal.endf'),
    (neutron_dir / 'n-006_C_000.endf', thermal_dir / 'tsl-graphite.endf'),
    (neutron_dir / 'n-008_O_016.endf', thermal_dir / 'tsl-OinBeO.endf'),
    (neutron_dir / 'n-008_O_016.endf', thermal_dir / 'tsl-OinUO2.endf'),
    (neutron_dir / 'n-013_Al_027.endf', thermal_dir / 'tsl-013_Al_027.endf'),
    (neutron_dir / 'n-026_Fe_056.endf', thermal_dir / 'tsl-026_Fe_056.endf'),
    (neutron_dir / 'n-014_Si_028.endf', thermal_dir / 'tsl-SiO2.endf'),
    (neutron_dir / 'n-040_Zr_090.endf', thermal_dir / 'tsl-ZrinZrH.endf'),
    (neutron_dir / 'n-092_U_238.endf', thermal_dir / 'tsl-UinUO2.endf')
]

pwd = Path.cwd()

(args.destination / 'photon').mkdir(parents=True, exist_ok=True)
(args.destination / 'wmp').mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory() as tmpdir:
    # Save current working directory and temporarily change dir
    if args.tmpdir:
        os.chdir(tmpdir)
    library = openmc.data.DataLibrary()

    # =========================================================================
    # Download files from NNDC server
    if args.download:
        for base, fname, checksum in files:
            download(urljoin(base, fname), checksum)

    # =========================================================================
    # EXTRACT FROM ZIP FILES

    if args.extract:
        for _, f, _ in files:
            print(f'Extracting {f}...')
            zipfile.ZipFile(f).extractall()

    # =========================================================================
    # PROCESS INCIDENT NEUTRON AND THERMAL SCATTERING DATA IN PARALLEL

    with Pool() as pool:
        neutron_paths = neutron_dir.glob('*.endf')
        results = []
        for p in neutron_paths:
            r = pool.apply_async(process_neutron, (p, args.destination))
            results.append(r)
        for p_neut, p_therm in thermal_paths:
            r = pool.apply_async(process_thermal, (p_neut, p_therm, args.destination))
            results.append(r)
        for r in results:
            r.wait()

    for p in sorted(args.destination.glob('*.h5'), key=sort_key):
        library.register_file(p)

    # =========================================================================
    # INCIDENT PHOTON DATA

    for z in range(1, 101):
        element = openmc.data.ATOMIC_SYMBOL[z]
        print('Generating HDF5 file for Z={} ({})...'.format(z, element))

        # Generate instance of IncidentPhoton
        photo_file = Path('photoat') / f'photoat-{z:03}_{element}_000.endf'
        atom_file = Path('atomic_relax') / f'atom-{z:03}_{element}_000.endf'
        data = openmc.data.IncidentPhoton.from_endf(photo_file, atom_file)

        # Write HDF5 file and register it
        outfile = args.destination / 'photon' / f'{element}.h5'
        data.export_to_hdf5(outfile, 'w', libver=args.libver)
        library.register_file(outfile)

    # =========================================================================
    # WINDOWED MULTIPOLE DATA

    # Download and extract data
    if args.download:
        download(urljoin(wmp_base, wmp_filename))
    if args.extract:
        with tarfile.open(wmp_filename, 'r') as tgz:
            tgz.extractall()

    # Add multipole data to library
    for src in Path('WMP_Library').glob('*.h5'):
        dst = args.destination / 'wmp' / src.name
        shutil.copy2(src, dst)
        library.register_file(dst)

    library.export_to_xml(args.destination / 'cross_sections.xml')

    # Change back to original directory
    if args.tmpdir:
        os.chdir(pwd)
