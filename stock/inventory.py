#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Not, Equal, Eval, Or, Bool
from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Inventory', 'InventoryLine']

STATES = {
    'readonly': Not(Equal(Eval('state'), 'draft')),
}
DEPENDS = ['state']


class Inventory(Workflow, ModelSQL, ModelView):
    'Stock Inventory'
    __name__ = 'stock.inventory'
    location = fields.Many2One(
        'stock.location', 'Location', required=True,
        domain=[('type', '=', 'storage')], states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines', [0]))),
            },
        depends=['state'])
    date = fields.Date('Date', required=True, states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines', [0]))),
            },
        depends=['state'])
    lost_found = fields.Many2One(
        'stock.location', 'Lost and Found', required=True,
        domain=[('type', '=', 'lost_found')], states=STATES, depends=DEPENDS)
    lines = fields.One2Many(
        'stock.inventory.line', 'inventory', 'Lines', states=STATES,
        depends=DEPENDS)
    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('lines', [0]))),
            },
        depends=['state'])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Canceled'),
        ], 'State', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(Inventory, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))
        cls._error_messages.update({
                'delete_cancel': ('Inventory "%s" must be cancelled before '
                    'deletion.'),
                'unique_line': ('Line "%s" is not unique '
                    'on Inventory "%s".'),
                })
        cls._transitions |= set((
                ('draft', 'done'),
                ('draft', 'cancel'),
                ))
        cls._buttons.update({
                'confirm': {
                    'invisible': Eval('state').in_(['done', 'cancel']),
                    },
                'cancel': {
                    'invisible': Eval('state').in_(['cancel', 'done']),
                    },
                'complete_lines': {
                    'readonly': Eval('state') != 'draft',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        super(Inventory, cls).__register__(module_name)
        cursor = Transaction().cursor

        # Add index on create_date
        table = TableHandler(cursor, cls, module_name)
        table.index_action('create_date', action='add')

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_date():
        Date = Pool().get('ir.date')
        return Date.today()

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_lost_found(cls):
        Location = Pool().get('stock.location')
        locations = Location.search(cls.lost_found.domain)
        if len(locations) == 1:
            return locations[0].id

    @classmethod
    def delete(cls, inventories):
        # Cancel before delete
        cls.cancel(inventories)
        for inventory in inventories:
            if inventory.state != 'cancel':
                cls.raise_user_error('delete_cancel', inventory.rec_name)
        super(Inventory, cls).delete(inventories)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def confirm(self, inventories):
        Move = Pool().get('stock.move')
        moves = []
        for inventory in inventories:
            keys = set()
            for line in inventory.lines:
                key = line.unique_key
                if key in keys:
                    self.raise_user_error('unique_line',
                        (line.rec_name, inventory.rec_name))
                keys.add(key)
                move = line.get_move()
                if move:
                    moves.append(move)
        if moves:
            moves = Move.create([m._save_values for m in moves])
            Move.do(moves)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(self, inventories):
        Line = Pool().get("stock.inventory.line")
        Line.cancel_move([l for i in inventories for l in i.lines])

    @classmethod
    def copy(cls, inventories, default=None):
        pool = Pool()
        Date = pool.get('ir.date')
        Line = pool.get('stock.inventory.line')

        if default is None:
            default = {}
        default = default.copy()
        default['date'] = Date.today()
        default['lines'] = None

        new_inventories = []
        for inventory in inventories:
            new_inventory, = super(Inventory, cls).copy([inventory],
                default=default)
            Line.copy(inventory.lines,
                default={
                    'inventory': new_inventory.id,
                    'moves': None,
                    })
            cls.complete_lines([new_inventory])
            new_inventories.append(new_inventory)
        return new_inventories

    @staticmethod
    def complete_lines(inventories):
        '''
        Complete or update the inventories
        '''
        pool = Pool()
        Line = pool.get('stock.inventory.line')
        Product = pool.get('product.product')

        to_create = []
        for inventory in inventories:
            # Compute product quantities
            with Transaction().set_context(stock_date_end=inventory.date):
                pbl = Product.products_by_location([inventory.location.id])

            # Index some data
            product2uom = {}
            product2type = {}
            product2consumable = {}
            for product in Product.browse([line[1] for line in pbl]):
                product2uom[product.id] = product.default_uom.id
                product2type[product.id] = product.type
                product2consumable[product.id] = product.consumable

            product_qty = {}
            for (location, product), quantity in pbl.iteritems():
                product_qty[product] = (quantity, product2uom[product])

            # Update existing lines
            for line in inventory.lines:
                if not (line.product.active and
                        line.product.type == 'goods'
                        and not line.product.consumable):
                    Line.delete([line])
                    continue
                if line.product.id in product_qty:
                    quantity, uom_id = product_qty.pop(line.product.id)
                elif line.product.id in product2uom:
                    quantity, uom_id = 0.0, product2uom[line.product.id]
                else:
                    quantity, uom_id = 0.0, line.product.default_uom.id
                values = line.update_values4complete(quantity, uom_id)
                if values:
                    Line.write([line], values)

            # Create lines if needed
            for product_id in product_qty:
                if (product2type[product_id] != 'goods'
                        or product2consumable[product_id]):
                    continue
                quantity, uom_id = product_qty[product_id]
                if not quantity:
                    continue
                values = Line.create_values4complete(product_id, inventory,
                    quantity, uom_id)
                to_create.append(values)
        if to_create:
            Line.create(to_create)


class InventoryLine(ModelSQL, ModelView):
    'Stock Inventory Line'
    __name__ = 'stock.inventory.line'
    _rec_name = 'product'
    product = fields.Many2One('product.product', 'Product', required=True,
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ])
    uom = fields.Function(fields.Many2One('product.uom', 'UOM'), 'get_uom')
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
            'get_unit_digits')
    expected_quantity = fields.Float('Expected Quantity', required=True,
            digits=(16, Eval('unit_digits', 2)), readonly=True,
            depends=['unit_digits'])
    quantity = fields.Float('Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)), depends=['unit_digits'])
    moves = fields.One2Many('stock.move', 'origin', 'Moves', readonly=True)
    inventory = fields.Many2One('stock.inventory', 'Inventory', required=True,
            ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(InventoryLine, cls).__setup__()
        cls._sql_constraints += [
            ('check_line_qty_pos',
                'CHECK(quantity >= 0.0)', 'Line quantity must be positive.'),
            ]
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        pool = Pool()
        Move = pool.get('stock.move')
        sql_table = cls.__table__()
        move_table = Move.__table__()

        super(InventoryLine, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        # Migration from 2.8: Remove constraint inventory_product_uniq
        table.drop_constraint('inventory_product_uniq')

        # Migration from 3.0: use Move origin
        if table.column_exist('move'):
            cursor.execute(*sql_table.select(sql_table.id, sql_table.move,
                    where=sql_table.move != None))
            for line_id, move_id in cursor.fetchall():
                cursor.execute(*move_table.update(
                        columns=[move_table.origin],
                        values=['%s,%s' % (cls.__name__, line_id)],
                        where=move_table.id == move_id))
            table.drop_column('move')

    @staticmethod
    def default_unit_digits():
        return 2

    @staticmethod
    def default_expected_quantity():
        return 0.

    @fields.depends('product')
    def on_change_product(self):
        change = {}
        change['unit_digits'] = 2
        if self.product:
            change['uom'] = self.product.default_uom.id
            change['uom.rec_name'] = self.product.default_uom.rec_name
            change['unit_digits'] = self.product.default_uom.digits
        return change

    def get_rec_name(self, name):
        return self.product.rec_name

    def get_uom(self, name):
        return self.product.default_uom.id

    def get_unit_digits(self, name):
        return self.product.default_uom.digits

    @property
    def unique_key(self):
        return (self.product,)

    @classmethod
    def cancel_move(cls, lines):
        Move = Pool().get('stock.move')
        moves = [m for l in lines for m in l.moves if l.moves]
        Move.cancel(moves)
        Move.delete(moves)

    def get_move(self):
        '''
        Return Move instance for the inventory line
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')

        delta_qty = Uom.compute_qty(self.uom,
            self.expected_quantity - self.quantity,
            self.uom)
        if delta_qty == 0.0:
            return
        from_location = self.inventory.location
        to_location = self.inventory.lost_found
        if delta_qty < 0:
            (from_location, to_location, delta_qty) = \
                (to_location, from_location, -delta_qty)

        return Move(
            from_location=from_location,
            to_location=to_location,
            quantity=delta_qty,
            product=self.product,
            uom=self.uom,
            company=self.inventory.company,
            effective_date=self.inventory.date,
            origin=self,
            )

    def update_values4complete(self, quantity, uom_id):
        '''
        Return update values to complete inventory
        '''
        values = {}
        # if nothing changed, no update
        if self.quantity == self.expected_quantity == quantity \
                and self.uom.id == uom_id:
            return values
        values['expected_quantity'] = quantity
        values['uom'] = uom_id
        # update also quantity field if not edited
        if self.quantity == self.expected_quantity:
            values['quantity'] = max(quantity, 0.0)
        return values

    @classmethod
    def create_values4complete(cls, product_id, inventory, quantity, uom_id):
        '''
        Return create values to complete inventory
        '''
        return {
            'inventory': inventory.id,
            'product': product_id,
            'expected_quantity': quantity,
            'quantity': max(quantity, 0.0),
            'uom': uom_id,
        }
