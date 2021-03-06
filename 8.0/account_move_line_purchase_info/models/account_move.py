# -*- coding: utf-8 -*-
# © 2015 Eficent Business and IT Consulting Services S.L. (www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from openerp import fields, models


class AccountMoveLine(models.Model):

    _inherit = 'account.move.line'

    purchase_line_id = fields.Many2one('purchase.order.line',
                                       'Purchase Order Line',
                                       ondelete='set null', select=True)
    purchase_id = fields.Many2one('purchase.order',
                                  related='purchase_line_id.order_id')
