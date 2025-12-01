from contextlib import contextmanager
import hashlib
import sys
import tarfile
import tempfile
import warnings
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request

import openmc.data


_BLOCK_SIZE = 16384


def process_neutron(path, output_dir, libver, temperatures=None):
    """Process ENDF neutron sublibrary file into HDF5 and write into a
    specified output directory."""
    print(f'Converting: {path}')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            data = openmc.data.IncidentNeutron.from_njoy(
                path, temperatures=temperatures
            )
    except Exception as e:
        print(path, e)
        raise
    h5_file = output_dir / f'{data.name}.h5'
    print(f'Writing {h5_file} ...')
    data.export_to_hdf5(h5_file, 'w', libver=libver)


def process_thermal(path_neutron, path_thermal, output_dir, libver):
    """Process ENDF thermal scattering sublibrary file into HDF5 and write into a
    specified output directory."""
    print(f'Converting: {path_thermal}')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            data = openmc.data.ThermalScattering.from_njoy(
                path_neutron, path_thermal
            )
    except Exception as e:
        print(path_neutron, path_thermal, e)
        raise
    h5_file = output_dir / f'{data.name}.h5'
    print(f'Writing {h5_file} ...')
    data.export_to_hdf5(h5_file, 'w', libver=libver)


def download(url, checksum=None, as_browser=False, output_path=None, **kwargs):
    """Download file from a URL

    Parameters
    ----------
    url : str
        URL from which to download
    checksum : str or None
        MD5 checksum to check against
    as_browser : bool
        Change User-Agent header to appear as a browser
    output_path : str or Path
        Specifies a location to save the downloaded file
    kwargs : dict
        Keyword arguments passed to :func:`urllib.request.urlopen`

    Returns
    -------
    local_path : pathlib.Path
        Name of file written locally

    """
    if as_browser:
        page = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    else:
        page = url

    with urlopen(page, **kwargs) as response:
        # Get file size from header
        file_size = response.length

        local_path = Path(Path(urlparse(url).path).name)
        if output_path is None:
            output_path = Path.cwd()
        else:
            Path(output_path).mkdir(parents=True, exist_ok=True)
        local_path = output_path / local_path
        # Check if file already downloaded
        if local_path.is_file():
            if local_path.stat().st_size == file_size:
                print('Skipping {}, already downloaded'.format(local_path))
                return local_path

        # Copy file to disk in chunks
        print('Downloading {}... '.format(local_path), end='')
        downloaded = 0
        with open(local_path, 'wb') as fh:
            while True:
                chunk = response.read(_BLOCK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
                downloaded += len(chunk)
                status = '{:10}  [{:3.2f}%]'.format(
                    downloaded, downloaded * 100. / file_size)
                print(status + '\b'*len(status), end='', flush=True)
            print('')

    if checksum is not None:
        downloadsum = hashlib.md5(open(local_path, 'rb').read()).hexdigest()
        if downloadsum != checksum:
            raise OSError("MD5 checksum for {} does not match. If this is "
                          "your first time receiving this message, please "
                          "re-run the script. Otherwise, please contact "
                          "OpenMC developers by emailing "
                          "openmc-users@googlegroups.com.".format(local_path))

    return local_path


def extract(
    compressed_file,
    extraction_dir=None,
    del_compressed_file=False,
    verbose=True,
):
    """Extracts zip, tar.gz or tgz compressed files

    Parameters
    ----------
    compressed_file : path-like
        The file to extract.
    extraction_dir : str
        The directory to extract the files to.
    del_compressed_file : bool
        Whether the compressed file should be deleted (True) or not (False)
    verbose : bool
        Controls the printing to terminal, if True filenames of the extracted
        files will be printed.
    """
    if extraction_dir is None:
        extraction_dir = Path.cwd()
    else:
        extraction_dir = Path(extraction_dir)
    Path.mkdir(extraction_dir, parents=True, exist_ok=True)

    path = Path(compressed_file)

    if path.suffix == '.zip':
        with zipfile.ZipFile(path, 'r') as zipf:
            if verbose:
                print(f'Extracting {path} to {extraction_dir}')
            zipf.extractall(path=extraction_dir)

    elif path.suffix in {'.gz', '.bz2', '.xz', '.lzma', '.zst', '.tgz', '.tar'}:
        with tarfile.open(path, 'r') as tar:
            if verbose:
                print(f'Extracting {path} to {extraction_dir}')
            # Use filter argument for Python 3.12+ to avoid deprecation warning
            if sys.version_info >= (3, 12):
                tar.extractall(path=extraction_dir, filter='data')
            else:
                tar.extractall(path=extraction_dir)
    else:
        raise ValueError('File type not currently supported by extraction '
                         f'function {str(path)}')

    if del_compressed_file:
        path.unlink()


@contextmanager
def fix_missing_tpid(path):
    """Fix missing TPID line in ENDF-format file.

    Parameters
    ----------
    path : path-like
        Path to the original evaluation.

    Yields
    ------
    new_path : pathlib.Path
        Path to the new evaluation file with TPID line added.
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_f:
        temp_f.write(" "*69 + "1 0  0    0\n")
        temp_f.write(Path(path).read_text())
        temp_path = Path(temp_f.name)

    try:
        yield temp_path
    finally:
        temp_path.unlink()
