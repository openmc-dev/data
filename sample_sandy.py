#!/usr/bin/env python3

import argparse
import glob
import os
import sys
import tarfile
from multiprocessing import Pool
import re
import shutil
from pathlib import Path

import openmc.data


description = """
This scripts generates random (gaussian) evaluations of a nuclear data file following 
its covariance matrix using SANDY, and converts them to HDF5 for use in OpenMC. Script
generates a cross_sections.xml file with the standard library plus the sampled evaluations.
"""


class CustomFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    pass


parser = argparse.ArgumentParser(
    description=description, formatter_class=CustomFormatter)

parser.add_argument("-n", "--nuclides", nargs="+", 
                    default="Fe56", help="The nuclide(s) to be sampled")
parser.add_argument("-d", "--destination", default=None, 
                    help="Desitination of the endf library")
parser.add_argument("-o", "--outdir", default=None, 
                    help="Directory to create new library in")
parser.add_argument("-s", "--samples", default=200, 
                    help="Number of samples per nuclide")
parser.add_argument("-p", "--processes", default=1, 
                    help="number of worker processes (default = 1)")
parser.add_argument("-f", "--format_only", default=False,
                    help="Only format previously sampled files to HDF5")

args = parser.parse_args()
scriptDir = Path.cwd()

outdir = args.outdir
if outdir == None:
    outdir = scriptDir / "sandy_rand"
else:
    outdir = Path(outdir).resolve()

outdirEndf = outdir / "endf"
outdirHdf5 = outdir / "hdf5"

libdir = args.destination
if libdir == None:
    libdir = Path(os.getenv("NUCLEAR_DATA_DIR")) / "nndc-b7.1-endf"
else:
    libdir = Path(libdir).resolve()

nucs = args.nuclides

format_only = args.format_only

# ==============================================================================
# CHECK IF REQUEST IS VALID AND IF ENDF FILES EXIST

prefix = "n-"
suffix = ".endf"

atomicDict = openmc.data.ATOMIC_NUMBER
nucDict = {}

for nuc in nucs:
    massNum = int(re.findall("(\d+)", nuc)[0])
    atomicSym = "".join([i for i in nuc if not i.isdigit()])
    if atomicSym not in atomicDict.keys():
        print(f"Entered nuclide {nuc} does not have a valid atomic symbol")
        sys.exit()
    atomicNum = atomicDict[atomicSym]

    fileMass = f"{massNum:03}"
    fileAtomic = f"{atomicNum:03}"

    fileName = f"{prefix}{fileAtomic}_{atomicSym}_{fileMass}{suffix}"

    if not (libdir / "neutron" / fileName).isfile():
        print(f"File {libdir / "neutron" / fileName} does not exist")
        sys.exit()
    nucDict[nuc] = {
        "sym": atomicSym,
        "massNum": massNum,
        "atomicNum": atomicNum,
        "fileName": fileName,
    }

# ==============================================================================
# GENERATE RANDOM EVALUATIONS OF NUCLEAR DATA USING SANDY

if not format_only:
    outdir.mkdir(exist_ok=True)
    outdirEndf.mkdir(exist_ok=True)

    for nuc in nucs:

        nucDirEndf = outdirEndf / nuc
        nucDirEndf.mkdir(exist_ok=True)

        shutil.copyfile(
            libdir / "neutron" / nucDict[nuc]["fileName"],
            nucDirEndf / nucDict[nuc]["fileName"],
        )
        os.chdir(nucDirEndf)
        sandyCommand = f"sandy {nucDict[nuc]["fileName"]} --samples {args.samples} --outname {nuc} --processes {args.processes}"
        os.system(sandyCommand)

    os.chdir(scriptDir)

# ==============================================================================
# CONVERT RANDOM EVALUATIONS TO HDF5


def process_neutron_random(nuc, i, outDir, inDir, fileNum):  # Need to add temperatures
    """Process ENDF neutron sublibrary file into HDF5 and write into a
    specified output directory."""

    fileIn = inDir / f"{nuc}-{i}"
    fileOut = outDir / f"{nuc}-{i}.h5"

    data = openmc.data.IncidentNeutron.from_njoy(fileIn)  # , temperatures=293.6)
    data.name = f"{nuc}-{i}"
    data.export_to_hdf5(fileOut, "w")
    if i % 40 == 0:
        print(f"Nuclide {nuc} {i+1}/{fileNum} finished")


print("Beginning NJOY processing")
with Pool() as pool:
    results = []
    fileNum = int(args.samples)
    for nuc in nucs:

        inDir = outdirEndf / nuc
        outDir = outdirHdf5 / nuc

        outdirHdf5.mkdir(exist_ok=True)
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

for nuc in nucs:
    outDir = outdirHdf5 / nuc
    for i in range(1, fileNum + 1):
        fileOut = outDir / f"{nuc}-{i}.h5")
        lib.register_file(fileOut)

pre = outdir / "cross_sections_Pre.xml"
post = outdir / "cross_sections_Sandy.xml"

lib.export_to_xml(pre)
if post.exists():
    command = f"python combine_libraries.py -l {pre} {post} -o {post}"
    os.system(command)
else:
    lib.export_to_xml(post)

os.remove(pre)
