#!/usr/bin/env python

import argparse
import pickle
import os.path
import logging
import pprint
import re
import sys

import googleapiclient.errors
import googleapiclient.discovery
import google_auth_oauthlib.flow
import google.auth.transport.requests

# Gmail filters don't have a name, and we don't want to hardcode the filter ID. So we
# use the first address in the the 'From' field as a magic identifier string. The filter
# to act on has to have this email first in 'From'.
MAGIC_FILTER_ADDR = 'spam@filter.invalid'

# The label that is used when initially creating the new filter to which email addresses
# will be added.
LABEL_STR = 'from-spam'

# Max number of email addresses in each filter. There is some limit to the length of the
# From field in a filter. This should keep the From field in each filter below the max
# length.
MAX_EMAILS_PER_FILTER = 30

# When modifying these scopes, delete the token.pickle file.
# The current list includes all scopes except 'https://mail.google.com/', which we
# don't need, and is not available to regular Gmail users.
# TODO: Check which scopes we actually need.
SCOPE_LIST = [
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.insert',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.metadata',
    'https://www.googleapis.com/auth/gmail.settings.basic',
]

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['add', 'list', 'from', 'test'],
                        help="Command")
    parser.add_argument(
        'email_str',
        nargs='?',
        default=None,
        metavar='email address',
        help="Sender email address to add to the spam filter",
    )
    logging.basicConfig(
        format='%(name)s %(levelname)-8s %(message)s', level=logging.DEBUG
    )
    logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)
    logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
    args = parser.parse_args()
    try:
        gmail = Gmail()
        if args.command == 'add':
            if args.email_str:
                gmail.add_email_to_filter(args.email_str)
            else:
                log.error("Email address required")
        elif args.command == 'list':
            gmail.list_filters()
        elif args.command == 'from':
            gmail.log_all_email_lists()
        elif args.command == 'test':
            for i in range(100):
                try:
                    gmail.add_email_to_filter(f'test{i}@test.invalid')
                except Exception as e:
                    log.debug(repr(e))
        else:
            raise AssertionError(f'Unknown command: {args.command}')
    except FilterError as e:
        log.error(str(e))
    except googleapiclient.errors.Error:
        log.exception(f'Unhandled exception from the Gmail API')
    except Exception:
        log.exception(f'Unhandled exception')


class Gmail:
    def __init__(self):
        self.token = self.get_token()
        self.service = googleapiclient.discovery.build(
            'gmail', 'v1', credentials=self.token
        )

    def list_filters(self):
        log.info('Filters:')
        filter_list = self.get_filter_generator()
        for filter_dict in filter_list:
            self.log_pp(filter_dict, 'Filter', log.info)
        if not filter_list:
            log.info('  <none>')

    def log_all_labels(self):
        results = self.service.users().labels().list(userId='me').execute()
        label_list = results.get('labels', [])
        if label_list:
            log.info('Labels:')
            for label in label_list:
                log.info(f'  {label["name"]}')
        raise FilterError('No labels found')

    def log_all_email_lists(self):
        for filter_dict in self.get_filter_generator():
            log.info(f'Filter ID: {filter_dict["id"]}')
            self.log_email_list(filter_dict)

    def log_email_list(self, filter_dict):
        log.info('From:')
        for email_str in self.get_email_list(filter_dict):
            log.info(f'  {email_str}')

    def add_email_to_filter(self, email_str):
        """Add a new email address to filter, creating the label and filter as required."""
        filter_dict = self.get_or_create_filter()
        email_list = self.get_email_list(filter_dict)
        if self.have_email(email_str):
            raise FilterError(f'Address already added. email="{email_str}"')
        email_list.insert(1, email_str)
        self.set_email_list(filter_dict, email_list)
        # There's no update API, so we ave to to create a new filter and delete the old
        # one. Including the filter ID for the old filter still causes Checked if filter
        # could be overwritten by including the old filter id, but it still just creates
        # a new filter.
        filter_id = filter_dict['id']
        filter_dict['id'] = None
        filters = self.service.users().settings().filters()
        filters.create(userId='me', body=filter_dict).execute()
        filters.delete(userId='me', id=filter_id).execute()
        log.info(f'Deleted previous version of filter: {filter_id}')
        log.info(f'Added address to filter. New "From" field: {email_str}')

    def get_filter_by_id(self, filter_id):
        filter_list = self.get_filter_generator()
        for filter_dict in filter_list:
            if filter_dict['id'] == filter_id:
                return filter_dict
        raise ItemDoesNotExist(f'Filter not found. id="{filter_id}"')

    def get_label_id(self, label_str):
        results = self.service.users().labels().list(userId='me').execute()
        label_list = results.get('labels', [])
        for label_dict in label_list:
            if label_dict["name"] == label_str:
                return label_dict['id']
        raise ItemDoesNotExist(f'Label does not exist. label_id={label_str}')

    def get_email_list(self, filter_dict):
        if 'from' in filter_dict['criteria']:
            return re.split(r'\s*OR\s*', filter_dict['criteria']['from'])
        return ['<empty>']

    def set_email_list(self, filter_dict, email_list):
        filter_dict['criteria']['from'] = ' OR '.join(email_list)

    def create_label(self, label_str):
        log.debug(f'Creating label. label_str={label_str}')
        labels = self.service.users().labels()
        result = labels.create(userId='me', body=dict(name=label_str)).execute()
        label_id = result.get("id")
        log.info(f'Created label. label_str="{label_str}" id="{label_id}"')
        return label_id

    def get_or_create_filter(self):
        """"""
        try:
            return self.get_open_filter()
        except ItemDoesNotExist:
            return self.create_filter_with_magic_email()

    def get_open_filter(self):
        """Get a filter that holds the magic email address as first entry and which has
        room for at least one email address.
        """
        for filter_dict in self.get_filter_generator():
            if self.get_email_list(filter_dict)[0] == MAGIC_FILTER_ADDR:
                email_list = self.get_email_list(filter_dict)
                if len(email_list) < MAX_EMAILS_PER_FILTER - 1:
                    return filter_dict
        raise ItemDoesNotExist(
            f'No filter found with first "From" address: {MAGIC_FILTER_ADDR}'
        )

    def have_email(self, email_str):
        for filter_dict in self.get_filter_generator():
            if email_str in self.get_email_list(filter_dict):
                return True
        return False

    def get_filter_generator(self):
        filters = self.service.users().settings().filters().list(userId='me').execute()
        for filter_dict in filters['filter']:
            yield filter_dict

    def create_filter_with_magic_email(self):
        try:
            label_id = self.get_label_id(LABEL_STR)
        except ItemDoesNotExist:
            label_id = self.create_label(LABEL_STR)
        filter_dict = {
            'criteria': {'from': MAGIC_FILTER_ADDR},
            'action': {'addLabelIds': [label_id], 'removeLabelIds': ['INBOX']},
        }
        filters = self.service.users().settings().filters()
        new_filter_dict = filters.create(userId='me', body=filter_dict).execute()
        # filter_id = result.get('id')
        log.info(f'Created filter: {new_filter_dict["id"]}')  # filter_id
        return new_filter_dict

    def log_pp(self, obj, msg=None, logger=log.debug):
        logger(f'{msg if msg else "Object"}:')
        for s in pprint.pformat(obj).splitlines(keepends=False):
            logger(f'  {s}')

    def get_token(self):
        token = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token_f:
                token = pickle.load(token_f)
        # If there are no (valid) credentials available, let the user log in.
        if not token or not token.valid:
            if token and token.expired and token.refresh_token:
                token.refresh(google.auth.transport.requests.Request())
            else:
                flow = (
                    google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPE_LIST
                    )
                )
                token = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token_f:
                pickle.dump(token, token_f)
        return token


class FilterError(Exception):
    pass


class ItemDoesNotExist(FilterError):
    pass


if __name__ == '__main__':
    sys.exit(main())
