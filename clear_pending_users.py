#!/usr/bin/env python

"""
This script clears pending users whose registration key has expired.

It should be run periodically to avoid clutter of the database.


rbp@isnomore.net
"""


import time
from . db import Connection
from . config import options


def delete_expired_pending_users(conn=None):
    if conn is None:
        conn = Connection(options.db_params, driver=options.db_driver)
        conn.connect()
    results = {'failed': []}
    now = int(time.time())
    expiration_time = now - options.registration_expiration
    expired = conn.get_pending_users_registered_before(expiration_time)
    for email in expired:
        try:
            conn.delete_pending_user(email)
        except Exception, e:
            results['failed'].append((email, e.args))
    return results


if __name__ == '__main__':
    results = delete_expired_pending_users()
    if results:
        print "Deletion failed for:"
        print "\n".join(i[0] for i in results["failed"])

