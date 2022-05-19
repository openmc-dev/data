#!/usr/bin/env python3

import argparse
import os
import tarfile
from pathlib import Path
from multiprocessing import Pool

import openmc.data

from openmc_data import download, state_download_size

description = """
Download random TENDL libraries from PSI and convert it to a HDF5 library for use with OpenMC. 
Only certain nuclides are available from PSI. This script generates a cross_sections_tendl.xml 
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
parser.add_argument(
    "-n",
    "--nuclides",
    choices=n_choices,
    nargs="+",
    default=["Fe56"],
    help="The nuclides to be downloaded. Available are: "
    "'O16','Si28', 'Si29','Si30', 'Fe54', 'Fe56', 'Fe57', 'Fe58', 'Na23', 'Pu240'. Use 'all' for all availiable",
)
parser.add_argument(
    "-d", "--destination", default=None, help="Directory to create new library in"
)
parser.add_argument(
    "-x",
    "--xlib",
    default=None,
    help="cross_section.xml library to add random evaluations to",
)
parser.add_argument("-b", "--batch", action="store_true", help="supresses standard in")
parser.add_argument(
    "-f",
    "--format_only",
    default=False,
    help="Only format previously sampled files to HDF5",
)

args = parser.parse_args()


def process_neutron_random(nuc, i, out_dir, in_dir, file_num):
    """Process ENDF neutron sublibrary file into HDF5 and write into a
    specified output directory."""

    fileIn = in_dir / f"{nuc}-{i}"
    fileOut = out_dir / f"{nuc}-{i}.h5"

    data = openmc.data.IncidentNeutron.from_njoy(fileIn)
    data.name = f"{nuc}-{i}"
    data.export_to_hdf5(fileOut, "w")
    if i % 40 == 0:
        print(f"Nuclide {nuc} {i}/{file_num} finished")


def main():

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
    script_dir = Path.cwd()

    library_name = "tendl_rand"  # this could be added as an argument to allow different libraries to be downloaded

    # the destination is decided after the release is know to avoid putting the release in a folder with a misleading name
    if args.destination is None:
        output_dir = script_dir / library_name
    else:
        output_dir = Path(args.destination).resolve()

    xlib = args.xlib
    if xlib == None:
        xlib = os.getenv("OPENMC_CROSS_SECTIONS")
    else:
        xlib = Path(xlib).resolve()

    endf_files_dir = output_dir / "endf"
    ace_files_dir = output_dir / "ace"
    hdf5_files_dir = output_dir / "hdf5"

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
            "file_num": 642,
            "down_size": 60,
            "file_size": 244,
            "is_it_ENDF": True,
            "gunzip": False,
        },
        "Si28": {
            "release": "ENDF2017",
            "filename": "Si028",
            "webname": "Si28",
            "file_num": 600,
            "down_size": 110,
            "file_size": 428,
            "is_it_ENDF": True,
            "gunzip": True,
        },
        "Si29": {
            "release": "ENDF2017",
            "filename": "Si029",
            "webname": "Si29",
            "file_num": 600,
            "down_size": 100,
            "file_size": 425,
            "is_it_ENDF": True,
            "gunzip": True,
        },
        "Si30": {
            "release": "ENDF2017",
            "filename": "Si030",
            "webname": "Si30",
            "file_num": 600,
            "down_size": 80,
            "file_size": 337,
            "is_it_ENDF": True,
            "gunzip": True,
        },
        "Fe54": {
            "release": "ENDF2017",
            "filename": "Fe054",
            "webname": "Fe054",
            "file_num": 501,
            "down_size": 320,
            "file_size": 1300,
            "is_it_ENDF": True,
            "gunzip": False,
        },
        "Fe56": {
            "release": "ENDF2017",
            "filename": "Fe056",
            "webname": "Fe056",
            "file_num": 614,
            "down_size": 410,
            "file_size": 1600,
            "is_it_ENDF": True,
            "gunzip": False,
        },
        "Fe57": {
            "release": "ENDF2017",
            "filename": "Fe057",
            "webname": "Fe057",
            "file_num": 733,
            "down_size": 525,
            "file_size": 2000,
            "is_it_ENDF": True,
            "gunzip": False,
        },
        "Fe58": {
            "release": "ENDF2017",
            "filename": "Fe058",
            "webname": "Fe058",
            "file_num": 501,
            "down_size": 280,
            "file_size": 1100,
            "is_it_ENDF": True,
            "gunzip": False,
        },
        "Na23": {
            "release": "ENDF2017",
            "filename": "Na023",
            "webname": "Na23",
            "file_num": 832,
            "down_size": 130,
            "file_size": 544,
            "is_it_ENDF": True,
            "gunzip": False,
        },
        "Pu240": {
            "release": "ENDF2017",
            "filename": "Pu240",
            "webname": "Pu240",
            "file_num": 630,
            "down_size": 200,
            "file_size": 900,
            "is_it_ENDF": True,
            "gunzip": False,
        },
    }

    if not format_only:

        download_file_size = 0
        uncompressed_file_size = 0
        num_of_files = 0

        for i in nuclides:
            download_file_size += nuclide_details[i]["down_size"]
            uncompressed_file_size += nuclide_details[i]["file_size"]
            num_of_files += nuclide_details[i]["file_num"]

        state_download_size(download_file_size, uncompressed_file_size, 'MB')
        extra_download_warning = f"""This corresponds to {num_of_files} random
            cross sections. The nuclides to be processed are: {nuclides}"""
        print(extra_download_warning)

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
            is_it_ENDF = nuclide_details[nucs]["is_it_ENDF"]
            out_dir = endf_files_dir if is_it_ENDF else ace_files_dir

            with tarfile.open(f, "r") as tgz:
                print(f"Extracting {f}...")
                tgz.extractall(path=out_dir / suffix)

        # ==============================================================================
        # Format file names

        for nucs in nuclides:
            f = nuclide_details[nucs]["webname"] + ".random.tgz"
            is_it_ENDF = nuclide_details[nucs]["is_it_ENDF"]
            numFiles = nuclide_details[nucs]["file_num"]

            if is_it_ENDF:
                out_dir = endf_files_dir / nucs
                prefix = "n-"
                suffix = "-rand-"

                for i in range(numFiles):
                    OldNumber = f"{i:04}"
                    OldFile = (
                        prefix + nuclide_details[nucs]["filename"] + suffix + OldNumber
                    )
                    newFile = f"{nucs}-{i+1}"

                    if nuclide_details[nucs]["gunzip"]:
                        os.system(f"gunzip {out_dir}/{OldFile}.gz")
                    (out_dir / OldFile).rename(out_dir / newFile)
            os.remove(f)

    # ==============================================================================
    # Convert ENDF files to HDF5 with njoy

    print("Beginning NJOY processing")
    with Pool() as pool:
        results = []
        for nuc in nuclides:

            file_num = nuclide_details[nuc]["file_num"]
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
        file_num = nuclide_details[nuc]["file_num"]
        out_dir = hdf5_files_dir / nuc
        for i in range(1, file_num + 1):
            fileOut = out_dir / f"{nuc}-{i}.h5"
            lib.register_file(fileOut)

    pre = output_dir / "cross_sections_pre.xml"
    post = output_dir / "cross_sections_tendl.xml"

    lib.export_to_xml(pre)
    if post.exists():
        command = f"combine_libraries.py -l {pre} {post} -o {post}"
        os.system(command)
    else:
        lib.export_to_xml(post)

    pre.unlink()


if __name__ == "__main__":
    main()
