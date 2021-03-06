from __future__ import print_function

from apiclient import discovery, errors
from httplib2 import Http
from oauth2client import file, client, tools

import json

# Set up auth for the API
#SCOPES = 'https://www.googleapis.com/auth/drive.readonly.metadata'
SCOPES = 'https://www.googleapis.com/auth/drive'
store = file.Storage('storage.json') # This stores the OAuth tokens.
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('client_id.json', SCOPES)
    creds = tools.run_flow(flow, store)
DRIVE = discovery.build('drive', 'v3', http=creds.authorize(Http()))

# Get relavant inputs
list_query = input('Enter the query: ')
max_results = input('Maximum number of results? (Default is no limit)')
if max_results and max_results != '':
    max_results = int(max_results)
else:
    max_results = None

# Query! (While chasing the next page tokens.)
has_next = True
files_found = []
owners_found = {}
total_size = 0
request = DRIVE.files().list(pageSize=max_results, q=list_query, fields='*') 
response = request.execute()
while has_next:
    files = response.get('files', [])
    for f in files:
        if 'size' in f and 'md5Checksum' in f:
            total_size += int(f['size'])
            print(f['name'], f['mimeType'], f['size'], f['id'], f['md5Checksum'])
        else:
            print(f['name'], f['mimeType'], f['id'])
        # Keep track of owners
        for owner in f['owners']:
            if not owner['emailAddress'] in owners_found:
                owners_found[owner['emailAddress']] = 1
            else:
                owners_found[owner['emailAddress']] += 1
        # Know when to stop showing results.
        files_found.append(f)
        if max_results and len(files_found) >= max_results:
            has_next = False
            break
    if response.get('nextPageToken'):
        request = DRIVE.files().list_next(previous_request=request, previous_response=response)
        response = request.execute()
    else:
        has_next = False
print("%d files found." % len(files_found))
print("%d bytes total" % total_size)
print("Number of items per owner: %s" % owners_found)

# Optionally save Drive ID's into a file.
save = input('File name? ')
if save and save != '':
    with open(save + '.json', 'w') as outfile:
        json.dump([f['id'] for f in files_found], outfile)

# Now optionally delete the ones that are found.
delete = input('Delete? ')
sure = input('Are you sure? [Y/n] ')

if delete == 'yes' and sure == 'Y':
    for f in files_found:
        try:
            DRIVE.files().delete(fileId=f['id']).execute()
            print("Successfully deleted %s" % f['id'])
        except errors.HttpError as e:
            print(e)
