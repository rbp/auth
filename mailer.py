#!/usr/bin/env python

"""
This script sends confirmation messages to recently registered users.

It should be run periodically so that users receive a registration
confirmation link soon after they have registered.


rbp@isnomore.net
"""


import smtplib
from email.message import Message
from . db import Connection
from . config import options


def create_message(email, key):
    msg = Message()
    msg['From'] = '{0} <{1}>'.format(options.reg_confirmation_from,
                                     options.reg_confirmation_from_addr)
    msg['To'] = email
    msg['Subject'] = options.reg_confirmation_subject
    body = open(options.reg_confirmation_template).read()
    msg.set_payload(body.format(registration_key=key))
    return msg


def mail_confirmation(email, msg):
    server = smtplib.SMTP(options.smtp_server)
    server.sendmail(options.reg_confirmation_from_addr,
                    email,
                    msg)
    server.quit()


def send_pending_confirmations():
    db_conn = Connection(options.db_params, driver=options.db_driver)
    db_conn.connect()
    results = {'failed': []}
    pending = db_conn.get_pending_users_unmailed()
    for email, key in pending:
        msg = create_message(email, key)
        try:
            mail_confirmation(email, msg.as_string())
        except Exception, e:
            results['failed'].append((email, e.args))
        else:
            db_conn.set_pending_user_as_mailed(email)
    return results


if __name__ == '__main__':
    results = send_pending_confirmations()
    if results:
        print "Sending failed for:"
        print "\n".join(i[0] for i in results["failed"])

