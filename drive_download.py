from __future__ import print_function

from apiclient import discovery, errors, http
from httplib2 import Http
from oauth2client import file, client, tools
from pathlib import Path
import hashlib
import io
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


def copy_file(drive_id, location):
    """
    Helper to download the Drive file to a local location.
    """
    # Rename file if a file with the same name already exists.
    if Path(location).is_file():
        logger.debug("File already exists at %s. Renaming." % location)
        location += '.1'
    # Actual download.
    logger.debug("Starting copying ID %s to %s" % (drive_id, location))
    try:
        request = DRIVE.files().get_media(fileId=drive_id)
        with io.FileIO(location, 'w') as file:
            downloader = http.MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.debug("Download %d%%." % int(status.progress() * 100))
        logger.info("Copied ID %s to %s" % (drive_id, location))
        # Check that our copying was correct.
        check_copied_file(drive_id, location)
    except errors.HttpError as e:
        # TODO: Maybe we should have an export option instead for non-binary
        # types.
        logger.error(e)
        # Cleanup.
        os.remove(location)
        logger.info("Removing file %s." % location)


def check_copied_file(drive_id, location):
    """
    Helper to check that a file on disk matches that on Drive.
    """
    logger.debug("Starting check of file at %s with ID %s" %
                 (location, drive_id))
    # Compute hash and file size of file on Drive.
    response = DRIVE.files().get(fileId=drive_id, fields='id, md5Checksum, size').execute()
    if not 'size' in response or not 'md5Checksum' in response:
        logger.info("File %s with ID %s cannot be checked for size and checksum." % (
            location, drive_id))
        return
    # Compute hash and file size of file on disk.
    m = hashlib.md5()
    with open(location, 'rb') as file:
        m.update(file.read())
    disk_md5 = m.hexdigest()
    disk_size = os.path.getsize(location)
    # Compare.
    if disk_md5 == response['md5Checksum']:
        logger.info("Checksum %s matches for file at %s with ID %s" %
                    (disk_md5, location, drive_id))
    else:
        logger.fatal("Checksums do not match for file at %s with ID %s: (%s, %s)" % (
            location, drive_id, disk_md5, response['md5Checksum']))
    if disk_size == int(response['size']):
        logger.info("Size %s matches for file at %s with ID %s" %
                    (disk_size, location, drive_id))
    else:
        logger.fatal("Sizes do not match for file at %s with ID %s: (%s, %s)" % (
            location, drive_id, disk_size, response['size']))


def get_files_in_directory(drive_id):
    """
    Helper to provide an iterator for files in a given directory.
    """
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

# Breadth-first trasversal of our directory structure.
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
