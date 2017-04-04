# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

import logging

from decimal import Decimal
import datetime

from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import fields, ModelSQL, ModelView, Workflow, Unique
from trytond.pyson import Eval

__all__ = ['AccountMoveImport', 'AccountMoveImportLine']

_logger = logging.getLogger(__name__)


class AccountMoveImport(Workflow, ModelSQL, ModelView):
    'Account Move Import'
    __name__ = 'account.move.import'

    name = fields.Char(
        'Name',
        required=True,
        states={
            'readonly': Eval('state') == 'done',
        },
    )
    journal = fields.Many2One(
        'account.journal', 'Journal',
        required=True,
        states={
            'readonly': Eval('state') == 'done',
        }
    )
    date_format = fields.Selection(
        [
            ('%d/%m/%Y', 'DD/MM/YY'),
            ('%d-%m-%Y', 'DD-MM-YY'),
        ],
        'Date Format',
        required=True,
        states={
            'readonly': Eval('state') == 'done',
        }
    )
    numeric_format = fields.Selection(
        [
            ('europe', '1.000,00'),
            ('usa', '1,000.00'),
        ],
        'Numeric Format',
        required=True,
        states={
            'readonly': Eval('state') == 'done',
        }
    )
    lines = fields.One2Many('account.move.import.line', 'account_import',
        'Lines', states={
            'readonly': Eval('state') == 'done',
        })
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ], 'State', required=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super(AccountMoveImport, cls).__setup__()
        cls._buttons.update({
            'process': {
                'readonly': ~Eval('lines') | ~Eval('journal')
                    | (Eval('state') == 'done')
                }
            })
        cls._error_messages.update({
            'incorrect_data': ('Import error: %s'),
            'not_found_period': ('Not found period: %s'),
            })
        cls._transitions |= set((
            ('draft', 'done'),
            ))
        t = cls.__table__()
        cls._sql_constraints.append(
            ('name_uniq', Unique(t, t.name),
                'Move Import name must be unique'),
        )

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def process(cls, records):
        pool = Pool()
        AccountMove = pool.get('account.move')
        Period = pool.get('account.period')

        to_create = []
        for move_import in records:
            to_create_lines = []
            default_journal = move_import.journal
            current_account_move = None
            account_move = None
            current_move = None

            for line_import in move_import.lines:
                # There might nor be a number for the account, then assume
                # we are working on the same account move
                current_account_move = line_import.account_moves or account_move

                if current_account_move != account_move:
                    account_move = current_account_move
                    if to_create_lines:
                        current_move.lines = to_create_lines
                        to_create.append(current_move)

                    to_create_lines = []
                    current_move = AccountMove()
                    current_move.journal = default_journal

                    date = move_import.get_datetime(line_import.date)
                    period_name = '%s-%02d' % (date.year, date.month)

                    periods = Period.search([
                        ('name', '=', period_name)], limit=1)
                    if not periods:
                        cls.raise_user_error('not_found_period', period_name)
                    period, = periods
                    current_move.period = period

                to_create_lines.append(
                    move_import.parse_import_line(line_import))

            if to_create_lines:
                current_move.lines = to_create_lines
                to_create.append(current_move)

        if to_create:
            AccountMove.create([x._save_values for x in to_create])

    def parse_import_line(self, line_import):
        "Parses an account.move.line.import object "
        "into a new account.move.line instance"
        pool = Pool()
        AccountMoveLine = pool.get('account.move.line')
        account_move_line = AccountMoveLine(
            account=self.find_account(line_import.accounts),
            party=self.find_party(line_import.party),
            date=self.parse_datetime(line_import.date),
            debit=self.parse_decimal(line_import.debit),
            credit=self.parse_decimal(line_import.credit),
            description=line_import.account_description,
        )
        return account_move_line

    def find_account(self, account_name):
        pool = Pool()
        Account = pool.get('account.account')
        account, = Account.search([('code', '=', account_name)], limit=1)
        if not account:
            self.raise_user_error(
                'incorrect_data', 'No account named %s' % account_name)
        return account

    def find_party(self, party_name):
        if not party_name:
            return None
        Party = Pool().get('party.party')
        party, = Party.search([('name', '=', party_name)], limit=1)
        if not party:
            self.raise_user_error(
                'incorrect_data', 'No party named %s' % party_name)
        return party

    def parse_datetime(self, date):
        """ Converts a formatted date to a datetime object """
        if date:
            return datetime.datetime.strptime(date, self.date_format)
        return None

    def parse_decimal(self, decimal):
        """ Converts a string to Decimal having thousand separators in mind """
        if self.numeric_format == 'europe':
            decimal = decimal.replace('.', '').replace(',', '.') or '00.00'
        else:
            decimal = decimal.replace(',', '') or '00.00'
        return Decimal(decimal)


class AccountMoveImportLine(ModelSQL, ModelView):
    'Account Move Import Line'
    __name__ = 'account.move.import.line'
    account_import = fields.Many2One(
        'account.move.import', 'Move Import',
        required=True, ondelete='CASCADE')
    account_moves = fields.Char('Account Moves')
    date = fields.Char('Date')
    accounts = fields.Char('Accounts', required=True)
    party = fields.Char('Party')
    debit = fields.Char('Debit')
    credit = fields.Char('Credit')
    account_description = fields.Char('Account Description')

    @classmethod
    def import_data(cls, fields_names, data):
        import_id = Transaction().context.get('import_id')
        if import_id and 'account_import' not in fields_names:
            fields_names, data = cls.preappend_move_import(
                fields_names, data, import_id)
        return super(AccountMoveImportLine, cls).import_data(
            fields_names, data)

    @staticmethod
    def preappend_move_import(fields_names, data, import_id):
        move_import = Pool().get('account.move.import')(import_id)
        fields_names = ['account_import'] + fields_names
        # This relies on account_import rec_name being unique!
        data = [
            [move_import.rec_name] + line
            for line in data
        ]
        return fields_names, data
