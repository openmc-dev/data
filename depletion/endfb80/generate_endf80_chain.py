#!/usr/bin/env python3

import os
from pathlib import Path
from zipfile import ZipFile

import openmc.deplete

from utils import download


URLS = [
    "https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_neutrons.zip",
    "https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_decay.zip",
    "https://www.nndc.bnl.gov/endf-b8.0/zips/ENDF-B-VIII.0_nfy.zip"
]


def main():
    endf_dir = os.environ.get("OPENMC_ENDF_DATA")
    if endf_dir is not None:
        endf_dir = Path(endf_dir)
    elif all(os.path.isdir(lib) for lib in ("neutrons", "decay", "nfy")):
        endf_dir = Path(".")
    else:
        for url in URLS:
            basename = download(url)
            with ZipFile(basename, "r") as zf:
                print("Extracting {}...".format(basename))
                zf.extractall()
                os.rename(str(basename).split(".zip")[0],
                          str(basename).split(".zip")[0].split("_")[1])
        endf_dir = Path(".")

    decay_files = list((endf_dir / "decay").glob("*endf"))
    neutron_files = list((endf_dir / "neutrons").glob("*endf"))
    nfy_files = list((endf_dir / "nfy").glob("*endf"))

    # check files exist
    for flist, ftype in [(decay_files, "decay"), (neutron_files, "neutron"),
                         (nfy_files, "neutron fission product yield")]:
        if not flist:
            raise IOError("No {} endf files found in {}".format(ftype, endf_dir))

    chain = openmc.deplete.Chain.from_endf(decay_files, nfy_files, neutron_files)
    chain.export_to_xml("chain_endfb80.xml")


if __name__ == "__main__":
    main()
