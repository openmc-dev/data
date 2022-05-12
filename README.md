[![test_urls](https://github.com/shimwell/data/actions/workflows/test_urls.yml/badge.svg)](https://github.com/shimwell/data/actions/workflows/test_urls.yml)

[![test_package](https://github.com/openmc-data-storage/openmc_data/actions/workflows/test_package.yml/badge.svg)](https://github.com/openmc-data-storage/openmc_data/actions/workflows/test_package.yml)

[![test_convert_scripts](https://github.com/openmc-data-storage/openmc_data/actions/workflows/test_processing.yml/badge.svg)](https://github.com/openmc-data-storage/openmc_data/actions/workflows/test_processing.yml)



# OpenMC Data Scripts

This repository contains a collection of scripts for generating HDF5 data
libraries that can be used with OpenMC. Some of these scripts convert existing
ACE libraries (such as those produced by LANL) whereas generate scripts use
NJOY to process ENDF files directly. Note that unless you are interested in
making a customized library, you can find pregenerated HDF5 libraries at
[https://openmc.org](https://openmc.org). Another source of data libraries for OpenMC is the
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

| Script name | Library | Release | Processed by | Download available | Downloads ACE files and convert to HDF5 | Downloads ENDF files and convert to HDF5 | Convert local ACE files |
|-|-|-|-|-|-|-|-|
|generate_cendl| CENDL | 3.1<br>3.2 |  |  |  | :heavy_check_mark: |  |
|convert_mcnp70| ENDF/B | VII.0 | LANL | [https://openmc.org](https://openmc.org) |  |  | :heavy_check_mark: |
|convert_mcnp71| ENDF/B | VII.1 | LANL | [https://openmc.org](https://openmc.org) |  |  | :heavy_check_mark: |
|generate_endf| ENDF/B | VII.1 | NNDC | [https://openmc.org](https://openmc.org) |  | :heavy_check_mark: |  |
|convert_nndc71| ENDF/B | VII.1 | NNDC | [https://openmc.org](https://openmc.org) | :heavy_check_mark: | :heavy_check_mark: |  |
|convert_lib80x| ENDF/B | VIII.0 | LANL | [https://openmc.org](https://openmc.org) |  |  | :heavy_check_mark: |
|generate_endf| ENDF/B | VIII.0 | NNDC | [https://openmc.org](https://openmc.org) |  | :heavy_check_mark: |  |
|convert_fendl| FENDL | 2.1<br>3.0<br>3.1a<br>3.1d<br>3.2 |  |  | :heavy_check_mark: |  |  |
|generate_jendl| JENDL | 4.0 |  |  |  | :heavy_check_mark: |  |
|convert_jeff32| JEFF | 3.2 |  | [https://openmc.org](https://openmc.org) | :heavy_check_mark: |  |  |
|convert_jeff33| JEFF | 3.3 |  | [https://openmc.org](https://openmc.org) | :heavy_check_mark: |  |  |
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
| convert_tendl_rand | |
| sample_sandy | |
| make_compton | |
| make_stopping_powers | |
| add_branching_ratios | |
| reduce_chain | |
