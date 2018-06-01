# drive-api-scripts
Quick and dirty scripts to clean up my Google Drive files, using the Drive REST API.

## Prerequisites
You will need to install the [`google-api-python-client`](https://anaconda.org/conda-forge/google-api-python-client) library as detailed in Google's [quick start guide](https://developers.google.com/drive/api/v3/quickstart/python), using `pip` or `conda`.

You will also need to set up Drive API access in the [Google Developer Console](https://console.developers.google.com/flows/enableapi?apiid=drive). After enabling the Drive API for your newly created project, create a set of credentials and leave them in a `client_id.json` file in this directory. There are more specific directions on how to do this at this [codelab](https://codelabs.developers.google.com/codelabs/gsuite-apis-intro/).

## Scripts
`drive_list.py` Search the entire Google Drive contents for files matching the [query parameters](https://developers.google.com/drive/api/v3/search-parameters) specified. Has optional option to delete the found files.

`drive_dedup.py` Search the entire Google Drive contents for files with the same MD5 checksums. Will dump results into a MD5-indexed JSON object file `md5dedup.json`.

## Troubleshooting

The OAuth tokens are stored in a script-generated file called `storage.json`. Feel free to delete this file to reset the OAuth grant.