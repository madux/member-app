import time
from odoo import models, fields, api, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import except_orm, ValidationError
from odoo.tools import misc, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import http

TYPE2JOURNAL = {
        'out_invoice': 'sale',
        'in_invoice': 'purchase',
        'out_refund': 'sale',
        'in_refund': 'purchase',
}

class Suspend_Member(models.Model):
    _name= "suspension.model"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _rec_name = "partner_id"

    _sql_constraints = [
        ('name_unique',
         'UNIQUE(partner_id)',
         'Partner must be unique')
    ]
    
    partner_id = fields.Many2one('res.partner', 'Name', domain=[('is_member','=', True)])
    member_id = fields.Many2one('member.app', 'Member ID', domain=[('state','!=', 'suspension')], readonly=False, compute="Domain_Member_Field")
    identification = fields.Char('identification.', size=6)
    email = fields.Char('Email',store=True)
    account_id = fields.Many2one('account.account', 'Account')
    date = fields.Datetime('Date', required=True)
    suspension_date = fields.Datetime('Suspension Date')
    users_followers = fields.Many2many('hr.employee', string='Add followers')
    subscription = fields.Many2many('subscription.payment', string ='Add Sections', compute='get_all_packages')
    package = fields.Many2many('package.model', string ='Packages', readonly=False,  compute='get_all_packages')# ,compute='get_all_packages')
    state = fields.Selection([('draft','Draft'),
                                ('hon_sec','Honourary'),
                                ('manager_approve','Manager'),
                                 ('suspend','Suspended'),
                                ], default = 'draft', string='Status')
    main_house_cost = fields.Float('Main House Fee',required=True)
     
    @api.depends('partner_id')
    def get_all_packages(self):
        get_package = self.env['member.app'].search([('partner_id','=',self.partner_id.id)])
        appends = []
        appends2 = []
        for rec in self:
            for ret in get_package.package:
                appends.append(ret.id)
            for rett in get_package.subscription:
                appends2.append(rett.id)
            rec.package = [(6,0,appends)]
            rec.subscription = [(6,0,appends2)]

    @api.depends('partner_id')
    def Domain_Member_Field(self):
        for record in self:
            member = self.env['member.app'].search([('partner_id', '=', record.partner_id.id)])
            for tec in member:
                record.main_house_cost = tec.main_house_cost
                record.account_id = tec.account_id.id
                record.identification = tec.identification
                record.email = tec.email
                record.member_id = tec.id
 # # #  BUTTON S             
    @api.multi
    def send_to_hon(self):
        self.write({'state':'hon_sec'})
        self.send_mail_to_manager()
        
    @api.multi
    def send_to_hon_back(self):
        self.write({'state':'draft'})
        # self.send_mail_to_manager()
        
        
    @api.multi
    def send_hon_to_manager(self):
        self.write({'state':'manager_approve'})
        self.send_mail_to_manager()
        
    @api.multi
    def send_manager_to_approve(self):
        memberx = self.env['member.app'].search([('partner_id', '=', self.partner_id.id)]) 
        if memberx:
            for rec in memberx:
                rec.write({'state':"suspension", 'active':False, 'activity':'inact'})
            self.write({'state':'suspend', 'suspension_date':fields.Datetime.now()})
            
            self.send_mail_suspend()
        else:
            raise ValidationError('No member record found')
        
    @api.one
    def payment_button(self):
        name = "Suspension Payment Fee"
        percent = 50/100
        amount = self.main_house_fee * percent
        level = 'Suspension'
        return self.button_payments(name,amount,level)
    
# #  FUNCTIONS # # # # #     
    @api.multi
    def send_mail_suspend(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra=self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify that the member with ID {} have been Suspended from Ikoyi Club on the date: {} </br>\
             Kindly contact the Ikoyi Club 1968 for any further enquires. </br><a href={}> </b>Click <a/> to review. Thanks"\
             .format(self.identification,fields.Datetime.now(),self.get_url(self.id, self._name))
        self.mail_sending(email_from,group_user_id,extra,bodyx) 
        
    @api.multi
    def send_mail_to_manager(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.membership_honour_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        
        extra=self.email
        bodyx = "Sir/Madam, </br>We wish to notify you that a member with ID: {} have been Suspended from Ikoyi Club on the date: {} </br>\
             Kindly <a href={}> </b>Click <a/> to Login to the ERP to view</br> \
             Thanks".format(self.identification,fields.Datetime.now(),self.get_url(self.id, self._name))
        self.mail_sending(email_from,group_user_id,extra,bodyx) 
            
        
    def get_url(self, id, model):    
        base_url = http.request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        base_url += '/web# id=%d&view_type=form&model=%s' % (id, model)
        
    def mail_sending(self, email_from,group_user_id,extra, bodyx):
        from_browse =self.env.user.name
        groups = self.env['res.groups']
        for order in self:
            group_users = groups.search([('id','=',group_user_id)])
            group_emails = group_users.users
            followers = []
            email_to=[]
            for group_mail in self.users_followers:
                followers.append(group_mail.work_email)

            for gec in group_emails:
                email_to.append(gec.login)

            email_froms = str(from_browse) + " <"+str(email_from)+">"
            mail_appends = (', '.join(str(item)for item in followers))
            mail_to = (','.join(str(item2)for item2 in email_to))
            subject = "Membership Suspension Notification"

            extrax = (', '.join(str(extra)))
            followers.append(extrax)
            mail_data={
                'email_from': email_froms,
                'subject':subject,
                'email_to':mail_to,
                'email_cc':mail_appends,#  + (','.join(str(extra)),
                'reply_to': email_from,
                'body_html':bodyx
                }
            mail_id =  order.env['mail.mail'].create(mail_data)
            order.env['mail.mail'].send(mail_id)
    
    # order.write({'payment_line': [(0, 0, values)],'payment_line2': [(0, 0, values)],'payment_status':'gpaid'})
    
    @api.multi
    def button_payments(self,name,amount,level):#  Send memo back
        return {
              'name':name,
              'view_type': 'form',
              "view_mode": 'form',
              'res_model': 'register.payment.member',
              'type': 'ir.actions.act_window',
              'target': 'new',
              'context': {
                  'default_payment_type': "outbound",
                  'default_date': fields.Datetime.now(),
                  'default_amount':amount,
                  
                  'default_partner_id':self.partner_id.id,
                  'default_member_ref':self.member_id.id,
                  'default_name':"Membership Payments",
                  'default_level':level,
                  'default_to_pay':amount

                  # 'default_communication':self.number
              },
        }