#!/usr/bin/env python3

import argparse
import glob
import os
import sys
import tarfile
from pathlib import Path
from multiprocessing import Pool

import openmc.data

from utils import download

description = """
Download random TENDL libraries from PSI and convert it to a HDF5 library for use with OpenMC. 
Only certain nuclides are available from PSI. This script generates a cross_sections_Tendl.xml 
file with random TENDL evaluations plus a standard library located in 'OPENMC_CROSS_SECTIONS'
"""


class CustomFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    pass


n_choices = [
    "all",
    "O16",
    "Si28",
    "Si29",
    "Si30",
    "Fe54",
    "Fe56",
    "Fe57",
    "Fe58",
    "Na23",
    "Pu240",
]

parser = argparse.ArgumentParser(
    description=description, formatter_class=CustomFormatter
)
parser.add_argument("-n", "--nuclides", choices=n_choices, nargs="+",
                    default="Fe56", help="The nuclides to be downloaded. Available are: "
                    "'O16','Si28', 'Si29','Si30', 'Fe54', 'Fe56', 'Fe57', 'Fe58', 'Na23', 'Pu240'. Use 'all' for all availiable")
parser.add_argument( "-d", "--destination", default=None, 
                    help="Directory to create new library in")
parser.add_argument("-b", "--batch", action="store_true", 
                    help="supresses standard in")
parser.add_argument("-f", "--format_only", default=False,
                    help="Only format previously sampled files to HDF5")

args = parser.parse_args()

if "all" in args.nuclides:
    nuclides = [
        "O16",
        "Si28",
        "Si29",
        "Si30",
        "Fe54",
        "Fe56",
        "Fe57",
        "Fe58",
        "Na23",
        "Pu240",
    ]
else:
    nuclides = args.nuclides
scriptDir = Path.cwd()

library_name = "tendl_rand"  # this could be added as an argument to allow different libraries to be downloaded

# the destination is decided after the release is know to avoid putting the release in a folder with a misleading name
if args.destination is None:
    outputDir = scriptDir / library_name
else:
    outputDir = Path(args.destination).resolve()


endf_files_dir = outputDir / "endf"
ace_files_dir = outputDir / "ace"
hdf5_files_dir = outputDir / "hdf5"

format_only = args.format_only

release_details = {
    "ENDF2017": {
        "base_url": "https://tendl.web.psi.ch/tendl_2017/tar_files/",
        "ending": ".random.tgz",
    },
    "ENDF2015": {
        "base_url": "https://tendl.web.psi.ch/tendl_2015/tar_files/",
        "ending": ".random.tgz",
    },
    "ACE2015": {
        "base_url": "https://tendl.web.psi.ch/tendl_2015/tar_files/",
        "ending": ".10.2016.tgz",
    },
}

nuclide_details = {
    "O16": {
        "release": "ENDF2017",
        "filename": "O016",
        "webname": "O016",
        "fileNum": 642,
        "downSize": 60,
        "fileSize": 244,
        "isItENDF": True,
        "gunzip": False,
    },
    "Si28": {
        "release": "ENDF2017",
        "filename": "Si028",
        "webname": "Si28",
        "fileNum": 600,
        "downSize": 110,
        "fileSize": 428,
        "isItENDF": True,
        "gunzip": True,
    },
    "Si29": {
        "release": "ENDF2017",
        "filename": "Si029",
        "webname": "Si29",
        "fileNum": 600,
        "downSize": 100,
        "fileSize": 425,
        "isItENDF": True,
        "gunzip": True,
    },
    "Si30": {
        "release": "ENDF2017",
        "filename": "Si030",
        "webname": "Si30",
        "fileNum": 600,
        "downSize": 80,
        "fileSize": 337,
        "isItENDF": True,
        "gunzip": True,
    },
    "Fe54": {
        "release": "ENDF2017",
        "filename": "Fe054",
        "webname": "Fe054",
        "fileNum": 501,
        "downSize": 320,
        "fileSize": 1300,
        "isItENDF": True,
        "gunzip": False,
    },
    "Fe56": {
        "release": "ENDF2017",
        "filename": "Fe056",
        "webname": "Fe056",
        "fileNum": 614,
        "downSize": 410,
        "fileSize": 1600,
        "isItENDF": True,
        "gunzip": False,
    },
    "Fe57": {
        "release": "ENDF2017",
        "filename": "Fe057",
        "webname": "Fe057",
        "fileNum": 733,
        "downSize": 525,
        "fileSize": 2000,
        "isItENDF": True,
        "gunzip": False,
    },
    "Fe58": {
        "release": "ENDF2017",
        "filename": "Fe058",
        "webname": "Fe058",
        "fileNum": 501,
        "downSize": 280,
        "fileSize": 1100,
        "isItENDF": True,
        "gunzip": False,
    },
    "Na23": {
        "release": "ENDF2017",
        "filename": "Na023",
        "webname": "Na23",
        "fileNum": 832,
        "downSize": 130,
        "fileSize": 544,
        "isItENDF": True,
        "gunzip": False,
    },
    "Pu240": {
        "release": "ENDF2017",
        "filename": "Pu240",
        "webname": "Pu240",
        "fileNum": 630,
        "downSize": 200,
        "fileSize": 900,
        "isItENDF": True,
        "gunzip": False,
    },
}

if not format_only:

    downloadFileSize = 0
    uncompressedFileSize = 0
    NumOfFiles = 0

    for i in nuclides:
        downloadFileSize += nuclide_details[i]["downSize"]
        uncompressedFileSize += nuclide_details[i]["fileSize"]
        NumOfFiles += nuclide_details[i]["fileNum"]

    downloadSize = f"{downloadFileSize} MB"
    uncomFileSize = f"{uncompressedFileSize} MB"
    if downloadFileSize > 1000:
        downloadSize = f"{downloadFileSize / 1000} GB"
    if uncompressedFileSize > 1000:
        uncomFileSize = f"{uncompressedFileSize / 1000} GB"


    download_warning = """
    WARNING: This script will download {} of 
    data, which is {} of data when processed. 
    This corresponds to {} random crossections.

    The nuclides to be processed are: 
    {}

    Are you sure you want to continue? ([y]/n)
    """.format(
        downloadSize, uncomFileSize, NumOfFiles, nuclides
    )


    response = input(download_warning) if not args.batch else "y"
    if response.lower().startswith("n"):
        sys.exit()

    # ==============================================================================
    # DOWNLOAD FILES FROM WEBSITE

    files_complete = []
    for nucs in nuclides:
        # Establish connection to URL
        url = (
            release_details[nuclide_details[nucs]["release"]]["base_url"]
            + nuclide_details[nucs]["webname"]
            + release_details[nuclide_details[nucs]["release"]]["ending"]
        )
        print(f"Downloading {nucs}...")
        downloaded_file = download(url)

    # ==============================================================================
    # EXTRACT FILES FROM TGZ

    for nucs in nuclides:
        f = nuclide_details[nucs]["webname"] + ".random.tgz"
        suffix = nucs
        isItENDF = nuclide_details[nucs]["isItENDF"]
        outDir = endf_files_dir if isItENDF else ace_files_dir

        with tarfile.open(f, "r") as tgz:
            print(f"Extracting {f}...")
            tgz.extractall(path=outDir / suffix)

    # ==============================================================================
    # Format file names

    for nucs in nuclides:
        f = nuclide_details[nucs]["webname"] + ".random.tgz"
        isItENDF = nuclide_details[nucs]["isItENDF"]
        numFiles = nuclide_details[nucs]["fileNum"]

        if isItENDF:
            outDir = endf_files_dir / nucs
            prefix = "n-"
            suffix = "-rand-"

            for i in range(numFiles):
                OldNumber = f"{i:04}"
                OldFile = prefix + nuclide_details[nucs]["filename"] + suffix + OldNumber
                newFile = f"{nucs}-{i+1}"
                
                if nuclide_details[nucs]["gunzip"]:
                    os.system(f"gunzip {outDir} {OldFile}.gz")
                (outDir / OldFile).rename(outDir / newFile)
        os.remove(f)

# ==============================================================================
# Convert ENDF files to HDF5 with njoy

def process_neutron_random(nuc, i, outDir, inDir, fileNum):
    """Process ENDF neutron sublibrary file into HDF5 and write into a
    specified output directory."""

    fileIn = inDir / f"{nuc}-{i}"
    fileOut = outDir / f"{nuc}-{i}.h5"

    data = openmc.data.IncidentNeutron.from_njoy(fileIn)
    data.name = f"{nuc}-{i}"
    data.export_to_hdf5(fileOut, "w")
    if i % 40 == 0:
        print(f"Nuclide {nuc} {i}/{fileNum} finished")


print("Beginning NJOY processing")
with Pool() as pool:
    results = []
    for nuc in nuclides:

        fileNum = nuclide_details[nuc]["fileNum"]
        inDir = endf_files_dir / nuc
        outDir = hdf5_files_dir / nuc

        hdf5_files_dir.mkdir(exist_ok=True)
        outDir.mkdir(exist_ok=True)

        print(f"Beginning nuclide {nuc} ...")
        for i in range(1, fileNum + 1):
            func_args = (nuc, i, outDir, inDir, fileNum)
            r = pool.apply_async(process_neutron_random, func_args)
            results.append(r)

    for r in results:
        r.wait()

# ==============================================================================
# Create xml library

lib = openmc.data.DataLibrary()
lib = lib.from_xml(os.getenv("OPENMC_CROSS_SECTIONS"))  # Gets current

for nuc in nuclides:
    fileNum = nuclide_details[nuc]["fileNum"]
    outDir = hdf5_files_dir / nuc
    for i in range(1, fileNum + 1):
        fileOut = outDir / f"{nuc}-{i}.h5"
        lib.register_file(fileOut)


pre = outputDir / "cross_sections_PreT.xml"
post = outputDir / "cross_sections_Tendl.xml"

lib.export_to_xml(pre)
if post.exists():
    command = f"combine_libraries.py -l {pre} {post} -o {post}"
    os.system(command)
else:
    lib.export_to_xml(post)

pre.unlink()
