# OpenMC Data Scripts

This repository contains a collection of scripts for generating HDF5 data
libraries that can be used with OpenMC. Some of these scripts convert existing
ACE libraries (such as those produced by LANL) whereas generate scripts use NJOY to
process ENDF files directly. Note that unless you are interested in making a
customized library, you can find pregenerated HDF5 libraries at
https://openmc.mcs.anl.gov.

|       |                      | Download HDF5 from https://openmc.mcs.anl.gov/ | Download ACE files and convert HDF5 | Download ENDF files and generate HDF5 | Convert local files |
|-------|----------------------|------------------------------------------------|-------------------------------------|---------------------------------------|---------------------|
| CENDL | 3.1                  |                                                |                                     | generate_cendl.py                     |                     |
| ENDF  | B-VII.1              | :heavy_check_mark:                             | convert_nndc71.py                   | generate_endf71.py                    |                     |
| EDNF  | B-VII.0              | :heavy_check_mark:                             |                                     | generate_endf80.py                    |                     |
| FENDL | 2.1, 3.0, 3.1a, 3.1d |                                                | convert_fendl.py                    |                                       |                     |
| JEFF  | 3.2                  | :heavy_check_mark:                             | convert_jeff32.py                   |                                       |                     |
| JEFF  | 3.3                  | :heavy_check_mark:                             | convert_jeff33.py                   |                                       |                     |
| MCNP  | 70                   | :heavy_check_mark:                             |                                     |                                       | convert_mcnp70.py   |
| MCNP  | 71                   | :heavy_check_mark:                             |                                     |                                       | convert_mcnp71.py   |
| MCNP  | 80x                  | :heavy_check_mark:                             |                                     |                                       | convert_lib80x.py   |