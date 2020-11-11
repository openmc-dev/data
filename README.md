# OpenMC Data Scripts

This repository contains a collection of scripts for generating and managing
data libraries that are used with OpenMC. The `convert_*.py` scripts convert
existing ACE libraries (such as those produced by LANL) into HDF5 libraries
whereas `generate_*.py` scripts use NJOY to process ENDF files directly.

**Note**: unless you are interested in making a customized library, you can find
pregenerated HDF5 libraries at https://openmc.org. Windowed multipole data,
which is needed for on-the-fly Doppler broadening, can be found at
https://github.com/mit-crpg/WMP_Library.

| Library | Release | Processed by | Download from [openmc.org](https://openmc.org/) | Download ACE files and convert HDF5 | Download ENDF files and generate HDF5 | Convert local ACE files |
|-|-|-|-|-|-|-|
| CENDL | 3.1 |  |  |  | generate_cendl.py |  |
| ENDF/B | VII.0 | LANL | :heavy_check_mark: |  |  | convert_mcnp70.py |
| ENDF/B | VII.1 | LANL | :heavy_check_mark: |  |  | convert_mcnp71.py |
| ENDF/B | VII.1 | NNDC | :heavy_check_mark: | convert_nndc71.py | generate_endf71.py |  |
| ENDF/B | VIII.0 | LANL | :heavy_check_mark: |  |  | convert_lib80x.py |
| ENDF/B | VIII.0 | NNDC | :heavy_check_mark: |  | generate_endf80.py |  |
| FENDL | 2.1 3.0 3.1a 3.1d |  |  | convert_fendl.py |  |  |
| JENDL | 4.0 |  |  |  | generate_jendl.py |  |
| JEFF | 3.2 |  | :heavy_check_mark: | convert_jeff32.py |  |  |
| JEFF | 3.3 |  | :heavy_check_mark: | convert_jeff33.py |  |  |
| TENDL | 2015 2017 2019 |  |  | convert_tendl.py |  |  |
