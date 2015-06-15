from trytond.model import fields

from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool

__all__ = ['User']
__metaclass__ = PoolMeta


class User:
    __name__ = "res.user"

    current_channel = fields.Many2One(
        'sale.channel', 'Current Channel', domain=[
            ('id', 'in', Eval('allowed_create_channels', [])),
        ], depends=['allowed_create_channels']
    )

    read_channels = fields.Many2Many(
        'sale.channel-read-res.user', 'user', 'channel', 'Read Channels'
    )
    create_channels = fields.Many2Many(
        'sale.channel-write-res.user', 'user', 'channel', 'Create Channels'
    )
    allowed_read_channels = fields.Function(
        fields.One2Many('sale.channel', None, 'Allowed Read Channels'),
        'get_allowed_channels'
    )

    allowed_create_channels = fields.Function(
        fields.One2Many('sale.channel', None, 'Allowed Create Channels'),
        'get_allowed_channels'
    )

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._preferences_fields.extend([
            'current_channel',
        ])
        cls._context_fields.insert(0, 'current_channel')
        cls._context_fields.insert(0, 'allowed_read_channels')
        cls._context_fields.insert(0, 'allowed_create_channels')

    def get_status_bar(self, name):
        status = super(User, self).get_status_bar(name)
        if self.current_channel:
            status += ' - %s' % (self.current_channel.rec_name)
        return status

    def get_allowed_channels(self, name):
        """
        Return allowed channels
        """
        Channel = Pool().get('sale.channel')
        Group = Pool().get('res.group')
        User = Pool().get('res.user')
        Model = Pool().get('ir.model.data')

        sale_admin_id = Model.get_id('sale', 'group_sale_admin')
        sale_admin = Group(sale_admin_id)

        if sale_admin.id in User.get_groups():
            # If user is sale_admin allow read and write on all channels
            return map(int, Channel.search([]))

        if name == 'allowed_read_channels':
            return set(map(int, self.read_channels + self.create_channels))

        elif name == 'allowed_create_channels':
            return map(int, self.create_channels)
