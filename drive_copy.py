from __future__ import print_function

from apiclient import discovery, errors
from httplib2 import Http
from oauth2client import file, client, tools
import json
import logging

# Set logging
logger = logging.getLogger('drive_copy')
logger.setLevel(logging.DEBUG)
log_file_handler = logging.FileHandler('drive_copy.log')
log_file_handler.setLevel(logging.INFO)
log_console_handler = logging.StreamHandler()
log_console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file_handler.setFormatter(formatter)
log_console_handler.setFormatter(formatter)
logger.addHandler(log_file_handler)
logger.addHandler(log_console_handler)
logger.info('=======================STARTING=======================')

# Set up auth for the API
SCOPES = 'https://www.googleapis.com/auth/drive'
store = file.Storage('storage.json') # This stores the OAuth tokens.
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('client_id.json', SCOPES)
    creds = tools.run_flow(flow, store)
DRIVE = discovery.build('drive', 'v3', http=creds.authorize(Http()))
logger.debug('Successfully authenticated.')

# Get relavant inputs
try:
    with open('files_to_copy.json', 'r') as f:
        files = json.load(f)
    logger.info('Attempting to copy %d files.', len(files))
    # Dict mapping file ID to file resource of copy.
    try:
        f = open('drive_copy_status.json', 'r+')
        status = json.loads(f.readlines()[-1]) # Just last line.
        logger.info('%d files already copied in a previous attempt.', len(status))
    except FileNotFoundError:
        f = open('drive_copy_status.json', 'w')
        status = {}
        logger.warning('No status file found. Starting from scratch.')
except json.decoder.JSONDecodeError as e:
    logger.fatal('Unable to decode status or list file. Quitting. %s', str(e))
    exit(1)

parent_id = input('Enter root Drive ID: ')
if not parent_id or parent_id == '':
    parent_id = 'root'
logger.info('Continuing with %s as the parent ID of copied files.', parent_id)

# Try copying.
for file_id in files:
    try:
        if not file_id in status:
            logger.debug("Attempting to copy file %s.", file_id)
            response = DRIVE.files().copy(fileId=file_id, body={'parents' : [parent_id]}).execute()
            logger.info("Copied file %s to %s", file_id, response['id'])
            logger.debug("Response: %s", response)
            status[file_id] = response
        else:
            logger.info("Already copied file %s in the past. Skipping.", file_id)
        # Checksum and size checks
        original_response = DRIVE.files().get(fileId=file_id, fields='id, md5Checksum, size').execute()
        logger.debug("Response: %s", original_response)
        if 'size' in original_response and 'md5Checksum' in original_response:
            checksum_response = DRIVE.files().get(fileId=status[file_id]['id'], fields='id, md5Checksum, size').execute()
            logger.debug("Response: %s", checksum_response)
            if checksum_response['md5Checksum'] == original_response['md5Checksum']:
                logger.info("Checksums match for file (%s, %s): %s %s", file_id, checksum_response['id'], checksum_response['md5Checksum'], original_response['md5Checksum'])
            else:
                logger.warning("Checksums do not match for file (%s, %s): %s %s", file_id, checksum_response['id'], checksum_response['md5Checksum'], original_response['md5Checksum'])
            if checksum_response['size'] == original_response['size']:
                logger.info("Sizes match for file (%s, %s): %s %s", file_id, checksum_response['id'], checksum_response['size'], original_response['size'])
            else:
                logger.warning("Sizes do not match for file (%s, %s): %s %s", file_id, checksum_response['id'], checksum_response['size'], original_response['size'])
        else:
            logger.info("Skipping checksum/size checks for %s because not binary.", file_id)
    except errors.HttpError as e:
        logger.fatal("Copying and verifying of %s failed: %s", file_id, str(e))

# This will most likely append because we've already read to the end of file.
f.write("\n")
json.dump(status, f)
f.close() # drive_copy_status.json
logger.info('=======================FINISHED=======================')