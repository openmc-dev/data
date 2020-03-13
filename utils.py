import hashlib
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request

_BLOCK_SIZE = 16384


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
    local_path : str
        Name of file written locally

    """
    if as_browser:
        page = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    else:
        page = url

    with urlopen(page, **kwargs) as response:
        # Get file size from header
        file_size = response.length

        # Check if file already downloaded
        local_path = Path(Path(urlparse(url).path).name)
        if output_path is not None:
            Path(output_path).mkdir(parents=True, exist_ok=True) 
        if local_path.is_file():
            if local_path.stat().st_size == file_size:
                print('Skipping {}, already downloaded'.format(local_path))
                return local_path

        # Copy file to disk in chunks
        print('Downloading {}... '.format(basename), end='')
        downloaded = 0
        with open(basename, 'wb') as fh:
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
        downloadsum = hashlib.md5(open(basename, 'rb').read()).hexdigest()
        if downloadsum != checksum:
            raise OSError("MD5 checksum for {} does not match. If this is "
                          "your first time receiving this message, please "
                          "re-run the script. Otherwise, please contact "
                          "OpenMC developers by emailing "
                          "openmc-users@googlegroups.com.".format(basename))

    return basename