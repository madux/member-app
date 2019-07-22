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
        account = self.env['account.invoice'].search([('number','ilike', self.communication)])
        subscription = self.env['subscription.model'].search([('invoice_id', '=', account.id)])#account.id)])
        if not subscription:
            raise ValidationError('No Invoice found')
        elif subscription:
            for rep in subscription:
                if rep.total >= self.amount:
                    rep.write({'state': 'done'})
                else:
                    rep.write({'state': 'partial'})
        return res


    # @api.multi
    # def posts(self):
    #     res = super(account_payment, self).post()
    #     subscription = self.env['subscription.model'].search([])#([('invoice_id.name', 'in', self.communication)])
    #     total = 0.0
    #     lists = []
    #     for rep in subscription:
    #         for invs in rep.invoice_id:
    #             for inv in invs:
    #                 total += inv.amount_total
    #                 lists.append(inv.name)
    #                 if "INV/2019/0076" in lists: #inv.name:
    #                     if inv.total >= total:
    #                         rep.write({'state': 'partial'})
    #                     else:
    #                         rep.write({'state': 'done'})
    #                 else:
    #                     raise ValidationError('No Invoice found')
    #     return res

    #    if subscription:
    #         for rec in subscription:
    #             if rec.total >= self.amount:
    #                 rec.write({'state': 'partial'})
    #             else:
    #                 rec.write({'state': 'done'})
    #     else:
    #         raise ValidationError('No Invoice found')
    #     return res
        
    