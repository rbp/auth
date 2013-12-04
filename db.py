#!/usr/bin/env python

"""
Database abstraction for this package.


rbp@isnomore.net
"""


import string
from . exceptions import (InternalError, InvalidDriverError,
                          UnsupportedParamStyle, UnsupportedQueryReturnType)


class Query(object):
    """A query to the database.
    This takes care of properly formatting the query and parameters,
    according to the chosen Python DB API v2.0 parameter style
    (if supported).
    """
    supported_paramstyles = ['qmark', 'numeric', 'named']

    def __init__(self, name, return_type, query, param_order=None):
        self._name = name
        self._return_type = return_type
        self._query = query
        self._param_order = param_order

    def __eq__(self, other):
        return self._name == other
    def __ne__(self, other):
        return self._name != other

    def __hash__(self):
        return self._name.__hash__()

    def __repr__(self):
        return self._name.__repr__()

    def reorder_params(self, params):
        """Returns another tuple (if params is a tuple, otherwise a list)
        in the order specified by self._param_order (if set). This is
        necessary because sometimes the natural order of parameters for
        a method is not the one needed by the query.
        """
        seq = tuple if isinstance(params, tuple) else list
        if self._param_order is None:
            return params
        return seq(params[i] for i in self._param_order)

    def query(self, *params, **kwargs):
        """Returns properly formatted (query string, parameter tuple)
        for this query, given parameters and optional paramstyle
        (which defaults to qmark).
        """
        paramstyle = kwargs.get('paramstyle', 'qmark')
        params = self.reorder_params(params)
        q_split = self._query.split('?')
        if paramstyle == 'qmark':
            return self._query, params
        elif paramstyle == 'numeric':
            converted = [(part + ':{0}'.format(i+1)) for i, part in
                         enumerate(q_split[:-1])] + q_split[-1:]
            return ''.join(converted), params
        elif paramstyle == 'named':
            converted = [part + ':{0}'.format(l) for l, part in
                         zip(string.ascii_letters, q_split[:-1])] + q_split[-1:]
            param_dict = dict(zip(string.ascii_letters, params))
            return ''.join(converted), param_dict

        raise UnsupportedParamStyle(
            'Unsupported paramstyle: {0}'.format(paramstyle))


class Connection(object):
    """Connection encapsulates a connection to the actual database.
    This takes care of connecting, requesting cursors and executing queries.
    """
    def __init__(self, *args, **kwargs):
        self._driver = kwargs.pop('driver', None)
        self._conn = None
        self._cursor = None
        self._conn_args = args
        self._conn_kwargs = kwargs

    def __getattr__(self, name):
        """Automatically execute a query called 'name',
        if the requested attribute is the name of a query stored in this module.
        """
        if name in queries:
            def call_query(*args):
                return self._execute_query(name, *args)
            return call_query
        else:
            raise AttributeError("'{0}' object has no attribute '{1}'".
                                 format(self.__class__, name))

    def connect(self):
        try:
            self._conn = self._driver.connect(*self._conn_args,
                                              **self._conn_kwargs)
        except AttributeError, e:
            raise InvalidDriverError(e)
        if self._conn:
            self._cursor = self._conn.cursor()

    def execute(self, query, params=()):
        if self._cursor:
            ret = None
            try:
                try:
                    ret = self._cursor.execute(query, params)
                except InternalError:
                    self._cursor = self._conn.cursor()
                    ret = self._cursor.execute(query, params)
            except Exception, e:
                self._conn.rollback()
                raise e
            else:
                self._conn.commit()
            return ret

    @property
    def paramstyle(self):
        return getattr(self._driver, 'paramstyle', 'qmark')

    def _execute_query(self, name, *params):
        """Executes the named query with the passed parameters.
        Returns results as specified by the appropriate Query object.
        """
        query_obj = queries[name]
        
        q, p = query_obj.query(*params, paramstyle=self.paramstyle)
        results = self.execute(q, p)
        if query_obj._return_type is None or results is None:
            return None
        rows = results.fetchall()

        if query_obj._return_type == 'rows':
            return rows
        if query_obj._return_type == 'one row':
            return rows[0] if rows else None
        if query_obj._return_type == 'one column':
            return [r[0] for r in rows]
        if query_obj._return_type == 'unique':
            return rows[0][0] if rows and rows[0] else None

        raise UnsupportedQueryReturnType('Unsupported return type: {0}'.
                                         format(query_obj._return_type))


queries = dict((q._name, q) for q in(
    Query('save_pending_user', None,
          """insert into pending_users
             (email, password, registration_key, registration_date)
             values (?, ?, ?, ?)"""),
    Query('get_pending_user', 'one row',
          """select email, password, registration_key, registration_date
             from pending_users where email = ?"""),
    Query('delete_pending_user', None,
          "delete from pending_users where email = ?"),
    Query('get_pending_users_unmailed', 'rows',
          """select email, registration_key from pending_users
             where confirmation_sent = 0"""),
    Query('set_pending_user_as_mailed', None,
          """update pending_users
             set confirmation_sent = 1 where email = ?"""),
    Query('get_pending_user_by_key', 'one row',
          """select email, password from pending_users
             where registration_key = ?"""),
    Query('get_pending_users_registered_before', 'one column',
          """select email from pending_users
             where registration_date < ?"""),
    Query('save_user', None,
          "insert into users (email, password) values (?, ?)"),
    Query('get_user', 'one row',
          """select email, password, failed_login_attempts, suspended_until
             from users where email = ?"""),
    Query('suspend_user', None,
          """update users
             set failed_login_attempts = ?, suspended_until = ?
             where email = ?""",
          param_order=[1, 2, 0]),
    Query('set_failed_login_attempts', None,
          """update users
             set failed_login_attempts = ?
             where email = ?""",
          param_order=[1, 0]),
    Query('lift_user_suspension', None,
          """update users
             set suspended_until = NULL, failed_login_attempts = 0
             where email = ?"""),
    Query('set_user_role', None,
          "update users set role = ? where email = ?",
          param_order=[1, 0]),
    Query('get_user_role', 'unique',
          "select role from users where email = ?")
))
