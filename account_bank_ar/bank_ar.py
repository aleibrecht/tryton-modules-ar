#This file is part of the account_bank_ar module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval

__all__ = ['AccountBank', 'AccountPartyBank', 'Party']

STATES = {
    'readonly': ~Eval('active', True),
}
DEPENDS = ['active']


class AccountBank(ModelSQL, ModelView):
    'Account Bank'
    __name__ = 'account.bank'

    name = fields.Char('Name', required=True, states=STATES, depends=DEPENDS)
    code = fields.Char('Code', states=STATES, depends=DEPENDS)
    street = fields.Char('Street', states=STATES, depends=DEPENDS)
    street2 = fields.Char('Street2', states=STATES, depends=DEPENDS)
    zip = fields.Char('Zip', states=STATES, depends=DEPENDS)
    city = fields.Char('City', states=STATES, depends=DEPENDS)
    state = fields.Many2One('country.subdivision', 'State', states=STATES,
        domain=[
            ('country', '=', Eval('country')),
            ], depends=['country'])
    country = fields.Many2One('country.country', 'Country', states=STATES,
        depends=DEPENDS)
    email = fields.Char('E-Mail', states=STATES, depends=DEPENDS)
    phone = fields.Char('Phone', states=STATES, depends=DEPENDS)
    fax = fields.Char('Fax', states=STATES, depends=DEPENDS)
    active = fields.Boolean('Active', select=True)

    @staticmethod
    def default_active():
        return True

    @classmethod
    def check_xml_record(cls, records, values):
        return True


class AccountPartyBank(ModelSQL, ModelView):
    'Account Party Bank'
    __name__ = 'account.party.bank'

    name = fields.Char('Account Number', required=True, states=STATES,
        depends=DEPENDS)
    bank = fields.Many2One('account.bank', 'Bank', required=True,
        states=STATES, depends=DEPENDS)
    party = fields.Many2One('party.party', 'Party', required=True,
        states=STATES, depends=DEPENDS)
    journal = fields.Many2One('account.journal', 'Account Journal',
        required=True, states=STATES, depends=DEPENDS)
    street = fields.Char('Street', states=STATES, depends=DEPENDS)
    street2 = fields.Char('Street2', states=STATES, depends=DEPENDS)
    zip = fields.Char('Zip', states=STATES, depends=DEPENDS)
    city = fields.Char('City', states=STATES, depends=DEPENDS)
    state = fields.Many2One('country.subdivision', 'State', states=STATES,
        domain=[
            ('country', '=', Eval('country')),
            ], depends=['country'])
    country = fields.Many2One('country.country', 'Country', states=STATES,
        depends=DEPENDS)
    email = fields.Char('E-Mail', states=STATES, depends=DEPENDS)
    phone = fields.Char('Phone', states=STATES, depends=DEPENDS)
    fax = fields.Char('Fax', states=STATES, depends=DEPENDS)
    active = fields.Boolean('Active', select=True)

    @staticmethod
    def default_active():
        return True

    def get_rec_name(self, name):
        return '[' + self.bank.name + '] ' + self.name


class Party(ModelSQL, ModelView):
    __name__ = 'party.party'

    # Migration to Tryton 3.2 -> Rename field for compatibility with bank module
    bank_accounts_ar = fields.One2Many('account.party.bank', 'party',
        'Bank Accounts', states=STATES, depends=DEPENDS)
