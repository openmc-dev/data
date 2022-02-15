
import requests

from urls import all_release_details


def test_fendl_urls():
    print(all_release_details)

    for release, value in all_release_details['tendl'].items():

        for file in value['compressed_files']:
            url = value['base_url'] + file

            responce = requests.get(url, stream=True)
            assert responce.status_code == 200
