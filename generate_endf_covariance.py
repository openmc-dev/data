#!/usr/bin/env python3

"""
generate_endf_with_cov.py

Download and process an ENDF/B library for use in OpenMC, then attach
multigroup MF=33 cross-section covariances (1500-group uniform-lethargy grid)
produced by NJOY/ERRORR to every incident-neutron HDF5 file.

This script is based on the existing generate_endf.py in openmc-dev/data,
extended with covariance processing.

Requires
--------
- openmc (with the MF=33 covariance PR merged)
- NJOY executable (set via --njoy or $NJOY environment variable)
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
import tarfile
import traceback
import zipfile
from multiprocessing import Pool
from pathlib import Path
from shutil import rmtree, copy, copyfileobj
from typing import Optional, Sequence

import numpy as np
import h5py
import openmc.data

from utils import download, process_neutron, process_thermal

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default covariance settings
# ---------------------------------------------------------------------------
DEFAULT_COV_GRID_EV = np.logspace(np.log10(1e-5), np.log10(20e6), 1501)
DEFAULT_COV_TEMPERATURE = 293.6
DEFAULT_EIG_TOL = 1e-10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass

def _build_release_details(endf_files_dir, neutron_dir, thermal_dir):
    return {
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
                    ('n-092_U_238.endf', 'tsl-UinUO2.endf'),
                ],
            },
            'photon': {
                'base_url': 'http://www.nndc.bnl.gov/endf-b7.1/zips/',
                'compressed_files': ['ENDF-B-VII.1-photoat.zip', 'ENDF-B-VII.1-atomic_relax.zip'],
                'checksums': ['5192f94e61f0b385cf536f448ffab4a4', 'fddb6035e7f2b6931e51a58fc754bd10'],
                'file_type': 'endf',
                'photo_files': endf_files_dir.joinpath('photon').rglob('photoat*.endf'),
                'atom_files': endf_files_dir.joinpath('photon').rglob('atom*.endf'),
            },
            'wmp': {
                'base_url': 'https://github.com/mit-crpg/WMP_Library/releases/download/v1.1/',
                'compressed_files': ['WMP_Library_v1.1.tar.gz'],
                'file_type': 'wmp',
            },
        },
        'viii.0': {
            'neutron': {
                'base_url': 'https://www.nndc.bnl.gov/endf-b8.0/',
                'compressed_files': ['zips/ENDF-B-VIII.0_neutrons.zip', 'erratafiles/n-005_B_010.endf'],
                'checksums': ['90c1b1a6653a148f17cbf3c5d1171859', 'eaf71eb22258f759abc205a129d8715a'],
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
                    ('n-092_U_238.endf', 'tsl-UinUO2.endf'),
                ],
            },
            'photon': {
                'base_url': 'https://www.nndc.bnl.gov/endf-b8.0/',
                'compressed_files': ['zips/ENDF-B-VIII.0_photoat.zip', 'erratafiles/atomic_relax.tar.gz'],
                'checksums': ['d49f5b54be278862e1ce742ccd94f5c0', '805f877c59ad22dcf57a0446d266ceea'],
                'file_type': 'endf',
                'photo_files': endf_files_dir.joinpath('photon').rglob('photoat*.endf'),
                'atom_files': endf_files_dir.joinpath('photon').rglob('atom*.endf'),
            },
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
                'checksums': ['6d5f4830f6290d6c618803a8391ba0cf', '70e9ca0c481236499b7a3e0a490f4ef2'],
                'file_type': 'endf',
                'photo_files': endf_files_dir.joinpath('photon').rglob('photoat*.endf'),
                'atom_files': endf_files_dir.joinpath('photon').rglob('atom*.endf'),
            },
        },
    }

# ---------------------------------------------------------------------------
# Neutron processing with covariance attachment
# ---------------------------------------------------------------------------
 
def process_neutron_with_covariance(
    endf_file,
    neutron_dest,
    libver,
    temperatures,
    *,
    njoy_exec,
    cov_energy_grid_ev=None,
    cov_temperature=293.6,
    eig_tol=1e-10,
):
    """Process a single ENDF neutron file: standard NJOY chain + optional
    MF=33 covariance attachment.
 
    If the covariance step fails (e.g. the evaluation lacks MF=33 data),
    the HDF5 file is still written with standard cross-section data.
    """
    from openmc.data.xs_covariance_njoy import NeutronXSCovariances
 
    # Step 1: standard NJOY processing (always runs)
    data = openmc.data.IncidentNeutron.from_njoy(
        endf_file,
        temperatures=temperatures,
        njoy_exec=njoy_exec,
    )
 
    # Step 2: covariance attachment (best-effort)
    if cov_energy_grid_ev is not None:
        try:
            cov = NeutronXSCovariances.from_endf(
                endf_file,
                cov_energy_grid_ev,
                njoy_exec=njoy_exec,
                temperature=cov_temperature,
                name=data.name,
                eig_tol=eig_tol,
            )
            data.mg_covariance = cov
            log.info("MF=33 covariance attached for %s", data.name)
        except Exception:
            log.warning(
                "MF=33 covariance skipped for %s (no MF=33 data or "
                "ERRORR failure):\n%s",
                data.name, traceback.format_exc(),
            )
 
    # Step 3: write HDF5 (always succeeds)
    h5_path = neutron_dest / f"{data.name}.h5"
    data.export_to_hdf5(h5_path, 'w', libver=libver)
    return h5_path
 
 
# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
 
def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=CustomFormatter,
    )
    parser.add_argument(
        '-d', '--destination', type=Path,
        help='Directory to create new library in',
    )
    parser.add_argument('--download', action='store_true',
                        help='Download files from NNDC')
    parser.add_argument('--no-download', dest='download', action='store_false')
    parser.add_argument('--extract', action='store_true',
                        help='Extract compressed files')
    parser.add_argument('--no-extract', dest='extract', action='store_false')
    parser.add_argument('--libver', choices=['earliest', 'latest'],
                        default='earliest', help='HDF5 versioning')
    parser.add_argument('-r', '--release',
                        choices=['vii.1', 'viii.0', 'viii.1'],
                        default='viii.1', help='ENDF/B release version')
    parser.add_argument('-p', '--particles',
                        choices=['neutron', 'thermal', 'photon', 'wmp'],
                        nargs='+', default=['neutron', 'thermal', 'photon'])
    parser.add_argument('--cleanup', action='store_true')
    parser.add_argument('--no-cleanup', dest='cleanup', action='store_false')
    parser.add_argument('--temperatures', type=float, nargs='+',
                        default=[250.0, 293.6, 600.0, 900.0, 1200.0, 2500.0])
    parser.add_argument('--njoy', type=str, default=None,
                        help='NJOY executable (falls back to $NJOY)')
    parser.add_argument('--no-covariance', action='store_true',
                        help='Skip MF=33 covariance processing')
    parser.set_defaults(download=True, extract=True, cleanup=False)
    args = parser.parse_args()
 
    def sort_key(path):
        if path.name.startswith('c_'):
            return (1000, path)
        else:
            return openmc.data.zam(path.stem)
 
    library_name = 'endfb'
    cwd = Path.cwd()
    endf_files_dir = cwd / '-'.join([library_name, args.release, 'endf'])
    neutron_dir = endf_files_dir / 'neutron'
    thermal_dir = endf_files_dir / 'thermal'
    download_path = cwd / '-'.join([library_name, args.release, 'download'])
    if args.destination is None:
        args.destination = Path('-'.join([library_name, args.release, 'hdf5']))
 
    release_details = _build_release_details(
        endf_files_dir, neutron_dir, thermal_dir,
    )
 
    # ---- Download ----
    if args.download:
        for particle in args.particles:
            details = release_details[args.release][particle]
            for i, f in enumerate(details['compressed_files']):
                url = details['base_url'] + f
                kw = {}
                if 'checksums' in details:
                    kw['checksum'] = details['checksums'][i]
                download(url, output_path=download_path / particle, **kw)
 
    # ---- Extract ----
    if args.extract:
        extract_kwargs = (
            {'filter': 'data'} if sys.version_info >= (3, 12) else {}
        )
        for particle in args.particles:
            ft = release_details[args.release][particle]['file_type']
            extraction_dir = (
                (args.destination / particle) if ft == 'wmp'
                else (endf_files_dir / particle)
            )
            extraction_dir.mkdir(parents=True, exist_ok=True)
            for f in release_details[args.release][particle]['compressed_files']:
                fname = Path(f).name
                if fname.endswith('.zip'):
                    print(f'Extracting {fname}...')
                    with zipfile.ZipFile(download_path / particle / fname) as zipf:
                        for member in zipf.namelist():
                            filename = Path(member).name
                            if not filename:
                                continue
                            with (zipf.open(member) as src,
                                  open(extraction_dir / filename, 'wb') as dst):
                                copyfileobj(src, dst)
                elif fname.endswith('.tar.gz'):
                    print(f'Extracting {fname}...')
                    with tarfile.open(
                        download_path / particle / fname, 'r',
                    ) as tgz:
                        for member in tgz.getmembers():
                            if member.isreg():
                                member.name = Path(member.name).name
                                tgz.extract(
                                    member, path=extraction_dir,
                                    **extract_kwargs,
                                )
                else:
                    copy(
                        download_path / particle / fname,
                        extraction_dir / fname,
                    )
        if args.cleanup and download_path.exists():
            rmtree(download_path)
 
    # ---- Output dirs ----
    for particle in args.particles:
        (args.destination / particle).mkdir(parents=True, exist_ok=True)
 
    library = openmc.data.DataLibrary()
 
    # ================================================================
    # NEUTRON
    # ================================================================
    if 'neutron' in args.particles:
        details = release_details[args.release]['neutron']
        neutron_dest = args.destination / 'neutron'
        endf_files = [
            f for f in details['endf_files']
            if f.name != 'n-000_n_001.endf'
        ]
 
        cov_grid = None if args.no_covariance else DEFAULT_COV_GRID_EV
 
        print(f"\nProcessing {len(endf_files)} neutron evaluations"
              f"{' (with MF=33 covariances)' if cov_grid is not None else ''}...")
 
        with Pool() as pool:
            results = []
            for fn in endf_files:
                r = pool.apply_async(
                    process_neutron_with_covariance,
                    (fn, neutron_dest, args.libver, args.temperatures),
                    dict(
                        njoy_exec=args.njoy,
                        cov_energy_grid_ev=cov_grid,
                        cov_temperature=DEFAULT_COV_TEMPERATURE,
                        eig_tol=DEFAULT_EIG_TOL,
                    ),
                )
                results.append((fn, r))
 
            for fn, r in results:
                try:
                    r.get()
                except Exception:
                    log.error(
                        "Processing FAILED for %s:\n%s",
                        fn.name, traceback.format_exc(),
                    )
 
        for p in sorted(neutron_dest.glob('*.h5'), key=sort_key):
            library.register_file(p)
 
    # ================================================================
    # THERMAL
    # ================================================================
    if 'thermal' in args.particles:
        details = release_details[args.release]['thermal']
        with Pool() as pool:
            results = []
            for path_n, path_t in details['sab_files']:
                r = pool.apply_async(
                    process_thermal,
                    (neutron_dir / path_n, thermal_dir / path_t,
                     args.destination / 'thermal', args.libver),
                )
                results.append(r)
            for r in results:
                r.wait()
        for p in sorted(
            (args.destination / 'thermal').glob('*.h5'), key=sort_key,
        ):
            library.register_file(p)
 
    # ================================================================
    # PHOTON
    # ================================================================
    if 'photon' in args.particles:
        details = release_details[args.release]['photon']
        for photo_path, atom_path in zip(
            sorted(details['photo_files']),
            sorted(details['atom_files']),
        ):
            print('Converting:', photo_path.name, atom_path.name)
            data = openmc.data.IncidentPhoton.from_endf(photo_path, atom_path)
            h5_file = args.destination / 'photon' / f'{data.name}.h5'
            data.export_to_hdf5(h5_file, 'w', libver=args.libver)
            library.register_file(h5_file)
 
    # ================================================================
    # WMP
    # ================================================================
    if 'wmp' in args.particles:
        for h5_file in sorted((args.destination / 'wmp').rglob('*.h5')):
            library.register_file(h5_file)
 
    # ---- cross_sections.xml ----
    library.export_to_xml(args.destination / 'cross_sections.xml')
    print(f"\nLibrary written to: {args.destination}")
 
 
if __name__ == '__main__':
    main()