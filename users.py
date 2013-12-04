#!/usr/bin/env python

"""
User-related functions.

This module concerns registration, authentication and access control of users.


rbp@isnomore.net
"""


import time
import re
import random
import string
from hashlib import sha256

from . config import options
from . exceptions import (InvalidEmailError, InvalidPasswordError,
                          InvalidRegistrationKeyError, ProgrammingError,
                          UserAlreadyActiveError, AuthenticationError,
                          UnauthorizedAccessError)


def validate_email(email):
    """Skeleton of email validation. Included for completion only.
    We should really use a third-party validator (such as Django's).
    """
    email_re = re.compile('[^@]+@[^@]+')
    if not email_re.match(email):
        raise InvalidEmailError()
    

def registration_key(username):
    """Generates a pseudo-random registration key."""
    return sha256(username + str(random.random())[2:]).hexdigest()


def mkhash(passwd, salt=None):
    """Returns the hashed password, prepended by a salt.
    If a salt is given, it is used. Otherwise, a random one is generated.
    """
    if salt is None:
        pool = string.letters + string.digits
        salt = ''.join(random.choice(pool) for i in xrange(Hash._salt_len))
    if len(salt) != Hash._salt_len:
        raise ValueError('Salt of unexpected size: {0}'.format(len(salt)))
    h = Hash(salt + sha256(salt + passwd).hexdigest())
    return h


def register_user(email=None, password=None, conn=None):
    if email is None:
        raise InvalidEmailError()
    validate_email(email)
    if password is None:
        raise InvalidPasswordError()
    if conn is None:
        raise ProgrammingError()
    
    passwd_hash = mkhash(password)
    key = registration_key(email)
    now = int(time.time())

    old_registration = conn.get_pending_user(email)
    if old_registration is not None:
        old_date = old_registration[3]
        if now - old_date >= options.registration_expiration:
            conn.delete_pending_user(email)
    already_active = conn.get_user(email)
    if already_active:
        raise UserAlreadyActiveError("user '{0}' already exists".format(email))
    conn.save_pending_user(email, passwd_hash, key, now)
    return key


def activate(key, conn):
    user = conn.get_pending_user_by_key(key)
    if not user:
        raise InvalidRegistrationKeyError()
    email, password = user
    conn.save_user(email, password)
    conn.delete_pending_user(email)


def authenticate(email, password, conn):
    db_credentials = conn.get_user(email)
    if db_credentials is not None:
        db_email, db_password, failed_attempts, suspended_until = db_credentials
        db_hashed = Hash(db_password)
        hashed = mkhash(password, salt=db_hashed.salt)
        now = time.time()
        if suspended_until is not None and now > suspended_until:
            conn.lift_user_suspension(email)
            suspended_until = None
            failed_attempts = 0
        if (email == db_email and hashed == db_hashed and
            suspended_until is None):
            if failed_attempts > 0:
                conn.lift_user_suspension(email)
            return True
        failed_attempts += 1
        if failed_attempts == options.failed_auth_limit:
            conn.suspend_user(email, failed_attempts,
                              now + options.login_suspended_period)
        else:
            conn.set_failed_login_attempts(email, failed_attempts)
    raise AuthenticationError("invalid authentication credentials")


def access_control(role):
    """Decorator to grant or deny access to functions, given a role"""
    def decorate(func):
        def auth_wrapper(email, conn, *args, **kwargs):
            user_data = conn.get_user(email)
            if user_data is None:
                raise UnauthorizedAccessError(
                    "User does not have the role required by this resource")
            user_role = conn.get_user_role(email)
            if user_role != role:
                raise UnauthorizedAccessError(
                        "User does not have the role required by this resource")
            return func(*args, **kwargs)
        return auth_wrapper
    return decorate


class Hash(str):
    _salt_len = 2

    @property
    def salt(self):
        return self[:self._salt_len]
