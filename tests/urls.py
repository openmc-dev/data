

all_release_details = {
    'tendl': {
            '2015': {
                'base_url': 'https://tendl.web.psi.ch/tendl_2015/tar_files/',
                'compressed_files': ['ACE-n.tgz'],
                'neutron_files': 'neutron_file/*/*/lib/endf/*-n.ace',
                'metastables': 'neutron_file/*/*/lib/endf/*m-n.ace',
                'compressed_file_size': '5.1 GB',
                'uncompressed_file_size': '40 GB'
            },
            '2017': {
                'base_url': 'https://tendl.web.psi.ch/tendl_2017/tar_files/',
                'compressed_files': ['tendl17c.tar.bz2'],
                'neutron_files': 'ace-17/*',
                'metastables': 'ace-17/*m',
                'compressed_file_size': '2.1 GB',
                'uncompressed_file_size': '14 GB'
            },
            '2019': {
                'base_url': 'https://tendl.web.psi.ch/tendl_2019/tar_files/',
                'compressed_files': ['tendl19c.tar.bz2'],
                'neutron_files': 'tendl19c/*',
                'metastables': 'tendl19c/*m',
                'compressed_file_size': '2.3 GB',
                'uncompressed_file_size': '10.1 GB'
            },
            '2021': {
                'base_url': 'https://tendl.web.psi.ch/tendl_2021/tar_files/',
                'compressed_files': ['tendl21c.tar.bz2'],
                'neutron_files': 'tendl21c/*',
                'metastables': 'tendl21c/*m',
                'compressed_file_size': '2.2 GB',
                'uncompressed_file_size': '10.5 GB'
            }
        }
}
