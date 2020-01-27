# Copyright 2019 VentorTech OU
# Part of Ventor modules. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def sort_printer_picking_list(self, move_line_ids):
        """ sort list of pack operations by configured field
        """
        strategy = self.env.user.company_id.outgoing_routing_strategy
        strategy_order = int(self.env.user.company_id.outgoing_routing_order)

        if strategy == 'product':
            return move_line_ids.sorted(key=lambda m: m.product_id.name,
                                        reverse=int(strategy_order))

        return move_line_ids.sorted(
            key=lambda r: getattr(r.location_id, strategy, 'None'),
            reverse=strategy_order
        )
