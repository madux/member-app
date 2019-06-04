import time
from odoo import models, fields, api, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import except_orm, ValidationError
from odoo.tools import misc, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import http


class Spouse_Exclusion(models.Model):
    _name = "spouse.exclusion"

    sponsor_id = fields.Many2one(
        'member.app',
        'Applied by',
        domain=[
            ('state',
             '!=',
             'suspension')],
        readonly=False,
    )

    name = fields.Many2one(
        'register.spouse.member',
        'Spouse Name',
        domain=[
            ('active',
             '!=',
             True)],
        readonly=False, required=True
    )
    state = fields.Selection([
        ('hon', 'Honourary'),
        ('mem', 'Membership'),
        ('manager', 'Manager'),
        ('done', 'Done'),
    ], default='hon', string='Status')

    email = fields.Char('Email', required=True)
    date_order = fields.Datetime('Offer Date', default=fields.Datetime.now())
    binary_attach_receipt = fields.Binary('Attach Letter')
    binary_fname_receipt = fields.Char('Binary Letter')

    @api.onchange('sponsor_id')
    def domain_name_depend(self):
        domain = {}
        names = []
        for rec in self:
            sponsor = self.env['member.app']
            sponsor_search = sponsor.search([('id', '=', self.sponsor_id.id)])
            for tex in sponsor_search.depend_name:
                names.append(tex.id)
                domain = {'name': [('id', 'in', name)]}
            return {'domain': domain}

    @api.onchange('sponsor_id')
    def name_changes(self):
        for rec in self:
            rec.email = rec.name.email

    @api.multi
    def send_hon_to_member(self):
        for rec in self:
            rec.write({'state': 'mem'})
            self.send_memofficer_mail()

    @api.multi
    def send_member_to_manager(self):
        for rec in self:
            rec.write({'state': 'manager'})

    @api.multi
    def send_manager_confirm(self):
        for rec in self:
            rec.write({'state': 'done'})
            sponsor = self.env['member.app']
            sponsor_search = sponsor.search([('id', '=', self.sponsor_id.id)])
            sponsor_search.write({'active': True})
            self.send_mail_spouse()

    @api.multi
    def send_mail_spouse(self, force=False):
        email_from = self.env.user.company_id.email
        mail_to = self.email
        subject = "Ikoyi Club Guest Confirmation"
        bodyx = "This is a notification message that you have \
        been excluded from being a member of Ikoyi Club on the date: {}. \
        </br> For further enquires,\
         kindly contact {} </br> {} </br>\
        Thanks".format(fields.Date.today(), self.env.user.company_id.name, self.env.user.company_id.phone)
        self.mail_sending_one(email_from, mail_to, bodyx, subject)

    @api.multi
    def send_memofficer_mail(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.membership_officer_ikoyi').id
        extra_user = self.env.ref('member_app.manager_member_ikoyi').id
        groups = self.env['res.groups']
        group_users = groups.search([('id', '=', extra_user)])
        group_emails = group_users.users[0]
        extra = group_emails.login
        bodyx = "Sir/Madam, </br>I wish to notify you that a request to \
        exclude a spouse with name: {} have been sent to you for approval\
        on the date: {}.</br>\
        Kindly <a href={}> </b>Click <a/> to Login to the ERP to view</br> \
        Thanks".format(self.name.partner_id.name, fields.Datetime.now(), self.get_url(self.id, self._name))
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    def mail_sending_one(self, email_from, mail_to, bodyx, subject):
        for order in self:
            mail_tos = str(mail_to)
            email_froms = "Ikoyi Club " + " <" + str(email_from) + ">"
            subject = subject
            mail_data = {
                'email_from': email_froms,
                'subject': subject,
                'email_to': mail_tos,
                #  'email_cc':,#  + (','.join(str(extra)),
                'reply_to': email_from,
                'body_html': bodyx
            }
            mail_id = order.env['mail.mail'].create(mail_data)
            order.env['mail.mail'].send(mail_id)

    def get_url(self, id, model):
        base_url = http.request.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')
        base_url += '/web# id=%d&view_type=form&model=%s' % (id, model)
