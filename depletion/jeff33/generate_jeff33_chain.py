#!/usr/bin/env python3

import os
from pathlib import Path
from zipfile import ZipFile
from tarfile import TarFile

import openmc.deplete

from utils import download


URLS = [
    "https://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/JEFF33-n.tgz",
    "https://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/JEFF33-rdd.zip",
    "https://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/JEFF33-nfy.asc"
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
            if url.endswith(".tgz"):
                tar = TarFile.open(basename, "r")
                print("Extracting {}...".format(basename))
                tar.extractall()
                os.system("mv endf6 neutrons")
            elif url.endswith(".zip"):
                with ZipFile(basename, "r") as zf:
                    print("Extracting {}...".format(basename))
                    os.mkdir("decay")
                    zf.extractall("decay")
            else:
                os.system("./nfy_to_endf.sh " + str(basename))
        endf_dir = Path(".")

    decay_files = list((endf_dir / "decay").glob("*ASC"))
    neutron_files = list((endf_dir / "neutrons").glob("*jeff33"))
    nfy_files = list((endf_dir / "nfy").glob("*endf"))

    # check files exist
    for flist, ftype in [(decay_files, "decay"), (neutron_files, "neutron"),
                         (nfy_files, "neutron fission product yield")]:
        if not flist:
            raise IOError("No {} endf files found in {}".format(ftype, endf_dir))

    chain = openmc.deplete.Chain.from_endf(decay_files, nfy_files, neutron_files)
    chain.export_to_xml("chain_jeff33.xml")


if __name__ == "__main__":
    main()
