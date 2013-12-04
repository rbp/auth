#!/usr/bin/env python

"""
Configuration options for this module.

In a simplistic mimic of argparse's interface, 'options' is simply an
object to which we attach attributes.


rbp@isnomore.net
"""


class Options(object):
    pass
options = Options()

# For how long new user registration is valid, in seconds
options.registration_expiration = 60 * 60 * 24 * 7

# "From" field of registration confirmation email
options.reg_confirmation_from = 'The Website People'
options.reg_confirmation_from_addr = 'webmaster@isnomore.net'

# "Subject" field of registration confirmation email
options.reg_confirmation_subject = 'Confirm your registration!'

# Template file for the registration confirmation email
options.reg_confirmation_template = 'reg_confirmation.template'

options.smtp_server = 'localhost'

# After this many consecutive failed authentication attemps,
# account is temporarily suspended
options.failed_auth_limit = 3

# For how long account is suspended, in seconds
options.login_suspended_period = 60 * 5
