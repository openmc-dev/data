#!/usr/bin/env python
"""Generate mass energy-absorption coefficients from NIST SRD 126.

NIST Standard Reference Database 126 provides HTML tables of the photon mass
attenuation coefficient (mu/rho) and mass energy-absorption coefficient
(mu_en/rho) for elements with Z = 1 to 92.  This script downloads the HTML
tables and writes one zero-padded atomic-number dataset per element to an HDF5
file.  Each dataset has shape (2, N): row 0 contains photon energy in eV and
row 1 contains mu_en/rho in cm^2/g, matching the layout written by
``make_mass_attenuation.py``.

The source tables are available at:
https://www.nist.gov/pml/x-ray-mass-attenuation-coefficients
"""

import argparse
import re
import time
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from lxml import html
import h5py
import numpy as np


TABLE3_URL = 'https://pml.nist.gov/PhysRefData/XrayMassCoef/tab3.html'
USER_AGENT = 'openmc-data/1.0'
NUMERIC_RE = re.compile(
    r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'
)


def fetch(url):
    """Fetch *url* and return its response body."""
    request = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(request) as response:
        return response.read()


def parse_element_links(page):
    """Return ``{Z: (name, URL)}`` from the NIST Table 3 index page."""
    tree = html.fromstring(page)
    elements = {}

    for link in tree.xpath('//a[@href]'):
        href = link.get('href')
        match = re.search(r'(?:^|/)z(\d{2})\.html$', href, re.IGNORECASE)
        if match is None:
            continue

        z = int(match.group(1))
        name = ' '.join(link.text_content().split())
        elements[z] = (name, urljoin(TABLE3_URL, href))

    expected = set(range(1, 93))
    if set(elements) != expected:
        missing = sorted(expected - set(elements))
        extra = sorted(set(elements) - expected)
        message = 'Could not identify the complete NIST elemental table index'
        if missing:
            message += f'; missing Z={missing}'
        if extra:
            message += f'; unexpected Z={extra}'
        raise ValueError(message)

    return elements


def _row_numbers(row):
    """Return numeric values in an HTML table row.

    Most rows contain three cells.  Rows at absorption edges additionally
    contain a shell label such as ``K``; the fallback regular expression also
    handles the case where that label shares a cell with the energy value.
    """
    cells = row.xpath('./th|./td')
    values = []
    for cell in cells:
        text = ' '.join(cell.text_content().split())
        try:
            values.append(float(text.replace('D', 'E').replace('d', 'e')))
        except ValueError:
            pass

    if len(values) >= 3:
        return values[-3:]

    values = []
    for value in NUMERIC_RE.findall(row.text_content()):
        values.append(float(value.replace('D', 'E').replace('d', 'e')))
    return values[-3:]


def parse_element_table(page):
    """Parse one NIST element page into an ``(energy, mu_en/rho)`` array.

    The returned energy is converted from MeV to eV.  The middle column,
    mu/rho, is intentionally discarded.
    """
    tree = html.fromstring(page)
    candidates = []

    for table in tree.xpath('//table'):
        rows = []
        # The NIST page has an outer layout table containing the actual data
        # table.  Restrict rows to direct table children so that the outer
        # table is not mistaken for one giant data row.
        table_rows = table.xpath('./tr | ./thead/tr | ./tbody/tr | ./tfoot/tr')
        for row in table_rows:
            values = _row_numbers(row)
            if len(values) == 3 and 1e-3 <= values[0] <= 20.0:
                rows.append(values)
        if len(rows) > len(candidates):
            candidates = rows

    if not candidates:
        raise ValueError('No NIST data table rows found')

    values = np.asarray(candidates, dtype=float)
    energy = 1.0e6*values[:, 0]
    mu_en_rho = values[:, 2]
    return np.array([energy, mu_en_rho])


def generate(output='mass_energy_absorption.h5', delay=0.5):
    """Download NIST SRD 126 and write the elemental HDF5 library."""
    print(f'Generating {output}...')
    elements = parse_element_links(fetch(TABLE3_URL))

    with h5py.File(output, 'w') as f:
        for z, (name, url) in sorted(elements.items()):
            label = name or f'Z={z}'
            print(f'  Processing {label} (Z={z})...')
            data = parse_element_table(fetch(url))
            f.create_dataset(f'{z:03}', data=data)
            if delay:
                time.sleep(delay)

    print(f'Done! Wrote {output}')


def main():
    parser = argparse.ArgumentParser(
        description='Generate an HDF5 library of NIST mass energy-absorption '
        'coefficients for elemental media.'
    )
    parser.add_argument(
        '-o', '--output', default='mass_energy_absorption.h5',
        help='output HDF5 filename (default: %(default)s)'
    )
    parser.add_argument(
        '--delay', type=float, default=0.5,
        help='seconds to wait between element requests (default: %(default)s)'
    )
    args = parser.parse_args()
    generate(args.output, args.delay)


if __name__ == '__main__':
    main()
