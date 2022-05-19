[![test_urls](https://github.com/shimwell/data/actions/workflows/test_urls.yml/badge.svg)](https://github.com/shimwell/data/actions/workflows/test_urls.yml)

[![test_package](https://github.com/openmc-data-storage/openmc_data/actions/workflows/test_package.yml/badge.svg)](https://github.com/openmc-data-storage/openmc_data/actions/workflows/test_package.yml)

[![test_convert_scripts](https://github.com/openmc-data-storage/openmc_data/actions/workflows/test_processing.yml/badge.svg)](https://github.com/openmc-data-storage/openmc_data/actions/workflows/test_processing.yml)


# OpenMC Data Scripts

This repository contains a collection of scripts for generating HDF5 data
libraries that can be used with OpenMC. Some of these scripts convert existing
ACE libraries (such as those produced by LANL) whereas generate scripts use
NJOY to process ENDF files directly

Note that unless you are interested in making a customized library, you can find pregenerated HDF5 libraries at [https://openmc.org](https://openmc.org).

Another source of data libraries for OpenMC is the [Windowed Multipole Library](https://github.com/mit-crpg/WMP_Library) repository which enables on-the-fly Doppler broadening to an arbitrary temperature.

# Prerequisites

You should have already installed OpenMC, see the [docs](https://docs.openmc.org/en/stable/quickinstall.html) for installation instructions.
# Installation


Currently the package can be installed from this temporary repository.

```bash
pip install git+https://github.com/openmc-data-storage/openmc_data.git
```

In the future pip installing from PyPi or Conda could be provided


# Usage

Once install several scripts are added to your python path that are able to
download and process nuclear data.

The scripts accept input arguments, to find out the input arguments available
for a particular script run the script name with ```--help``` after the name.
For example:

```convert_nndc71 --help```

A few categories of scripts are available:
<ul>
<li>Scripts that generate h5 cross section files for using in OpenMC from either ACE or ENDF files.</li>
<li>Scripts that generate chain files for use in depletion simulations. </li>
<li>Other scripts that don't fall into either category.</li>
</ul> 

## Cross Section

| Script name | Library | Release | Processed by | Download available | Downloads ACE files and convert to HDF5 | Downloads ENDF files and convert to HDF5 | Convert local ACE files |
|-|-|-|-|-|-|-|-|
|generate_cendl| CENDL | 3.1<br>3.2 |  |  |  | :heavy_check_mark: |  |
|convert_mcnp70| ENDF/B | VII.0 | LANL | [openmc.org](https://anl.box.com/shared/static/t25g7g6v0emygu50lr2ych1cf6o7454b.xz) |  |  | :heavy_check_mark: |
|convert_mcnp71| ENDF/B | VII.1 | LANL | [openmc.org](https://anl.box.com/shared/static/d359skd2w6wrm86om2997a1bxgigc8pu.xz) |  |  | :heavy_check_mark: |
|generate_endf| ENDF/B | VII.1 | NNDC | [openmc.org](https://anl.box.com/shared/static/9igk353zpy8fn9ttvtrqgzvw1vtejoz6.xz) |  | :heavy_check_mark: |  |
|convert_nndc71| ENDF/B | VII.1 | NNDC | [openmc.org](https://anl.box.com/shared/static/9igk353zpy8fn9ttvtrqgzvw1vtejoz6.xz) | :heavy_check_mark: | :heavy_check_mark: |  |
|convert_lib80x| ENDF/B | VIII.0 | LANL | [openmc.org](https://anl.box.com/shared/static/nd7p4jherolkx4b1rfaw5uqp58nxtstr.xz) |  |  | :heavy_check_mark: |
|generate_endf| ENDF/B | VIII.0 | NNDC | [openmc.org](https://anl.box.com/shared/static/uhbxlrx7hvxqw27psymfbhi7bx7s6u6a.xz) |  | :heavy_check_mark: |  |
|convert_fendl| FENDL | 2.1<br>3.0<br>3.1a<br>3.1d<br>3.2 |  | [openmc.org 3.2](https://anl.box.com/shared/static/3cb7jetw7tmxaw6nvn77x6c578jnm2ey.xz) | :heavy_check_mark: |  |  |
|generate_jendl| JENDL | 4.0 |  |  |  | :heavy_check_mark: |  |
|convert_jeff32| JEFF | 3.2 |  | [openmc.org](https://anl.box.com/shared/static/pb94oxriiipezysu7w4r2qdoufc2epxv.xz) | :heavy_check_mark: |  |  |
|convert_jeff33| JEFF | 3.3 |  | [openmc.org](https://anl.box.com/shared/static/ddetxzp0gv1buk1ev67b8ynik7f268hw.xz) | :heavy_check_mark: |  |  |
|convert_tendl| TENDL | 2015<br>2017<br>2019<br>2021|  |  | :heavy_check_mark: |  |  |

## Depletion Chains

| Sctipt name | Library | Release | Download available | Download ENDF files and generates XML chain files |
|-|-|-|-|-|
|generate_endf71_chain_casl|ENDF/B|-|[https://github.com/openmc-dev/data/tree/master/depletion](https://github.com/openmc-dev/data/tree/master/depletion)|:heavy_check_mark:|
|generate_endf71_chain|ENDF/B|-|[https://github.com/openmc-dev/data/tree/master/depletion](https://github.com/openmc-dev/data/tree/master/depletion)|:heavy_check_mark:|
|generate_serpent_fissq|-|-|[https://github.com/openmc-dev/data/tree/master/depletion](https://github.com/openmc-dev/data/tree/master/depletion)|:heavy_check_mark:|
|generate_tendl_chain|TENDL|2019<br>2021|[https://github.com/openmc-dev/data/tree/master/depletion](https://github.com/openmc-dev/data/tree/master/depletion)|:heavy_check_mark:|

## Other scripts


| Sctipt name | Description |
|-|-|
| convert_tendl_rand | Download random TENDL libraries from PSI and convert it to a HDF5 library for use with OpenMC. Only certain nuclides are available from PSI. This script generates a cross_sections_tendl.xml file with random TENDL evaluations plus a standard library located in 'OPENMC_CROSS_SECTIONS' |
| sample_sandy | This scripts generates random (gaussian) evaluations of a nuclear data file following its covariance matrix using SANDY, and converts them to HDF5 for use in OpenMC. Script generates a cross_sections_sandy.xml file with the standard library plus the sampled evaluations. |
| make_compton | |
| make_stopping_powers | |
| add_branching_ratios | Writes a depletion chain XML file from a depletion chain XML file and branching ratios |
| reduce_chain | |
