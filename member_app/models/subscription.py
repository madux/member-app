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
    def name_get(self):
        result = []
        for record in self:
            result.append(
                (record.id, u"%s - %s" % (record.member_id.partner_id.name, record.identification) 
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
    identification = fields.Char('Identification.', size=6, compute="Domain_Member_Field")
    email = fields.Char('Email', compute="Domain_Member_Field")
    account_id = fields.Many2one('account.account', 'Account', compute="Domain_Member_Field")
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
                              ('partial', 'Partially Paid'),
                              ('done', 'Done'),
                              ], default='draft', string='Status')

    # # # # 
    p_type = fields.Selection([('normal', 'Normal'),
                               ('ano', 'Anomaly'),
                               ('sub', 'Subscription'),

                               ], default='normal', string='Type')
    invoice_id = fields.Many2one('account.invoice', string='Invoice', store=True)
    total_paid = fields.Float('Total Paid', default =0)
    balance_total = fields.Float('Outstanding', default =0, compute="get_balance_total")
    
    @api.depends('total_paid')
    def get_balance_total(self):
        self.balance_total = self.total - self.total_paid
    
    @api.onchange('partner_id')
    def onchange_partner_invoice(self):
        res = {}
        if self.partner_id:
            res['domain'] = {'invoice_id': [('partner_id', '=', self.partner_id.id)]}
        return res

    # # # # 
    periods_month = fields.Selection([
        ('Jan-June 2011', 'Jan-June 2011'),
        ('July-Dec 2011', 'July-Dec 2011'),
        ('Jan-June 2012', 'Jan-June 2012'),
        ('July-Dec 2012', 'July-Dec 2012'),
        ('Jan-June 2013', 'Jan-June 2013'),
        ('July-Dec 2013', 'July-Dec 2013'),
        ('Jan-June 2014', 'Jan-June 2014'),
        ('July-Dec 2014', 'July-Dec 2014'),
        ('Jan-June 2015', 'Jan-June 2015'),
        ('July-Dec 2015', 'July-Dec 2015'),
        ('Jan-June 2016', 'Jan-June 2016'),
        ('July-Dec 2016', 'July-Dec 2016'),
        ('Jan-June 2017', 'Jan-June 2017'),
        ('July-Dec 2017', 'July-Dec 2017'),
        ('Jan-June 2018', 'Jan-June 2018'),
        ('July-Dec 2018', 'July-Dec 2018'),
        ('Jan-June 2019', 'Jan-June 2019'),
        ('July-Dec 2019', 'July-Dec 2019'),
        ('Jan-June 2020', 'Jan-June 2020'),
        ('July-Dec 2020', 'July-Dec 2020'),
        ('Jan-June 2021', 'Jan-June 2021'),
        ('July-Dec 2021', 'July-Dec 2021'),
    ], 'Period', index=True, required=True, readonly=False, copy=False, 
                                           track_visibility='always')

    duration_period = fields.Selection([
        ('Months', 'Months'),
        ('Full Year', 'Full Year'),
    ], 'Duration to Pay', default="Months", index=True, required=False, readonly=False, copy=False, 
                                           track_visibility='always')

    number_period = fields.Integer('No. of Years/Months', default=6)
    date_end = fields.Datetime(
        string='End Date',
        default=fields.Datetime.now,
    )
    
    total = fields.Float(
        'Total Subscription Fee',
        required=True,
        compute="get_total")

    @api.depends('subscription', 'periods_month')
    def get_total(self):
        for rec in self:
            tot = 0.0
            for sub in rec.subscription:
                tot += sub.member_price

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

    @api.one
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
                 
    def _set_dates(self):
        number = 0
        if self.duration_period == "Months":
            number = self.number_period * 30
            
        if self.duration_period == "Full Year":
            number = self.number_period * 365
            
        required_date = datetime.strptime(self.date, '%Y-%m-%d %H:%M:%S')
        self.date_end = required_date + timedelta(days=number)
        
    def check_expiry(self):
        start = datetime.strptime(self.date, '%Y-%m-%d %H:%M:%S')
        end = datetime.strptime(self.date_end, '%Y-%m-%d %H:%M:%S')
        cal = end - start
        total = 0.0
        if self.duration_period == "Months":
            total = cal.days
            record = self.number_period * 30
            if record > total:
                self.send_reminder_message()
                raise ValidationError("The Member's subscription has expired")
            
            else:
                raise ValidationError("The member's subscription has not expired")
            
        elif self.duration_period == "Full Year":
            total = cal.days / 365
            record = self.number_period * 365
            if record > total:
                self.send_reminder_message()
                # raise ValidationError("The Member's subscription has expired")
                message = {
                    'title': 'Subscription Notice',
                    'message': "The member's subscription has not expired"
                }
                
                return {'warning': message}
            
            else:
                # raise ValidationError("The member's subscription has not expired")
                message = {
                    'title': 'Subscription Notice',
                    'message': "The member's subscription has not expired"
                }
                
                return {'warning': message}

    def send_reminder_message(self):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify that you -ID {} , that your membership subscription has expired and is\
        due for payment on the date: {} </br> Kindly contact the Ikoyi Club 1968 for any further enquires. \
        </br>Thanks" .format(self.identification, fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)
 
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
        group_emails = group_users.users[1]
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
        self._set_dates()

    @api.multi  # suscription , mem_manager
    def button_anamoly(self):
        self.write({'state': 'manager_approve', 'p_type': 'ano'})
        return self.send_mail_to_accountmanager()

    @api.multi
    def send_Finmanager_Fine(self):  #  manager_approve , accountboss
        self.write({'state': 'fined'})
        self.send_mail_to_mem_officer()
        return self.payment_button_normal()

    @api.multi
    def payment_button_normal(self):  # suscription, 
        '''name = "."
        amount = 0.0  #  * percent
        level = ''
        if self.p_type != "ano":
            level = 'Renewed Subscription'
            amount = self.total
            name = "Renewed Subscription"
            return self.button_payments(name, amount, level)'''
        self.create_member_bill()

    @api.multi
    def print_receipt_sus(self):
        report = self.env["ir.actions.report.xml"].search(
            [('report_name', '=', 'member_app.subscription_receipt_template')], limit=1)
        if report:
            report.write({'report_type': 'qweb-pdf'})
        return self.env['report'].get_action(
            self.id, 'member_app.subscription_receipt_template')

    @api.multi
    def payment_button_anormally(self):  # suscription, manager_approve
        name = "."
        percent = 12.5 / 100
        amount = 0.0  # * percent
        level = ''
        if self.p_type == "ano":
            level = 'Fine'
            amount = percent * self.total
            name = "Fine"
            return self.button_payments(name, amount, level)

# #  FUNCTIONS # # # #
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
            },
        }
     
    @api.multi
    def create_member_bill(self):
        """ Create Customer Invoice for vendors.
        """
        invoice_list = []
        qty = 1
        for partner in self:
            invoice = self.env['account.invoice'].create({
                'partner_id': partner.member_id.partner_id.id,
                'account_id': partner.member_id.partner_id.property_account_payable_id.id,#partner.account_id.id,
                'fiscal_position_id': partner.member_id.partner_id.property_account_position_id.id,
                'branch_id': self.env.user.branch_id.id,
                # 'origin': self.identification,
                'date_invoice': datetime.today(),
                'type': 'out_invoice', # vendor
                # 'type': 'out_invoice', # customer
            })
            for line in self.subscription:
                product = 0
                products = self.env['product.product']
                product_search = products.search(
                    [('name', '=ilike', line.name)])
                if product_search:
                    product = product_search[0].id
                else:
                    name = self.env['product.product'].create({'name': line.name, 
                                                               'type': 'service',
                                                               'membershipx': True,
                                                               'list_price': line.member_price,
                                                               'taxes_id': []})
                    product = name.id
                prods = products.search(
                    [('id', '=', product)])
                line_values = {
                    'product_id': prods.id, # partner.product_id.id,
                    'price_unit': prods.list_price,
                    'quantity': qty, # name.product_qty,
                    'price_subtotal': prods.list_price * qty,
                    'invoice_id': invoice.id,
                    'invoice_line_tax_ids': [],
                    'account_id': self.member_id.partner_id.property_account_payable_id.id,
                    'name': "Subscription Payments"
                    }
                # create a record in cache, apply onchange then revert back to a dictionary 
                invoice_line = self.env['account.invoice.line'].new(line_values)
                invoice_line._onchange_product_id()
                line_values = invoice_line._convert_to_write(
                     {name: invoice_line[name] for name in invoice_line._cache})
                invoice.write({'invoice_line_ids': [(0, 0, line_values)]})
                invoice_list.append(invoice.id)
            # invoice.compute_taxes()
            #self.write({'invoice_id': [(4, [invoice.id])]})
            partner.write({'invoice_id': invoice.id})
            find_id = self.env['account.invoice'].search(
                [('id', '=', invoice.id)])
            find_id.action_invoice_open()

        return invoice_list

    @api.multi
    def generate_receipt(self):  # verify,

        search_view_ref = self.env.ref(
            'account.view_account_invoice_filter', False)
        form_view_ref = self.env.ref('account.invoice_form', False)
        tree_view_ref = self.env.ref('account.invoice_tree', False)

        return {
            'domain': [('id', 'in', [item.id for item in self.invoice_id])],
            'name': 'Invoices',
            'res_model': 'account.invoice',
            'type': 'ir.actions.act_window',
            'views': [(tree_view_ref.id, 'tree'), (form_view_ref.id, 'form')],
            'search_view_id': search_view_ref and search_view_ref.id,
        }


class RegisterPaymentMemberx(models.Model):
    _inherit = "register.payment.member"
    _order = "id desc"
    '''@api.multi
    def button_pay(self, values):
        self.ensure_one()
        ids = values.get('member_ref')
        data = super(RegisterPaymentMemberx, self).button_pay()
        mem = self.env['subscription.model'].search([('id','=', self.num)])
        if mem:
            # raise Validation('Fire %d' %mem.id)
            mem.write({'state': 'done'}) 
        return data'''


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
    periods_month = fields.Selection([
        ('Jan-June 2011', 'Jan-June 2011'),
        ('July-Dec 2011', 'July-Dec 2011'),
        ('Jan-June 2012', 'Jan-June 2012'),
        ('July-Dec 2012', 'July-Dec 2012'),
        ('Jan-June 2013', 'Jan-June 2013'),
        ('July-Dec 2013', 'July-Dec 2013'),
        ('Jan-June 2014', 'Jan-June 2014'),
        ('July-Dec 2014', 'July-Dec 2014'),
        ('Jan-June 2015', 'Jan-June 2015'),
        ('July-Dec 2015', 'July-Dec 2015'),
        ('Jan-June 2016', 'Jan-June 2016'),
        ('July-Dec 2016', 'July-Dec 2016'),
        ('Jan-June 2017', 'Jan-June 2017'),
        ('July-Dec 2017', 'July-Dec 2017'),
        ('Jan-June 2018', 'Jan-June 2018'),
        ('July-Dec 2018', 'July-Dec 2018'),
        ('Jan-June 2019', 'Jan-June 2019'),
        ('July-Dec 2019', 'July-Dec 2019'),
        ('Jan-June 2020', 'Jan-June 2020'),
        ('July-Dec 2020', 'July-Dec 2020'),
        ('Jan-June 2021', 'Jan-June 2021'),
        ('July-Dec 2021', 'July-Dec 2021'),
    ], 'Period', index=True, required=False, readonly=False, copy=False, 
                                           track_visibility='always')
