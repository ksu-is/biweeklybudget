"""
The latest version of this package is available at:
<http://github.com/jantman/biweeklybudget>

################################################################################
Copyright 2019 Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>

    This file is part of biweeklybudget, also known as biweeklybudget.

    biweeklybudget is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    biweeklybudget is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with biweeklybudget.  If not, see <http://www.gnu.org/licenses/>.

The Copyright and Authors attributions contained herein may not be removed or
otherwise altered, except to add the Author attribution of a contributor to
this work. (Additional Terms pursuant to Section 7b of the AGPL v3)
################################################################################
While not legally required, I sincerely request that anyone who finds
bugs please submit them at <https://github.com/jantman/biweeklybudget> or
to me via email, and that you send any contributions or improvements
either as a pull request on GitHub, or to me via email.
################################################################################

AUTHORS:
Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>
################################################################################


Requirements
------------

plaid-python>=3.0

Setup
-----

1. Download the Python quickstart from:
   https://github.com/plaid/quickstart/tree/master/python
2. Export your real ``PLAID_`` credential environment variables.
3. Run the quickstart.
4. Find your account and authenticate to it.
5. Record the ITEM_ID and ACCESS_TOKEN values.

References
----------

https://www.twilio.com/blog/2017/06/check-daily-spending-sms-python-plaid-twilio.html

https://github.com/madhat2r/plaid2text
"""

from datetime import datetime, timedelta, timezone
import os
import argparse
import logging
import json
from uuid import uuid4
from decimal import Decimal

import plaid

from ofxparse.ofxparse import (
    Ofx, Statement, Account, Institution, Transaction, Signon, AccountType
)

from biweeklybudget.cliutils import set_log_debug, set_log_info
from biweeklybudget.ofxapi import apiclient

logger = logging.getLogger(__name__)

# suppress requests logging
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)
requests_log.propagate = True


class PlaidGetter(object):

    @staticmethod
    def accounts(client):
        """
        Return a dict of account information of ofxgetter-enabled accounts,
        str account name to dict of information about the account.

        :param client: API client
        :type client: Instance of :py:class:`~.OfxApiLocal` or
          :py:class:`~.OfxApiRemote`
        :returns: dict of account information; see
          :py:meth:`~.OfxApiLocal.get_accounts` for details.
        :rtype: dict
        """
        return client.get_accounts()

    def __init__(self, client, savedir='./'):
        """
        Initialize PlaidGetter class.

        :param client: API client
        :type client: Instance of :py:class:`~.OfxApiLocal` or
          :py:class:`~.OfxApiRemote`
        :param savedir: directory/path to save statements in
        :type savedir: str
        """
        self._plaid = plaid.Client(
            client_id=os.getenv('PLAID_CLIENT_ID'),
            secret=os.getenv('PLAID_SECRET'),
            public_key=os.getenv('PLAID_PUBLIC_KEY'),
            environment=os.getenv('PLAID_ENV', 'development'),
            api_version='2019-05-29'
        )
        self._client = client
        self.savedir = savedir
        self._account_data = self.accounts(self._client)
        logger.debug('Initialized with data for %d accounts',
                     len(self._account_data))
        self.now_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    def get_ofx(self, account_name, write_to_file=True, days=30):
        """
        Download OFX from the specified account. Return it as a string.

        :param account_name: account name to download
        :type account_name: str
        :param write_to_file: if True, also write to a file named
          "<account_name>_<date stamp>.ofx"
        :type write_to_file: bool
        :param days: number of days of data to download
        :type days: int
        :return: OFX string
        :rtype: str
        """
        access_token = os.environ[f'PLAID_TOKEN_{account_name}']
        fname = None
        end_date = datetime.now()
        end_ds = end_date.strftime('%Y-%m-%d')
        start_date = end_date - timedelta(days=days)
        start_ds = start_date.strftime('%Y-%m-%d')
        logger.debug(
            'Downloading Plaid transactions for account: %s from %s to %s',
            account_name, start_ds, end_ds
        )
        txns = self._plaid.Transactions.get(
            access_token, start_ds, end_ds
        )
        logger.debug(txns)
        if write_to_file:
            fname = self._write_plaid_file(account_name, txns)
        with open('/tmp/jantman/plaidreal.json', 'w') as fh:
            fh.write(json.dumps(txns, sort_keys=True, indent=4))
        self._ofx_to_db(account_name, fname, txns, start_date, end_date)
        return txns

    def _ofx_to_db(self, account_name, fname, txns, start_dt, end_dt):
        """
        Put Plaid transaction data to the DB

        :param account_name: account name to download
        :type account_name: str
        :param fname: filename OFX was written to
        :type fname: str
        :param txns: Plaid transaction response
        :type txns: dict
        """
        logger.debug('Generating OFX')
        dt = datetime.now(timezone.utc)
        ofx = Ofx()
        ofx.account = Account()
        acct = txns['accounts'][0]
        ofx.account.account_id = acct['mask']
        ofx.account.curdef = acct['balances']['iso_currency_code']
        ofx.account.institution = Institution()
        ofx.account.institution.fid = '9999'
        ofx.account.institution.organization = txns['item']['institution_id']
        if txns['accounts'][0]['type'] == 'credit':
            ofx.account.type = AccountType.CreditCard
        else:
            ofx.account.type = AccountType.Unknown
        ofx.accounts = [ofx.account]
        ofx.headers = {
            'OFXHEADER': '100',
            'DATA': 'OFXSGML',
            'VERSION': '102',
            'SECURITY': None,
            'ENCODING': 'USASCII',
            'CHARSET': '1252',
            'COMPRESSION': None,
            'OLDFILEUID': None,
            'NEWFILEUID': str(uuid4()).replace('-', '')
        }
        ofx.signon = Signon({
            'code': 0,
            'severity': 'INFO',
            'message': 'Login successful',
            'dtserver': dt.strftime('%Y%m%d%H%M%S.000[0:UTC]'),
            'language': 'ENG',
            'dtprofup': None,
            'fi_org': txns['item']['institution_id'],
            'fi_fid': '9999',
            'intu.bid': None,
            'org': txns['item']['institution_id'],
            'fid': '9999'
        })
        ofx.status = {'code': 0, 'severity': 'INFO'}
        ofx.trnuid = str(uuid4()).replace('-', '')
        # build the statement...
        stmt = Statement()
        stmt.start_date = start_dt
        stmt.end_date = end_dt
        stmt.balance = Decimal(acct['balances']['current'])
        stmt.balance_date = end_dt
        stmt.currency = acct['balances']['iso_currency_code']
        ofx.account.statement = stmt
        stmt.transactions = []
        trans = txns['transactions']
        if len(trans) != txns['total_transactions']:
            raise RuntimeError(
                f'ERROR: Plaid response indicates {txns["total_transactions"]}'
                f' total transactions but only contains {len(trans)} '
                f'transactions.'
            )
        for pt in trans:
            t = Transaction()
            t.amount = Decimal(str(pt['amount']))
            t.date = datetime.strptime(pt["date"], '%Y-%m-%d')
            t.id = pt['payment_meta']['reference_number']
            t.payee = pt['name']
            stmt.transactions.append(t)
        logger.debug('Updating OFX in DB')
        _, count_new, count_upd = self._client.update_statement_ofx(
            self._account_data[account_name]['id'], ofx, filename=fname
        )
        logger.info('Account "%s" - inserted %d new OFXTransaction(s), updated '
                    '%d existing OFXTransaction(s)',
                    account_name, count_new, count_upd)
        logger.debug('Done updating OFX in DB')

    def _write_plaid_file(self, account_name, data):
        """
        Write Plaid data to a file.

        :param account_name: account name
        :type account_name: str
        :param data: Plaid API response
        :type data: dict
        :returns: name of the file that was written
        :rtype: str
        """
        if not os.path.exists(os.path.join(self.savedir, account_name)):
            os.makedirs(os.path.join(self.savedir, account_name))
        fname = '%s_%s.plaid.json' % (account_name, self.now_str)
        fpath = os.path.join(self.savedir, account_name, fname)
        j = json.dumps(data)
        logger.debug('Writing %d bytes of Plaid JSON to: %s', len(j), fpath)
        with open(fpath, 'w') as fh:
            fh.write(j)
        logger.debug('Wrote Plaid JSON data to: %s', fpath)
        return fname


def parse_args():
    p = argparse.ArgumentParser(description='Download Plaid transactions')
    p.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                   help='verbose output. specify twice for debug-level output.')
    p.add_argument('-l', '--list-accts', dest='list', action='store_true',
                   help='list accounts and exit')
    p.add_argument('-r', '--remote', dest='remote', action='store', type=str,
                   default=None,
                   help='biweeklybudget API URL to use instead of direct DB '
                        'access')
    p.add_argument('--ca-bundle', dest='ca_bundle', action='store', type=str,
                   default=None,
                   help='Path to CA certificate bundle file or directory to '
                        'use for SSL verification')
    p.add_argument('--client-cert', dest='client_cert', action='store',
                   type=str, default=None,
                   help='path to client certificate to use for SSL client '
                        'cert auth')
    p.add_argument('--client-key', dest='client_key', action='store',
                   type=str, default=None,
                   help='path to unencrypted client key to use for SSL client '
                        'cert auth, if key is not contained in the cert file')
    p.add_argument('-s', '--save-path', dest='save_path', action='store',
                   type=str, default=None,
                   help='Statement save path; must be specified when running '
                        'in remote (-r) mode.')
    p.add_argument('-d', '--days', dest='days', action='store', type=int,
                   default=30,
                   help='number of days of history to get; default 30')
    p.add_argument('ACCOUNT_NAME', type=str, action='store', default=None,
                   nargs='?',
                   help='Account name; omit to download all accounts')
    args = p.parse_args()
    return args


def main():
    global logger
    format = "[%(asctime)s %(levelname)s] %(message)s"
    logging.basicConfig(level=logging.WARNING, format=format)
    logger = logging.getLogger()

    args = parse_args()

    # set logging level
    if args.verbose > 1:
        set_log_debug(logger)
    elif args.verbose == 1:
        set_log_info(logger)
    if args.verbose <= 1:
        # if we're not in verbose mode, suppress routine logging for cron
        lgr = logging.getLogger('alembic')
        lgr.setLevel(logging.WARNING)
        lgr = logging.getLogger('biweeklybudget.db')
        lgr.setLevel(logging.WARNING)

    client = apiclient(
        api_url=args.remote, ca_bundle=args.ca_bundle,
        client_cert=args.client_cert, client_key=args.client_key
    )
    if args.list:
        for k in sorted(PlaidGetter.accounts(client).keys()):
            print(k)
        raise SystemExit(0)

    if args.remote is None:
        from biweeklybudget import settings
        save_path = settings.STATEMENTS_SAVE_PATH
    else:
        if args.save_path is None:
            logger.error('ERROR: -s|--save-path must be specified when running '
                         'in remote mode.')
            raise SystemExit(1)
        save_path = os.path.abspath(args.save_path)

    getter = PlaidGetter(client, save_path)

    if args.ACCOUNT_NAME is not None:
        getter.get_ofx(args.ACCOUNT_NAME, days=args.days)
        raise SystemExit(0)
    # else all of them
    total = 0
    success = 0
    for acctname in sorted(PlaidGetter.accounts(client).keys()):
        try:
            total += 1
            getter.get_ofx(acctname, days=args.days)
            success += 1
        except Exception:
            logger.error(
                'Failed to download account %s', acctname, exc_info=True
            )
    if success != total:
        logger.warning('Downloaded %d of %d accounts', success, total)
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
