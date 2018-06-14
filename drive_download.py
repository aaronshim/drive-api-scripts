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
import threading
import time

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
    # Use a new Drive service just for this thread.
    drive_service = discovery.build(
        'drive', 'v3', http=creds.authorize(Http()))
    # Rename file if a file with the same name already exists.
    if Path(location).is_file():
        logger.debug("File already exists at %s. Renaming." % location)
        location += '.1'
    # Actual download.
    logger.debug("Starting copying ID %s to %s" % (drive_id, location))
    try:
        request = drive_service.files().get_media(fileId=drive_id)
        with io.FileIO(location, 'w') as file:
            downloader = http.MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.debug("Download %d%% on %s." %
                             (int(status.progress() * 100), location))
        logger.info("Copied ID %s to %s" % (drive_id, location))
        # Check that our copying was correct.
        check_copied_file(drive_service, drive_id, location)
    except errors.HttpError as e:
        # TODO: Maybe we should have an export option instead for non-binary
        # types.
        logger.error(e)
        # Cleanup.
        os.remove(location)
        logger.info("Removing file %s." % location)


def check_copied_file(drive_service, drive_id, location):
    """
    Helper to check that a file on disk matches that on Drive.
    """
    logger.debug("Starting check of file at %s with ID %s" %
                 (location, drive_id))
    # Compute hash and file size of file on Drive.
    response = drive_service.files().get(
        fileId=drive_id, fields='id, md5Checksum, size').execute()
    if not 'size' in response or not 'md5Checksum' in response:
        logger.info("File %s with ID %s cannot be checked for size and checksum." % (
            location, drive_id))
        return
    # Compute hash and file size of file on disk.
    m = hashlib.md5()
    with open(location, 'rb') as file:
        for chunk in iter(lambda: file.read(131072), b""):
            m.update(chunk)
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


def get_files_in_directory(drive_service, drive_id):
    """
    Helper to provide an iterator for files in a given directory.
    """
    has_next = True
    request = drive_service.files().list(pageSize='1000', q="'%s' in parents" %
                                         drive_id, fields='*')
    response = request.execute()
    while has_next:
        files = response.get('files', [])
        for f in files:
            yield f
        if response.get('nextPageToken'):
            request = drive_service.files().list_next(
                previous_request=request, previous_response=response)
            response = request.execute()
        else:
            has_next = False


def take_care_of_threads(threads):
    """
    Makes sure 10 threads are running at a time.
    """
    running_threads = set(threading.enumerate())
    running_threads_in_queue = []
    not_started_in_queue = []
    for t in threads:
        if t in running_threads:
            running_threads_in_queue.append(t)
        elif t.ident is None:  # Not started yet.
            not_started_in_queue.append(t)
    for t in not_started_in_queue[:11 - len(running_threads)]:
        logger.debug("Starting download thread for %s" % t.name)
        t.start()


def safe_mkdir(path):
    """
    mkdir that only runs if the directory doesn't exist.
    """
    if Path(path).is_file():
        logger.fatal("Cannot mkdir to %s where a file already exists!" % path)
        exit(1)
    if not os.path.exists(path):
        os.mkdir(path)


# Figure out directory to start iterating from.
directory_to_start = input('ID of directory to download: ')
if directory_to_start == None or directory_to_start == '':
    directory_to_start = 'root'
directory_to_save = input('Path of directory to save to: ')
directory_queue = [(directory_to_start, directory_to_save)]

safe_mkdir(directory_queue[0][1])

# Breadth-first trasversal of our directory structure.
download_threads = []
while len(directory_queue) > 0:
    directory = directory_queue.pop(0)
    for f in get_files_in_directory(DRIVE, directory[0]):
        # Basic escaping.
        item_path = os.path.join(directory[1], f['name'].replace('/', '.'))
        if f['mimeType'] == 'application/vnd.google-apps.folder':
            # It's a folder.
            directory_queue.append((f['id'], item_path))
            logger.debug("Making directory %s" % item_path)
            safe_mkdir(item_path)
        else:
            # It's a file. Try to download it?
            logger.debug("Queing download of file %s with ID %s to %s" %
                         (f['name'], f['id'], item_path))
            thread = threading.Thread(target=copy_file, args=(
                f['id'], item_path), name=f['name'])
            download_threads.append(thread)
            # Basic thread manager.
            take_care_of_threads(download_threads)

# Wait for all downloads to finish.
live_threads = [t for t in download_threads if t.is_alive()]
while len(live_threads) > 0:
    logger.debug("Still running %s threads." % len(live_threads))
    take_care_of_threads(download_threads)
    time.sleep(1)
    live_threads = [t for t in download_threads if t.is_alive()]

logger.info('=======================FINISHED=======================')
