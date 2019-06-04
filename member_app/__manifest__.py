#  -*- coding: utf-8 -*-
#  See LICENSE file for full copyright and licensing details.

{
    'name': 'Member Ikoyi',
    'version': '10.0.1.0.0',
    'author': 'Maduka Sopulu',
    'description':"""A simple membership module for Ikoyi club""",
    'summary':'A membership module for Ikoyi club',
    'category': 'Base',
    # 'live_test_url': "https://www.youtube.com/watch?v=4v5P1UdhdxU",

    'depends': ['base', 'hr','sale','ikoyi_module','account','product','branch'],
    'data': [
        'security/security_group.xml',
        'security/ir.model.access.csv',
        'views/member_app_view.xml',
        'views/suspension_view.xml',
        'views/subscription_view.xml',
        'views/guest_view.xml',
        'views/subscription_view.xml',
        'reports/id_card_template.xml',
        'reports/id_card.xml',
        
    ],
    'qweb': [
        'static/src/xml/base.xml',
    ],
    'price': 14000.99,
    'currency': 'USD',


    'installable': True,
    'auto_install': False,
}
