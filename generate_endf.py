#!/usr/bin/env python3

"""
Download ENDF/B-VIII.0 or ENDF/B-VII.1 library for use in OpenMC by first
processing ENDF files using NJOY. The resulting library will contain incident
neutron, incident photon, and thermal scattering data.
"""


import argparse
import sys
import tarfile
import zipfile
from multiprocessing import Pool
from pathlib import Path
from shutil import rmtree, copy, copyfileobj

import openmc.data
from utils import download, process_neutron, process_thermal


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=CustomFormatter
    )

    parser.add_argument('-d', '--destination', type=Path,
                        help='Directory to create new library in')
    parser.add_argument('--download', action='store_true',
                        help='Download zip files from NNDC')
    parser.add_argument('--no-download', dest='download', action='store_false',
                        help='Do not download zip files from NNDC')
    parser.add_argument('--extract', action='store_true',
                        help='Extract zip files')
    parser.add_argument('--no-extract', dest='extract', action='store_false',
                        help='Do not extract zip files')
    parser.add_argument('--libver', choices=['earliest', 'latest'],
                        default='earliest', help="Output HDF5 versioning. Use "
                        "'earliest' for backwards compatibility or 'latest' for "
                        "performance")
    parser.add_argument('-r', '--release', choices=['vii.1', 'viii.0', 'viii.1'],
                        default='viii.1', help="The nuclear data library release "
                        "version. The currently supported options are vii.1, "
                        "viii.0, viii.1")
    parser.add_argument('-p', '--particles', choices=['neutron', 'thermal', 'photon', 'wmp'],
                        nargs='+', default=['neutron', 'thermal', 'photon'],
                        help="Incident particles to include, wmp is not available "
                        "for release b8.0 at the moment")
    parser.add_argument('--cleanup', action='store_true',
                        help="Remove download directories when data has "
                        "been processed")
    parser.add_argument('--no-cleanup', dest='cleanup', action='store_false',
                        help="Do not remove download directories when data has "
                        "been processed")
    parser.add_argument('--temperatures', type=float,
                        default=[250.0, 293.6, 600.0, 900.0, 1200.0, 2500.0],
                        help="Temperatures in Kelvin", nargs='+')
    parser.set_defaults(download=True, extract=True, cleanup=False)
    args = parser.parse_args()


    def sort_key(path):
        if path.name.startswith('c_'):
            # Ensure that thermal scattering gets sorted after neutron data
            return (1000, path)
        else:
            return openmc.data.zam(path.stem)


    library_name = 'endfb'

    cwd = Path.cwd()

    endf_files_dir = cwd.joinpath('-'.join([library_name, args.release, 'endf']))
    neutron_dir = endf_files_dir / 'neutron'
    thermal_dir = endf_files_dir / 'thermal'
    download_path = cwd.joinpath('-'.join([library_name, args.release, 'download']))
    # the destination is decided after the release is known
    # to avoid putting the release in a folder with a misleading name
    if args.destination is None:
        args.destination = Path('-'.join([library_name, args.release, 'hdf5']))

    # This dictionary contains all the unique information about each release. This
    # can be extended to accommodate new releases
    release_details = {
        'vii.1': {
            'neutron': {
                'base_url': 'http://www.nndc.bnl.gov/endf-b7.1/zips/',
                'compressed_files': ['ENDF-B-VII.1-neutrons.zip'],
                'checksums': ['e5d7f441fc4c92893322c24d1725e29c'],
                'file_type': 'endf',
                'endf_files': neutron_dir.rglob('n-*.endf'),
            },
            'thermal': {
                'base_url': 'http://www.nndc.bnl.gov/endf-b7.1/zips/',
                'compressed_files': ['ENDF-B-VII.1-thermal_scatt.zip'],
                'checksums': ['fe590109dde63b2ec5dc228c7b8cab02'],
                'file_type': 'endf',
                'sab_files': [
                    ('n-001_H_001.endf', 'tsl-HinH2O.endf'),
                    ('n-001_H_001.endf', 'tsl-HinCH2.endf'),
                    ('n-001_H_001.endf', 'tsl-HinZrH.endf'),
                    ('n-001_H_001.endf', 'tsl-ortho-H.endf'),
                    ('n-001_H_001.endf', 'tsl-para-H.endf'),
                    ('n-001_H_001.endf', 'tsl-benzine.endf'),
                    ('n-001_H_001.endf', 'tsl-l-CH4.endf'),
                    ('n-001_H_001.endf', 'tsl-s-CH4.endf'),
                    ('n-001_H_002.endf', 'tsl-DinD2O.endf'),
                    ('n-001_H_002.endf', 'tsl-ortho-D.endf'),
                    ('n-001_H_002.endf', 'tsl-para-D.endf'),
                    ('n-004_Be_009.endf', 'tsl-BeinBeO.endf'),
                    ('n-004_Be_009.endf', 'tsl-Be-metal.endf'),
                    ('n-006_C_000.endf', 'tsl-graphite.endf'),
                    ('n-008_O_016.endf', 'tsl-OinBeO.endf'),
                    ('n-008_O_016.endf', 'tsl-OinUO2.endf'),
                    ('n-013_Al_027.endf', 'tsl-013_Al_027.endf'),
                    ('n-026_Fe_056.endf', 'tsl-026_Fe_056.endf'),
                    ('n-014_Si_028.endf', 'tsl-SiO2.endf'),
                    ('n-040_Zr_090.endf', 'tsl-ZrinZrH.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUO2.endf')
                ],
            },
            'photon': {
                'base_url': 'http://www.nndc.bnl.gov/endf-b7.1/zips/',
                'compressed_files': [
                    'ENDF-B-VII.1-photoat.zip',
                    'ENDF-B-VII.1-atomic_relax.zip'
                ],
                'checksums': [
                    '5192f94e61f0b385cf536f448ffab4a4',
                    'fddb6035e7f2b6931e51a58fc754bd10'
                ],
                'file_type': 'endf',
                'photo_files': endf_files_dir.joinpath('photon').rglob('photoat*.endf'),
                'atom_files': endf_files_dir.joinpath('photon').rglob('atom*.endf'),
            },
            'wmp': {
                'base_url': 'https://github.com/mit-crpg/WMP_Library/releases/download/v1.1/',
                'compressed_files': ['WMP_Library_v1.1.tar.gz'],
                'file_type': 'wmp',
            }
        },
        'viii.0': {
            'neutron': {
                'base_url': 'https://www.nndc.bnl.gov/endf-b8.0/',
                'compressed_files': [
                    'zips/ENDF-B-VIII.0_neutrons.zip',
                    'erratafiles/n-005_B_010.endf'
                ],
                'checksums': [
                    '90c1b1a6653a148f17cbf3c5d1171859',
                    'eaf71eb22258f759abc205a129d8715a'
                ],
                'file_type': 'endf',
                'endf_files': neutron_dir.rglob('n-*.endf'),

            },
            'thermal': {
                'base_url': 'https://www.nndc.bnl.gov/endf-b8.0/zips/',
                'compressed_files': ['ENDF-B-VIII.0_thermal_scatt.zip'],
                'checksums': ['ecd503d3f8214f703e95e17cc947062c'],
                'file_type': 'endf',
                'sab_files': [
                    ('n-001_H_001.endf', 'tsl-HinC5O2H8.endf'),
                    ('n-001_H_001.endf', 'tsl-HinH2O.endf'),
                    ('n-001_H_001.endf', 'tsl-HinCH2.endf'),
                    ('n-001_H_001.endf', 'tsl-HinZrH.endf'),
                    ('n-001_H_001.endf', 'tsl-HinIceIh.endf'),
                    ('n-001_H_001.endf', 'tsl-HinYH2.endf'),
                    ('n-001_H_001.endf', 'tsl-ortho-H.endf'),
                    ('n-001_H_001.endf', 'tsl-para-H.endf'),
                    ('n-001_H_001.endf', 'tsl-benzene.endf'),
                    ('n-001_H_001.endf', 'tsl-l-CH4.endf'),
                    ('n-001_H_001.endf', 'tsl-s-CH4.endf'),
                    ('n-001_H_002.endf', 'tsl-DinD2O.endf'),
                    ('n-001_H_002.endf', 'tsl-ortho-D.endf'),
                    ('n-001_H_002.endf', 'tsl-para-D.endf'),
                    ('n-004_Be_009.endf', 'tsl-BeinBeO.endf'),
                    ('n-004_Be_009.endf', 'tsl-Be-metal.endf'),
                    ('n-006_C_012.endf', 'tsl-CinSiC.endf'),
                    ('n-006_C_012.endf', 'tsl-crystalline-graphite.endf'),
                    ('n-006_C_012.endf', 'tsl-reactor-graphite-10P.endf'),
                    ('n-006_C_012.endf', 'tsl-reactor-graphite-30P.endf'),
                    ('n-007_N_014.endf', 'tsl-NinUN.endf'),
                    ('n-008_O_016.endf', 'tsl-OinBeO.endf'),
                    ('n-008_O_016.endf', 'tsl-OinD2O.endf'),
                    ('n-008_O_016.endf', 'tsl-OinIceIh.endf'),
                    ('n-008_O_016.endf', 'tsl-OinUO2.endf'),
                    ('n-013_Al_027.endf', 'tsl-013_Al_027.endf'),
                    ('n-026_Fe_056.endf', 'tsl-026_Fe_056.endf'),
                    ('n-014_Si_028.endf', 'tsl-SiinSiC.endf'),
                    ('n-014_Si_028.endf', 'tsl-SiO2-alpha.endf'),
                    ('n-014_Si_028.endf', 'tsl-SiO2-beta.endf'),
                    ('n-039_Y_089.endf', 'tsl-YinYH2.endf'),
                    ('n-040_Zr_090.endf', 'tsl-ZrinZrH.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUN.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUO2.endf')
                ],
            },
            'photon': {
                'base_url': 'https://www.nndc.bnl.gov/endf-b8.0/',
                'compressed_files': ['zips/ENDF-B-VIII.0_photoat.zip',
                                    'erratafiles/atomic_relax.tar.gz'],
                'checksums': ['d49f5b54be278862e1ce742ccd94f5c0',
                            '805f877c59ad22dcf57a0446d266ceea'],
                'file_type': 'endf',
                'photo_files': endf_files_dir.joinpath('photon').rglob('photoat*.endf'),
                'atom_files': endf_files_dir.joinpath('photon').rglob('atom*.endf'),
            }
        },
        'viii.1': {
            'neutron': {
                'base_url': 'https://www.nndc.bnl.gov/endf-releases/releases/B-VIII.1/neutrons/',
                'compressed_files': ['neutrons-version.VIII.1.tar.gz'],
                'checksums': ['dc622c0f1c3c4477433e698266e0fc80'],
                'file_type': 'endf',
                'endf_files': neutron_dir.rglob('n-*.endf'),
            },
            'thermal': {
                'base_url': 'https://www.nndc.bnl.gov/endf-releases/releases/B-VIII.1/thermal_scatt/',
                'compressed_files': ['thermal_scatt-version.VIII.1.tar.gz'],
                'checksums': ['f7bcae02b2da577e28a3a083e07a3a3a'],
                'file_type': 'endf',
                'sab_files': [
                    ('n-001_H_001.endf', 'tsl-H1inCaH2.endf'),
                    ('n-001_H_001.endf', 'tsl-H2inCaH2.endf'),
                    ('n-001_H_001.endf', 'tsl-Hin7LiH-mixed.endf'),
                    ('n-001_H_001.endf', 'tsl-HinC5O2H8.endf'),
                    ('n-001_H_001.endf', 'tsl-HinC8H8.endf'),
                    ('n-001_H_001.endf', 'tsl-HinCH2.endf'),
                    ('n-001_H_001.endf', 'tsl-HinH2O.endf'),
                    ('n-001_H_001.endf', 'tsl-HinHF.endf'),
                    ('n-001_H_001.endf', 'tsl-HinIceIh.endf'),
                    ('n-001_H_001.endf', 'tsl-HinParaffinicOil.endf'),
                    ('n-001_H_001.endf', 'tsl-HinUH3.endf'),
                    ('n-001_H_001.endf', 'tsl-HinYH2.endf'),
                    ('n-001_H_001.endf', 'tsl-HinZrH2.endf'),
                    ('n-001_H_001.endf', 'tsl-HinZrH.endf'),
                    ('n-001_H_001.endf', 'tsl-HinZrHx.endf'),
                    ('n-001_H_001.endf', 'tsl-ortho-H.endf'),
                    ('n-001_H_001.endf', 'tsl-para-H.endf'),
                    ('n-001_H_001.endf', 'tsl-benzene.endf'),
                    ('n-001_H_001.endf', 'tsl-l-CH4.endf'),
                    ('n-001_H_001.endf', 'tsl-s-CH4.endf'),
                    ('n-001_H_002.endf', 'tsl-Din7LiD-mixed.endf'),
                    ('n-001_H_002.endf', 'tsl-DinD2O.endf'),
                    ('n-001_H_002.endf', 'tsl-ortho-D.endf'),
                    ('n-001_H_002.endf', 'tsl-para-D.endf'),
                    ('n-003_Li_007.endf', 'tsl-7Liin7LiD-mixed.endf'),
                    ('n-003_Li_007.endf', 'tsl-7Liin7LiH-mixed.endf'),
                    ('n-003_Li_007.endf', 'tsl-LiinFLiBe.endf'),
                    ('n-004_Be_009.endf', 'tsl-BeinBe2C.endf'),
                    ('n-004_Be_009.endf', 'tsl-BeinBeF2.endf'),
                    ('n-004_Be_009.endf', 'tsl-BeinBeO.endf'),
                    ('n-004_Be_009.endf', 'tsl-BeinFLiBe.endf'),
                    ('n-004_Be_009.endf', 'tsl-Be-metal.endf'),
                    ('n-004_Be_009.endf', 'tsl-Be-metal+Sd.endf'),
                    ('n-006_C_012.endf', 'tsl-CinBe2C.endf'),
                    ('n-006_C_012.endf', 'tsl-CinC5O2H8.endf'),
                    ('n-006_C_012.endf', 'tsl-CinC8H8.endf'),
                    ('n-006_C_012.endf', 'tsl-CinCF2.endf'),
                    ('n-006_C_012.endf', 'tsl-CinSiC.endf'),
                    ('n-006_C_012.endf', 'tsl-CinUC-100P.endf'),
                    ('n-006_C_012.endf', 'tsl-CinUC-10P.endf'),
                    ('n-006_C_012.endf', 'tsl-CinUC-5P.endf'),
                    ('n-006_C_012.endf', 'tsl-CinUC.endf'),
                    ('n-006_C_012.endf', 'tsl-CinUC-HALEU.endf'),
                    ('n-006_C_012.endf', 'tsl-CinUC-HEU.endf'),
                    ('n-006_C_012.endf', 'tsl-CinZrC.endf'),
                    ('n-006_C_012.endf', 'tsl-crystalline-graphite.endf'),
                    ('n-006_C_012.endf', 'tsl-graphiteSd.endf'),
                    ('n-006_C_012.endf', 'tsl-reactor-graphite-10P.endf'),
                    ('n-006_C_012.endf', 'tsl-reactor-graphite-20P.endf'),
                    ('n-006_C_012.endf', 'tsl-reactor-graphite-30P.endf'),
                    ('n-007_N_014.endf', 'tsl-NinUN-100P.endf'),
                    ('n-007_N_014.endf', 'tsl-NinUN-10P.endf'),
                    ('n-007_N_014.endf', 'tsl-NinUN-5P.endf'),
                    ('n-007_N_014.endf', 'tsl-NinUN.endf'),
                    ('n-007_N_014.endf', 'tsl-NinUN-HALEU.endf'),
                    ('n-007_N_014.endf', 'tsl-NinUN-HEU.endf'),
                    ('n-008_O_016.endf', 'tsl-OinAl2O3.endf'),
                    ('n-008_O_016.endf', 'tsl-OinBeO.endf'),
                    ('n-008_O_016.endf', 'tsl-OinC5O2H8.endf'),
                    ('n-008_O_016.endf', 'tsl-OinD2O.endf'),
                    ('n-008_O_016.endf', 'tsl-OinIceIh.endf'),
                    ('n-008_O_016.endf', 'tsl-OinMgO.endf'),
                    ('n-008_O_016.endf', 'tsl-OinPuO2.endf'),
                    ('n-008_O_016.endf', 'tsl-OinSiO2-alpha.endf'),
                    ('n-008_O_016.endf', 'tsl-OinUO2-100P.endf'),
                    ('n-008_O_016.endf', 'tsl-OinUO2-10P.endf'),
                    ('n-008_O_016.endf', 'tsl-OinUO2-5P.endf'),
                    ('n-008_O_016.endf', 'tsl-OinUO2.endf'),
                    ('n-008_O_016.endf', 'tsl-OinUO2-HALEU.endf'),
                    ('n-008_O_016.endf', 'tsl-OinUO2-HEU.endf'),
                    ('n-009_F_019.endf', 'tsl-FinBeF2.endf'),
                    ('n-009_F_019.endf', 'tsl-FinCF2.endf'),
                    ('n-009_F_019.endf', 'tsl-FinFLiBe.endf'),
                    ('n-009_F_019.endf', 'tsl-FinHF.endf'),
                    ('n-009_F_019.endf', 'tsl-FinMgF2.endf'),
                    ('n-012_Mg_024.endf', 'tsl-MginMgF2.endf'),
                    ('n-012_Mg_024.endf', 'tsl-MginMgO.endf'),
                    ('n-013_Al_027.endf', 'tsl-013_Al_027.endf'),
                    ('n-013_Al_027.endf', 'tsl-AlinAl2O3.endf'),
                    ('n-026_Fe_056.endf', 'tsl-026_Fe_056.endf'),
                    ('n-014_Si_028.endf', 'tsl-SiinSiC.endf'),
                    ('n-014_Si_028.endf', 'tsl-SiinSiO2-alpha.endf'),
                    ('n-014_Si_028.endf', 'tsl-SiO2-beta.endf'),
                    ('n-020_Ca_040.endf', 'tsl-CainCaH2.endf'),
                    ('n-039_Y_089.endf', 'tsl-YinYH2.endf'),
                    ('n-040_Zr_090.endf', 'tsl-ZrinZrC.endf'),
                    ('n-040_Zr_090.endf', 'tsl-ZrinZrH2.endf'),
                    ('n-040_Zr_090.endf', 'tsl-ZrinZrH.endf'),
                    ('n-040_Zr_090.endf', 'tsl-ZrinZrHx.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUC-100P.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUC-10P.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUC-5P.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUC.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUC-HALEU.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUC-HEU.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUN-100P.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUN-10P.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUN-5P.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUN.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUN-HALEU.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUN-HEU.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUO2-100P.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUO2-10P.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUO2-5P.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUO2.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUO2-HALEU.endf'),
                    ('n-092_U_238.endf', 'tsl-UinUO2-HEU.endf'),
                    ('n-092_U_238.endf', 'tsl-U-metal-100P.endf'),
                    ('n-092_U_238.endf', 'tsl-U-metal-10P.endf'),
                    ('n-092_U_238.endf', 'tsl-U-metal-5P.endf'),
                    ('n-092_U_238.endf', 'tsl-U-metal.endf'),
                    ('n-092_U_238.endf', 'tsl-U-metal-HALEU.endf'),
                    ('n-092_U_238.endf', 'tsl-U-metal-HEU.endf'),
                    ('n-094_Pu_239.endf', 'tsl-PuinPuO2.endf'),
                ],
            },
            'photon': {
                'base_url': 'https://www.nndc.bnl.gov/endf-releases/releases/B-VIII.1/',
                'compressed_files': [
                    'photoat/photoat-version.VIII.1.tar.gz',
                    'atomic_relax/atomic_relax-version.VIII.1.tar.gz',
                ],
                'checksums': [
                    '6d5f4830f6290d6c618803a8391ba0cf',
                    '70e9ca0c481236499b7a3e0a490f4ef2',
                ],
                'file_type': 'endf',
                'photo_files': endf_files_dir.joinpath('photon').rglob('photoat*.endf'),
                'atom_files': endf_files_dir.joinpath('photon').rglob('atom*.endf'),
            },
        }
    }

    # ==============================================================================
    # DOWNLOAD FILES FROM NNDC SITE

    if args.download:
        for particle in args.particles:
            details = release_details[args.release][particle]
            for i, f in enumerate(details['compressed_files']):
                url = details['base_url'] + f
                if 'checksums' in details.keys():
                    checksum = details['checksums'][i]
                    download(url, output_path=download_path / particle, checksum=checksum)
                else:
                    download(url, output_path=download_path / particle)

    # ==============================================================================
    # EXTRACT FILES FROM TGZ

    if args.extract:
        # Avoid deprecation warning on Python 3.12+
        extract_kwargs = {'filter': 'data'} if sys.version_info >= (3, 12) else {}

        for particle in args.particles:

            if release_details[args.release][particle]['file_type'] == 'wmp':
                extraction_dir = args.destination / particle
            elif release_details[args.release][particle]['file_type'] == 'endf':
                extraction_dir = endf_files_dir / particle
            Path.mkdir(extraction_dir, parents=True, exist_ok=True)

            for f in release_details[args.release][particle]['compressed_files']:
                fname = Path(f).name
                # Extract files different depending on compression method
                if fname.endswith('.zip'):
                    print(f'Extracting {fname}...')
                    with zipfile.ZipFile(download_path / particle / fname) as zipf:
                        # Extracts files without folder structure in the zip file
                        for member in zipf.namelist():
                            filename = Path(member).name
                            # skip directories
                            if not filename:
                                continue
                            source = zipf.open(member)
                            target = open(extraction_dir / filename, "wb")
                            with source, target:
                                copyfileobj(source, target)
                elif fname.endswith('.tar.gz'):
                    with tarfile.open(download_path / particle / fname, 'r') as tgz:
                        print(f'Extracting {fname}...')
                        # extract files ignoring the internal folder structure
                        for member in tgz.getmembers():
                            if member.isreg():
                                member.name = Path(member.name).name
                                tgz.extract(member, path=extraction_dir, **extract_kwargs)
                else:
                    # File is not compressed. Used for erratafiles. This ensures
                    # the n-005_B_010.endf erratafile overwrites the orginal
                    copy(download_path/particle/fname, extraction_dir/fname)

        if args.cleanup and download_path.exists():
            rmtree(download_path)

    # =========================================================================
    # PROCESS INCIDENT NEUTRON DATA

    # Create output directory if it doesn't exist
    for particle in args.particles:
        particle_destination = args.destination / particle
        particle_destination.mkdir(parents=True, exist_ok=True)

    library = openmc.data.DataLibrary()

    if 'neutron' in args.particles:
        particle = 'neutron'
        with Pool() as pool:
            details = release_details[args.release][particle]
            results = []
            for filename in details['endf_files']:

                # Skip neutron evaluation that fails the processing stage
                if filename.name == 'n-000_n_001.endf':
                    continue

                func_args = (filename, args.destination / particle, args.libver,
                             args.temperatures)
                r = pool.apply_async(process_neutron, func_args)
                results.append(r)

            for r in results:
                r.wait()

        for p in sorted((args.destination / particle).glob('*.h5'), key=sort_key):
            library.register_file(p)

    # =========================================================================
    # PROCESS THERMAL SCATTERING DATA

    if 'thermal' in args.particles:
        particle = 'thermal'
        with Pool() as pool:
            details = release_details[args.release][particle]
            results = []
            for path_neutron, path_thermal in details['sab_files']:
                func_args = (neutron_dir / path_neutron, thermal_dir / path_thermal,
                             args.destination / particle, args.libver)
                r = pool.apply_async(process_thermal, func_args)
                results.append(r)

            for r in results:
                r.wait()

        for p in sorted((args.destination / particle).glob('*.h5'), key=sort_key):
            library.register_file(p)


    # =========================================================================
    # INCIDENT PHOTON DATA

    if 'photon' in args.particles:
        particle = 'photon'
        details = release_details[args.release][particle]
        for photo_path, atom_path in zip(sorted(details['photo_files']),
                                        sorted(details['atom_files'])):
            # Generate instance of IncidentPhoton
            print('Converting:', photo_path.name, atom_path.name)
            data = openmc.data.IncidentPhoton.from_endf(photo_path, atom_path)

            # Export HDF5 file
            h5_file = args.destination / particle / f'{data.name}.h5'
            data.export_to_hdf5(h5_file, 'w', libver=args.libver)

            # Register with library
            library.register_file(h5_file)

    # =========================================================================
    # INCIDENT WMP NEUTRON DATA

    if 'wmp' in args.particles:
        for h5_file in sorted(Path(args.destination / 'wmp').rglob('*.h5')):
            library.register_file(h5_file)

    # Write cross_sections.xml
    library.export_to_xml(args.destination / 'cross_sections.xml')


if __name__ == '__main__':
    main()
