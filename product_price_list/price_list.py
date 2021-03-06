#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import tokenize
from StringIO import StringIO
from trytond.model import ModelView, ModelSQL, MatchMixin, fields
from trytond.tools import safe_eval
from trytond.pyson import If, Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend

__all__ = ['PriceList', 'PriceListLine']


# code snippet taken from http://docs.python.org/library/tokenize.html
def decistmt(s):
    """Substitute Decimals for floats in a string of statements.

    >>> from decimal import Decimal
    >>> s = 'print +21.3e-5*-.1234/81.7'
    >>> decistmt(s)
    "print +Decimal ('21.3e-5')*-Decimal ('.1234')/Decimal ('81.7')"

    >>> exec(s)
    -3.21716034272e-007
    >>> exec(decistmt(s))
    -3.217160342717258261933904529E-7
    """
    result = []
    # tokenize the string
    g = tokenize.generate_tokens(StringIO(s).readline)
    for toknum, tokval, _, _, _ in g:
        # replace NUMBER tokens
        if toknum == tokenize.NUMBER and '.' in tokval:
            result.extend([
                (tokenize.NAME, 'Decimal'),
                (tokenize.OP, '('),
                (tokenize.STRING, repr(tokval)),
                (tokenize.OP, ')')
            ])
        else:
            result.append((toknum, tokval))
    return tokenize.untokenize(result)


class PriceList(ModelSQL, ModelView):
    'Price List'
    __name__ = 'product.price_list'

    name = fields.Char('Name', required=True, translate=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    lines = fields.One2Many('product.price_list.line', 'price_list', 'Lines')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def _get_context_price_list_line(self, party, product, unit_price,
            quantity, uom):
        '''
        Get price list context for unit price

        :param party: the BrowseRecord of the party.party
        :param product: the BrowseRecord of the product.product
        :param unit_price: a Decimal for the default unit price in the
            company's currency and default uom of the product
        :param quantity: the quantity of product
        :param uom: the BrowseRecord of the product.uom
        :return: a dictionary
        '''
        return {
            'unit_price': unit_price,
        }

    def compute(self, party, product, unit_price, quantity, uom,
            pattern=None):
        '''
        Compute price based on price list of party

        :param unit_price: a Decimal for the default unit price in the
            company's currency and default uom of the product
        :param quantity: the quantity of product
        :param uom: a instance of the product.uom
        :param pattern: a dictionary with price list field as key
            and match value as value
        :return: the computed unit price
        '''

        Uom = Pool().get('product.uom')

        if pattern is None:
            pattern = {}

        pattern = pattern.copy()
        pattern['product'] = product and product.id or None
        pattern['quantity'] = Uom.compute_qty(uom, quantity,
            product.default_uom, round=False) if product else quantity

        for line in self.lines:
            if line.match(pattern):
                with Transaction().set_context(
                        self._get_context_price_list_line(party, product,
                            unit_price, quantity, uom)):
                    return line.get_unit_price()
        return unit_price


class PriceListLine(ModelSQL, ModelView, MatchMixin):
    'Price List Line'
    __name__ = 'product.price_list.line'

    price_list = fields.Many2One('product.price_list', 'Price List',
            required=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product')
    sequence = fields.Integer('Sequence')
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
            depends=['unit_digits'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    formula = fields.Char('Formula', required=True,
        help=('Python expression that will be evaluated with:\n'
            '- unit_price: the original unit_price'))

    @classmethod
    def __setup__(cls):
        super(PriceListLine, cls).__setup__()
        cls._order.insert(0, ('price_list', 'ASC'))
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'invalid_formula': ('Invalid formula "%(formula)s" in price '
                    'list line "%(line)s".'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(PriceListLine, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    @staticmethod
    def default_formula():
        return 'unit_price'

    @fields.depends('product')
    def on_change_with_unit_digits(self, name=None):
        if self.product:
            return self.product.default_uom.digits
        return 2

    @classmethod
    def validate(cls, lines):
        super(PriceListLine, cls).validate(lines)
        for line in lines:
            line.check_formula()

    def check_formula(self):
        '''
        Check formula
        '''
        pool = Pool()
        PriceList = pool.get('product.price_list')
        context = PriceList()._get_context_price_list_line(None, None,
                Decimal('0.0'), 0, None)

        with Transaction().set_context(**context):
            try:
                if not isinstance(self.get_unit_price(), Decimal):
                    self.raise_user_error('invalid_formula', {
                            'formula': self.formula,
                            'line': self.rec_name,
                            })
            except Exception:
                self.raise_user_error('invalid_formula', {
                        'formula': self.formula,
                        'line': self.rec_name,
                        })

    def match(self, pattern):
        if 'quantity' in pattern:
            pattern = pattern.copy()
            if self.quantity > pattern.pop('quantity'):
                return False
        return super(PriceListLine, self).match(pattern)

    def get_unit_price(self):
        '''
        Return unit price (as Decimal)
        '''
        context = Transaction().context.copy()
        context['Decimal'] = Decimal
        return safe_eval(decistmt(self.formula), context)
