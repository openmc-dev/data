#!/usr/bin/env python

from pathlib import Path
import tarfile

import numpy as np
import h5py

from openmc_data.utils import download

def main():

    base_url = 'http://geant4.cern.ch/support/source/'
    version = '6.48'
    filename = f'G4EMLOW.{version}.tar.gz'

    # ==============================================================================
    # DOWNLOAD FILES FROM GEANT4 SITE

    download(base_url + filename)

    # ==============================================================================
    # EXTRACT FILES FROM TGZ

    g4dir = Path(f'G4EMLOW{version}')
    if not g4dir.is_dir():
        with tarfile.open(filename, 'r') as tgz:
            print(f'Extracting {filename}...')
            tgz.extractall()

    # ==============================================================================
    # GENERATE COMPTON PROFILE HDF5 FILE

    print('Generating compton_profiles.h5...')

    shell_file = g4dir / 'doppler' / 'shell-doppler.dat'

    with open(shell_file, 'r') as shell, h5py.File('compton_profiles.h5', 'w') as f:
        # Read/write electron momentum values
        pz = np.loadtxt(g4dir / 'doppler' / 'p-biggs.dat')
        f.create_dataset('pz', data=pz)

        for z in range(1, 101):
            # Create group for this element
            group = f.create_group(f'{z:03}')

            # Read data into one long array
            path = g4dir / 'doppler' / f'profile-{z}.dat'
            with open(path, 'r') as profile:
                j = np.fromstring(profile.read(), sep=' ')

            # Determine number of electron shells and reshape. Profiles are
            # tabulated against a grid of 31 momentum values.
            n_shells = j.size // 31
            j.shape = (n_shells, 31)

            # Write Compton profile for this Z
            group.create_dataset('J', data=j)

            # Determine binding energies and number of electrons for each shell
            num_electrons = []
            binding_energy = []
            while True:
                words = shell.readline().split()
                if words[0] == '-1':
                    break
                num_electrons.append(float(words[0]))
                binding_energy.append(float(words[1]))

            # Write binding energies and number of electrons
            group.create_dataset('num_electrons', data=num_electrons)
            group.create_dataset('binding_energy', data=binding_energy)


if __name__ == '__main__':
    main()
