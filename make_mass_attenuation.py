#!/usr/bin/env python
"""Obtain photon mass attenuation coefficients for elements Z=1 to 100 from the
NIST Standard Reference Database 8 (XCOM Photon Cross Sections Database,
https://www.nist.gov/pml/xcom-photon-cross-sections-database) and write them
to an HDF5 file.

Data are retrieved by submitting a POST request to the XCOM CGI for each
element. The resulting HDF5 file contains 100 datasets (keyed by zero-padded
atomic number, e.g. '001'--'100'), each a 2D array with shape (2, N) where
row 0 is photon energy in [eV] and row 1 is the mass attenuation coefficient
mu/rho (Total Attenuation with Coherent Scattering) in [cm^2/g].
"""

import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from lxml import html
import numpy as np
import h5py
from openmc.data import ATOMIC_SYMBOL


XCOM_URL = 'https://physics.nist.gov/cgi-bin/Xcom/xcom3_1'

# POST payload template
# OutOpt='PIC': all quantities in cm2/g
# Output='on':  include the standard energy grid
# NumAdd='1':   number of additional energy input rows (hidden field default)
# Graph0='on':  select "None" for graph (faster; data table is unaffected)
PAYLOAD_TEMPLATE = {
    'ZSym': '',
    'OutOpt': 'PIC',
    'Output': 'on',
    'NumAdd': '1',
    'Energies': '',
    'WindowXmin': '0.001',
    'WindowXmax': '100000',
    'ResizeFlag': 'on',
    'Graph0': 'on',
}

# ==============================================================================
# QUERY XCOM AND GENERATE MASS ATTENUATION HDF5 FILE

print('Generating mass_attenuation.h5...')

with h5py.File('mass_attenuation.h5', 'w') as f:

    for Z in range(1, 101):
        print(f'  Processing {ATOMIC_SYMBOL[Z]} (Z={Z})...')

        # Build and submit POST request for this element
        payload = urlencode(dict(PAYLOAD_TEMPLATE, ZNum=str(Z))).encode('utf-8')
        req = Request(XCOM_URL, data=payload, headers={'User-Agent': 'openmc-data/1.0'})
        with urlopen(req) as response:
            page = response.read()

        # Parse the HTML results table.
        # Row structure: rows 0-2 are headers; data rows follow.
        # Columns: 0=edge label, 1=energy(MeV), 2=coherent, 3=incoherent,
        #          4=photoelectric, 5=pair(nuclear), 6=pair(electron),
        #          7=total w/ coherent, 8=total w/o coherent
        tree = html.fromstring(page)
        trs = tree.xpath('//table//tr')

        energies = []
        mu_rho = []
        for tr in trs[3:]:  # skip 3 header rows
            tds = tr.xpath('.//td')
            cells = [td.text_content().strip() for td in tds]
            if len(cells) < 8:
                continue
            try:
                energies.append(1e6*float(cells[1]))  # convert MeV to eV
                mu_rho.append(float(cells[7]))  # total attenuation w/ coherent
            except ValueError:
                continue

        if not energies:
            raise ValueError(f'No data parsed for Z={Z}')

        # Convert to numpy arrays
        energies = np.array(energies)
        mu_rho = np.array(mu_rho)

        # Only include values up to 20 MeV
        mask = energies <= 20e6
        energies = energies[mask]
        mu_rho = mu_rho[mask]

        # Create dataset as 2D array: row 0 = energy (eV), row 1 = mu/rho (cm2/g)
        data = np.array([energies, mu_rho])
        f.create_dataset(f'{Z:03}', data=data)

        # Be respectful to the NIST server
        time.sleep(0.5)

print('Done! Wrote mass_attenuation.h5')
