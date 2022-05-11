[![test_urls](https://github.com/shimwell/data/actions/workflows/test_urls.yml/badge.svg)](https://github.com/shimwell/data/actions/workflows/test_urls.yml)

# OpenMC Data Scripts

This repository contains a collection of scripts for generating HDF5 data
libraries that can be used with OpenMC. Some of these scripts convert existing
ACE libraries (such as those produced by LANL) whereas generate scripts use
NJOY to process ENDF files directly. Note that unless you are interested in
making a customized library, you can find pregenerated HDF5 libraries at
https://openmc.org. Another source of data libraries for OpenMC is the
[Windowed Multipole Library](https://github.com/mit-crpg/WMP_Library)
repository which enables on-the-fly Doppler broadening to an arbitrary
temperature.

# Prerequisites

You should have already installed OpenMC, see the [docs](https://docs.openmc.org/en/stable/quickinstall.html) for installation instructions.
# Installation


Currently the package can be installed from this temporary repository.

```bash
sudo pip install -e git+https://github.com/openmc-data-storage/openmc_data.git
```

In the future pip installing from PyPi or Conda could be provided


# Usage

Once install several scripts are added to your python path that are able to
download and process nuclear data.

The scripts accept input arguments, to find out the input arguments available
for a particular script run the script name with ```--help``` after the name.
For example:

```convert_fendl --help```

Two categories of scripts are available, those that generate h5 cross section
files for using in OpenMC and those that generate chain files for use in
depletion simulations.

## Cross Section

| Library | Release | Processed by | Download from [openmc.org](https://openmc.org/) | Download ACE files and convert HDF5 | Download ENDF files and generate HDF5 | Convert local ACE files |
|-|-|-|-|-|-|-|
| CENDL | 3.1<br>3.2 |  |  |  | generate_cendl |  |
| ENDF/B | VII.0 | LANL | :heavy_check_mark: |  |  | convert_mcnp70 |
| ENDF/B | VII.1 | LANL | :heavy_check_mark: |  |  | convert_mcnp71 |
| ENDF/B | VII.1 | NNDC | :heavy_check_mark: | convert_nndc71 | generate_endf |  |
| ENDF/B | VIII.0 | LANL | :heavy_check_mark: |  |  | convert_lib80x |
| ENDF/B | VIII.0 | NNDC | :heavy_check_mark: |  | generate_endf |  |
| FENDL | 2.1<br>3.0<br>3.1a<br>3.1d<br>3.2 |  |  | convert_fendl |  |  |
| JENDL | 4.0 |  |  |  | generate_jendl |  |
| JEFF | 3.2 |  | :heavy_check_mark: | convert_jeff32 |  |  |
| JEFF | 3.3 |  | :heavy_check_mark: | convert_jeff33 |  |  |
| TENDL | 2015<br>2017<br>2019<br>2021|  |  | convert_tendl |  |  |

## Depletion Chains

| Library | Release | Processed by | Download from [openmc.org](https://openmc.org/) | Download ENDF files and XML chain files |
|-|-|-|-|
|-|-|-|-|
TODO