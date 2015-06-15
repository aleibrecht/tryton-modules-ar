# This file is part sale_shop module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['User']
__metaclass__ = PoolMeta


class User:
    __name__ = "res.user"
    shops = fields.Many2Many('sale.shop-res.user', 'user', 'shop', 'Shops')
    shop = fields.Many2One('sale.shop', 'Shop', domain=[
            ('id', 'in', Eval('shops', [])),
            ], depends=['shops'])

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._preferences_fields.extend([
                'shop',
                'shops',
                ])
        cls._context_fields.insert(0, 'shop')
        cls._context_fields.insert(0, 'shops')

    def get_status_bar(self, name):
        status = super(User, self).get_status_bar(name)
        if self.shop:
            status += ' - %s' % (self.shop.rec_name)
        return status
