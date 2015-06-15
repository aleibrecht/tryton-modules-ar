# This file is part sale_shop module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from .shop import *
from .sale import *
from .user import *
from .stock import *


def register():
    Pool.register(
        SaleShop,
        SaleShopResUser,
        Sale,
        User,
        ShipmentOut,
        ShipmentOutReturn,
        module='sale_shop', type_='model')
