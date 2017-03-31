# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
import datetime

from trytond.pool import Pool
from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pyson import Eval

__all__ = ['AccountMoveImport', 'AccountMoveImportLine']


class AccountMoveImport(Workflow, ModelSQL, ModelView):
    'Account Move Import'
    __name__ = 'account.move.import'
    _rec_name = 'description'

    description = fields.Char('Name',
        states={
            'readonly': Eval('state') == 'done',
        })
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states={
            'readonly': Eval('state') == 'done',
        })
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
        for record in records:
            to_create_lines = []
            default_journal = record.journal
            current_account_move = None
            account_move = None
            current_move = None

            for line in record.lines:
                # There might nor be a number for the account, then assume
                # we are working on the same account move
                current_account_move = line.account_moves or account_move

                if current_account_move != account_move:
                    account_move = current_account_move
                    if to_create_lines:
                        current_move.lines = to_create_lines
                        to_create.append(current_move)

                    to_create_lines = []
                    current_move = AccountMove()
                    current_move.journal = default_journal

                    date = record.get_datetime(line.date)
                    period_name = '%s-%02d' % (date.year, date.month)

                    periods = Period.search([
                        ('name', '=', period_name)], limit=1)
                    if not periods:
                        cls.raise_user_error('not_found_period', period_name)
                    period, = periods
                    current_move.period = period

                is_data_correct = record.check_data(line)

                # is_data_correct ->
                # (Bool(is_data_correct), [Error or parsed data])
                if not is_data_correct[0]:
                    cls.raise_user_error('incorrect_data', is_data_correct[1])

                to_create_lines.append(
                    record.parse_excel_data(is_data_correct[1])
                    )

            if to_create_lines:
                current_move.lines = to_create_lines
                to_create.append(current_move)

        if to_create:
            AccountMove.create([x._save_values for x in to_create])

    def check_data(self, data):
        """ Checks that all the data is correct """
        pool = Pool()
        Account = pool.get('account.account')
        Party = pool.get('party.party')

        if not data.accounts:
            return (False, 'No account found in move ' + data.account_moves)

        account = Account.search([('code', '=', data.accounts)], limit=1)
        party = Party.search([('name', '=', data.party)], limit=1)

        if not account:
            return (False, 'No account for ' + data.accounts + ' in move ' +
                data.account_moves)
        if not party and data.party:
            return (False, 'Unable to find party ' + data.party + ' in move ' +
                data.account_moves)

        data.date = self.get_datetime(data.date)

        results = {
            'account': account[0],
            'party': self.get_value(party),
            'date': data.date or None,
            'debit': Decimal(data.debit.replace('.', '').replace(',', '.')
                or '00.00'),
            'credit': Decimal(data.credit.replace('.', '').replace(',', '.')
                or '00.00'),
            'description': data.account_description,
            'move_description': data.account_description,
        }

        return (True, results)

    def parse_excel_data(self, data):
        """ Preapes the data to be created """
        pool = Pool()
        AccountMoveLine = pool.get('account.move.line')
        account_move_line = AccountMoveLine()
        account_move_line.account = data['account']
        account_move_line.party = data['party']
        account_move_line.date = data['date']
        account_move_line.debit = data['debit']
        account_move_line.credit = data['credit']
        account_move_line.description = data['description']

        return account_move_line

    def get_datetime(self, date):
        """ Converts a date to datetime format """
        if date:
            date = date.replace('-', '/')
            return datetime.datetime.strptime(date, '%d/%m/%Y')
        return None

    def get_value(self, value):
        try:
            return value[0]
        except:
            return None


class AccountMoveImportLine(ModelSQL, ModelView):
    'Account Move Import Line'
    __name__ = 'account.move.import.line'
    account_import = fields.Many2One('account.move.import', 'lines',
        required=True, readonly=True, ondelete='CASCADE')
    account_moves = fields.Char('Account Moves')
    date = fields.Char('Date')
    accounts = fields.Char('Accounts', required=True)
    party = fields.Char('Party')
    debit = fields.Char('Debit')
    credit = fields.Char('Credit')
    account_description = fields.Char('Account Description')
