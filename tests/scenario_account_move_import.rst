======================
Scenario AccountImport
======================

"""
The scenario will check if the account import module actually imports the
accounts correctly.
The accounts wit no number are considered to be part of the same move as the
previous one, same happens with the date
"""


Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code

Create config::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install Prescriptions::

	>>> Module = Model.get('ir.module')
  >>> module, = Module.find([('name', '=', 'account_move_import')])
  >>> Module.install ([module.id], config.context)
  >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

  >>> _ = create_company()
  >>> company = get_company()

Reload the context::

  >>> User = Model.get('res.user')
  >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

  >>> fiscalyear = create_fiscalyear(company)
  >>> fiscalyear.click('create_period')
  >>> period = fiscalyear.periods[0]

Create chart of accounts::

  >>> _ = create_chart(company)
  >>> accounts = get_accounts(company)
  >>> receivable = accounts['receivable']
  >>> payable = accounts['payable']
  >>> revenue = accounts['revenue']
  >>> expense = accounts['expense']
  >>> account_tax = accounts['tax']
  >>> account_cash = accounts['cash']

  >>> revenue.code = 'revenue'
  >>> expense.code = 'expense'
  >>> revenue.save()
  >>> expense.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Supplier')
    >>> party.account_payable = payable
    >>> party.account_receivable = receivable
    >>> party.save()

Create Journal::

    >>> Journal = Model.get('account.journal')
    >>> journal, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal.update_posted = True
    >>> journal.save()

Create Accounts import::

    >>> AccountImport = Model.get('account.move.import')
    >>> AccountImportLine = Model.get('account.move.import.line')
    >>> account_import = AccountImport()
    >>> account_import.journal = journal
    >>> account_import.description = 'Test import'

    >>> line = account_import.lines.new()
    >>> line.account_moves = '1234'
    >>> line.date = '10/11/2017'
    >>> line.accounts = revenue.code
    >>> line.debit = '10,00'
    >>> line.credit = '0,0'
    >>> line.account_description = 'First account move of the test'


    >>> line2 = account_import.lines.new()
    >>> line2.account_moves = ''
    >>> line2.date = '10/11/2017'
    >>> line2.accounts = revenue.code
    >>> line2.credit = '10,00'
    >>> line2.debit = '0,0'
    >>> line2.account_description = 'Second account move of the test'

    >>> line3 = account_import.lines.new()
    >>> line3.account_moves = '4321'
    >>> line3.date = '12/11/2017'
    >>> line3.accounts = expense.code
    >>> line3.debit = '10,00'
    >>> line3.credit = '0,0'
    >>> line3.account_description = 'Third account move of the test'

    >>> account_import.save()
    >>> account_import.click('process')

Check imports::

    >>> AccountMoves = Model.get('account.move')
    >>> account_moves = AccountMoves.find([])
    >>> len(account_moves) == 2
    True
    >>> len(account_moves[1].lines) == 2
    True
    >>> len(account_moves[0].lines) == 1
    True
    >>> account_moves[1].lines[0].credit == Decimal('10.00')
    True
