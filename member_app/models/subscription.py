import time
from odoo import models, fields, api, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import except_orm, ValidationError
from odoo.tools import misc, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import http


from gtts import gTTS
import os
 

TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale',
    'in_refund': 'purchase',
}


class Subscription_Member(models.Model):
    _name = "subscription.model"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _rec_name = "partner_id"

    _sql_constraints = [
        ('name_unique',
         'UNIQUE(partner_id)',
         'Partner must be unique')
    ]
    
    
    
    @api.multi
    def AI_voice(self):
        s = []
        '''with open(fname, 'r') as f:
            for line in f:
                s.append(line)'''
        member = self.env['member.app'].search([])
        for rec in member: 
            s.append(rec.partner_id.name + " registered using " + rec.phone + " as Phone Number")
        
        text = str(s)
        obj = gTTS(text=text, lang='en', slow=False)
        obj.save("/welcome.mp3") # Documents
        os.system("/welcome.mp3")
        print "Done"
        


    @api.multi
    def name_get(self):
        result = []
        for record in self:
            result.append(
                (record.id,u"%s - %s" % (record.member_id.partner_id.name, record.identification) 
                 ))
            record.name = result
        return result
    # url_audio = fields.Char('Audio.', size=6)
    
    partner_id = fields.Many2one(
        'res.partner', 'Name', domain=[
            ('is_member', '=', True)])
    member_id = fields.Many2one(
        'member.app',
        'Member ID',
        domain=[
            ('state',
             '!=',
             'suspension')],
        readonly=False,
        compute="Domain_Member_Field")
    identification = fields.Char('Identification.', size=6)
    
    email = fields.Char('Email', store=True)
    account_id = fields.Many2one('account.account', 'Account')
    date = fields.Datetime('Date', required=True)
    # suspension_date = fields.Datetime('Suspension Date')

    users_followers = fields.Many2many('hr.employee', string='Add followers')
    subscription = fields.Many2many(
        'subscription.payment',
        string='Add Sections',
        readonly=False,
        store=True,
        compute='get_all_packages')
    package = fields.Many2many(
        'package.model',
        string='Packages',
        readonly=False,
        store=True,
        compute='get_all_packages')  #  ,compute='get_all_packages')
    state = fields.Selection([('draft', 'Draft'),
                              ('suscription', 'Suscribed'),
                              ('manager_approve', 'F&A Manager'),
                              ('fined', 'Fined'),
                              ('done', 'Done'),
                              ], default='draft', string='Status')

    # # # # 
    p_type = fields.Selection([('normal', 'Normal'),
                               ('ano', 'Anomaly'),
                               ('sub', 'Subscription'),

                               ], default='normal', string='Type')

    # # # # 
    periods_month = fields.Selection([
                                      ('1st Half', 'Ist Half'),
                                      ('Full Year', 'Full Year'),
                                      ('2nd Half', '2nd Half'),

                                      ],default="1st Half", string='Subscription Periods', required=True)

    # main_house_cost = fields.Float('Main House Fee',required=True)
    # # # # 
    total = fields.Float(
        'Total Subscription Fee',
        required=True,
        compute="get_total")

    @api.depends('subscription', 'periods_month')
    def get_total(self):
        for rec in self:
            tot = 0.0
            overall = 0.0

            for sub in rec.subscription:
                tot += sub.member_price

            '''if rec.periods_month == 'full_Year':
                tot = tot * 12
            elif rec.periods_month == "quarter_ly":
                tot = tot * 3
            else:
                tot = tot'''
            rec.total = tot

    @api.depends('partner_id')
    def get_all_packages(self):
        get_package = self.env['member.app'].search(
            [('partner_id', '=', self.partner_id.id)])
        appends = []
        appends2 = []
        #  for rec in self:
        for ret in get_package.package:
            appends.append(ret)
        for rett in get_package.subscription:
            appends2.append(rett)
        for r in appends:
            self.package = [(4, r.id)]  #  [(6,0,r.id)]
        for r2 in appends2:
            self.subscription = [(4, r2.id)]  #  [(6,0,r2.id)] [(4,r)] o(n2)

    @api.depends('partner_id')
    def Domain_Member_Field(self):
        for record in self:
            member = self.env['member.app'].search(
                [('partner_id', '=', record.partner_id.id)])
            for tec in member:
                # record.main_house_cost = tec.main_house_cost
                record.account_id = tec.account_id.id
                record.identification = tec.identification
                record.email = tec.email
                record.member_id = tec.id

 #  BUTTON S
    def button_send_mail(self):  #  draft
        self.send_mail_to_member()

    @api.multi
    def send_mail_to_member(self, force=False):  #  draft
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify that you -ID {} , that your membership subscription is \
        due for payment on the date: {} </br> Kindly contact the Ikoyi Club 1968 for any further enquires. \
        </br>Thanks" .format(self.identification, fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def send_mail_to_member_sub(self, force=False):  #  draft
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify that you -ID {} , that your membership subscription \
        have been updated on the date: {}. </br> Kindly contact the Ikoyi Club 1968 for any further enquires. \
        </br>Thanks" .format(self.identification, fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def send_mail_to_accountmanager(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('ikoyi_module.account_boss_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id

        extra = self.email
        bodyx = "Sir/Madam, </br>We wish to notify you that a member with ID: {} had Anomalities on renewal payments on the date: {}.</br>\
             Kindly <a href={}> </b>Click <a/> to Login to the ERP to view</br> \
             Thanks".format(self.identification, fields.Datetime.now(), self.get_url(self.id, self._name))
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def send_mail_to_mem_officer(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.membership_officer_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra_user = self.env.ref('member_app.manager_member_ikoyi').id

        groups = self.env['res.groups']
        group_users = groups.search([('id', '=', extra_user)])
        group_emails = group_users.users[0]
        extra = group_emails.login

        #  extra=self.email
        bodyx = "Sir/Madam, </br>We wish to notify you that a member with ID: {} had Anomalities on renewal payments on the date: {}.</br>\
             Kindly <a href={}> </b>Click <a/> to Login to the ERP to view</br> \
             Thanks".format(self.identification, fields.Datetime.now(), self.get_url(self.id, self._name))
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def button_subscribe(self):  #  draft, fine
        self.write({'state': 'suscription'})
        self.send_mail_to_member_sub()

    @api.multi  #  suscription , mem_manager
    def button_anamoly(self):
        self.write({'state': 'manager_approve', 'p_type': 'ano'})
        return self.send_mail_to_accountmanager()

    @api.multi
    def send_Finmanager_Fine(self):  #  manager_approve , accountboss
        self.write({'state': 'fined'})
        self.send_mail_to_mem_officer()
        return self.payment_button_normal()

    @api.multi
    def payment_button_normal(self):  #  suscription, 
        name = "."
        amount = 0.0  #  * percent
        level = ''
        if self.p_type != "ano":
            level = 'Renewed Subscription'
            amount = self.total
            name = "Renewed Subscription"
            return self.button_payments(name, amount, level)
    @api.multi
    def print_receipt_sus(self):
        report = self.env["ir.actions.report.xml"].search(
            [('report_name', '=', 'member_app.subscription_receipt_template')], limit=1)
        if report:
            report.write({'report_type': 'qweb-pdf'})
        return self.env['report'].get_action(
            self.id, 'member_app.subscription_receipt_template')    
    @api.multi
    def payment_button_anormally(self):  #  suscription, manager_approve
        name = "."
        percent = 12.5 / 100
        amount = 0.0  #  * percent
        level = ''
        if self.p_type == "ano":
            level = 'Fine'
            amount = percent * self.total
            name = "Fine"
            return self.button_payments(name, amount, level)

# #  FUNCTIONS # # # # # 
    @api.multi
    def send_mail_suspend(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify that the member with ID {} have been Suspended from Ikoyi Club on the date: {} </br>\
             Kindly contact the Ikoyi Club 1968 for any further enquires. </br><a href={}> </b>Click <a/> to review. Thanks"\
             .format(self.identification, fields.Datetime.now(), self.get_url(self.id, self._name))
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    def get_url(self, id, model):
        base_url = http.request.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')
        base_url += '/web# id=%d&view_type=form&model=%s' % (id, model)

    def mail_sending(self, email_from, group_user_id, extra, bodyx):
        from_browse = self.env.user.name
        groups = self.env['res.groups']
        for order in self:
            group_users = groups.search([('id', '=', group_user_id)])
            group_emails = group_users.users
            followers = []
            email_to = []
            for group_mail in self.users_followers:
                followers.append(group_mail.work_email)

            for gec in group_emails:
                email_to.append(gec.login)

            email_froms = str(from_browse) + " <" + str(email_from) + ">"
            mail_appends = (', '.join(str(item)for item in followers))
            mail_to = (','.join(str(item2)for item2 in email_to))
            subject = "Membership Suspension Notification"

            extrax = (', '.join(str(extra)))
            followers.append(extrax)
            mail_data = {
                'email_from': email_froms,
                'subject': subject,
                'email_to': mail_to,
                'email_cc': mail_appends,  #  + (','.join(str(extra)),
                'reply_to': email_from,
                'body_html': bodyx
            }
            mail_id = order.env['mail.mail'].create(mail_data)
            order.env['mail.mail'].send(mail_id)

    # order.write({'payment_line': [(0, 0, values)],'payment_line2': [(0, 0, values)],'payment_status':'gpaid'})

    @api.multi
    def button_payments(self, name, amount, level):  #  Send memo back
        return {
            'name': name,
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'register.payment.member',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_payment_type': "outbound",
                'default_date': fields.Datetime.now(),
                'default_amount': amount,

                'default_partner_id': self.partner_id.id,
                'default_member_ref': self.member_id.id,
                'default_name': "Subscription Payments",
                'default_level': level,
                'default_to_pay': amount,
                'default_num':self.id,
                'default_p_type': self.p_type,

                #  'default_communication':self.number
            },
        }
        
        
class RegisterPaymentMemberx(models.Model):
    _inherit = "register.payment.member"
    _order = "id desc"
    @api.multi
    def button_pay(self,values):
        self.ensure_one()
        ids = values.get('member_ref')
        data = super(RegisterPaymentMemberx,self).button_pay()
        mem = self.env['subscription.model'].search([('id','=', self.num)])
        if mem:
            #raise Validation('Fire %d' %mem.id)
            mem.write({'state':'done'})
            
        return data

class subscription_LineMain(models.Model):
    _name = "subscription.line"

    member_id = fields.Many2one('member.app', 'Member ID')
    sub_order = fields.Many2one('subscription.model', 'Member ID')
    name = fields.Char('Activity', required=True)

    total_price = fields.Float(
        string='Total Price',
        digits=dp.get_precision('Product Price'),
        required=True)
    paid_amount = fields.Float(string='Paid Amount')
    balance = fields.Float(string='Balance')

    pdate = fields.Date(
        'Subscription Date',
        default=fields.Date.today(),
        required=True)
    periods_month = fields.Selection([('1st Half', '1st Half'),
                                      ('2nd Half', '2nd Half'),
                                      ('Full Year', 'Full Year'),

                                      ], string='Periods', required=True)
