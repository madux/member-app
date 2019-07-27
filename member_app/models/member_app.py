import time
from odoo import models, fields, api, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import except_orm, ValidationError
from odoo.tools import misc, DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from odoo import http
# Add this to member.app
# def send_induction_mail(self):
#     send_induction_mail


TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale',
    'in_refund': 'purchase',
}


class Account_payment(models.Model):
    _inherit = "account.payment"
    _order = "id desc"

    member_id = fields.Many2one('member.app', string="Payment Ref")
    filex = fields.Binary("Evidence of Payment")
    file_namex = fields.Char("FileName")


class App_Member(models.Model):
    _name = "member.app"
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    _sql_constraints = [
        ('name_unique',
         'UNIQUE(identification, partner_id, temp_id)',
         'Partner or Identification Numbers must be unique')
    ]

    @api.model
    def create(self, vals):
        res = super(App_Member, self).create(vals)
        partner_id = vals.get('partner_id')
        partner = self.env['res.partner'].search([('id', '=', partner_id)])
        partner.write({'street': vals.get('street'),
                       'street2': vals.get('street'),
                       'email': vals.get('email'),
                       'state_id': vals.get('state_id'),
                       'title': vals.get('title'),
                       'image': vals.get('image'),
                       'phone': vals.get('phone'),
                       'function': vals.get('occupation')})
        #  partner.write({'is_member':True})
        return res

    @api.constrains('depend_name')
    def _check_dependant(self):
        if self.state in ['white', 'draft', 'issue_green', 'green', 'wait', 'interview']:
            for rec in self:
                if len(rec.depend_name) > 1:
                    raise ValidationError('Spouse at this stage cannot be more than one')

    @api.model
    def _needaction_domain_get(self):
        if self.env.user == "Administrator":
            return False  #  don't show to Bob!
        return [('state', 'in', ['white', 'green', 'ord', 'life'])]

    #  CANNOT DELETE MEMBERS ON LIFE
    @api.multi
    def unlink(self):
        for holiday in self.filtered(
            lambda holiday: holiday.state not in [
                'green',
                'manager',
                'manager_two',
                'ord',
                'issue_green',
                'temp',
                'life']):
            raise ValidationError(
                _('You cannot delete a Member who is in %s state.') %
                (holiday.state,))
        return super(App_Member, self).unlink()

    def _get_requester(self):
        for i in self:
            empl_obj = self.env['product.template'].search(
                [('membershipx_white', '=', True)])
            pro_id = empl_obj.id
            return pro_id

    #  GETS THE COUNTRY FROM STATE_ID
    @api.multi
    def name_get(self):
        if not self.ids:
            return []
        res = []
        for field6 in self.browse(self.ids):
            partner = str(field6.partner_id.name)
            res.append((field6.id, partner))
        return res

    @api.onchange('partner_id')
    def _get_state(self):
        for r in self.partner_id:
            #  r=rec.partner_id.id
            street = r.street
            country = r.country_id.id
            city = r.city
            #  city=r.city
            post = r.function
            phone = r.phone
            state = r.state_id
            title = r.title.id
            email = r.email
            image = r.image
            self.country_id = country
            self.state_id = state
            self.city = city
            self.phone = phone
            self.title = title
            self.image = image
            self.occupation = post
            self.email = email

    image = fields.Binary(
        "Image",
        attachment=True,
        help="This field holds the image used as avatar for this contact, limited to 1024x1024px",
    )
    image_medium = fields.Binary(
        "Medium-sized image",
        attachment=True,
        help="Medium-sized image of this contact. It is automatically "
        "resized as a 128x128px image, with aspect ratio preserved. "
        "Use this field in form views or some kanban views.")
    image_small = fields.Binary(
        "Small-sized image",
        attachment=True,
        help="Small-sized image of this contact. It is automatically "
        "resized as a 64x64px image, with aspect ratio preserved. "
        "Use this field anywhere a small image is required.")

    partner_id = fields.Many2one(
        'res.partner', 'Name', domain=[
            ('is_member', '=', True)])
    account_id = fields.Many2one('account.account', 'Account')
    city = fields.Char('City')
    street = fields.Char('Street')
    url = fields.Char('Website')
    phone = fields.Char('Phone')

    state_id = fields.Many2one('res.country.state', store=True)
    country_id = fields.Many2one('res.country', 'Country', store=True)
    dob = fields.Datetime('Date Of Birth', required=True)
    email = fields.Char('Email', store=True)
    occupation = fields.Char('Job title')
    nok = fields.Many2one('res.partner', 'Next of Kin', store=True)
    title = fields.Many2one('res.partner.title', 'Title', store=True)
    #  GET MEMBERS FROM MEMBERS APP
    # sponsor = fields.Many2one('res.partner',string='Sponsors', domain=[('is_member','=', True)])
    sponsor = fields.Many2many('res.partner', string='Sponsors')
    #  IF MEDICAL STATUS SELECTED, MEDICAL DESC APPEARS TO ADD DESC.
    medical_status = fields.Boolean('Medical Issues')
    medical_desc = fields.Text('Describe Health Status')
    associate_member = fields.Many2one('member.app', 'Associate Member Name')
    payment_status = fields.Selection([('draft',
                                        'Draft'),
                                       ('open',
                                        'Prospect'),
                                       ('gpaid',
                                        'Green Prospect'),
                                       ('issue',
                                        'Green Issued'),
                                       ('paid',
                                        'Paid')],
                                      default='draft',
                                      string='Payment status')
    identification = fields.Char('ID No.', size=8)
    payment_line = fields.One2many(
        'member.payment',
        'member_id',
        string='Payment line ids')
    payment_line2 = fields.One2many(
        'member.payment.new',
        'member_idx',
        string='Payment line ids')

    #  IF MEMBER TYPE, ADD COST OF MEMBER TYPE TO AMOUNT

    product_id = fields.Many2one(
        'product.product', string='Membership type', default=_get_requester, domain=[
            ('membershipx', '=', True)], required=False)
    member_price = fields.Float(
        string='Member Price',
        compute="get_section_member_price",
        required=True,
        readonly=False)
    white_member_price = fields.Float(
        string='White Membership cost', default=2000.00)
    payment_plan = fields.Many2one('account.payment.term', 'Payment Terms')
    payment_breakdown = fields.One2many(
        'plot.payment.breakdowns',
        'project_and_plot_id',
        'Payment Breakdown')
    payment_type = fields.Selection([('installment', 'Installment'),
                                     ('outright', 'OutRight Payment')],
                                    "Payment Type")

    #  CALCULATE MMBER SUBSCRIPTION
    total = fields.Integer(
        'Total Including Subscription',
        compute='get_totals')
    total_subsequent = fields.Integer(
        'Total Subsequent Subscription',
        compute='get_totals_sub')
    balance_total = fields.Integer(
        'Outstandings',
        )

    #  CALCULATE PAYMENT DEADLINE account_id

    due_date = fields.Datetime('Due payment date ')
    date_order = fields.Date('Offer Date', default=fields.Date.today())
    membership_date_from = fields.Date(
        string='Membership Start Date',
        help='Date from which membership becomes active.')
    membership_date_to = fields.Date(
        string='Membership End Date',
        help='Date until which membership remains active.')

    invoice_id = fields.Many2one('account_id', 'Invoice', store=True)
    asso_member = fields.Boolean(string='Associate Member')

    active = fields.Boolean(string='Active', default=True)
    #  domain=[('is_member','=', True)]))
    depend_name = fields.Many2many(
        'register.spouse.member',
        string="Dependents")
    # spouse_depends = fields.Many2many('register.spouse.member', string="Dependents")
    # # # # # # # # # # # # # # # # # # # # # # #  NEW FIELD # # # # # # # # # # # # # # # # # # # # # # # # # 
    binary_attach_cv = fields.Binary('Attach CV')
    binary_fname_cv = fields.Char('Binary Name')

    binary_attach_letter = fields.Binary('Attach Letter')
    binary_fname_letter = fields.Char('Binary Name')
    users_followers = fields.Many2many('hr.employee', string='Add followers')
    date_pickup = fields.Datetime('Date of Form Pickup')
    date_issue_green = fields.Datetime('Green Card Issued on')
    duration_pick = fields.Float(
        'Pickup Duration',
        store=True,
        compute='get_duration_pick')
    delay_charges = fields.Float(
        'Delay Charges',
        store=True,
        compute='check_pickupp_duration')
    int_form_price = fields.Float(
        'Intending Member Form Price',
        required=True,
        default=8000)
    section_heads = fields.Many2many('res.partner', string='Section Heads')
    subscription = fields.Many2many(
        'subscription.payment',
        string='Add Sections')
    member_age = fields.Integer(
        'Age',
        required=True,
        compute="get_duration_age")
    date_green_pickup = fields.Datetime('Date of Green Form')
    penalty_charges = fields.Float(
        'Penalty Charges',
        store=True,
        compute='check_pickupp_duration')
    duration_pick_green = fields.Float(
        'Green Pickup Duration',
        store=True,
        compute='get_green_duration_pick')
    green_form_price = fields.Float(
        'Green Form Price',
        required=True,
        default=20000)
    activity = fields.Selection([('act',
                                  'Active'),
                                 ('inact',
                                  'InActive'),
                                 ('dom',
                                  'Dormant'),
                                 ],
                                'Active Status',
                                default='act',
                                index=True,
                                required=True,
                                readonly=False,
                                copy=False,
                                track_visibility='always')

    subscription_period = fields.Selection([
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

    duration_period = fields.Selection([
        ('Months', 'Months'),
        ('Full Year', 'Full Year'),
    ], 'Duration to Pay', Default="Months", index=True, required=False, readonly=False, copy=False, 
                                           track_visibility='always')

    number_period = fields.Integer('No. of Years/Months', default=1)
    spouse_amount = fields.Float('Spouse Amount', compute="get_dependents_amount")
#  Depends on Periods
    package = fields.Many2many(
        'package.model',
        string='Compulsory Packages',
        readonly=False,
        store=True,
        compute='get_all_packages')
    package_cost = fields.Float(
        'Package Cost',
        required=True,
        readonly=False,
        compute='get_package_cost')
    green_id = fields.Char('Green Card ID.', size=9)
    temp_id = fields.Char('Temporary ID No.', size=9)
    date_of_temp = fields.Datetime('Date of Temp. Confirmation')
    
    coffee = fields.Boolean('Coffee Fee', default=True)
    main_house_cost = fields.Float('Main House Fee', required=True) 
    state = fields.Selection([('draft', 'Draft'),
                              ('white', 'White Prospect'),
                              ('wait', 'Waiting List'),
                              ('interview', 'Interview'),
                              ('issue_green', 'Green Card Issue'),
                              ('account', 'Account&Finance'),
                              ('green', 'Green'),
                              ('temp', 'Temporal'),
                              ('induction', 'Induction'),
                              ('manager', 'Manager'),
                              ('manager_two', 'Manager'),
                              ('ord', 'Ordinary'),
                              ('jun', 'Junior'),
                              ('life', 'Life'),
                              ('hon', 'Honorary'),
                              ('suspension', 'Suspension'),
                              ], default='draft', string='Status')

    #  $$$$$$$$$$$$$%%%%%%%%%%%%%%%%%%%%%% %%%%%%%%%%%%%%%%% %%%%%%%%%^^^^^^^^^

    sub_line = fields.One2many(
        'subscription.line',
        'member_id',
        string='Sub Lines')
    
    date_of_interview = fields.Datetime('Date of Interview')
    coffee_book = fields.Float(
                                'Coffee Book Fee', 
                                default=10000.00, required=True)
    harmony = fields.Float('Harmony Magazine Fee', default=2000.00, required=True)
    binary_attach_interview = fields.Binary('Attach Upload Report')
    binary_fname_interview = fields.Char('Interview Report')
    
    # @api.one
    @api.onchange('subscription_period')
    def get_all_packages(self):
        for rex in self:
            get_package = self.env['package.model'].search(
                [('subscription_period', '=', self.subscription_period)])
            appends = []
            if get_package:
                for ret in get_package:
                    appends.append(ret.id)
            rex.package = [(6, 0, appends)]
            
    @api.onchange('subscription_period')
    def domain_subscirption(self):
        res = {}
        if self.subscription_period:
            res['domain'] = {'subscription':[('subscription_period','=', self.subscription_period)]}
        return res


#  calculate package cost
    @api.one
    @api.depends('package')
    def get_package_cost(self):
        total = 0.0
        for rec in self.package:
            total += rec.package_cost
        self.package_cost = total
        
    #  calculate package cost
    @api.one
    @api.depends('depend_name')
    def get_dependents_amount(self):
        total = 0.0
        for rec in self.depend_name:
            total += rec.total
        self.spouse_amount = total
     
#  Calculates subscription cost
    @api.one
    @api.depends('subscription')
    def get_section_member_price(self):
        total = 0.00
        for rex in self.subscription:
            total += rex.member_price
        self.member_price = total

#  Total of main house + subscription + packaget cost
    @api.one
    @api.depends('member_price', 'package_cost', 'main_house_cost')
    def get_totals(self):
        self.total = self.member_price + self.package_cost + self.main_house_cost + self.spouse_amount

    @api.depends('member_price', 'package_cost','main_house_cost', 'spouse_amount')
    def get_totals_sub(self):
        total = 0.00
        for rex in self:
            rex.total_subsequent = rex.member_price + rex.package_cost + rex.spouse_amount + rex.main_house_cost
            
    @api.onchange('partner_id')
    def get_partner_account(self):
        for rex in self:
            rex.account_id = rex.partner_id.property_account_payable_id.id

    @api.onchange('product_id')
    def onchange_product(self):
        """This function returns value of  product's member price based on product id.
        """
        price_dict = self.product_id.price_compute('list_price')
        # self.member_price = price_dict.get(self.product_id.id) or False
        self.membership_date_from = self.product_id.membership_date_fromx
        self.membership_date_to = self.product_id.membership_date_tox

    # # # # Date check # # # # # 
    @api.depends('date_pickup')
    def get_duration_pick(self):
        for rec in self:
            start = rec.date_pickup
            end = fields.Datetime.now()
            if start and end:
                server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                strt = datetime.strptime(start, server_dt)
                ends = datetime.strptime(end, server_dt)
                durations = ends - strt
                rec.duration_pick = durations.days
    
    @api.model
    def _run_cron(self):
        return self.run_crons()           
    #@api.multi
    def run_crons(self):
        
        for rec in self:
            
            current_date = fields.Date.today()
            #last_dates = fields.Datetime.now
            for date in rec.payment_line2:
                last_date = date[-1].pdate
            if current_date and last_date:
                # raise ValidationError("The date is {}".format(last_date))
                server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                start = datetime.strptime(last_date, '%Y-%m-%d')
                end = datetime.strptime(current_date,'%Y-%m-%d')
                diff = end - start
                duration = diff.days#/365
                if duration in range(4,5): # and self.state == "ord"
                    # rec.activity = "act"
                    rec.write({'activity': "inact"})# "active":False})
                    #raise ValidationError("The date is {}".format(last_date))
                elif duration > 5:
                    rec.write({'activity': "dom"})#, "active": False})
                    # self.activity = "dom"
                    #raise ValidationError("The date is --- {}".format(last_date))
                else:
                    rec.write({'activity': "act"})
                    
                
            

    @api.multi
    @api.depends('date_green_pickup')
    def get_green_duration_pick(self):
        for rec in self:
            start = rec.date_green_pickup
            end = fields.Datetime.now()
            if start and end:
                server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                strt = datetime.strptime(start, server_dt)
                ends = datetime.strptime(end, server_dt)
                durations = ends - strt
                rec.duration_pick_green = durations.days

    # # # # Date check # # # # # 
    @api.depends('dob')
    def get_duration_age(self):
        for rec in self:
            start = rec.dob
            end = fields.Datetime.now()
            if start and end:
                server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                strt = datetime.strptime(start, server_dt)
                ends = datetime.strptime(end, server_dt)
                durations = ends - strt
                rec.member_age = durations.days / 365

    @api.depends('duration_pick')
    def check_pickupp_duration(self):
        for rec in self:
            if rec.duration_pick > 3:
                rec.delay_charges = 5000
                return rec.int_form_price + rec.delay_charges

    

    @api.multi
    def button_register_spouse(self):  #  Send memo back
        lists = []
        for rec in self.subscription:
            lists.append(rec.id)
        return {
            'name': "Register Dependant",
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'register.spouse.member',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {
                'default_product_id': self.product_id.id,
                'default_member_price': self.member_price,
                'default_total': self.total,
                'default_sponsor': self.id,
                'default_subscription': [(6, 0, lists)]
            },
        }

#  TREAT IMPORTANT REGISTER WHITE
    @api.multi
    def button_white_payments(self):  #  state draft
        self.state = 'white'
        return self.sendmail_white_confirm()

    @api.multi
    def button_confirm_white_payments_first(self):  #  state draft

        name = "White Payment Fee" or "{} Payment".format(
            str(self.state).upper())
        #  self.write({'payment_status':'gpaid'})
        self.write({'payment_status': 'open'})

        amount = self.int_form_price + self.harmony
        level = 'wait'
        self.sendmail_white_confirm()
        return self.button_payments(name, amount, level)

    @api.multi
    def button_confirm_white_delay_payments(self):  #  state draft
        #self.date_pickup = fields.Datetime.now()
        name = "Late Submission Fee" or "{} Payment".format(
            str(self.state).upper())
        self.write({'payment_status': 'open'})

        amount = self.delay_charges
        level = 'wait'
        if self.date_pickup or self.date_of_interview:
            if self.delay_charges > 0.00:
                return self.button_payments(name, amount, level)

            else:
                raise ValidationError('There is no penalty fee for this member')
        else:
            raise ValidationError('Please Enter the following fields: "White form submission",  "Date of Interview"')

    def sendmail_white_confirm(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        #  extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        #  bodyxx
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify that you have been issued a white prospect Card on the date: {}.</br>\
             </br> Please Endure to submit the card on or before the range of 3 months of the pickup date.</br>\
             Kindly contact the Ikoyi Club 1938 for further enquires </br> Thanks".format(fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)


    @api.one
    def button_send_interview(self):  #  state wait
        if self.date_of_interview == False:
            raise ValidationError('Please you must set the field: "Date of Interview"')
            
        else:
            self.write({'state': 'interview'})
            self.send_one_interview()

    def send_one_interview(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        #  .format(fields.Datetime.now())
        bodyx = "Dear Sir/Madam, </br>We wish to notify that you have been shortlisted for an interview at Ikoyi Club 1938.</br>\
                </br>.</br>\
                Kindly contact the Ikoyi Club 1938 for more enquires </br> Thanks"
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def function_sendall_interview(self):  #  state wait
        for rec in self:
            search_id = self.env['member.app'].search([('state', '=', "wait")])
            rec.write({'state': 'interview'})
            self.send_mail_set_interview()

    @api.multi
    def send_mail_set_interview(self, force=False):
        for rec in self:
            email_from = self.env.user.company_id.email
            group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
            # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
            extra = rec.email
            bodyx = "Dear Sir/Madam, </br>We wish to notify that you have \
             been shortlisted for an interview at Ikoyi Club 1938.</br>\
                </br>Interview Dated is {}.</br>\
                Kindly contact the Ikoyi Club 1938 for \
                 more enquires </br> Thanks".format(rec.date_of_interview)
            rec.mail_sending(email_from, group_user_id, extra, bodyx)
    
    @api.multi
    def send_mail_issue_green(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify \
        that you have been promoted to a Green prospect\
        membership on the date: {}.</br>\
        Kindly contact the Ikoyi Club 1938 for further \
        enquires </br> Thanks".format(fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)

#  click button, check the difference, now create payment register
    @api.multi
    def create_invoice_green(self):# Interview
        
        """ Selects the interview state, make payment for green card collection
            Set state date of green pick up to current date.
            Then set state to issue_green 
            
            Payment is green form price + coffee book = 30000 
        """
        for order in self:
            product = 0
            state_now = str(order.state).replace('_', ' ').capitalize()
            products = self.env['product.product']
            product_search = products.search([('name', 'ilike', state_now)])
            if product_search:
                #  product.append(product_search.id)
                product = product_search[0].id
            else:
                pro = products.create({'name': state_now, 'membershipx': True})
                product = pro.id
            #  order.penalty_charges = 15000
            
            amount = order.green_form_price + order.coffee_book  
            level = 'interview'
            name = "Interview Card Payment Fee" or "{} Payment Fee".format(
                    str(order.state).upper())
            
            order.write(
                {
                 'date_issue_green': fields.Datetime.now()})
             
            self.send_mail_green(name)
            
            return self.button_payments(name, amount, level)
    
     
    
    @api.multi
    def set_interview(self):
        self.state = "interview"
        
    @api.multi
    def button_confirmall_green(self):
        search_id = self.env['member.app'].search(
            [('state', 'in', "issue_green")])
        for mem in search_id:
            mem.write({'payment_status': 'issue', 'state': 'green'})
            self.send_mail_issue_green()

    @api.multi
    def check_green_delay(self):
        """
        Set the date of green form pickup to the current 
        date(back date to check), if three months, 
        the system brings out payment
        """
        popup_message = "Hurray!!!... There is no penalty charge for the member"
        penalty = 15000
        if self.date_green_pickup or self.green_id:
            for order in self:
                product = 0
                state_now = str(order.state).replace('_', ' ').capitalize()
                products = self.env['product.product']
                product_search = products.search([('name', 'ilike', state_now)])
                if product_search:
                    product = product_search[0].id
                else:
                    pro = products.create({'name': state_now, 'membershipx': True})
                    product = pro.id

                total_duration = 0.0
                start = order.date_issue_green
                end = fields.Datetime.now()
                if start and end:
                    server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                    strt = datetime.strptime(start, server_dt)
                    ends = datetime.strptime(end, server_dt)
                    durations = ends - strt
                    total_duration = durations.days # / 365

                if total_duration > 30:
                    order.penalty_charges = 15000
                    amount = penalty
                    values = {
                        'member_id': self.id,
                        'member_price': amount,
                        'pdate': self.date_order,
                        'product_id': product,
                        'paid_amount': amount,
                        'penalty_fee': self.penalty_charges
                    }
                    level = 'green'
                    '''order.write({'payment_line': [(0, 0, values)], 'payment_line2': [
                                (0, 0, values)], 'payment_status': 'gpaid'})'''
                    order.write({'payment_status': 'gpaid'})
                                
                    name = "Green Card Payment Fee" or "{} Payment Fee".format(
                        str(order.state).upper())
                    self.send_mail_green(name)
                    return self.button_payments(name, amount, level)
                elif total_duration < 30:
                    order.write({'state': 'green'})
                    return self.popup_notification(popup_message)
        raise ValidationError('Please Add the fields: "Green Form submission date", "Green card ID"')
                
    def popup_notification(self,popup_message):
        view = self.env.ref('sh_message.sh_message_wizard')
        view_id = view and view.id or False
        context = dict(self._context or {})
        context['message'] = popup_message # 'Successful'
        return {'name':'Checking Alert',
                    'type':'ir.actions.act_window',
                    'view_type':'form',
                    'res_model':'sh.message.wizard',
                    'views':[(view.id, 'form')],
                    'view_id':view.id,
                    'target':'new',
                    'context':context,
                }         
    @api.multi
    def send_mail_green(self, name,force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        amount = self.green_form_price + 10000
        bodyx = "Dear Sir/Madam, </br>We wish to notify that a {} Card payment of N-{} have been made on the date: {}.</br>\
             Kindly contact the Ikoyi Club 1938 for any further enquires </br> Thanks".format(name, amount, fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def button_print_green_card(self):
        pass

    def _check_fields(self):
        errors = ['Please provide details for the following : ']
        if not self.green_id:
                errors.append('-Green Card ID')

        if not self.package:
            errors.append('-Compulsory Packages')
            
        if not self.subscription_period:
            errors.append('-Subscription Period')
        
        if not self.duration_period:
            errors.append('-Duration to Pay')
            
        if not self.main_house_cost:
            errors.append('-Main House Cost Must be Greater than 1000')
                
        if len(errors) > 1:
            raise ValidationError('\n'.join(errors))
        
    duration_period = fields.Selection([
        ('Weeks', 'Weeks'),
        ('Months', 'Months'),
        ('Full Year', 'Year'),
    ], 'Duration to Pay', Default="Months", index=True, required=False, readonly=False, copy=False, 
                                           track_visibility='always')
    
    number_period = fields.Integer('Number of Years/Months', default=1)
            
    @api.multi
    def button_account_to_temp_payments(self):  #  state draft total
        self._check_fields()
        name = "Green Form Payment Fee" or "{} Payment".format(str(self.state).upper())
        amountx = 0.0
        spouse_payment = 0.0
        spouse_total = 0.0
        balance_spouse = 0.0
        balance_member = 0.0
        cal_amount = 0.0
        balance_totals = 0.0
        search_spouse = self.env['register.spouse.member'].search(
                [('partner_id', '=', self.partner_id.id)])

        if self.duration_period == "Months":
            cal_amount = (self.member_price / 6) * self.number_period
    
            if self.depend_name:
                for reco in self.depend_name:
                    if reco.relationship != 'Child':
                        spouse_total = reco.total
                        spouse_payment = (reco.total / 6) * self.number_period
                        balance_spouse = reco.total - spouse_payment
                    else:
                        spouse_payment = 0.0
            balance_member = self.member_price - cal_amount
            balance_totals = balance_spouse + balance_member
            self.balance_total += balance_totals
            
        elif self.duration_period == "Full Year":
            cal_amount = self.member_price * self.number_period
            
            if self.depend_name:
                for reco in self.depend_name:
                    if reco.relationship != 'Child':
                        spouse_total = reco.total
                        spouse_payment = reco.total * self.number_period
                        balance_spouse = reco.total - spouse_payment
                        
                    else:
                        spouse_payment = 0.0
            balance_member = self.member_price - cal_amount
            balance_totals = balance_spouse + balance_member
            self.balance_total += balance_totals
        
        # if self.depend_name:
        #     for rec in self.depend_name:
        #         if rec.relationship != 'Child':
        #             spouse_payment = rec.total
        #         else: 
        #             spouse_payment = 0.0 
        if search_spouse:
            level = "temp"
            for xec in search_spouse:
                if xec.relationship in ["Child","Brother","Sister", "Friend", "Spouse"]:
                    percent = 50 / 100
                    discount = main_house_cost * percent
                    # amount = discount + self.package_cost + spouse_payment + cal_amount
                    # self.write({'main_house_cost': discount, 'total': amount})
                    amount = (spouse_total + discount + self.package_cost + self.member_price) - balance_totals
            
                    self.send_mail_temp()
                    self.button_payments(name, amount, level)
        else:
            # amount = spouse_total + self.main_house_cost + self.package_cost + # cal_amount # self.member_price
            # amount = totalofspouse(30000) + mainhouse(50000) + package(10000)+totalsection(10000)
            # cal = 30000 + 50000 + 10000 + 10000 = 100000
            amount = (spouse_total + self.main_house_cost + self.package_cost + self.member_price) - balance_totals
            level = 'temp'
            self.send_mail_temp()
            return self.button_payments(name, amount, level)

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
                'default_amount': amount, #  self.int_form_price,
                'default_member_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_member_ref': self.id,
                'default_name': "Member Payments",
                'default_spouse_amount':self.spouse_amount,
                'default_level': level,
                'default_to_pay': amount,
                'default_num':self.id,
            },
        }      
        
    @api.multi
    def send_mail_temp(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify \
         that you have been promoted to a temporary member on the date: {} \
         </br> Kindly contact the Ikoyi Club 1938 for any further enquires \
         </br> Thanks".format(fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.one
    def button_make_induction(self):
        for rec in self:
            if self.temp_id:
                start = rec.date_of_temp
                end = fields.Datetime.now()
                if start and end:
                    server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                    strt = datetime.strptime(start, server_dt)
                    ends = datetime.strptime(end, server_dt)
                    durations = ends - strt
                    days = durations.days
                    if days > 90:
                        rec.write({'state': "induction"})
                        self.send_mail_induction()
                    elif days < 90:
                        raise ValidationError(
                            "You are trying to Set this member for induction,\
                             it's not up to 3months validity")
                        #  rec.write({'state':"induction"})
            else:
                raise ValidationError(
                            "Please Enter Temporarily ID")

    @api.multi
    def button_make_induction2(self):
        for rec in self:
            member = self.env['member.app']  #  .search([()])
            mem_search = member.browse([])
            if mem_search.state == "temp":
                start = mem_search.date_of_temp
                end = fields.Datetime.now()
                if start and end:
                    server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                    strt = datetime.strptime(start, server_dt)
                    ends = datetime.strptime(end, server_dt)
                    durations = ends - strt
                    days = durations.days
                    if days > 90:
                        mem_search.write({'state': "induction"})
                        mem_search.send_mail_induction()
                    elif days < 90:
                        # raise ValidationError("You are trying to Set this member for induction, it's not up to 3months validity")
                        mem_search.write({'state': "temp"})
                        #  rec.write({'state':"induction"})
                        #  self.send_mail_induction()
    def send_mail_allinduction(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify that you have been enlisted for induction on the date: {} </br>\
             Thanks".format(fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def action_send_induction(self):    
        members = self.env['member.app'].search([('state','=', 'temp')])
        for vals in members:
            emails = vals.send_mail_allinduction()
        return True

    @api.multi
    def send_mail_induction(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify that you have been enlisted for induction on the date: {} </br>\
             Thanks".format(fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def make_ordinary_or_junior(self):
        if self.identification:
            body = "Ordinary Member Promoted on %s" % (
                datetime.strftime(datetime.today(), '%d-%m-%y'))
            records = self._get_followers()
            followers = records
            self.message_post(
                body=body,
                subtype='mt_comment',
                message_type='notification',
                partner_ids=followers)

            self.send_mail_manager()
            self.write({'state': 'manager'})
        else:
            raise ValidationError('Please Enter Member ID Field:')

    def send_mail_manager(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>I wish to notify you that you have been completed all necessary requirement for Ikoyi Club Membership\
        . The Membership Manager will soon confirm your approval to permanent\
        membership.</br> Kindly contact Ikoyi Club 1938 for further details</br>Thanks"
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def make_manager_confirms(self):
        body = "Ordinary Member Promoted on %s" % (
            datetime.strftime(datetime.today(), '%d-%m-%y'))
        records = self._get_followers()
        followers = records
        self.message_post(
            body=body,
            subtype='mt_comment',
            message_type='notification',
            partner_ids=followers)
        self.send_mail_confirm_final()

        partner = self.env['res.partner'].search(
            [('id', '=', self.partner_id.id)])
        if partner:
            partner.write({'is_member': True})
        else:
            raise ValidationError('No Partner Record found for this member')
        self.write({'state': 'ord'})

    def send_mail_confirm_final(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.membership_officer_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>Congratulations! You have been approved as a permanent\
        member Ikoyi Club with ID. Number {} on the date {}.</br> Kindly contact Ikoyi\
         Club 1938 for further details</br>Thanks".format(self.identification, fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    # # # # # # # # # # # # # # # # # # # # # # # # #  EMAIL FOR ONE ONLY mail_sending # 
    def get_url(self, id, model):
        base_url = http.request.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')
        base_url += '/web# id=%d&view_type=form&model=%s' % (id, mmodel)

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
            subject = "Membership Notification"

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

    @api.one
    def life_member(self):
        for rec in self:
            if rec.state == "ord":
                start = rec.date_of_temp
                end = fields.Datetime.now()
                if start and end:
                    server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                    strt = datetime.strptime(start, server_dt)
                    ends = datetime.strptime(end, server_dt)
                    durations = ends - strt
                    days = durations.days
                    if days > 9125 and self.member_age > 65:
                        rec.write({'state': "manager_two"})
                        self.send_mail_life()
                    elif days < 9125 and self.member_age < 65:
                        raise ValidationError(
                            'You cannot confirm to life membership because the\
                                               Member\'s age must not be lower than 65 years<br/>\
                                              and Membership period Must be up to 25 years')
                    else:
                        raise ValidationError(
                                        'Please the date of Temporarily confirmation must be greater than 20 years')
            # return True

    @api.multi
    def send_mail_life(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>We wish to notify that you have been enlisted for promotion to a life member on the date: {} </br>\
             Thanks".format(fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)

    @api.multi
    def make_manager_life_confirms(self):
        body = "Ordinary Member Promoted on %s" % (
            datetime.strftime(datetime.today(), '%d-%m-%y'))
        records = self._get_followers()
        followers = records
        self.message_post(
            body=body,
            subtype='mt_comment',
            message_type='notification',
            partner_ids=followers)
        self.send_mail_confirm_final_life()
        self.write({'state': 'life'})

    def send_mail_confirm_final_life(self, force=False):
        email_from = self.env.user.company_id.email
        group_user_id = self.env.ref('member_app.membership_officer_ikoyi').id
        # extra = self.env.ref('ikoyi_module.inventory_officer_ikoyi').id
        extra = self.email
        bodyx = "Dear Sir/Madam, </br>Congratulations! You have been approved as a Life\
        member of Ikoyi Club on the date {}  after serving for 25 years.</br> Kindly contact Ikoyi\
         Club 1938 for further details</br>Thanks".format(fields.Datetime.now())
        self.mail_sending(email_from, group_user_id, extra, bodyx)
    #  Account only confirm payment and makes

     # # # # # # # # # # # # # # # # # # # # # # OLD BUTTON # # # # # # # # # # # 
    @api.multi
    def button_dla_pay(self):  #  vis_post
        self.ensure_one()
        #  self.write({'state':'done'})
        '''res = self.env['ir.actions.act_window'].for_xml_id('account', 'action_account_payments_payable')
        return res '''
        user = self.env.user
        account = user.company_id
        journal = account.bank_journal_ids.id
        account_id = self.account_id.id
        bal = self.total - self.member_price

        product = 0
        state_now = str(self.state).replace('_', ' ').capitalize()
        products = self.env['product.product']
        product_search = products.search([('name', 'ilike', state_now)])
        if product_search:
            #  product.append(product_search.id)
            product = product_search[0].id
        else:
            pro = products.create({'name': state_now, 'membershipx': True})
            product = pro.id

        respx = {'type': 'ir.actions.act_window',
                 'name': _('Membership Payment'),
                 'res_model': 'account.payment',
                 'view_type': 'form',
                 'view_mode': 'form',
                 'target': 'new',
                 'context': {
                     'default_amount': self.total,
                     'default_communication': 'M' + str(self.identification),
                     'default_payment_type': 'inbound',
                     'default_partner_type': 'customer',
                     'default_partner_id': self.partner_id.id,
                     #  'default_journal_id':journal
                 }
                 }

        values = {
            'member_id': self.id,
            'member_price': self.harmony + self.int_form_price,
            'pdate': self.date_order,
            'product_id': product or self.product_id.id,
            'paid_amount': self.total,
            'balance': bal
        }

        self.write({'payment_line2': [(0, 0, values)]})

        self.write({'payment_status': 'paid'})
        return respx

    # # # # # # # # # # # # # # # # # # # # # #  PRINT ID CARD # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
    @api.multi
    def print_id_card(self):
        report = self.env["ir.actions.report.xml"].search(
            [('report_name', '=', 'member_app.member_profile_report_template')], limit=1)
        if report:
            report.write({'report_type': 'qweb-pdf'})
        return self.env['report'].get_action(
            self.id, 'member_app.member_profile_report_template')
        
    @api.multi
    def print_receipt(self):
        report = self.env["ir.actions.report.xml"].search(
            [('report_name', '=', 'member_app.membership_receipt_template')], limit=1)
        if report:
            report.write({'report_type': 'qweb-pdf'})
        return self.env['report'].get_action(
            self.id, 'member_app.membership_receipt_template')

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #  reverse states # # # # # # # # # # # # # # # # # # # # # # # # # 
    @api.multi
    def reverse_draft(self):
        self.write({'state': 'draft'})

    @api.multi
    def reverse_white(self):
        self.write({'state': 'white'})

    @api.multi
    def reverse_green(self):
        self.write({'state': 'green'})

    @api.multi
    def reverse_ord(self):
        self.write({'state': 'ord'})

    @api.multi
    def reverse_life(self):
        self.write({'state': 'life'})

    @api.multi
    def inactivate(self):
        self.run_crons()
        # self.write({'activity': "inact"})

    @api.model
    def create(self, vals):  #  vals is an already odoo context
        #  id used as context to extract current record
        partner = vals.get('partner_id')
        if partner:
            partner_duplicate = self.search([('partner_id', '=', partner)])
            if partner_duplicate:
                raise ValidationError(
                    'You cannot have existing Member registerd again')

        record = super(App_Member, self).create(vals)
        return record

    @api.multi
    def write(self, vals):
        plot = self
        offer_dt = vals.get('date_order') or plot.date_order
        payment_plan = vals.get('payment_plan')
        payment_type = vals.get('payment_type')
        payment_plan_ids = self.env['plot.payment.breakdowns'].search(
            [('project_and_plot_id', '=', self.id)])
        if payment_plan:
            if payment_plan_ids:
                payment_plan_ids.unlink()
                self.calc_payment_plan(offer_dt, payment_plan)
            else:
                self.calc_payment_plan(offer_dt, payment_plan)
        #  clear payment_breakdown when payment is changed to outright
        if payment_type and payment_plan_ids and payment_type == 'outright':
            payment_plan_ids.unlink()
            vals['payment_type'] = 'outright'
        elif payment_type == 'installment':
            self.calc_payment_plan_two()
        val = super(App_Member, self).write(vals)
        return val

    def calc_payment_plan(self, offer_dt, payment_plan):
        """Calculate the payment plan based on percentage."""
        intervals = self.env['account.payment.term'].search(
            [('id', '=', payment_plan)])
        #  parse and convert the date to a python datetime date
        offer_dt = datetime.strptime(offer_dt, '%Y-%m-%d')
        #  for count, interval in enumerate(intervals):
        for interval in intervals.line_ids:
            due_date = offer_dt + timedelta(interval.days)
            value_amount = interval.value_amount
            interval_payment = interval.value
            amount_to_pay = 0.00
            #  compute the amount_to_pay based on the type of payment
            if interval_payment == 'percent':  #  procent ==> percent
                amount_to_pay = value_amount * self.member_price / 100

            elif interval_payment == 'fixed':
                amount_to_pay = value_amount
            values = {
                'project_and_plot_id': self.id,
                'name': 'Payment Breakdowns',
                'interval': str(interval.days) + ' days',
                'amount_to_pay': amount_to_pay,
                'due_date': due_date.strftime('%Y-%m-%d')
            }
            self.env['plot.payment.breakdowns'].create(values)

    def calc_payment_plan_two(self):
        """Calculate the payment plan based on percentage."""
        intervals = self.env['account.payment.term'].search(
            [('id', '=', self.payment_plan.id)])

        #  parse and convert the date to a python datetime date
        offer_dt = datetime.strptime(self.date_order, '%Y-%m-%d')
        #  for count, interval in enumerate(intervals):
        for interval in intervals.line_ids:
            due_date = offer_dt + timedelta(interval.days)
            value_amount = interval.value_amount
            interval_payment = interval.value
            amount_to_pay = 0.00
            #  compute the amount_to_pay based on the type of payment
            if interval_payment == 'percent':  #  procent ==> percent
                amount_to_pay = value_amount * self.member_price / 100

            elif interval_payment == 'fixed':
                amount_to_pay = value_amount

            values = {
                'project_and_plot_id': self.id,
                'name': 'Payment Breakdowns',
                'interval': str(interval.days) + ' days',
                'amount_to_pay': amount_to_pay,
                'due_date': due_date.strftime('%Y-%m-%d')
            }
            self.env['plot.payment.breakdowns'].create(values)

    #  @api.onchange('associate_member')
    @api.multi
    def asso_button(self):

        for rec in self:
            product = rec.associate_member.product_id.id
            price = rec.associate_member.member_price
            get_partner_state = rec.associate_member.state

            rec.product_id = product
            rec.member_price = price

            if rec.associate_member:
                rec.state = get_partner_state

            #  rec.payment_line.unlink()
            for rex in rec.associate_member.payment_line[-1]:
                values = {
                    'member_id': rex.id,
                    'member_price': rex.member_price,
                    'pdate': rex.pdate,
                    'product_id': rex.product_id.id,
                }
                rec.write({'payment_line': [(0, 0, values)]})

    def direct_mail_sending(self, email_from, email_to, bodyx):
        subject = "Ikoyi Membership Notification"
        mail_data = {
            'email_from': email_from,
            'subject': subject,
            'email_to': email_to,
            #  'email_cc':mail_appends,
            'reply_to': email_from,
            'body_html': bodyx,
        }
        mail_id = self.env['mail.mail'].create(mail_data)
        self.env['mail.mail'].send(mail_id)

    @api.multi
    def membership_invoice(self):
        if self:
            '''datas = {
                'membership_product_id': self.product_id.id,
                'amount': self.member_price
            } '''
        invoice_list = self.create_membership_invoice()
        # invoice_list = self.env['member.app'].browse(self._context.get('active_ids')).create_membership_invoice()
        search_view_ref = self.env.ref(
            'account.view_account_invoice_filter', False)
        form_view_ref = self.env.ref('account.invoice_form', False)
        tree_view_ref = self.env.ref('account.invoice_tree', False)

        return {
            'domain': [('id', '=', self.invoice_id.id)],
            'name': 'Membership Invoices',
            'res_model': 'account.invoice',
            'type': 'ir.actions.act_window',
            'views': [(tree_view_ref.id, 'tree'), (form_view_ref.id, 'form')],
            'search_view_id': search_view_ref and search_view_ref.id,
        }

    def branch_id(self):
        branch = self.env.user.branch_id.id
        if not branch:
            raise ValidationError(
                'Please Ensure that the user has a specific branch')
        else:
            return branch

    @api.multi
    def create_membership_invoice(self):
        """ Create Customer Invoice of Membership for partners.
        @param datas: datas has dictionary value which consist Id of Membership product and Cost Amount of Membership.
                      datas = {'membership_product_id': None, 'amount': None}
        """
        product = 0
        state_now = str(self.state).replace('_', ' ').capitalize()
        products = self.env['product.product']
        product_search = products.search([('name', 'ilike', state_now)])
        if product_search:
            #  product.append(product_search.id)
            product = product_search[0].id
        else:
            pro = products.create({'name': state_now, 'membershipx': True})
            product = pro.id
        product_id = product
        #  self.product_id # or datas.get('membership_product_id')
        self.write({'product_id': product})
        amount = self.total  #  datas.get('amount', 0.0)
        invoice_list = []
        branch_id = 0
        branch = self.env['res.branch']
        branch_search = branch.search([('name', 'ilike', 'Ikoyi Club Lagos')])
        if not branch_search:
            branch_create = branch.create(
                {'name': 'Ikoyi Club Lagos', 'company_id': self.env.user.company_id.id or 1})
            branch_id = branch_create.id
        else:
            branch_id = branch_search.id

        for partner in self:
            invoice = self.env['account.invoice'].create({
                'partner_id': partner.partner_id.id,
                #  partner.partner_id.property_account_receivable_id.id,
                'account_id': partner.account_id.id,
                'fiscal_position_id': partner.partner_id.property_account_position_id.id,
                'branch_id': self.branch_id()
            })
            line_values = {
                'product_id': product_id,  #  partner.product_id.id,
                'price_unit': amount,
                'invoice_id': invoice.id,
                'account_id': partner.account_id.id or partner.partner_id.property_account_payable_id.id,

            }
            #  create a record in cache, apply onchange then revert back to a
            #  dictionnary
            invoice_line = self.env['account.invoice.line'].new(line_values)
            invoice_line._onchange_product_id()
            line_values = invoice_line._convert_to_write(
                {name: invoice_line[name] for name in invoice_line._cache})
            line_values['price_unit'] = amount
            invoice.write({'invoice_line_ids': [(0, 0, line_values)]})
            invoice_list.append(invoice.id)
            invoice.compute_taxes()

            partner.invoice_id = invoice.id

            find_id = self.env['account.invoice'].search(
                [('id', '=', invoice.id)])
            find_id.action_invoice_open()
        return invoice_list

    @api.multi
    def see_breakdown_invoice(self):  #  vis_account,

        search_view_ref = self.env.ref(
            'account.view_account_invoice_filter', False)
        form_view_ref = self.env.ref('account.invoice_form', False)
        tree_view_ref = self.env.ref('account.invoice_tree', False)

        return {
            'domain': [('id', '=', self.invoice_id.id)],
            'name': 'Membership Invoices',
            'res_model': 'account.invoice',
            'type': 'ir.actions.act_window',
            #  'views': [(form_view_ref.id, 'form')],
            'views': [(tree_view_ref.id, 'tree'), (form_view_ref.id, 'form')],
            'search_view_id': search_view_ref and search_view_ref.id,
        }


class Member_Payment_Breakdown(models.Model):
    _name = 'plot.payment.breakdowns'  #  breakdown
    project_and_plot_id = fields.Many2one('member.app', 'Member')
    name = fields.Char('Payment')
    interval = fields.Char('Payment Interval in days')
    amount_to_pay = fields.Float('Amount to be paid')
    due_date = fields.Datetime('Due date')

    '''@api.multi
    def print_receipt(self):
        return self.env['report'].get_action(
            self.id, 'construction_rewrite.receipt_view_report')'''


class App_Member_Line(models.Model):
    _name = "member.payment"
    member_id = fields.Many2one('member.app', 'Member ID')
    name = fields.Char('Membership Type')
    product_id = fields.Many2one(
        'product.product',
        string='Membership',
        required=True)
    member_price = fields.Float(
        string='Member Price',
        digits=dp.get_precision('Product Price'),
        required=True)
    paid_amount = fields.Float(string='Amount Paid', required=True)
    balance = fields.Float(string='Balance', default=0.0)
    pdate = fields.Date('Offer Date', default=fields.Date.today())
    penalty_fee = fields.Float(string='Penalty Fee', default=0.0)

    @api.onchange('paid_amount', 'member_price')
    def balance_change(self):
        cal = self.member_price - self.paid_amount
        self.balance = cal


class App_Member_Line_major(models.Model):
    _name = "member.payment.new"
    member_idx = fields.Many2one('member.app', 'Member ID')
    name = fields.Char('Membership Type')
    product_id = fields.Many2one(
        'product.product',
        string='Membership',
        required=False)
    member_price = fields.Float(
        string='Subscriptions',
        digits=dp.get_precision('Product Price'),
        required=True)
    paid_amount = fields.Float(string='Amount Paid', required=True)
    spouse_amount =fields.Float(string='Spouse Amount')
    balance = fields.Float(string='Balance', default=0.0)
    pdate = fields.Date('Paid Date', default=fields.Date.today())
    penalty_fee = fields.Float(string='Penalty Fee', default=0.0)

    @api.onchange('paid_amount', 'member_price')
    def balance_change(self):
        cal = self.member_price - self.paid_amount
        self.balance = cal


class App_Partner_Line(models.Model):
    _inherit = "res.partner"
    is_member = fields.Boolean(string='Is Member')

    _sql_constraints = [
        ('name_unique',
         'UNIQUE(name)',
         'Partner Name must be unique')
    ]

#  $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


class App_subscription_Line(models.Model):
    _name = "subscription.payment"
    name = fields.Char('Activity', required=True)
    '''product_id = fields.Many2one('product.product', string='Membership', required=True)'''
    member_price = fields.Float(
        string='Member Price',
        digits=dp.get_precision('Product Price'),
        required=True)
    pdate = fields.Date(
        'Offer Price Date',
        default=fields.Date.today(),
        required=True)
    subscription_period = fields.Selection([
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

#  $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$


class Package_model(models.Model):
    _name = "package.model"
    name = fields.Char('Package Name', required=True)
    '''product_id = fields.Many2one('product.product', string='Membership', required=True)'''
    package_cost = fields.Float(string='Package Price', required=True)
    pdate = fields.Date(
        'Offer Price Date',
        default=fields.Date.today(),
        required=True)
    subscription_period = fields.Selection([
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


class ProductMA(models.Model):
    _inherit = 'product.template'

    membershipx = fields.Boolean(
        help='Check if the product is eligible for membership.')
    membershipx_white = fields.Boolean(
        help='Check if the product is eligible for membership.')
    membershipx_green = fields.Boolean()
    membershipx_ord = fields.Boolean()
    membershipx_life = fields.Boolean()
    membership_date_fromx = fields.Date(
        string='Membership Start Date',
        help='Date from which membership becomes active.')
    membership_date_tox = fields.Date(
        string='Membership End Date',
        help='Date until which membership remains active.')
    duration_rangex = fields.Integer('Duration')
    subscription = fields.Many2many(
        'subscription.payment',
        string='Add Membership Subscriptions')

    @api.model
    def fields_view_get(
            self,
            view_id=None,
            view_type='form',
            toolbar=False,
            submenu=False):
        if self._context.get('product') == 'membership_product':
            if view_type == 'form':
                view_id = self.env.ref(
                    'member_app.membership_products_formx').id
            else:
                view_id = self.env.ref(
                    'member_app.membership_products_treex').id
        return super(
            ProductMA,
            self).fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu)


class RegisterSpouseMember(models.Model):
    _name = 'register.spouse.member'
    _description = 'Register Member Dependant'

    @api.multi
    def name_get(self):
        if not self.ids:
            return []
        res = []
        for field6 in self.browse(self.ids):
            partner = str(field6.partner_id.name)
            res.append((field6.id, partner))
        return res

    _sql_constraints = [
        ('name_unique',
         'UNIQUE(partner_id)',
         'Partner Name must be unique')
    ]
    @api.onchange('partner_id')
    def _get_state(self):
        for r in self.partner_id:
            #  r=rec.partner_id.id
            street = r.street
            country = r.country_id.id
            city = r.city
            #  city=r.city
            post = r.function
            phone = r.phone
            state = r.state_id
            title = r.title.id
            email = r.email
            image = r.image
            self.country_id = country
            self.state_id = state
            self.city = city
            self.phone = phone
            self.title = title
            self.image = image
            self.occupation = post
            self.email = email

    image = fields.Binary(
        "Image",
        attachment=True,
        help="This field holds the image used as avatar for this contact, limited to 1024x1024px",
    )
    image_medium = fields.Binary(
        "Medium-sized image",
        attachment=True,
        help="Medium-sized image of this contact. It is automatically "
        "resized as a 128x128px image, with aspect ratio preserved. "
        "Use this field in form views or some kanban views.")
    image_small = fields.Binary(
        "Small-sized image",
        attachment=True,
        help="Small-sized image of this contact. It is automatically "
        "resized as a 64x64px image, with aspect ratio preserved. "
        "Use this field anywhere a small image is required.")
    partner_id = fields.Many2one(
        'res.partner', 'Name', domain=[
            ('is_member', '=', True)])
    city = fields.Char('City')
    street = fields.Char('Street')
    url = fields.Char('Website')
    phone = fields.Char('Phone')
    state_id = fields.Many2one('res.country.state', store=True)
    country_id = fields.Many2one('res.country', 'Country', store=True)
    dob = fields.Datetime('Date Of Birth', required=True)
    email = fields.Char('Email', store=True)
    occupation = fields.Char('Job title')
    nok = fields.Many2one('res.partner', 'Next of Kin', store=True)
    title = fields.Many2one('res.partner.title', 'Title', store=True)
    sponsor = fields.Many2one(
        'member.app',
        string='Parent Member',
        required=True)
    account_id = fields.Many2one('account.account', 'Account')
    invoice_id = fields.Many2one('account_id', 'Invoice', store=True)

    product_id = fields.Many2one(
        'product.product', string='Related Membership type', domain=[
            ('membershipx', '=', True)], required=False)
    member_price = fields.Float(
        string='Member Price',
        compute="get_section_member_price",
        required=True,
        readonly=False)
    total = fields.Integer('Total Section Amount', compute='get_totals')
    date_order = fields.Datetime('Offer Date', default=fields.Datetime.now())
    member_age = fields.Integer(
        'Age',
        required=True,
        compute="get_duration_age")
    subscription = fields.Many2many(
        'subscription.payment',
        string='Add Sections')

    #  ,compute='get_all_packages')
    package = fields.Many2many('package.model', string='Compulsory Packages')
    package_cost = fields.Float(
        'Package Cost',
        required=True,
        compute='get_package_cost')
    mode = fields.Selection([('jun',
                              'Junior'),
                             ('old',
                              'Old'),
                             ('new',
                              'New'),
                             ],
                            'Mode',
                            default='jun',
                            index=True,
                            required=True,
                            readonly=False,
                            copy=False,
                            track_visibility='always')
    state = fields.Selection([('draft',
                               'Draft'),
                              ('wait',
                               'Waiting'),
                              ('account',
                               'Accounts'),
                              ('confirm',
                               'Confimred'),
                              ],
                             'Status',
                             default='draft',
                             index=True,
                             required=True,
                             readonly=False,
                             copy=False,
                             track_visibility='always')
    relationship = fields.Selection([('Child',
                                      'Child'),
                                     ('Brother',
                                      'Brother'),
                                     ('Sister',
                                      'Sister'),
                                     ('Friend',
                                      'Friend'),
                                     ('Spouse',
                                      'Spouse'),
                                     ],
                                    'Status',
                                    default='Spouse',
                                    index=True,
                                    required=True,
                                    readonly=False,
                                    copy=False,
                                    track_visibility='always')
    
    active = fields.Boolean(string='Active', default=True)
    
    @api.onchange('sponsor')
    def change_details(self):
        for rec in self:
            for fec in rec.sponsor:
                lists = []
                for tec in fec.subscription:
                    lists.append(tec.id)
                rec.subscription = [(6, 0, lists)]

    @api.depends('subscription')
    def get_section_member_price(self):
        total = 0.00
        for rex in self:
            for rec in rex.subscription:
                total += rec.member_price
            rex.member_price = total

    @api.depends('dob')
    def get_duration_age(self):
        for rec in self:
            start = rec.dob
            end = fields.Datetime.now()
            if start and end:
                server_dt = DEFAULT_SERVER_DATETIME_FORMAT
                strt = datetime.strptime(start, server_dt)
                ends = datetime.strptime(end, server_dt)
                durations = ends - strt
                rec.member_age = durations.days / 365

    @api.depends('member_price', 'package_cost')
    def get_totals(self):
        total = 0.00
        for rex in self:
            rex.total = rex.member_price + rex.package_cost  #  + rex.product_id.list_price

    @api.depends('package')
    def get_package_cost(self):
        total = 0.0
        for rec in self:
            for ret in rec.package:
                total += ret.package_cost
            rec.package_cost = total

    @api.multi
    def button_make_wait(self):
        self.write({'state': 'wait'})

    @api.multi
    def button_make_confirm(self):
        self.write({'state': 'confirm'})
        partner = self.env['res.partner'].search(
            [('id', '=', self.partner_id.id)])
        if partner:
            partner.write({'is_member': True})

        self.Appendto_Sponsor()
        return True

    def Appendto_Sponsor(self):
        lists = []
        mem_obj = self.env['member.app']
        for fec in self:
            for rec in self.sponsor:
                '''lists.append(self.id)
                # lists[] = self.id
                rec.depend_name = [(6,0,lists)]'''
                '''values ={'id':self.id,'partner_id':fec.partner_id.id,'dob':fec.dob,'image':fec.image,'product_id':fec.product_id.id,\
                         'member_price':fec.member_price, 'email':fec.email}'''
                membrowse = mem_obj.search([('id', '=', rec.id)])
                #  membrowse.write({'depend_name':[(0,0,values)]})
                res_id = self
                membrowse.depend_name += res_id
            #  return True

    @api.model
    def create(self, vals):
        res = super(RegisterSpouseMember, self).create(vals)
        partner_id = vals.get('partner_id')
        partner = self.env['res.partner'].search([('id', '=', partner_id)])
        partner.write({'street': vals.get('street'),
                       'street2': vals.get('street'),
                       'email': vals.get('email'),
                       'state_id': vals.get('state_id'),
                       'title': vals.get('title'),
                       'image': vals.get('image'),
                       'phone': vals.get('phone'),
                       'function': vals.get('occupation')})
        return res

    @api.multi
    def button_make_payment(self):
        self.write({'state': 'account'})
        if self:
            invoice_list = self.create_membership_invoice()
            # invoice_list = self.env['member.app'].browse(self._context.get('active_ids')).create_membership_invoice()
            search_view_ref = self.env.ref(
                'account.view_account_invoice_filter', False)
            form_view_ref = self.env.ref('account.invoice_form', False)
            tree_view_ref = self.env.ref('account.invoice_tree', False)

            return {
                'domain': [('id', '=', self.invoice_id.id)],
                'name': 'Membership Invoices',
                'res_model': 'account.invoice',
                'type': 'ir.actions.act_window',
                'views': [(tree_view_ref.id, 'tree'), (form_view_ref.id, 'form')],
                'search_view_id': search_view_ref and search_view_ref.id,
            }

    @api.multi
    def create_membership_invoice(self):
        """ Create Customer Invoice of Membership for partners.
        @param datas: datas has dictionary value which consist Id of Membership product and Cost Amount of Membership.
                      datas = {'membership_product_id': None, 'amount': None}
        """
        product = 0
        state_now = str(self.state).replace('_', ' ').capitalize()
        products = self.env['product.product']
        product_search = products.search(
            [('name', 'ilike', 'Spouse Membership')])
        if product_search:
            #  product.append(product_search.id)
            product = product_search[0].id
        else:
            pro = products.create(
                {'name': 'Spouse Membership', 'membershipx': True})
            product = pro.id
        product_id = product
        #  self.product_id # or datas.get('membership_product_id')
        self.write({'product_id': product})
        amount = self.total  #  datas.get('amount', 0.0)
        invoice_list = []
        branch_id = 0
        branch = self.env['res.branch']
        branch_search = branch.search([('name', 'ilike', 'Ikoyi Club Lagos')])
        if branch_search:
            branch_id = branch_search[0].id

        else:
            branch_create = branch.create(
                {'name': 'Ikoyi Club Lagos', 'company_id': self.env.user.company_id.id or 1})
            branch_id = branch_create.id

        for partner in self:
            invoice = self.env['account.invoice'].create({
                'partner_id': partner.partner_id.id,
                #  partner.partner_id.property_account_receivable_id.id,
                'account_id': partner.account_id.id,
                'fiscal_position_id': partner.partner_id.property_account_position_id.id,
                'branch_id': branch_id
            })
            line_values = {
                'product_id': product_id,  #  partner.product_id.id,
                'price_unit': amount,
                'invoice_id': invoice.id,
                'account_id': partner.account_id.id or partner.partner_id.property_account_payable_id.id,

            }
            #  create a record in cache, apply onchange then revert back to a
            #  dictionnary
            invoice_line = self.env['account.invoice.line'].new(line_values)
            invoice_line._onchange_product_id()
            line_values = invoice_line._convert_to_write(
                {name: invoice_line[name] for name in invoice_line._cache})
            line_values['price_unit'] = amount
            invoice.write({'invoice_line_ids': [(0, 0, line_values)]})
            invoice_list.append(invoice.id)
            invoice.compute_taxes()

            partner.invoice_id = invoice.id

            find_id = self.env['account.invoice'].search(
                [('id', '=', invoice.id)])
            find_id.action_invoice_open()

        return invoice_list

    @api.multi
    def see_breakdown_invoice(self):  #  vis_account,

        search_view_ref = self.env.ref(
            'account.view_account_invoice_filter', False)
        form_view_ref = self.env.ref('account.invoice_form', False)
        tree_view_ref = self.env.ref('account.invoice_tree', False)

        return {
            'domain': [('id', '=', self.invoice_id.id)],
            'name': 'Membership Invoices',
            'res_model': 'account.invoice',
            'type': 'ir.actions.act_window',
            #  'views': [(form_view_ref.id, 'form')],
            'views': [(tree_view_ref.id, 'tree'), (form_view_ref.id, 'form')],
            'search_view_id': search_view_ref and search_view_ref.id,
        }


class RegisterPaymentMember(models.Model):
    _name = 'register.payment.member'
    _description = 'Register Member Payment'

    @api.model
    def _default_journal(self):
        if self._context.get('default_journal_id', False):
            return self.env['account.journal'].browse(
                self._context.get('default_journal_id'))
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get(
            'company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', filter(None, map(TYPE2JOURNAL.get, inv_types))),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)

    def compute_zero(self):
        zero = 0.00
        return zero

    partner_id = fields.Many2one('res.partner', 'Customer', required=True)
    filex = fields.Binary("File Upload")
    file_namex = fields.Char("FileName")
    name = fields.Char("Description", readonly=False)
    level = fields.Char("Level", readonly=False)
    users_followers = fields.Many2many('res.users', string='Add followers')
    member_ref = fields.Many2one('member.app', 'Payment Ref.')
    payment_method = fields.Many2one('account.journal', string='Journal.',
                                     required=True, readonly=False,
                                     default=_default_journal,)
    to_pay = fields.Float('Amount to Pay', readonly=True, default=0.0)
    #  , required=True,default=lambda self: self.env['account.account'].search([('name', '=', 'Account Receivable')], limit=1))
    advance_account = fields.Many2one(
        'account.account',
        'Account',
        related='payment_method.default_debit_account_id')
    date = fields.Date('Paid Date', required=True)
    amount = fields.Float('Paid Amount', required=True, readonly=False)
    spouse_amount = fields.Float('Spouse Amount')
    print_memo = fields.Boolean('Print Memo', default=True)
    state = fields.Selection([('draft', 'Draft'),

                              ('pay', 'Paid'),
                              ('can', 'Cancel'),
                              ], default='draft', string='Status')
    p_type = fields.Selection([('sub', 'Subscription'),
                               ('ano', 'Anomaly'),
                               ('normal', 'Normal'),
                               ], default='normal', string='Type')
    
    mode_payment = fields.Selection([('Transfer', 'Transfer'),
                               ('POS', 'POS'),
                               ('CHEQUE', 'CHEQUE'),
                               ('BANK DRAFT', 'BANK DRAFT'),
                               ], default='Transfer', string='Payment Mode')
    num = fields.Float('Number')
    
    @api.one
    def button_pay(self):
        #  self.mail_sending()
        for rey in self:
            acm = self.env['account.payment.method'].create(
                {'payment_type': 'inbound', 'name': rey.name, 'code': str(rey.id)})
            payment_data = {
                'amount': rey.amount,  #  values.get('amount'),
                'payment_date': rey.date,
                'partner_type': 'customer',
                'payment_type': 'inbound',
                'partner_id': rey.partner_id.id,
                'journal_id': rey.payment_method.id,
                'member_id': rey.member_ref.id,
                'communication': "Membership Payment " + str(rey.name),
                'payment_method_id': acm.id,
                'filex': rey.filex,  # values.get('advance_account')
                            }
            payment_model = self.env['account.payment'].create(payment_data)

            model_name = 'account.payment'
            amounts = rey.amount
            model_name = 'account.payment'
            self.send_mail_to_accounts(payment_model.id, model_name, amounts)

            search_id = self.env['member.app'].search(
                [('id', '=', self.member_ref.id)])
             
            sub_id = self.env['subscription.model'].search([('id', '=', self.num)])
            for fec in search_id:  #  level
                product = 0
                state_now = str(fec.state).replace('_', ' ').capitalize()
                products = self.env['product.product']
                product_search = products.search(
                    [('name', 'ilike', state_now)])
                if product_search:
                    #  product.append(product_search.id)
                    product = product_search[0].id
                else:
                    pro = products.create(
                        {'name': state_now, 'membershipx': True})
                    product = pro.id

                if fec.state in ['white', 'wait']:
                    fec.write({'state': 'wait'})
                    lists = []
                    list1 = []
                    balance = rey.to_pay - rey.amount
                    fec.balance_total += balance
                    values = (0, 0,
                              {'member_idx': fec.id,
                               'product_id': product,
                               'paid_amount': rey.amount,
                               'balance': balance,
                               'pdate': rey.date,
                               'member_price': fec.int_form_price + fec.harmony,
                               'name': "White Form Payment"})
                    
                    lists.append(values)
                    list1.append(values)
                    fec.payment_line2 = lists
                    # fec.payment_line1 = list1
                    rey.state = "pay"

                elif fec.state in ['issue_green']:
                    fec.write({'state': 'green'})
                    lists = []
                    list1 = []
                    balance = rey.to_pay - rey.amount
                    # fec.balance_total += balance
                    values = (0,
                              0,
                              {'member_idx': fec.id,
                               'product_id': product,
                               'paid_amount': rey.amount,
                               # 'balance': balance,
                               'pdate': rey.date,
                               'member_price': rey.amount,# fec.green_form_price + fec.coffee_book,
                               'name': "Green Form Delay Payment"})
                    
                    lists.append(values)
                    list1.append(values)
                    fec.payment_line2 = lists
                    # fec.payment_line1 = list1
                    rey.state = "pay"
                    
                elif fec.state in ['interview']:
                    fec.write({'state': 'issue_green'})
                    lists = []
                    list1 = []
                    balance = rey.to_pay - rey.amount
                    fec.balance_total += balance
                    total_green = fec.green_form_price + fec.coffee_book
                    
                    values = (0, 0,
                              {'member_idx': fec.id,
                               'product_id': product,
                               'paid_amount': rey.amount,
                               'balance': balance,
                               'pdate': rey.date,
                               'name':"Green Card Payment",
                               'member_price': total_green})
                    lists.append(values)
                    list1.append(values)
                    fec.payment_line2 = lists
                    # fec.payment_line1 = list1
                    rey.state = "pay"

                elif fec.state in ['green']:
                    fec.write({'state': 'temp',
                               'date_of_temp': fields.Datetime.now()})
                    lists = []
                    list1 = []
                    balance = fec.total - rey.amount
                    # fec.balance_total += balance
                    values = (0, 0,
                              {'member_idx': fec.id,
                               'product_id': product,
                               'paid_amount': rey.amount,
                               'spouse_amount': fec.spouse_amount,
                               'name':"Membership Form Payment",
                               'balance': balance,
                               'pdate': self.date,
                               'member_price': fec.total})
                    
                    lists.append(values)
                    list1.append(values)
                    fec.payment_line2 = lists
                    fec.payment_line1 = list1
                    rey.state = "pay"
                
                else:
                    if rey.p_type != "ano":
                        lists = []
                        list1 = []
                        list3 = []
                        balance = rey.to_pay - rey.amount
                        fec.balance_total += balance
                        if sub_id:
                            for tey in sub_id:
                                tey.state = "done"
                                name_s = str(
                                    tey.periods_month).capitalize().replace(
                                    '_', ' ') + "Subscription"
                                sub_values = (0,
                                              0,
                                              {'sub_order': tey.id,
                                               'member_id': fec.id,
                                               'name': name_s,
                                               'periods_month': tey.periods_month,
                                               'pdate': rey.date,
                                               'total_price': tey.total,
                                               'paid_amount': rey.amount,
                                               'balance': balance})
                                list3.append(sub_values)
                            fec.sub_line = list3

                    else:
                        lists = []
                        list1 = []
                        list3 = []
                        # percent = 12.5/100
                        # fine = percent
                        balance = rey.to_pay - rey.amount
                        fec.balance_total += balance
                        if sub_id:
                            for gec in fec.sub_line:
                                if gec.sub_order.id == sub_id.id:
                                    gec.unlink()

                            sub_id.state = "fined"
                                #  str(tey.periods_month).capitalize().replace('_',' ') + "Subscription"
                            name_s = "Fine for Anomaly"
                            sub_values = (0, 0,
                                              {'sub_order': sub_id.id,
                                               'member_id': sub_id.id,
                                               'name': name_s,
                                               'periods_month': sub_id.periods_month,
                                               'pdate': sub_id.date,
                                               'total_price': sub_id.total,
                                               'paid_amount': rey.amount,
                                               'balance': balance})
                            list3.append(sub_values)
                            fec.sub_line = list3
                                # payment_model.unlink()
                            payment_model.write(
                                    {'communication': 'Fine Payment', 'amount': rey.amount})

        return {'type': 'ir.actions.act_window_close'}

        #  return

    @api.one
    def button_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

    def print_memo_addition(self):
        # body = "%s Printed an offer letter" %self.env.user.name
        #  self.message_post(body=body)
        pass

    def send_mail_to_accounts(self, pay_id, model, amount):
        base_url = http.request.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')
        base_url += '/web# id=%d&view_type=form&model=%s' % (pay_id, model)

        email_from = self.env.user.email
        group_user_id2 = self.env.ref('ikoyi_module.account_boss_ikoyi').id
        group_user_id = self.env.ref('member_app.manager_member_ikoyi').id
        group_user_id3 = self.env.ref('ikoyi_module.gm_ikoyi').id
        member = self.env['member.app'].search(
            [('id', '=', self.member_ref.id)])

        model = 'account.payment'
        # pay = payment_schedule.search([('ikoyi_ref','=',self.id)])
        if pay_id:
            bodyx = "Dear Sir/Madam, </br>This is a notification that the member with ID No. {}\
            has made a payment of {} on the {}.</br> Please kindly <a href={}> </b>Click<a/> to Confirm.</br>\
            Regards".format(member.identification, amount, fields.Datetime.now(), base_url,)
            self.mail_sending(
                email_from,
                group_user_id,
                group_user_id2,
                group_user_id3,
                bodyx)

    def mail_sending(
            self,
            email_from,
            group_user_id,
            group_user_id2,
            group_user_id3,
            bodyx):
        from_browse = self.env.user.name
        groups = self.env['res.groups']
        for order in self:
            group_users = groups.search([('id', '=', group_user_id)])
            group_users2 = groups.search([('id', '=', group_user_id2)])
            group_users3 = groups.search([('id', '=', group_user_id3)])
            group_emails = group_users.users
            group_emails2 = group_users2.users
            group_emails3 = group_users3.users

            append_mails = []
            append_mails_to = []
            append_mails_to3 = []
            for group_mail in group_emails:
                append_mails.append(group_mail.login)

            for group_mail2 in group_emails2:
                append_mails_to.append(group_mail2.login)

            for group_mail3 in group_emails3:
                append_mails_to3.append(group_mail3.login)

            all_mails = append_mails + append_mails_to + append_mails_to3
            print (all_mails)
            email_froms = str(from_browse) + " <" + str(email_from) + ">"
            mail_sender = (', '.join(str(item)for item in all_mails))

            subject = "Payment Notification"
            mail_data = {
                'email_from': email_froms,
                'subject': subject,
                'email_to': mail_sender,
                'email_cc': mail_sender,  #  + (','.join(str(extra)),
                'reply_to': email_from,
                'body_html': bodyx
            }
            mail_id = order.env['mail.mail'].create(mail_data)
            order.env['mail.mail'].send(mail_id)
