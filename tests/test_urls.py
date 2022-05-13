
import requests

from openmc_data import all_release_details


def test_tendl_urls():
    """Cycles through all the urls in each nuclear data library and checks
    that they return a status 200 code (success)"""

    print("library, release, particle, responce.status_code")
    for library, releases in all_release_details.items():
        for release, particles in releases.items():
            for particle, value in particles.items():
                for file in value['compressed_files']:
                    url = value['base_url'] + file
                    print(library, release, particle, url)
                    responce = requests.get(url, stream=True)
                    print(library, release, particle, url, responce.status_code)
                    # printing output so that in the event of a failure the
                    # failing url can be identified
                    assert responce.status_code == 200
