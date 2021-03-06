# -*- coding: utf-8 -*-
# © 2015 Eficent Business and IT Consulting Services S.L. (www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from openerp import models, api


class EasyReconcileAdvanced(models.AbstractModel):

    _inherit = 'easy.reconcile.advanced'

    @api.model
    def _base_columns(self):
        """ Mandatory columns for move lines queries
        An extra column aliased as ``key`` should be defined
        in each query."""
        aml_cols = super(EasyReconcileAdvanced, self)._base_columns()
        aml_cols.append('account_move_line.purchase_line_id')
        aml_cols.append('account_move_line.product_id')
        return aml_cols
