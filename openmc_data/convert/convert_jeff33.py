#!/usr/bin/env python

"""
Convert JEFF 3.3 ACE data distributed by OECD/NEA into an HDF5 library that can
be used by OpenMC. It will download archives containing all the ACE files,
extract them, convert them, and write HDF5 files into a destination directory.
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urljoin

import openmc.data

from openmc_data import download, extract, state_download_size, all_release_details


# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"


class CustomFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    pass


parser = argparse.ArgumentParser(description=__doc__, formatter_class=CustomFormatter)
parser.add_argument(
    "-d",
    "--destination",
    type=Path,
    default=Path("jeff-3.3-hdf5"),
    help="Directory to create new library in",
)
parser.add_argument(
    "--download", action="store_true", help="Download tarball from OECD-NEA"
)
parser.add_argument(
    "--no-download",
    dest="download",
    action="store_false",
    help="Do not download tarball from OECD-NEA",
)
parser.add_argument("--extract", action="store_true", help="Extract zip files")
parser.add_argument(
    "--no-extract",
    dest="extract",
    action="store_false",
    help="Do not extract .tgz file if it has already been extracted",
)
parser.add_argument(
    "--libver",
    choices=["earliest", "latest"],
    default="earliest",
    help="Output HDF5 versioning. Use "
    "'earliest' for backwards compatibility or 'latest' for "
    "performance",
)
parser.add_argument(
    "-r",
    "--release",
    choices=["3.3"],
    default="3.3",
    help="The nuclear data library release version. "
    "The only currently supported option is 3.3.",
)
parser.add_argument(
    "-t",
    "--temperatures",
    choices=[
        "293",
        "600",
        "900",
        "1200",
        "1500",
        "1800",
    ],
    default=[
        "293",
        "600",
        "900",
        "1200",
        "1500",
        "1800",
    ],
    help="Temperatures to download in Kelvin",
    nargs="+",
)
parser.add_argument(
    "--cleanup",
    action="store_true",
    help="Remove download directories when data has " "been processed",
)
parser.add_argument(
    "--no-cleanup",
    dest="cleanup",
    action="store_false",
    help="Do not remove download directories when data has " "been processed",
)
parser.set_defaults(download=True, extract=True, cleanup=False)
args = parser.parse_args()


def key(p):
    """Return (temperature, atomic number, mass number, metastable)"""
    z, x, a, temp = p.stem.split("-")
    return int(temp), int(z), int(a[:-1]), a[-1]


def main():

    library_name = "jeff"

    cwd = Path.cwd()

    ace_files_dir = cwd.joinpath("-".join([library_name, args.release, "ace"]))
    download_path = cwd.joinpath("-".join([library_name, args.release, "download"]))

    # This dictionary contains all the unique information about each release.
    # This can be extended to accommodate new releases
    details = all_release_details[library_name][args.release]['neutron']

    # ==============================================================================
    # DOWNLOAD FILES FROM WEBSITE

    if args.download:
        state_download_size(details["compressed_file_size"], details["uncompressed_file_size"], 'GB')
        for f, t in zip(details["compressed_files"], details["temperatures"]):
            if t in args.temperatures or t is None:
                download(urljoin(details["base_url"], f), output_path=download_path)

    # ==============================================================================
    # EXTRACT FILES FROM TGZ

    if args.extract:
        extract(
            compressed_files=[
                download_path / f
                for f, t in zip(details["compressed_files"], details["temperatures"])
                if t in args.temperatures or t is None
            ],
            extraction_dir=ace_files_dir,
            del_compressed_file=args.cleanup,
        )

    # ==============================================================================
    # CONVERT INCIDENT NEUTRON FILES

    # Create output directory if it doesn't exist
    args.destination.mkdir(parents=True, exist_ok=True)

    lib = openmc.data.DataLibrary()

    for p in sorted(ace_files_dir.glob(details['neutron_files']), key=key):
        print(f"Converting: {p}")
        temp, z, a, m = key(p)

        data = openmc.data.IncidentNeutron.from_ace(p)
        if m == "m" and not data.name.endswith("_m1"):
            # Correct metastable
            data.metastable = 1
            data.name += "_m1"

        for T in list(filter(None, args.temperatures)):
            p_add = ace_files_dir / f"ace_{T}" / (p.stem.replace("293", T) + ".ace")
            print(f"Adding temperature: {p_add}")
            data.add_temperature_from_ace(p_add)

        h5_file = args.destination / f"{data.name}.h5"
        data.export_to_hdf5(h5_file, "w", libver=args.libver)
        lib.register_file(h5_file)

    # ==============================================================================
    # CONVERT THERMAL SCATTERING FILES

    thermal_mats = [
        "al-sap",
        "be",
        "ca-cah2",
        "d-d2o",
        "graph",
        "h-cah2",
        "h-ch2",
        "h-h2o",
        "h-ice",
        "h-zrh",
        "mesi",
        "mg",
        "o-d2o",
        "orto-d",
        "orto-h",
        "o-sap",
        "para-d",
        "para-h",
        "sili",
        "tolu",
    ]

    def thermal_temp(p):
        return int(p.stem.split("-")[-1])

    thermal_dir = ace_files_dir / details["thermal_files"]

    for mat in thermal_mats:
        for i, p in enumerate(
            sorted(thermal_dir.glob(f"{mat}*.ace"), key=thermal_temp)
        ):
            if i == 0:
                print(f"Converting: {p}")
                data = openmc.data.ThermalScattering.from_ace(p)
            else:
                print(f"Adding temperature: {p}")
                data.add_temperature_from_ace(p)

        h5_file = args.destination / f"{data.name}.h5"
        data.export_to_hdf5(h5_file, "w", libver=args.libver)
        lib.register_file(h5_file)

    lib.export_to_xml(args.destination / "cross_sections.xml")


if __name__ == "__main__":
    main()
