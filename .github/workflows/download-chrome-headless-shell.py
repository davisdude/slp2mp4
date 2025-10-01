import json
import pathlib
import sys
import urllib.request as urlrequest
import zipfile


def get_url(platform):
    json_url = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
    with urlrequest.urlopen(json_url) as response:
        body = response.read()
    data = json.loads(body)
    downloads=data["channels"]["Stable"]["downloads"]["chrome-headless-shell"]
    return [d["url"] for d in downloads if d["platform"] == platform][0]

def download_url(url, name):
    with urlrequest.urlopen(url) as data:
        with open(name, "wb") as f:
            f.write(data.read())

def extract_data(path):
    with zipfile.ZipFile(path, "r") as zfile:
        zfile.extractall(path=pathlib.Path("lib/"))

if __name__ == "__main__":
    url = get_url("win64")
    path = pathlib.Path("chrome-headless-shell.zip")
    download_url(url, path)
    extract_data(path)
