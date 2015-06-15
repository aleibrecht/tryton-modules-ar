#!/usr/bin/env python
#This file is part sale_shop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
import unittest
import doctest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction


class SaleShopTestCase(unittest.TestCase):
    'Test SaleShop module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('sale_shop')
        self.company = POOL.get('company.company')
        self.user = POOL.get('res.user')
        self.shop = POOL.get('sale.shop')
        self.location = POOL.get('stock.location')
        self.price_list = POOL.get('product.price_list')
        self.payment_term = POOL.get('account.invoice.payment_term')
        self.sequence = POOL.get('ir.sequence')

    def test0005views(self):
        'Test views'
        test_view('sale_shop')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0010_create_shop(self):
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            #This is needed in order to get default values for other test
            #executing in the same database
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            self.user.write([self.user(USER)], {
                    'main_company': company.id,
                    'company': company.id,
                    })
            CONTEXT.update(self.user.get_preferences(context_only=True))
            with transaction.set_context(company=company.id):
                sequence, = self.sequence.search([
                        ('code', '=', 'sale.sale'),
                        ], limit=1)
                warehouse, = self.location.search([
                        ('code', '=', 'WH'),
                        ])
                price_list, = self.price_list.create([{
                            'name': 'Test',
                            }])
                term, = self.payment_term.create([{
                            'name': 'Payment term',
                            'lines': [
                                ('create', [{
                                            'sequence': 0,
                                            'type': 'remainder',
                                            'days': 0,
                                            'months': 0,
                                            'weeks': 0,
                                            }])]
                            }])
                shop, = self.shop.create([{
                            'name': 'Shop',
                            'warehouse': warehouse.id,
                            'price_list': price_list.id,
                            'payment_term': term.id,
                            'sale_sequence': sequence.id,
                            'sale_invoice_method': 'order',
                            'sale_invoice_method': 'order',
                            }])
                user = self.user(USER)
                self.user.write([user], {
                        'shops': [('add', [shop])],
                        'shop': shop.id,
                         })
            # Clear user values before commiting
            self.user.write([self.user(USER)], {
                    'main_company': None,
                    'company': None,
                    })
            transaction.cursor.commit()


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        SaleShopTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_shop.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
