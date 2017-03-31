# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.pool import Pool
from . import move


def register():
    Pool.register(
        move.AccountMoveImport,
        move.AccountMoveImportLine,
        module='account_move_import', type_='model')
