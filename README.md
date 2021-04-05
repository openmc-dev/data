# OpenMC Data Scripts

This repository contains a collection of scripts for generating HDF5 data
libraries that can be used with OpenMC.

Some of these scripts **convert** existing ACE libraries (such as those
produced by LANL) whereas **generate** scripts use NJOY to process ENDF files directly. Note that unless you are interested in making a customized library,
you can find pregenerated HDF5 libraries from:

- The [openmc.org](https://openmc.org) which provides compressed files for 
entire libraries.
- The [Windowed Multipole Library](https://github.com/mit-crpg/WMP_Library)
repository which enables on-the-fly Doppler broadening to an arbitrary temperature.
- [OpenMC data downloader](https://github.com/openmc-data-storage/openmc_data_downloader).
repository and package which provides just in time cross section downloading
for specific isotopes.

| Library | Release | Processed by | Download from [openmc.org](https://openmc.org/) | Download ACE files and convert HDF5 | Download ENDF files and generate HDF5 | Convert local ACE files | [OpenMC data downloader](https://github.com/openmc-data-storage/openmc_data_downloader) |
|-|-|-|-|-|-|-|-|
| CENDL | 3.1<br>3.2 |  |  |  | generate_cendl.py |  |
| ENDF/B | VII.0 | LANL | :heavy_check_mark: |  |  | convert_mcnp70.py |
| ENDF/B | VII.1 | LANL | :heavy_check_mark: |  |  | convert_mcnp71.py |
| ENDF/B | VII.1 | NNDC | :heavy_check_mark: | convert_nndc71.py | generate_endf.py |  |:heavy_check_mark: |
| ENDF/B | VIII.0 | LANL | :heavy_check_mark: |  |  | convert_lib80x.py |
| ENDF/B | VIII.0 | NNDC | :heavy_check_mark: |  | generate_endf.py |  |
| FENDL | 2.1<br>3.0<br>3.1a<br>3.1d |  |  | convert_fendl.py |  |  |3.1d :heavy_check_mark: |
| JENDL | 4.0 |  |  |  | generate_jendl.py |  |
| JEFF | 3.2 |  | :heavy_check_mark: | convert_jeff32.py |  |  | :heavy_check_mark: |
| JEFF | 3.3 |  | :heavy_check_mark: | convert_jeff33.py |  |  |
| TENDL | 2015 2017 2019 |  |  | convert_tendl.py |  |  | 2019 :heavy_check_mark: |
