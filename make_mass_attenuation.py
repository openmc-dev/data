#!/usr/bin/env python
"""Obtain X-ray mass attenuation coefficients from the NIST Standard Reference
Database 126 (https://www.nist.gov/pml/x-ray-mass-attenuation-coefficients) and
write them to an HDF5 file.

For each element Z=1 to 92, the data is scraped from the individual element
pages on the NIST site. The resulting HDF5 file contains 92 datasets, each a
2D array with shape (2, N) where row 0 is photon energy in eV and row 1 is
the mass attenuation coefficient mu/rho in cm^2/g.
"""

import re
import time
from urllib.request import urlopen, Request

from lxml import html
import numpy as np
import h5py
from openmc.data import ATOMIC_SYMBOL


BASE_URL = 'https://physics.nist.gov/PhysRefData/XrayMassCoef/ElemTab/z{:02}.html'

# Pattern to match scientific notation floats (e.g. 1.00000E-03, 7.217E+00)
FLOAT_RE = re.compile(r'[0-9]+\.[0-9]+E[+-][0-9]+')

# ==============================================================================
# SCRAPE DATA FROM NIST SITE AND GENERATE MASS ATTENUATION HDF5 FILE

print('Generating mass_attenuation.h5...')

with h5py.File('mass_attenuation.h5', 'w') as f:

    for Z in range(1, 93):
        print(f'  Processing {ATOMIC_SYMBOL[Z]} (Z={Z})...')

        # Fetch page for this element
        url = BASE_URL.format(Z)
        req = Request(url, headers={'User-Agent': 'openmc-data/1.0'})
        with urlopen(req) as response:
            page = response.read()

        # Extract text within <pre> tags (the ASCII-formatted table)
        tree = html.fromstring(page)
        pre_text = tree.xpath('//pre//text()')

        # The data is in the last text node, after the underline separator.
        # Split on underlines and take the last part to skip the header.
        data_text = pre_text[-1]
        parts = data_text.split('____')
        data_section = parts[-1] if len(parts) > 1 else data_text

        # Extract all floats in scientific notation -- this cleanly skips
        # absorption edge labels (K, L1, L2, L3, M1, etc.) and any other text
        values = np.array([float(x) for x in FLOAT_RE.findall(data_section)])

        if len(values) % 3 != 0:
            raise ValueError(
                f'Number of parsed values ({len(values)}) for Z={Z} '
                f'is not divisible by 3'
            )

        # Reshape into rows of 3: energy, mu/rho, mu_en/rho
        table = values.reshape((-1, 3))

        # Create dataset as 2D array: row 0 = energy, row 1 = mu/rho
        data = np.vstack([1e6 * table[:, 0], table[:, 1]])
        f.create_dataset(f'{Z:03}', data=data)

        # Be respectful to the NIST server
        time.sleep(0.5)

print('Done! Wrote mass_attenuation.h5')
