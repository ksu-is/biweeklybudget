"""
The latest version of this package is available at:
<http://github.com/jantman/biweeklybudget>

################################################################################
Copyright 2016 Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>

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
"""

from biweeklybudget.models import *
from biweeklybudget.models.account import AcctType
from biweeklybudget.utils import dtnow
from datetime import timedelta


class SampleDataLoader(object):

    def __init__(self, db_session):
        self.db = db_session
        self.accounts = {}
        self.statements = {}
        self.transactions = {}
        self.dt = dtnow()

    def load(self):
        self.accounts = {
            'BankOne': self._bank_one(),
            'BankTwoStale': self._bank_two_stale(),
            'CreditOne': self._credit_one(),
            'CreditTwo': self._credit_two(),
            'InvestmentOne': self._investment_one(),
            'DisabledBank': self._disabled_bank()
        }

    def _add_account(self, acct, statements, transactions):
        self.db.add(acct)
        for s in statements:
            self.db.add(s)
            acct.set_balance(
                overall_date=s.as_of,
                ledger=s.ledger_bal,
                ledger_date=s.ledger_bal_as_of,
                avail=s.avail_bal,
                avail_date=s.avail_bal_as_of
            )
        for s in transactions.keys():
            for t in transactions[s]:
                self.db.add(t)
        return {
            'account': acct,
            'statements': statements,
            'transactions': transactions
        }

    def _bank_one(self):
        acct = Account(
            description='First Bank Account',
            name='BankOne',
            ofx_cat_memo_to_name=True,
            ofxgetter_config_json='{"foo": "bar"}',
            vault_creds_path='secret/foo/bar/BankOne',
            acct_type=AcctType.Bank
        )
        statements = [
            OFXStatement(
                account=acct,
                filename='/stmt/BankOne/0',
                file_mtime=(self.dt - timedelta(hours=46)),
                currency='USD',
                bankid='BankOne',
                routing_number='11',
                acct_type='Checking',
                acctid='1111',
                type='Bank',
                as_of=(self.dt - timedelta(hours=46)),
                ledger_bal=12345.67,
                ledger_bal_as_of=(self.dt - timedelta(hours=46)),
                avail_bal=12340.00,
                avail_bal_as_of=(self.dt - timedelta(hours=46))
            ),
            OFXStatement(
                account=acct,
                filename='/stmt/BankOne/1',
                file_mtime=(self.dt - timedelta(hours=14)),
                currency='USD',
                bankid='BankOne',
                routing_number='11',
                acct_type='Checking',
                acctid='1111',
                type='Bank',
                as_of=(self.dt - timedelta(hours=14)),
                ledger_bal=12789.01,
                ledger_bal_as_of=(self.dt - timedelta(hours=14)),
                avail_bal=12563.18,
                avail_bal_as_of=(self.dt - timedelta(hours=14))
            )
        ]
        transactions = {
            0: [
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='BankOne.0.0',
                    trans_type='Credit',
                    date_posted=(self.dt - timedelta(days=7)),
                    amount=1234.56,
                    name='BankOne.0.0'
                ),
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='BankOne.0.1',
                    trans_type='Debit',
                    date_posted=(self.dt - timedelta(days=6)),
                    amount=-20.00,
                    name='Late Fee'
                )
            ],
            1: []
        }
        for x in range(1, 21):
            mult = 1
            if x % 2 == 0:
                mult = -1
            amt = (11 * x) * mult
            transactions[1].append(OFXTransaction(
                    account=acct,
                    statement=statements[1],
                    fitid='BankOne.1.%d' % x,
                    trans_type='Debit',
                    date_posted=(self.dt - timedelta(days=6, hours=x)),
                    amount=amt,
                    name='Generated Trans %d' % x
            ))
        return self._add_account(acct, statements, transactions)

    def _bank_two_stale(self):
        acct = Account(
            description='Stale Bank Account',
            name='BankTwoStale',
            ofx_cat_memo_to_name=False,
            ofxgetter_config_json='{"foo": "baz"}',
            vault_creds_path='secret/foo/bar/BankTwo',
            acct_type=AcctType.Bank,
            is_active=True
        )
        statements = [
            OFXStatement(
                account=acct,
                filename='/stmt/BankTwoStale/0',
                file_mtime=(self.dt - timedelta(days=18)),
                currency='USD',
                bankid='BankTwoStale',
                routing_number='22',
                acct_type='Savings',
                acctid='2222',
                type='Bank',
                as_of=(self.dt - timedelta(days=18)),
                ledger_bal=100.23,
                ledger_bal_as_of=(self.dt - timedelta(days=18))
            )
        ]
        transactions = {
            0: [
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='0',
                    trans_type='Debit',
                    date_posted=(self.dt - timedelta(days=23)),
                    amount=432.19,
                    name='Transfer to Other Account'
                ),
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='1',
                    trans_type='Interest',
                    date_posted=(self.dt - timedelta(days=22)),
                    amount=0.23,
                    name='Interest Paid',
                    memo='Some Date'
                )
            ]
        }
        return self._add_account(acct, statements, transactions)

    def _credit_one(self):
        acct = Account(
            description='First Credit Card, limit 2000',
            name='CreditOne',
            ofx_cat_memo_to_name=False,
            acct_type=AcctType.Credit,
            credit_limit=2000.00,
            is_active=True
        )
        statements = [
            OFXStatement(
                account=acct,
                filename='/stmt/CreditOne/0',
                file_mtime=(self.dt - timedelta(hours=13)),
                currency='USD',
                bankid='CreditOne',
                acct_type='Credit',
                acctid='CreditOneAcctId',
                type='Credit',
                as_of=(self.dt - timedelta(hours=13)),
                ledger_bal=952.06,
                ledger_bal_as_of=(self.dt - timedelta(hours=13)),
            )
        ]
        transactions = {
            0: [
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='T1',
                    trans_type='Purchase',
                    date_posted=(self.dt - timedelta(hours=22)),
                    amount=123.81,
                    name='123.81 Credit Purchase T1',
                    memo='38328',
                    description='CreditOneT1Desc'
                )
            ]
        }
        return self._add_account(acct, statements, transactions)

    def _credit_two(self):
        acct = Account(
            description='Credit 2 limit 5500',
            name='CreditTwo',
            ofx_cat_memo_to_name=False,
            ofxgetter_config_json='',
            vault_creds_path='/foo/bar',
            acct_type=AcctType.Credit,
            credit_limit=5500,
            is_active=True
        )
        statements = [
            OFXStatement(
                account=acct,
                filename='/stmt/CreditTwo/0',
                file_mtime=(self.dt - timedelta(hours=36)),
                currency='USD',
                bankid='CreditTwo',
                acct_type='Credit',
                acctid='',
                type='CreditCard',
                as_of=(self.dt - timedelta(hours=36)),
                ledger_bal=5498.65,
                ledger_bal_as_of=(self.dt - timedelta(hours=36))
            )
        ]
        transactions = {
            0: [
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='001',
                    trans_type='Purchase',
                    date_posted=(self.dt - timedelta(days=6)),
                    amount=28.53,
                    name='Interest Charged',
                    memo=''
                ),
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='002',
                    trans_type='Credit',
                    date_posted=(self.dt - timedelta(days=5)),
                    amount=-50.00,
                    name='Online Payment - Thank You',
                    memo=''
                )
            ]
        }
        return self._add_account(acct, statements, transactions)

    def _investment_one(self):
        acct = Account(
            description='Investment One Stale',
            name='InvestmentOne',
            ofx_cat_memo_to_name=False,
            ofxgetter_config_json='',
            vault_creds_path='',
            acct_type=AcctType.Investment,
            is_active=True
        )
        statements = [
            OFXStatement(
                account=acct,
                filename='/stmt/InvOne/0',
                file_mtime=(self.dt - timedelta(days=13, hours=6)),
                currency='USD',
                acct_type='Retirement',
                brokerid='InvOneBroker',
                acctid='1000001',
                type='Investment',
                as_of=(self.dt - timedelta(days=13, hours=6)),
                ledger_bal=10362.91,
                ledger_bal_as_of=(self.dt - timedelta(days=13, hours=6))
            )
        ]
        return self._add_account(acct, statements, {})

    def _disabled_bank(self):
        acct = Account(
            description='Disabled Bank Account',
            name='DisabledBank',
            ofx_cat_memo_to_name=True,
            ofxgetter_config_json='{"bar": "baz"}',
            vault_creds_path='',
            acct_type=AcctType.Bank,
            is_active=False
        )
        statements = [
            OFXStatement(
                account=acct,
                filename='/stmt/DisabledBank/0',
                file_mtime=(self.dt - timedelta(days=41)),
                currency='USD',
                bankid='111DDD111',
                routing_number='111DDD111',
                acct_type='Savings',
                acctid='D1111111',
                type='Bank',
                as_of=(self.dt - timedelta(hours=46)),
                ledger_bal=10.00,
                ledger_bal_as_of=(self.dt - timedelta(days=41)),
                avail_bal=10.00,
                avail_bal_as_of=(self.dt - timedelta(days=41))
            )
        ]
        transactions = {
            0: [
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='001',
                    trans_type='Credit',
                    date_posted=(self.dt - timedelta(days=43)),
                    amount=0.01,
                    name='Interest Paid',
                    memo=''
                ),
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='002',
                    trans_type='Debit',
                    date_posted=(self.dt - timedelta(days=51)),
                    amount=3218.87,
                    name='ATM Withdrawal',
                    memo='Disabled002Memo',
                    description='Disabled002Desc'
                )
            ]
        }
        return self._add_account(acct, statements, transactions)

    def _example_bank(self):
        """Sample to copy"""
        acct = Account(
            description='',
            name='',
            ofx_cat_memo_to_name=False,
            ofxgetter_config_json='',
            vault_creds_path='',
            acct_type=AcctType.Bank,
            # credit_limit=0,
            is_active=True
        )
        statements = [
            OFXStatement(
                account=acct,
                filename='/stmt/BankOne/0',
                file_mtime=(self.dt - timedelta(hours=46)),
                currency='USD',
                bankid='',
                routing_number='',
                acct_type='',
                brokerid='',
                acctid='',
                type='',
                as_of=(self.dt - timedelta(hours=46)),
                ledger_bal=12345.67,
                ledger_bal_as_of=(self.dt - timedelta(hours=46)),
                avail_bal=12340.00,
                avail_bal_as_of=(self.dt - timedelta(hours=46))
            )
        ]
        transactions = {
            0: [
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='',
                    trans_type='',
                    date_posted=(self.dt - timedelta(days=7)),
                    amount=1234.56,
                    name='',
                    memo=''
                ),
                OFXTransaction(
                    account=acct,
                    statement=statements[0],
                    fitid='',
                    trans_type='',
                    date_posted=(self.dt - timedelta(days=7)),
                    amount=1234.56,
                    name='',
                    memo=''
                )
            ]
        }
        return self._add_account(acct, statements, transactions)