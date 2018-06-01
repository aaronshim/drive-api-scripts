from __future__ import print_function

from apiclient import discovery, errors
from httplib2 import Http
from oauth2client import file, client, tools
import json

# Set up auth for the API
SCOPES = 'https://www.googleapis.com/auth/drive.readonly.metadata'
# SCOPES = 'https://www.googleapis.com/auth/drive'
store = file.Storage('storage.json') # This stores the OAuth tokens.
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('client_id.json', SCOPES)
    creds = tools.run_flow(flow, store)
DRIVE = discovery.build('drive', 'v3', http=creds.authorize(Http()))

# Query! (While chasing the next page tokens.)
has_next = True
files_by_hash = {}
files_with_md5 = 0 # How many files with valid MD5's did we count?
total_files_seen = 0 # How many files were seen, MD5 or not?
request = DRIVE.files().list(fields='*') 
response = request.execute()
while has_next:
    files = response.get('files', [])
    for f in files:
        if 'md5Checksum' in f:
            if f['md5Checksum'] in files_by_hash:
                files_by_hash[f['md5Checksum']].append(f)
                print("%s conflicts with %s, both with a MD5 hash of %s." % (f['id'], files_by_hash[f['md5Checksum']][0]['id'], f['md5Checksum']))
            else:
                files_by_hash[f['md5Checksum']] = [f]
            files_with_md5+=1
    total_files_seen += len(files)
    print("%d files analyzed." % total_files_seen)
    if response.get('nextPageToken'):
        request = DRIVE.files().list_next(previous_request=request, previous_response=response)
        response = request.execute()
    else:
        has_next = False

print("%d total files checked for MD5." % files_with_md5)
with open('md5dedup.json', 'w') as outfile:
    json.dump(files_by_hash, outfile)