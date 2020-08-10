#!/usr/bin/env python

import glob

from setuptools import setup

kwargs = {
    'name': 'nuclear-data-scripts',
    'version': "0.0.1",
    'scripts': glob.glob('nuclear-data-scripts/*.py'),

    # Metadata
    'author': 'The OpenMC Development Team',
    'author_email': 'openmc-dev@googlegroups.com',
    'description': 'OpenMC-nuclear-data',
    'url': 'https://openmc.org',
    'download_url': 'https://github.com/openmc-dev/data',
    'project_urls': {
        'Issue Tracker': 'https://github.com/openmc-dev/data/issues',
        'Documentation': 'https://docs.openmc.org',
        'Source Code': 'https://github.com/openmc-dev/data',
    },
    'classifiers': [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Topic :: Scientific/Engineering'
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    # Dependencies
    'python_requires': '>=3.5',
    'install_requires': [
        'numpy>=1.9', 'h5py'
    ],
}

setup(**kwargs)
