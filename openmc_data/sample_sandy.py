#!/usr/bin/env python3

import argparse
import os
import sys
from multiprocessing import Pool
import re
import shutil
from pathlib import Path

import openmc.data


description = """
This scripts generates random (gaussian) evaluations of a nuclear data file following 
its covariance matrix using SANDY, and converts them to HDF5 for use in OpenMC. Script
generates a cross_sections_sandy.xml file with the standard library plus the sampled evaluations.
"""


class CustomFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    pass


parser = argparse.ArgumentParser(
    description=description, formatter_class=CustomFormatter)

parser.add_argument("-n", "--nuclides", nargs="+", 
                    default=["Fe56"], help="The nuclide(s) to be sampled")
parser.add_argument("-d", "--destination", default=None, 
                    help="Directory to create new library in")
parser.add_argument("-l", "--libdir", default=None, 
                    help="Directory of endf library to sample eg. nndc-b7.1-endf folder")
parser.add_argument("-x", "--xlib", default=None, 
                    help="cross_section.xml library to add random evaluations to. Default is OPENMC_CROSS_SECTIONS")
parser.add_argument("-s", "--samples", default=200, 
                    help="Number of samples per nuclide")
parser.add_argument("-p", "--processes", default=1, 
                    help="number of worker processes (default = 1)")
parser.add_argument("-f", "--format_only", default=False,
                    help="Only format previously sampled files to HDF5")

args = parser.parse_args()


def main():

    script_dir = Path.cwd()

    output_dir = args.destination
    if output_dir == None:
        output_dir = script_dir / "sandy_rand"
    else:
        output_dir = Path(output_dir).resolve()

    endf_files_dir = output_dir / "endf"
    hdf5_files_dir = output_dir / "hdf5"

    libdir = args.libdir
    if libdir == None:
        raise Exception("Directory of ENDF library required for sampling, eg. nndc-b7.1-endf folder. Use -l prefix to specify")
    else:
        libdir = Path(libdir).resolve()

    xlib = args.xlib
    if xlib == None:
        xlib = os.getenv("OPENMC_CROSS_SECTIONS")
    else:
        xlib = Path(xlib).resolve()

    nuclides = args.nuclides

    format_only = args.format_only

    # ==============================================================================
    # CHECK IF REQUEST IS VALID AND IF ENDF FILES EXIST

    prefix = "n-"
    suffix = ".endf"

    atomic_dict = openmc.data.ATOMIC_NUMBER
    nuc_dict = {}

    for nuc in nuclides:
        mass_num = int(re.findall("(\d+)", nuc)[0])
        atomic_sym = "".join([i for i in nuc if not i.isdigit()])
        if atomic_sym not in atomic_dict.keys():
            print(f"Entered nuclide {nuc} does not have a valid atomic symbol")
            sys.exit()
        atomic_num = atomic_dict[atomic_sym]

        file_mass = f"{mass_num:03}"
        file_atomic = f"{atomic_num:03}"

        file_name = f"{prefix}{file_atomic}_{atomic_sym}_{file_mass}{suffix}"

        if not (libdir / "neutron" / file_name).is_file():
            print(f"File {libdir / 'neutron' / file_name} does not exist")
            sys.exit()
        nuc_dict[nuc] = {
            "sym": atomic_sym,
            "mass_num": mass_num,
            "atomic_num": atomic_num,
            "file_name": file_name,
        }

    # ==============================================================================
    # GENERATE RANDOM EVALUATIONS OF NUCLEAR DATA USING SANDY

    if not format_only:
        output_dir.mkdir(exist_ok=True)
        endf_files_dir.mkdir(exist_ok=True)

        for nuc in nuclides:

            nuc_dir_endf = endf_files_dir / nuc
            nuc_dir_endf.mkdir(exist_ok=True)

            shutil.copyfile(
                libdir / "neutron" / nuc_dict[nuc]["file_name"],
                nuc_dir_endf / nuc_dict[nuc]["file_name"],
            )
            os.chdir(nuc_dir_endf)
            sandy_command = f"sandy {nuc_dict[nuc]['file_name']} --samples {args.samples} --outname {nuc} --processes {args.processes}"
            os.system(sandy_command)

        os.chdir(script_dir)

    # ==============================================================================
    # CONVERT RANDOM EVALUATIONS TO HDF5


    def process_neutron_random(nuc, i, out_dir, in_dir, file_num):  # Need to add temperatures
        """Process ENDF neutron sublibrary file into HDF5 and write into a
        specified output directory."""

        fileIn = in_dir / f"{nuc}-{i}"
        fileOut = out_dir / f"{nuc}-{i}.h5"

        data = openmc.data.IncidentNeutron.from_njoy(fileIn)
        data.name = f"{nuc}-{i}"
        data.export_to_hdf5(fileOut, "w")
        if i % 40 == 0:
            print(f"Nuclide {nuc} {i+1}/{file_num} finished")


    print("Beginning NJOY processing")
    with Pool() as pool:
        results = []
        file_num = int(args.samples)
        for nuc in nuclides:

            in_dir = endf_files_dir / nuc
            out_dir = hdf5_files_dir / nuc

            hdf5_files_dir.mkdir(exist_ok=True)
            out_dir.mkdir(exist_ok=True)

            print(f"Beginning nuclide {nuc} ...")
            for i in range(1, file_num + 1):
                func_args = (nuc, i, out_dir, in_dir, file_num)
                r = pool.apply_async(process_neutron_random, func_args)
                results.append(r)

        for r in results:
            r.wait()


    # ==============================================================================
    # Create xml library

    lib = openmc.data.DataLibrary()
    lib = lib.from_xml(xlib)  # Gets current

    for nuc in nuclides:
        out_dir = hdf5_files_dir / nuc
        for i in range(1, file_num + 1):
            fileOut = out_dir / f"{nuc}-{i}.h5"
            lib.register_file(fileOut)

    pre = output_dir / "cross_sections_pre.xml"
    post = output_dir / "cross_sections_sandy.xml"

    lib.export_to_xml(pre)
    if post.exists():
        command = f"combine_libraries.py -l {pre} {post} -o {post}"
        os.system(command)
    else:
        lib.export_to_xml(post)

    pre.unlink()


if __name__ == '__main__':
    main()
