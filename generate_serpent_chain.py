#!/usr/bin/env python3
"""
Generate an equivalent depletion chain from Serpent data.

Two additional files are typically distributed with the Serpent
Monte Carlo code:

1) Radioactive decay file, typically ``sss_endfb7.dec``, and
2) Neutron-induced fission product yields, typically ``sss_endfb7.nfy.

These files can be used to create a :class:`openmc.deplete.Chain`, but
some cleanup steps have to be taken.

First, the files appear to be ENDF-6 formatted files concatenated
together. Unfortunately, there is a TEND record after each dataset,
so :func:`openmc.data.endf.get_evaluations` will only read and return
the first evaluation. For this reason, we must read the file until
all records have been found manually.

Secondly, the decay file does not have a tape indent (TPID) record,
which can throw off the first reading. This exception can be caught,
but it currently involves skipping the first item in the file. At the
time of this writing, this skipped item contains the decay data for a
neutron.

Lastly, there is a single negative uncertainty in the Co-55 k-shell
conversion energies. This quantity is not used in the depletion chain,
but it must be altered to prevent downstream failures.
"""
import os
import sys
from pathlib import Path
import argparse
import warnings

from openmc.data.endf import Evaluation
from openmc.deplete import Chain

# Make sure Python version is sufficient
assert sys.version_info >= (3, 6), "Python 3.6+ is required"


def get_decay_evals(decpath: Path):
    """Find all but the first decay record in the file

    Due to the lack of a TPID entry, the first line is skipped,
    throwing off the rest of the read process. The exception is
    caught, but the first decay item (neutron decay) is not stored.

    Co-55 fix is described here:
    https://github.com/openmc-dev/openmc/pull/1452#issuecomment-576773726
    """
    out = []
    EXPECTED_ASSERT = 1
    counted_assert = 0
    with decpath.open("r") as stream:
        while True:
            try:
                ev = Evaluation(stream)
            except AssertionError:
                if counted_assert < EXPECTED_ASSERT:
                    counted_assert += 1
                    continue
                raise
            except ValueError:
                break
            if ev.gnd_name == "Co55":
                # Fix negative uncertainty
                sec = ev.section[8, 457]
                ev.section[8, 457] = "0".join([sec[:762], sec[764:]])
            out.append(ev)
    print(f"Found {len(out)} items in {decpath}")
    print(f"  First: {out[0]}\n  Last: {out[-1]}")
    return out


def get_fpy_evals(fpypath: Path):
    """Obtain neutron-induced fission product yields from file"""
    # Can't use get_evaluations or else only one is returned
    out = []
    with fpypath.open("r") as stream:
        while stream:
            try:
                ev = Evaluation(stream)
            except ValueError:
                break
            out.append(ev)
    print(f"Found {len(out)} items in {fpypath}")
    print(f"  First: {out[0]}\n  Last: {out[-1]}")
    return out


class CustomFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    pass


parser = argparse.ArgumentParser(
    description="""Generate an equivalent depletion chain from Serpent data""",
    formatter_class=CustomFormatter,
)

parser.add_argument(
    "nfy", type=Path, help="Path to neutron-induced fission yield file",
)

parser.add_argument(
    "dec", type=Path, help="Path to radioactive decay file",
)

parser.add_argument(
    "--neutron-dir",
    type=Path,
    help=(
        "Path to ENDF-formatted incident neutron data. Defaults to pull "
        "data from OPENMC_ENDF_DATA if not provided"
    ),
)


parser.add_argument(
    "--branches-from",
    type=Path,
    help="Pull branching ratios from existing XML depletion chain",
)

parser.add_argument(
    "-o",
    "--output",
    type=Path,
    help="Write new depletion chain to this file",
    default="serpent_chain.xml",
)

args = parser.parse_args()

if not args.nfy.is_file():
    raise FileNotFoundError(args.nfy)

if not args.dec.is_file():
    raise FileNotFoundError(args.dec)

if args.neutron_dir is None:
    endfd = os.environ.get("OPENMC_ENDF_DATA")
    if endfd is None:
        raise EnvironmentError(
            "Need to pass neutron directory or set OPENMC_ENDF_DATA "
            "environment variable to find neutron reaction data"
        )
    neutron_dir = Path(endfd) / "neutrons"
else:
    neutron_dir = args.neutron_dir

if not neutron_dir.is_dir():
    raise NotADirectoryError(neutron_dir)

if args.output.exists() and not args.output.is_file():
    raise IOError(f"{args.output} exists but is not a file")

nfy_evals = get_fpy_evals(args.nfy)
dec_evals = get_decay_evals(args.dec)
neutrons = neutron_dir.glob("*.endf")

chain = Chain.from_endf(dec_evals, nfy_evals, neutrons)

if args.branches_from is not None:
    if not args.branches_from.is_file():
        raise FileNotFoundError(args.branches_from)
    other_br = Chain.from_xml(args.branches_from).get_branch_ratios()
    if other_br:
        chain.set_branch_ratios(other_br)
    else:
        warnings.warn(
            f"No branching ratios found in {args.branches_from}",
            RuntimeWarning,
        )

chain.export_to_xml(args.output)
