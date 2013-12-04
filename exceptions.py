#!/usr/bin/env python

"""
Custom exceptions defined for this package.

Whenever suitable, database-related exceptions conform to Python's DB API v2.0.


rbp@isnomore.net
"""


from __future__ import absolute_import
import exceptions as builtin_exceptions


class InvalidEmailError(Exception):
    pass

class InvalidPasswordError(Exception):
    pass

class InvalidDriverError(Exception):
    pass

class InvalidRegistrationKeyError(Exception):
    pass

class AuthenticationError(Exception):
    pass

class UnauthorizedAccessError(Exception):
    pass

class Error(builtin_exceptions.StandardError):
    pass

class DatabaseError(Error):
    pass

class ProgrammingError(DatabaseError):
    pass

class InternalError(DatabaseError):
    pass

class UserAlreadyActiveError(DatabaseError):
    pass

class UnsupportedParamStyle(Error):
    pass

class UnsupportedQueryReturnType(Error):
    pass
