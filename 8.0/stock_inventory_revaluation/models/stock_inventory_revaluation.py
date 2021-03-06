# -*- coding: utf-8 -*-
# © 2015 Eficent Business and IT Consulting Services S.L.
# - Jordi Ballester Alomar
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from openerp import api, fields, models, _
import openerp.addons.decimal_precision as dp
import time
from openerp.exceptions import Warning as UserError

_STATES = [
    ('draft', 'Draft'),
    ('posted', 'Posted'),
    ('cancel', 'Cancelled')]


class StockInventoryRevaluation(models.Model):

    _name = 'stock.inventory.revaluation'
    _description = 'Inventory revaluation'

    @api.model
    def _default_journal(self):
        res = self.env['account.journal'].search([('type', '=', 'general')])
        return res and res[0] or False

    @api.one
    def _get_product_template_qty(self):
        self.qty_available = 0
        for prod_variant in self.product_template_id.product_variant_ids:
            self.qty_available += prod_variant.qty_available

    @api.one
    def _calc_product_template_value(self):
        qty_available = 0
        current_value = 0.0
        quant_obj = self.env['stock.quant']
        for prod_variant in self.product_template_id.product_variant_ids:
            qty_available += prod_variant.qty_available
            if self.product_template_id.cost_method == 'real':
                quants = quant_obj.search([('product_id', '=',
                                            prod_variant.id),
                                           ('location_id.usage', '=',
                                            'internal')])
                for quant in quants:
                    current_value += quant.cost
            else:
                current_value = \
                    self.product_template_id.standard_price * qty_available
        self.current_value = current_value

    name = fields.Char('Reference',
                       help="Reference for the journal entry",
                       readonly=True,
                       required=True,
                       states={'draft': [('readonly', False)]},
                       copy=False,
                       default='/')

    revaluation_type = fields.Selection(
        [('price_change', 'Price Change'),
         ('inventory_value', 'Inventory Debit/Credit')],
        string="Revaluation Type",
        readonly=True, required=True,
        default='price_change',
        help="'Price Change': You can re-valuate inventory values by Changing "
             "the price for a specific product. The inventory price is "
             "changed and inventory value is recalculated according to the "
             "new price.\n "
             "'Inventory Debit/Credit': Changing the value of the inventory. "
             "The quantity of inventory remains unchanged, resulting in a "
             "change in the price",
        states={'draft': [('readonly', False)]})

    remarks = fields.Text('Remarks',
                          help="Displays by default Inventory Revaluation. "
                               "This text is copied to the journal entry.",
                          readonly=True,
                          default='Inventory Revaluation',
                          states={'draft': [('readonly', False)]})

    state = fields.Selection(selection=_STATES,
                             string='Status',
                             readonly=True,
                             required=True,
                             default='draft',
                             states={'draft': [('readonly', False)]})

    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', readonly=True,
        default=lambda self: self.env['res.company']._company_default_get(
            'stock.inventory.revaluation'),
        states={'draft': [('readonly', False)]})

    document_date = fields.Date(
        'Creation date', required=True, readonly=True,
        default=lambda self: fields.Date.context_today(self),
        states={'draft': [('readonly', False)]})

    journal_id = fields.Many2one('account.journal', 'Journal',
                                 default=_default_journal,
                                 readonly=True,
                                 states={'draft': [('readonly', False)]})

    product_template_id = fields.Many2one('product.template', 'Product',
                                          required=True,
                                          domain=[('type', '=', 'product')])

    cost_method = fields.Selection(string="Cost Method", readonly=True,
                                   related='product_template_id.cost_method')

    uom_id = fields.Many2one('product.uom', 'UoM', readonly=True,
                             related="product_template_id.uom_id")

    old_cost = fields.Float('Old cost',
                            help='Displays the previous cost of the '
                                 'product.',
                            digits=dp.get_precision('Product Price'),
                            readonly=True)

    current_cost = fields.Float('Current cost',
                                help='Displays the current cost of the '
                                     'product.',
                                digits=dp.get_precision('Product Price'),
                                compute="_calc_current_cost",
                                readonly=True)

    new_cost = fields.Float('New cost',
                            help="Enter the new cost you wish to assign to "
                                 "the product. Relevant only when the "
                                 "selected revaluation type is Price Change.",
                            digits=dp.get_precision('Product Price'))

    current_value = fields.Float('Current value',
                                 help='Displays the current value of the '
                                      'product.',
                                 digits=dp.get_precision('Account'),
                                 compute="_calc_product_template_value",
                                 readonly=True)

    old_value = fields.Float('Old value',
                             help='Displays the current value of the product.',
                             digits=dp.get_precision('Account'),
                             readonly=True)

    new_value = fields.Float('Credit/Debit amount',
                             help="Enter the amount you wish to credit or "
                                  "debit from the current inventory value of "
                                  "the item. Enter credit as a negative value."
                                  "Relevant only if the selected revaluation "
                                  "type is Inventory Credit/Debit.",
                             digits=dp.get_precision('Account'))

    qty_available = fields.Float(
        'Quantity On Hand', compute='_get_product_template_qty',
        digits_compute=dp.get_precision('Product Unit of Measure'))

    increase_account_id = fields.Many2one(
        'account.account', 'Increase Account',
        help="Define the G/L accounts to be used as the balancing account in "
             "the transaction created by the revaluation. The Increase "
             "Account is used when the inventory value is increased due to "
             "the revaluation.")

    decrease_account_id = fields.Many2one(
        'account.account', 'Decrease Account',
        help="Define the G/L accounts to be used as the balancing account in "
             "the transaction created by the revaluation. The Decrease "
             "Account is used when the inventory value is decreased.")

    move_id = fields.Many2one('account.move', 'Account move', readonly=True,
                              copy=False)

    reval_quant_ids = fields.One2many('stock.inventory.revaluation.quant',
                                      'revaluation_id',
                                      string='Revaluation line quants')

    @api.one
    @api.depends("product_template_id", "product_template_id.standard_price")
    def _calc_current_cost(self):
        self.current_cost = self.product_template_id.standard_price

    @api.one
    @api.constrains('product_template_id', 'company_id')
    def _check_is_stockable(self):
        if self.product_template_id.type != 'product':
            raise UserError(_('Configuration error!\nThe product must be '
                              'stockable.'))

    @api.one
    @api.onchange("product_template_id")
    def _onchange_product_template_id(self):
        if self.product_template_id:
            self.increase_account_id = self.product_template_id.categ_id and \
                self.product_template_id.categ_id.\
                property_inventory_revaluation_increase_account_categ
            self.decrease_account_id = self.product_template_id.categ_id and \
                self.product_template_id.categ_id.\
                property_inventory_revaluation_decrease_account_categ

    @api.model
    def _prepare_move_data(self, date_move):

        period = self.env['account.period'].find(date_move)[0]

        return {
            'narration': self.remarks,
            'date': date_move,
            'ref': self.name,
            'journal_id': self.journal_id.id,
            'period_id': period.id,
        }

    @api.model
    def _prepare_debit_move_line_data(self, amount, account_id, prod_id):
        return {
            'name': self.name,
            'date': self.move_id.date,
            'product_id': prod_id,
            'account_id': account_id,
            'move_id': self.move_id.id,
            'debit': amount
        }

    @api.model
    def _prepare_credit_move_line_data(self, amount, account_id, prod_id):
        return {
            'name': self.name,
            'date': self.move_id.date,
            'product_id': prod_id,
            'account_id': account_id,
            'move_id': self.move_id.id,
            'credit': amount
        }

    @api.model
    def _create_accounting_entry(self, amount_diff):
        timenow = time.strftime('%Y-%m-%d')
        move_data = self._prepare_move_data(timenow)
        datas = self.env['product.template'].get_product_accounts(
            self.product_template_id.id)
        self.move_id = self.env['account.move'].create(move_data).id
        move_line_obj = self.env['account.move.line']

        if not self.decrease_account_id or not self.increase_account_id:
            raise UserError(_("Please add a  Increase Account and "
                              "a Decrease Account."))

        for prod_variant in self.product_template_id.product_variant_ids:
                qty = prod_variant.qty_available
                if qty:
                    if amount_diff > 0:
                        debit_account_id = self.decrease_account_id.id
                        credit_account_id = \
                            datas['property_stock_valuation_account_id']
                    else:
                        debit_account_id = \
                            datas['property_stock_valuation_account_id']
                        credit_account_id = self.increase_account_id.id
                    move_line_data = self._prepare_debit_move_line_data(
                        abs(amount_diff), debit_account_id, prod_variant.id)
                    move_line_obj.create(move_line_data)
                    move_line_data = self._prepare_credit_move_line_data(
                        abs(amount_diff), credit_account_id, prod_variant.id)
                    move_line_obj.create(move_line_data)
                    if self.move_id.journal_id.entry_posted:
                        self.move_id.post()

    @api.one
    def post(self):

        amount_diff = 0.0
        if self.product_template_id.cost_method == 'real':
            for reval_quant in self.reval_quant_ids:
                amount_diff += reval_quant.get_total_value()
                reval_quant.write_new_cost()
            if amount_diff == 0.0:
                return True
        else:
            if self.product_template_id.cost_method in ['standard', 'average']:

                if self.revaluation_type == 'price_change':
                    diff = self.current_cost - self.new_cost
                    amount_diff = self.qty_available * diff
                else:
                    amount_diff = self.current_value - self.new_value
                    if self.new_value < 0:
                        raise UserError(_("The new value for product %s "
                                          "cannot be negative"
                                          % self.product_template_id.name))
                    if self.qty_available <= 0.0:
                        raise UserError(
                            _("Cannot do an inventory value change if the "
                              "quantity available for product %s "
                              "is 0 or negative" %
                              self.product_template_id.name))

                if self.revaluation_type == 'price_change':
                    self.old_cost = self.current_cost
                    self.product_template_id.write({'standard_price':
                                                    self.new_cost})
                else:
                    self.old_cost = self.current_cost
                    self.old_value = self.current_value
                    value_diff = self.current_value - self.new_value
                    new_cost = value_diff / self.qty_available
                    self.product_template_id.write({'standard_price':
                                                    new_cost})

        if self.product_template_id.valuation == 'real_time':
            self._create_accounting_entry(amount_diff)

    @api.model
    def create(self, values):
        sequence_obj = self.env['ir.sequence']
        if values.get('name', '/') == '/':
            values['name'] = sequence_obj.get('stock.inventory.revaluation')
        return super(StockInventoryRevaluation, self).create(values)

    @api.multi
    def button_post(self):
        self.post()
        self.write({'state': 'posted'})
        return True

    @api.multi
    def button_draft(self):
        self.write({'state': 'draft'})
        return True

    @api.multi
    def button_cancel(self):
        moves = self.env['account.move']
        if self.move_id:
            moves += self.move_id
        for reval_quant in self.reval_quant_ids:
            reval_quant.quant_id.write({'cost': reval_quant.old_cost})
        if moves:
            # second, invalidate the move(s)
            moves.button_cancel()
            # delete the move this revaluation was pointing to
            # Note that the corresponding move_lines and move_reconciles
            # will be automatically deleted too
            moves.unlink()
        self.write({'state': 'cancel'})
        return True


class StockInventoryRevaluationQuant(models.Model):

    _name = 'stock.inventory.revaluation.quant'
    _description = 'Inventory revaluation quant'

    revaluation_id = fields.Many2one('stock.inventory.revaluation',
                                     'Revaluation', required=True,
                                     readonly=True, ondelete='cascade')

    quant_id = fields.Many2one(
        'stock.quant', 'Quant', required=True, readonly=True,
        domain=[('quant_id.product_id.product_tmpl_id', '=',
                 'revaluation_id.product_template_id')])

    product_id = fields.Many2one('product.product', 'Product',
                                 readonly=True,
                                 related="quant_id.product_id")

    location_id = fields.Many2one('stock.location', 'Location',
                                  readonly=True,
                                  related="quant_id.location_id")

    qty = fields.Float('Quantity', readonly=True,
                       related="quant_id.qty")

    in_date = fields.Datetime('Incoming Date', readonly=True,
                              related="quant_id.in_date")

    current_cost = fields.Float('Current Cost',
                                readonly=True,
                                related="quant_id.cost")

    old_cost = fields.Float('Previous cost',
                            help='Shows the previous cost of the quant',
                            readonly=True)

    new_cost = fields.Float('New Cost',
                            help="Enter the new cost you wish to assign to "
                                 "the Quant. Relevant only when the "
                                 "selected revaluation type is Price Change.",
                            digits=dp.get_precision('Product Price'),
                            copy=False)

    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', readonly=True,
        related="revaluation_id.company_id")

    def get_total_value(self):
        amount_diff = 0.0
        if self.product_id.product_tmpl_id.cost_method == 'real':
            if self.revaluation_id.revaluation_type != 'price_change':
                raise UserError(_("You can only post quant cost changes."))
            else:
                diff = self.current_cost - self.new_cost
            amount_diff = self.qty * diff
        return amount_diff

    def write_new_cost(self):
        self.old_cost = self.current_cost
        self.quant_id.write({'cost': self.new_cost})
        return True
