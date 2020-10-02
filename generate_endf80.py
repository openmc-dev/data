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

from utils import download, process_neutron, process_thermal

# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"

description = """
Generate ENDF/B-VIII.0 HDF5 library for use in OpenMC by first processing ENDF
files using NJOY. The resulting library will contain incident neutron, incident
photon, and thermal scattering data.

"""

temperatures = [250.0, 293.6, 600.0, 900.0, 1200.0, 2500.0]


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=Path('endfb80_hdf5'),
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


def sort_key(path):
    if path.name.startswith('c_'):
        # Ensure that thermal scattering gets sorted after neutron data
        return (1000, path)
    else:
        return openmc.data.zam(path.stem)


base_endf = 'https://www.nndc.bnl.gov/endf/b8.0/zips/'
base_errata = 'https://www.nndc.bnl.gov/endf/b8.0/erratafiles/'
files = [
    (base_endf, 'ENDF-B-VIII.0_neutrons.zip', '90c1b1a6653a148f17cbf3c5d1171859'),
    (base_endf, 'ENDF-B-VIII.0_photoat.zip', 'd49f5b54be278862e1ce742ccd94f5c0'),
    (base_endf, 'ENDF-B-VIII.0_atomic_relax.zip', 'e04d50098cb2a7e4fe404ec4071611cc'),
    (base_endf, 'ENDF-B-VIII.0_thermal_scatt.zip', 'ecd503d3f8214f703e95e17cc947062c'),
    (base_errata, 'n-005_B_010.endf', None)
]


neutron_dir = Path('ENDF-B-VIII.0_neutrons')
thermal_dir = Path('ENDF-B-VIII.0_thermal_scatt')
photoat_dir = Path('ENDF-B-VIII.0_photoat')
atomic_dir = Path('ENDF-B-VIII.0_atomic_relax')
thermal_paths = [
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinC5O2H8.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinH2O.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinCH2.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinZrH.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinIceIh.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-HinYH2.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-ortho-H.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-para-H.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-benzene.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-l-CH4.endf'),
    (neutron_dir / 'n-001_H_001.endf', thermal_dir / 'tsl-s-CH4.endf'),
    (neutron_dir / 'n-001_H_002.endf', thermal_dir / 'tsl-DinD2O.endf'),
    (neutron_dir / 'n-001_H_002.endf', thermal_dir / 'tsl-ortho-D.endf'),
    (neutron_dir / 'n-001_H_002.endf', thermal_dir / 'tsl-para-D.endf'),
    (neutron_dir / 'n-004_Be_009.endf', thermal_dir / 'tsl-BeinBeO.endf'),
    (neutron_dir / 'n-004_Be_009.endf', thermal_dir / 'tsl-Be-metal.endf'),
    (neutron_dir / 'n-006_C_012.endf', thermal_dir / 'tsl-CinSiC.endf'),
    (neutron_dir / 'n-006_C_012.endf', thermal_dir / 'tsl-crystalline-graphite.endf'),
    (neutron_dir / 'n-006_C_012.endf', thermal_dir / 'tsl-reactor-graphite-10P.endf'),
    (neutron_dir / 'n-006_C_012.endf', thermal_dir / 'tsl-reactor-graphite-30P.endf'),
    (neutron_dir / 'n-007_N_014.endf', thermal_dir / 'tsl-NinUN.endf'),
    (neutron_dir / 'n-008_O_016.endf', thermal_dir / 'tsl-OinBeO.endf'),
    (neutron_dir / 'n-008_O_016.endf', thermal_dir / 'tsl-OinD2O.endf'),
    (neutron_dir / 'n-008_O_016.endf', thermal_dir / 'tsl-OinIceIh.endf'),
    (neutron_dir / 'n-008_O_016.endf', thermal_dir / 'tsl-OinUO2.endf'),
    (neutron_dir / 'n-013_Al_027.endf', thermal_dir / 'tsl-013_Al_027.endf'),
    (neutron_dir / 'n-026_Fe_056.endf', thermal_dir / 'tsl-026_Fe_056.endf'),
    (neutron_dir / 'n-014_Si_028.endf', thermal_dir / 'tsl-SiinSiC.endf'),
    (neutron_dir / 'n-014_Si_028.endf', thermal_dir / 'tsl-SiO2-alpha.endf'),
    (neutron_dir / 'n-014_Si_028.endf', thermal_dir / 'tsl-SiO2-beta.endf'),
    (neutron_dir / 'n-039_Y_089.endf', thermal_dir / 'tsl-YinYH2.endf'),
    (neutron_dir / 'n-040_Zr_090.endf', thermal_dir / 'tsl-ZrinZrH.endf'),
    (neutron_dir / 'n-092_U_238.endf', thermal_dir / 'tsl-UinUN.endf'),
    (neutron_dir / 'n-092_U_238.endf', thermal_dir / 'tsl-UinUO2.endf')
]

pwd = Path.cwd()

(args.destination / 'photon').mkdir(parents=True, exist_ok=True)

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
            if f.endswith('.zip'):
                print(f'Extracting {f}...')
                with zipfile.ZipFile(f) as zipf:
                    zipf.extractall()
            elif f.endswith('.tar.gz'):
                print(f'Extracting {f}...')
                with tarfile.open(f) as tgz:
                    tgz.extractall()

        # Copy corrected B10 file
        shutil.copy('n-005_B_010.endf', neutron_dir)

    # =========================================================================
    # PROCESS INCIDENT NEUTRON AND THERMAL SCATTERING DATA IN PARALLEL

    with Pool() as pool:
        neutron_paths = neutron_dir.glob('*.endf')
        results = []
        for p in neutron_paths:
            # Skip neutron evaluation
            if p.name == 'n-000_n_001.endf':
                continue

            func_args = (p, args.destination, args.libver, temperatures)
            r = pool.apply_async(process_neutron, func_args)
            results.append(r)
        for p_neut, p_therm in thermal_paths:
            func_args = (p_neut, p_therm, args.destination, args.libver)
            r = pool.apply_async(process_thermal, func_args)
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
        photo_file = photoat_dir / f'photoat-{z:03}_{element}_000.endf'
        atom_file = atomic_dir / f'atom-{z:03}_{element}_000.endf'
        data = openmc.data.IncidentPhoton.from_endf(photo_file, atom_file)

        # Write HDF5 file and register it
        outfile = args.destination / 'photon' / f'{element}.h5'
        data.export_to_hdf5(outfile, 'w', libver=args.libver)
        library.register_file(outfile)

    library.export_to_xml(args.destination / 'cross_sections.xml')

    # Change back to original directory
    if args.tmpdir:
        os.chdir(pwd)
