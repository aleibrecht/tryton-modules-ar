#This file is part of the account_bank_ar module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.

from trytond.pool import Pool
from .bank_ar import *


def register():
    Pool.register(
        AccountBank,
        AccountPartyBank,
        Party,
        module='account_bank_ar', type_='model')
