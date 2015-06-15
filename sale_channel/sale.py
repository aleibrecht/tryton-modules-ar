# -*- coding: utf-8 -*-
"""
    sale

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: see LICENSE for more details.
"""
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Or, Bool

__all__ = ['Sale']
__metaclass__ = PoolMeta


class Sale:
    __name__ = 'sale.sale'

    channel = fields.Many2One(
        'sale.channel', 'Channel', required=True, domain=[
            ('id', 'in', Eval('context', {}).get('allowed_read_channels', [])),
        ],
        states={
            'readonly': Or(
                (Eval('id', default=0) > 0),
                Bool(Eval('lines', default=[])),
            )
        }, depends=['id']
    )

    channel_type = fields.Function(
        fields.Char('Channel Type'), 'on_change_with_channel_type'
    )

    has_channel_exception = fields.Function(
        fields.Boolean('Has Channel Exception ?'), 'get_has_channel_exception'
    )

    def get_has_channel_exception(self, name):
        """
        Returs True if sale has exception
        """
        ChannelException = Pool().get('channel.exception')

        return bool(
            ChannelException.search([
                ('origin', '=', '%s,%s' % (self.__name__, self.id)),
                ('channel', '=', self.channel.id),
                ('is_resolved', '=', False)
            ])
        )

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()

        cls._error_messages.update({
            'channel_missing': (
                'Go to user preferences and select a current_channel ("%s")'
            ),
            'channel_change_not_allowed': (
                'Cannot change channel'
            ),
            'not_create_channel': (
                'You cannot create order under this channel because you do not '
                'have required permissions'
            ),
        })

    @classmethod
    def default_channel(cls):
        User = Pool().get('res.user')

        user = User(Transaction().user)
        channel_id = Transaction().context.get('current_channel')

        if channel_id:
            return channel_id
        return user.current_channel and \
            user.current_channel.id  # pragma: nocover

    @staticmethod
    def default_company():
        Sale = Pool().get('sale.sale')
        Channel = Pool().get('sale.channel')

        channel_id = Sale.default_channel()
        if channel_id:
            return Channel(channel_id).company.id

        return Transaction().context.get('company')  # pragma: nocover

    @staticmethod
    def default_invoice_method():
        Sale = Pool().get('sale.sale')
        Channel = Pool().get('sale.channel')
        Config = Pool().get('sale.configuration')

        channel_id = Sale.default_channel()
        if not channel_id:  # pragma: nocover
            config = Config(1)
            return config.sale_invoice_method

        return Channel(channel_id).invoice_method

    @staticmethod
    def default_shipment_method():
        Sale = Pool().get('sale.sale')
        Channel = Pool().get('sale.channel')
        Config = Pool().get('sale.configuration')

        channel_id = Sale.default_channel()
        if not channel_id:  # pragma: nocover
            config = Config(1)
            return config.sale_invoice_method

        return Channel(channel_id).shipment_method

    @staticmethod
    def default_warehouse():
        Sale = Pool().get('sale.sale')
        Channel = Pool().get('sale.channel')
        Location = Pool().get('stock.location')

        channel_id = Sale.default_channel()
        if not channel_id:  # pragma: nocover
            return Location.search([('type', '=', 'warehouse')], limit=1)[0].id
        else:
            return Channel(channel_id).warehouse.id

    @staticmethod
    def default_price_list():
        Sale = Pool().get('sale.sale')
        Channel = Pool().get('sale.channel')

        channel_id = Sale.default_channel()
        if channel_id:
            return Channel(channel_id).price_list.id
        return None  # pragma: nocover

    @staticmethod
    def default_payment_term():
        Sale = Pool().get('sale.sale')
        Channel = Pool().get('sale.channel')

        channel_id = Sale.default_channel()
        if channel_id:
            return Channel(channel_id).payment_term.id
        return None  # pragma: nocover

    @fields.depends('channel', 'party')
    def on_change_channel(self):
        if not self.channel:
            return {}  # pragma: nocover
        res = {}
        for fname in ('company', 'warehouse', 'currency', 'payment_term'):
            fvalue = getattr(self.channel, fname)
            if fvalue:
                res[fname] = fvalue.id
        if (not self.party or not self.party.sale_price_list):
            res['price_list'] = self.channel.price_list.id  # pragma: nocover
        if self.channel.invoice_method:
            res['invoice_method'] = self.channel.invoice_method
        if self.channel.shipment_method:
            res['shipment_method'] = self.channel.shipment_method

        # Update AR record
        for key, value in res.iteritems():
            if '.' not in key:
                setattr(self, key, value)
        return res

    @fields.depends('channel')
    def on_change_party(self):  # pragma: nocover
        res = super(Sale, self).on_change_party()
        channel = self.channel

        if channel:
            if not res.get('price_list') and res.get('invoice_address'):
                res['price_list'] = channel.price_list.id
                res['price_list.rec_name'] = channel.price_list.rec_name
            if not res.get('payment_term') and res.get('invoice_address'):
                res['payment_term'] = channel.payment_term.id
                res['payment_term.rec_name'] = \
                    self.channel.payment_term.rec_name

        # Update AR record
        for key, value in res.iteritems():
            setattr(self, key, value)
        return res

    @fields.depends('channel')
    def on_change_with_channel_type(self, name=None):
        """
        Returns the source of the channel
        """
        if self.channel:
            return self.channel.source

    def check_create_access(self, silent=False):
        """
            Check sale creation in channel
        """
        User = Pool().get('res.user')
        user = User(Transaction().user)

        if user.id == 0:
            return  # pragma: nocover

        if self.channel not in user.allowed_create_channels:
            if silent:
                return False
            self.raise_user_error('not_create_channel')
        return True

    @classmethod
    def write(cls, sales, values, *args):
        """
        Check if channel in sale is is user's create_channel
        """
        if 'channel' in values:
            # Channel cannot be changed at any cost.
            cls.raise_user_error('channel_change_not_allowed')

        super(Sale, cls).write(sales, values, *args)

    @classmethod
    def create(cls, vlist):
        """
        Check if user is allowed to create sale in channel
        """
        User = Pool().get('res.user')
        user = User(Transaction().user)

        for values in vlist:
            if 'channel' not in values and not cls.default_channel():
                cls.raise_user_error(
                    'channel_missing', (user.rec_name,)
                )  # pragma: nocover

        sales = super(Sale, cls).create(vlist)
        for sale in sales:
            sale.check_create_access()
        return sales

    @classmethod
    def copy(cls, sales, default=None):
        """
        Duplicating records
        """
        if default is None:
            default = {}

        for sale in sales:
            if not sale.check_create_access(True):
                default['channel'] = cls.default_channel()

        return super(Sale, cls).copy(sales, default=default)
