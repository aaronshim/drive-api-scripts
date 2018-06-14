from __future__ import print_function

from apiclient import discovery, errors
from httplib2 import Http
from oauth2client import file, client, tools
import json
import logging
import os

# Set logging
logger = logging.getLogger('drive_download')
logger.setLevel(logging.DEBUG)
log_file_handler = logging.FileHandler('drive_download.log')
log_file_handler.setLevel(logging.INFO)
log_console_handler = logging.StreamHandler()
log_console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file_handler.setFormatter(formatter)
log_console_handler.setFormatter(formatter)
logger.addHandler(log_file_handler)
logger.addHandler(log_console_handler)
logger.info('=======================STARTING=======================')

# Set up auth for the API
SCOPES = 'https://www.googleapis.com/auth/drive'
store = file.Storage('storage.json')  # This stores the OAuth tokens.
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('client_id.json', SCOPES)
    creds = tools.run_flow(flow, store)
DRIVE = discovery.build('drive', 'v3', http=creds.authorize(Http()))
logger.debug('Successfully authenticated.')

# Helper to download the Drive file to a local location.


def copy_file(drive_id, location):
    logger.info("Copying ID %s to %s" % (drive_id, location))
    # Equivalent to touch.
    open(location + drive_id, 'a').close()

# Helper to provide an iterator for files in a given directory.


def get_files_in_directory(drive_id):
    has_next = True
    request = DRIVE.files().list(pageSize='1000', q="'%s' in parents" %
                                 drive_id, fields='*')
    response = request.execute()
    while has_next:
        files = response.get('files', [])
        for f in files:
            yield f
        if response.get('nextPageToken'):
            request = DRIVE.files().list_next(
                previous_request=request, previous_response=response)
            response = request.execute()
        else:
            has_next = False


# Figure out directory to start iterating from.
directory_to_start = input('ID of directory to download: ')
if directory_to_start == None or directory_to_start == '':
    directory_to_start = 'root'
directory_queue = [(directory_to_start, 'root')]

os.mkdir('root')

while len(directory_queue) > 0:
    directory = directory_queue.pop(0)
    for f in get_files_in_directory(directory[0]):
        # Basic escaping.
        item_path = os.path.join(directory[1], f['name'].replace('/', '.'))
        if f['mimeType'] == 'application/vnd.google-apps.folder':
            # It's a folder.
            directory_queue.append((f['id'], item_path))
            logger.debug("Making directory %s" % item_path)
            os.mkdir(item_path)
        else:
            # It's a file. Try to download it?
            logger.debug("Downloading file %s with ID %s to %s" %
                         (f['name'], f['id'], item_path))
            copy_file(f['id'], item_path)

logger.info('=======================FINISHED=======================')
