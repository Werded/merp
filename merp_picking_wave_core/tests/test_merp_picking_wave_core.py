# Copyright 2019 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase
from odoo.exceptions import Warning


class TestMerpPickingWaveCore(TransactionCase):

    def setUp(self):
        super(TestMerpPickingWaveCore, self).setUp()
        self.location_1 = self.env['stock.location'].create({
            'name': 'test_location_1',
            'removal_prio': 2
        })
        self.location_2 = self.env['stock.location'].create({
            'name': 'test_location_2',
            'removal_prio': 3
        })
        product = self.env['product.product'].search([], limit=1)
        company = self.env.user.company_id
        move = self.env['stock.move']

        def create_moves(move, state, qty, product):
            i = 0
            moves = []
            while i <= qty:

                stock_move = move.create({
                    'location_id': self.env.ref('stock.stock_location_stock').id,
                    'company_id': company.id,
                    'product_id': product.id,
                    'state': state,
                    'product_uom_qty': 45.000,
                    'name': 'Test',
                    'product_uom': product.uom_id.id,
                    'location_dest_id': self.env.ref('stock.stock_location_customers').id
                })
                moves.append(stock_move)
                i += 1
            return moves

        self.draft_moves = create_moves(move, 'draft', 4, product)
        self.confirmed_move = create_moves(move, 'confirmed', 1, product)
        self.assigned_move = create_moves(move, 'assigned', 1, product)
        self.picking_type = self.env['stock.picking.type'].search([], limit=2)
        self.procurement_group = self.env['procurement.group'].create({
            'name': 'procurement_group_1',
            'move_type': 'direct'
        })
        self.stock_picking_1 = self.env['stock.picking'].create({
            'name': 'test_stock_picking_1',
            'location_id': self.location_1.id,
            'location_dest_id': self.location_2.id,
            'move_type': 'direct',
            'company_id': company.id,
            'picking_type_id': self.picking_type[0].id
        })
        self.stock_picking_2 = self.env['stock.picking'].create({
            'name': 'test_stock_picking_2',
            'location_id': self.location_2.id,
            'location_dest_id': self.location_1.id,
            'move_type': 'direct',
            'company_id': company.id,
            'picking_type_id': self.picking_type[0].id
        })
        self.picking_batch = self.env['stock.picking.batch'].create({
            'name': 'test_stock_picking_batch',
            'picking_ids': [(4, self.stock_picking_1.id)]
        })

    def test_picking_wave_type(self):
        self.assertEqual(self.picking_batch.picking_wave_type.id, self.picking_type[0].id)

    def test_done(self):
        self.stock_picking_1.write({
            'move_lines': [(4, self.confirmed_move[0].id), (4, self.assigned_move[0].id)]
        })
        self.assertEqual(self.picking_batch.done().get('context').get('sub_done_called'), True)

    def test_confirm_picking(self):
        self.stock_picking_1.write({
            'move_lines': [(4, self.draft_moves[0].id), (4, self.draft_moves[1].id)]
        })
        self.picking_batch.confirm_picking()
        self.assertEqual(self.picking_batch.state, 'in_progress')
        self.assertEqual(self.stock_picking_1.state, 'assigned')
        for stock_move in self.draft_moves[:2]:
            self.assertEqual(stock_move.state, 'assigned')

    def test_first_proc_picking(self):
        for move in self.draft_moves:
            move.write({
                'group_id': self.procurement_group.id
            })
        self.stock_picking_1.write({
            'move_lines': [(4, self.draft_moves[0].id), (4, self.draft_moves[1].id)]
        })
        self.stock_picking_2.write({
            'move_lines': [(4, self.draft_moves[2].id), (4, self.draft_moves[3].id)]
        })
        self.assertEqual(self.stock_picking_2.first_proc_picking, self.stock_picking_1)

    def test_create_stock_picking(self):
        self.assertEqual(self.stock_picking_1.batch_id.picking_wave_type.id, self.picking_type[0].id)
        with self.assertRaises(Warning):
            self.env['stock.picking.batch'].create({
                'name': 'test_stock_picking_batch',
                'picking_ids': [(4, self.stock_picking_1.id)],
                'picking_wave_type': self.picking_type[1].id
            })

    def test_write_stock_picking(self):
        self.picking_batch.write({
            'picking_wave_type': False
        })
        self.stock_picking_1.write({
            'picking_type_id': self.picking_type[1].id
        })
        self.assertEqual(self.picking_batch.picking_wave_type.id, self.picking_type[1].id)
        with self.assertRaises(Warning):
            self.stock_picking_1.write({
                'picking_type_id': self.picking_type[0].id
            })
