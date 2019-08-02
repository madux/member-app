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

    
    @api.multi
    def post(self):
        res = super(account_payment, self).post()
        # import pdb; pdb.set_trace()
        product_name = 'Subscription'
        product = 0
        lists = []
        sub_item = []
        account = self.env['account.invoice'].search([('number', '=', self.communication)])
        subscription = self.env['subscription.model'].search([('invoice_id', '=', account.id)])
        if subscription:
            for rep in subscription:
                member_id = rep.member_id.id
                member_browse = self.env['member.app'].search([('id', '=', member_id)])
                amount_to_pay = self.amount + member_browse.balance_total
                products = self.env['product.product']
                product_search = products.search(
                        [('name', 'ilike', product_name)])
                if product_search:
                    product = product_search[0].id
                else:
                    pro = products.create({'name': product_name, 'membershipx': True})
                    product = pro.id
                balance = rep.total - amount_to_pay
                values = (0, 0,
                           {'member_idx': member_id,
                            'product_id': product,
                            'paid_amount': amount_to_pay,
                            'balance': balance,
                            'pdate': self.payment_date,
                            'member_price': rep.total,
                            'name': "Subscription Payment"})
                lists.append(values)
                rep.total_paid += self.amount
                if rep.total_paid + self.amount >= rep.total: 
                    rep.write({'state': 'done'})
                else:
                    rep.write({'state': 'partial'})
                for rex in rep.subscription:
                    sub_item.append(rex.id)
                if member_browse:
                    # member_browse.balance_total += balance
                    member_browse.payment_line2 = lists
                    member_browse.subscription = sub_item
                    
                else:
                    raise ValidationError('We do not find any record related to this member')

        return res
