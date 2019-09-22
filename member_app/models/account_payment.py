import time
from odoo import models, fields, api, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import except_orm, ValidationError
from odoo.tools import misc, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import http


class account_payment(models.Model):
    _inherit = "account.payment"
    
    balances = fields.Float('Balance', compute="get_balance")
    amount_to_pay = fields.Float('To pay', compute="get_balance")
    
    @api.one
    @api.depends('amount', 'payment_difference')
    def get_balance(self):
        # invoice = self.invoice_ids[0]
        # topay = invoice.residual
        total = self.amount + self.payment_difference
        self.balances = total
        self.amount_to_pay = self.amount + self.balances
        
    @api.multi
    def post(self):
        res = super(account_payment, self).post()
        domain_inv = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        members_search = self.env['member.app'].search(domain_inv)
        if members_search: 
            members_search.state_payment_inv(self.amount, self.payment_date)  
        else:
            pass
        domain_sub = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        sub_search = self.env['subscription.model'].search(domain_sub)
        if sub_search:
            sub_search.state_payment_inv(self.amount, self.payment_date, sub_search, self.payment_difference)
        else:
            pass

        domain_guest = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        guest_search = self.env['register.guest'].search(domain_guest)
        if guest_search:
            guest_search.write({'state': 'wait'}) # state_payment_inv(self.amount, self.payment_date, guest_search, self.payment_difference)
        else:
            pass 
        
        domain_suspend = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        suspend_search = self.env['suspension.model'].search(domain_suspend)
        if suspend_search:
            suspend_search.state_payment_inv()
        else:
            pass 
        
        domain_spouse = [('invoice_id', 'in', [item.id for item in self.invoice_ids])]
        spouse_search = self.env['register.spouse.member'].search(domain_spouse)
        if spouse_search:
            spouse_search.button_make_confirm()
        else:
            pass 
        return res
 