#!/usr/bin/env python3

"""
Generate JEFF 3.3 HDF5 library for use in OpenMC by first processing ENDF files
using NJOY. The resulting library will contain incident neutron, photoatomic,
and thermal scattering data. Note that JEFF doesn't distribute photoatomic or
atomic relaxation data so these are obtained from ENDF/B-VIII.0.

"""

import argparse
import os
import sys
import tarfile
import tempfile
import zipfile
from multiprocessing import Pool
from pathlib import Path
from urllib.parse import urljoin

import openmc.data

from openmc_data import download, process_neutron, process_thermal

# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=CustomFormatter
)
parser.add_argument('-d', '--destination', type=Path, default=Path('jeff33_hdf5'),
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
parser.add_argument('--temperatures', type=float,
                    default=[250.0, 293.6, 600.0, 900.0, 1200.0, 2500.0],
                    help="Temperatures in Kelvin", nargs='+')
parser.set_defaults(download=True, extract=True, tmpdir=True)
args = parser.parse_args()


def sort_key(path):
    if path.name.startswith('c_'):
        # Ensure that thermal scattering gets sorted after neutron data
        return (1000, path)
    else:
        return openmc.data.zam(path.stem)


def main():

    base_endf = 'https://www.nndc.bnl.gov/endf-b8.0/zips/'
    base_jeff = 'http://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/'
    files = [
        (base_jeff, 'JEFF33-n.tgz', 'e540bbf95179257280c61acfa75c83de'),
        (base_jeff, 'JEFF33-tsl.tgz', '82a6df4cb802aa4a09b95309f7861c54'),
        (base_endf, 'ENDF-B-VIII.0_photoat.zip', 'd49f5b54be278862e1ce742ccd94f5c0'),
        (base_endf, 'ENDF-B-VIII.0_atomic_relax.zip', 'e04d50098cb2a7e4fe404ec4071611cc'),
    ]

    tendl_files = [
        'https://tendl.web.psi.ch/tendl_2019/neutron_file/C/C013/lib/endf/n-C013.tendl',
        'https://tendl.web.psi.ch/tendl_2019/neutron_file/O/O017/lib/endf/n-O017.tendl',
    ]

    neutron_dir = Path('endf6')
    thermal_dir = Path('JEFF33-tsl')
    photoat_dir = Path('ENDF-B-VIII.0_photoat')
    atomic_dir = Path('ENDF-B-VIII.0_atomic_relax')
    thermal_paths = [
        (neutron_dir / '1-H-1g.jeff33', thermal_dir / 'tsl-HinCaH2.jeff33'),
        (neutron_dir / '1-H-1g.jeff33', thermal_dir / 'tsl-HinCH2.jeff33'),
        (neutron_dir / '1-H-1g.jeff33', thermal_dir / 'tsl-HinH2O.jeff33'),
        (neutron_dir / '1-H-1g.jeff33', thermal_dir / 'tsl-HinIce.jeff33'),
        (neutron_dir / '1-H-1g.jeff33', thermal_dir / 'tsl-HinMesitylene-PhaseII.jeff33'),
        (neutron_dir / '1-H-1g.jeff33', thermal_dir / 'tsl-HinOrthoH.jeff33'),
        (neutron_dir / '1-H-1g.jeff33', thermal_dir / 'tsl-HinParaH.jeff33'),
        (neutron_dir / '1-H-1g.jeff33', thermal_dir / 'tsl-HinToluene.jeff33'),
        (neutron_dir / '1-H-1g.jeff33', thermal_dir / 'tsl-HinZrH.jeff33'),
        (neutron_dir / '1-H-2g.jeff33', thermal_dir / 'tsl-DinD2O.jeff33'),
        (neutron_dir / '1-H-2g.jeff33', thermal_dir / 'tsl-DinOrthoD.jeff33'),
        (neutron_dir / '1-H-2g.jeff33', thermal_dir / 'tsl-DinParaD.jeff33'),
        (neutron_dir / '4-Be-9g.jeff33', thermal_dir / 'tsl-Be.jeff33'),
        (neutron_dir / '6-C-0g.jeff33', thermal_dir / 'tsl-Graphite.jeff33'),
        (neutron_dir / '8-O-16g.jeff33', thermal_dir / 'tsl-O16inAl2O3.jeff33'),
        (neutron_dir / '8-O-16g.jeff33', thermal_dir / 'tsl-OinD2O.jeff33'),
        (neutron_dir / '12-Mg-24g.jeff33', thermal_dir / 'tsl-Mg.jeff33'),
        (neutron_dir / '13-Al-27g.jeff33', thermal_dir / 'tsl-Al27inAl2O3.jeff33'),
        (neutron_dir / '14-Si-28g.jeff33', thermal_dir / 'tsl-Silicon.jeff33'),
        (neutron_dir / '20-Ca-40g.jeff33', thermal_dir / 'tsl-CainCaH2.jeff33'),
    ]

    pwd = Path.cwd()

    destination = args.destination.resolve()
    (destination / 'photon').mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Save current working directory and temporarily change dir
        if args.tmpdir:
            os.chdir(tmpdir)
        library = openmc.data.DataLibrary()

        # =========================================================================
        # DOWNLOAD FILES
        if args.download:
            for base, fname, checksum in files:
                download(urljoin(base, fname), checksum)

        # =========================================================================
        # EXTRACT ARCHIVES

        if args.extract:
            for _, f, _ in files:
                if f.endswith('.zip'):
                    print(f'Extracting {f}...')
                    with zipfile.ZipFile(f) as zipf:
                        zipf.extractall()
                elif f.endswith('.tar.gz') or f.endswith('.tgz'):
                    print(f'Extracting {f}...')
                    with tarfile.open(f) as tgz:
                        tgz.extractall()

        # =========================================================================
        # REPLACE C13 AND O17 WITH FILES FROM TENDL 2019

        # The evaluations for C13 and O17 can't be processed by recent versions of
        # NJOY 2016 because of a bug in MF=6 in the evaluations. Instead of trying
        # to patch the evaluation, we just replace it with more recent evaluations
        # from TENDL 2019

        for url in tendl_files:
            download(url, output_path=neutron_dir)

        (neutron_dir / 'n-C013.tendl').rename(neutron_dir / '6-C-13g.jeff33')
        (neutron_dir / 'n-O017.tendl').rename(neutron_dir / '8-O-17g.jeff33')

        # =========================================================================
        # PROCESS INCIDENT NEUTRON AND THERMAL SCATTERING DATA IN PARALLEL

        with Pool() as pool:
            neutron_paths = neutron_dir.glob('*.jeff33')
            results = []
            for p in neutron_paths:
                func_args = (p, destination, args.libver, args.temperatures)
                r = pool.apply_async(process_neutron, func_args)
                results.append(r)
            for p_neut, p_therm in thermal_paths:
                func_args = (p_neut, p_therm, destination, args.libver)
                r = pool.apply_async(process_thermal, func_args)
                results.append(r)
            for r in results:
                r.wait()

        for p in sorted(destination.glob('*.h5'), key=sort_key):
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
            outfile = destination / 'photon' / f'{element}.h5'
            data.export_to_hdf5(outfile, 'w', libver=args.libver)
            library.register_file(outfile)

        library.export_to_xml(destination / 'cross_sections.xml')

        # Change back to original directory
        if args.tmpdir:
            os.chdir(pwd)


if __name__ == '__main__':
    main()
