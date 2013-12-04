#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import exceptions
import mocker
from mocker import expect

from .. import users
from .. import db
from .. users import (register_user, activate, authenticate, access_control,
                      registration_key, mkhash, Hash)
from .. exceptions import (InvalidEmailError, InvalidPasswordError,
                           ProgrammingError, DatabaseError, InternalError,
                           InvalidRegistrationKeyError, AuthenticationError,
                           UnauthorizedAccessError, UnsupportedParamStyle,
                           Error)


class TestUserRegistration(mocker.MockerTestCase):
    def test_user_registration_requires_email_address(self):
        self.assertRaises(InvalidEmailError, register_user)

    def test_user_registration_requires_password(self):
        self.assertRaises(InvalidPasswordError,
                          register_user, 'someone@isnomore.net')

    def test_user_registration_requires_valid_email(self):
        for email in ['invalid email', '@invalid', 'invalid@', '@']:
            self.assertRaises(InvalidEmailError,
                              register_user, email, 'some password')
    
    def test_user_registration_requires_db_connection_object(self):
        self.assertRaises(ProgrammingError,
                          register_user, 'someone@isnomore.net', 'password')

    def test_user_registration_executes_query_on_db(self):
        conn = db.Connection()
        mock_connection = self.mocker.patch(conn)
        expect(mock_connection.execute(mocker.ARGS)).count(1, None)
        self.mocker.replay()

        register_user('user@isnomore.net', 'password', mock_connection)


class TestExceptionDBAPIConformance(unittest.TestCase):
    def test_programmingerror_must_descend_from_databaseerror(self):
        assert issubclass(ProgrammingError, DatabaseError)

    def test_databaseerror_must_descend_from_error(self):
        assert issubclass(ProgrammingError, Error)

    def test_error_must_descend_from_standarderror(self):
        assert issubclass(Error, exceptions.StandardError)

    def test_internalerror_must_descend_from_databaseerror(self):
        assert issubclass(InternalError, DatabaseError)


class TestRegistrationKey(mocker.MockerTestCase):
    def test_registration_key_returns_string(self):
        assert isinstance(registration_key('username'), str)

    def test_different_usernames_change_registration_key(self):
        assert registration_key('user1') != registration_key('user2')

    def test_same_username_yields_different_registration_key(self):
        assert registration_key('username') != registration_key('username')

    def test_registration_key_uses_random_salt(self):
        assert registration_key('username') != registration_key('username')

        mock_random = self.mocker.mock()
        expect(mock_random.random()).result('').count(2)
        self.mocker.replay()

        r = users.random
        users.random = mock_random
        try:
            assert registration_key('username') == registration_key('username')
        finally:
            users.random = r


class TestHash(mocker.MockerTestCase):
    def test_mkhash_must_receive_input_string(self):
        self.assertRaises(TypeError, mkhash)

    def test_mkhash_returns_hash_object(self):
        assert isinstance(mkhash('foo'), Hash)

    def test_salt_is_prepended_to_the_hash(self):
        h = mkhash('some password')
        assert h.salt
        assert h.startswith(h.salt)

    def test_mkhash_may_receive_optional_salt(self):
        h = mkhash('a password', salt='xy')
        assert h.salt == 'xy'

    def test_mkhash_with_same_password_and_salt_returns_same_hash(self):
        assert mkhash('foobar', salt='42') == mkhash('foobar', salt='42')

    def test_mkhash_same_password_different_salt_returns_different_hashes(self):
        h1 = mkhash('foobar', salt='42')
        h2 = mkhash('foobar', salt='43')
        assert h1 != h2
        assert h1[len(h1.salt):] != h2[len(h2.salt):]

    def test_mkhash_different_password_same_salt_returns_different_hashes(self):
        h1 = mkhash('foo', salt='42')
        h2 = mkhash('bar', salt='42')
        assert h1 != h2
        assert h1[len(h1.salt):] != h2[len(h2.salt):]

    def test_mkhash_uses_random_salt_when_not_given(self):
        mock_random = self.mocker.mock()
        expect(mock_random.choice(mocker.ANY)).result('a')
        expect(mock_random.choice(mocker.ANY)).result('b')
        expect(mock_random.choice(mocker.ANY)).result('c')
        expect(mock_random.choice(mocker.ANY)).result('d')
        self.mocker.replay()

        r = users.random
        users.random = mock_random
        h1 = mkhash('passwd')
        h2 = mkhash('passwd')
        try:
            assert h1.salt == 'ab'
            assert h2.salt == 'cd'
        finally:
            users.random = r

    def test_salt_must_be_of_proper_length(self):
        big_salt = 'a'*Hash._salt_len + 'a'
        small_salt = 'a'*(Hash._salt_len - 1)
        self.assertRaises(ValueError, mkhash, 'foo', salt=big_salt)
        self.assertRaises(ValueError, mkhash, 'foo', salt=small_salt)

    def test_mkhash_works_with_unicode_strings(self):
        u_passwd = 'áéíóú'
        hash = mkhash(u_passwd)


class TestDBConnection(mocker.MockerTestCase):
    def setUp(self):
        self.mock_driver = self.mocker.mock()
        self.mock_conn = self.mocker.mock()
        self.mock_cursor = self.mocker.mock()

    def test_connection_accepts_arbitrary_connection_parameters(self):
        db.Connection()
        db.Connection('some connection parameters')
        db.Connection(1, 2, and_another=42)

    def test_connection_passes_connection_parameters_to_driver(self):
        self.mock_driver.connect()
        self.mock_driver.connect('some connection parameters')
        self.mock_driver.connect(1, 2, and_another=42)
        self.mocker.replay()

        conn1 = db.Connection(driver=self.mock_driver)
        conn1.connect()
        conn2 = db.Connection('some connection parameters', driver=self.mock_driver)
        conn2.connect()
        conn3 = db.Connection(1, 2, driver=self.mock_driver, and_another=42)
        conn3.connect()

    def test_connect_with_no_driver_raises(self):
        conn = db.Connection()
        self.assertRaises(db.InvalidDriverError, conn.connect)

    def test_driver_without_connect_method_raises(self):
        expect(self.mock_driver.connect()).throw(AttributeError)
        self.mocker.replay()

        conn = db.Connection(driver=self.mock_driver)
        self.assertRaises(db.InvalidDriverError, conn.connect)

    def test_connecting_gets_new_cursor(self):
        expect(self.mock_driver.connect()).result(self.mock_conn)
        self.mock_conn.cursor()
        self.mocker.replay()

        conn = db.Connection(driver=self.mock_driver)
        conn.connect()

    def test_execute_with_cursor_error_tries_new_cursor(self):
        expect(self.mock_driver.connect()).result(self.mock_conn)
        expect(self.mock_conn.cursor()).result(self.mock_cursor)
        expect(self.mock_cursor.execute(mocker.ARGS)).throw(InternalError)
        expect(self.mock_conn.cursor()).result(self.mock_cursor)
        self.mock_cursor.execute(mocker.ARGS)
        self.mock_conn.commit()
        self.mocker.replay()

        conn = db.Connection(driver=self.mock_driver)
        conn.connect()
        conn.execute('')

    def test_cursor_only_tries_to_recover_from_error_once(self):
        expect(self.mock_driver.connect()).result(self.mock_conn)
        expect(self.mock_conn.cursor()).result(self.mock_cursor)
        expect(self.mock_cursor.execute(mocker.ARGS)).throw(InternalError)
        expect(self.mock_conn.cursor()).result(self.mock_cursor)
        expect(self.mock_cursor.execute(mocker.ARGS)).throw(InternalError)
        self.mock_conn.rollback()
        self.mocker.replay()

        conn = db.Connection(driver=self.mock_driver)
        conn.connect()
        self.assertRaises(InternalError, conn.execute, '')

    def test_query_execution_commits(self):
        expect(self.mock_driver.connect()).result(self.mock_conn)
        expect(self.mock_conn.cursor()).result(self.mock_cursor)
        self.mock_cursor.execute(mocker.ARGS)
        self.mock_conn.commit()
        self.mocker.replay()

        conn = db.Connection(driver=self.mock_driver)
        conn.connect()
        conn.execute('something')
        
    def test_query_execution_commits_after_requesting_new_cursor(self):
        expect(self.mock_driver.connect()).result(self.mock_conn)
        expect(self.mock_conn.cursor()).result(self.mock_cursor)
        expect(self.mock_cursor.execute(mocker.ARGS)).throw(InternalError)
        expect(self.mock_conn.cursor()).result(self.mock_cursor)
        self.mock_cursor.execute(mocker.ARGS)
        self.mock_conn.commit()
        self.mocker.replay()

        conn = db.Connection(driver=self.mock_driver)
        conn.connect()
        conn.execute('something')
        

class TestDBQuery(unittest.TestCase):
    def test_db_query_is_equal_to_string_of_its_name(self):
        q = db.Query('some name', None, None)
        assert q == 'some name'
        assert q != 'some other name'

    def test_db_query_can_be_used_as_dict_key(self):
        q = db.Query('some name', None, None)
        d = {}
        d[q] = 42
        d['some name'] == q


class TestDBQueries(mocker.MockerTestCase):
    def test_db_queries_default_to_qmark(self):
        query_obj = db.queries['get_user_role']
        query, params = query_obj.query('u@isnomore.net')
        assert query == query_obj._query
        assert query == "select role from users where email = ?", query
        assert params == ('u@isnomore.net',)
        assert (query, params) == query_obj.query('u@isnomore.net')

    def test_db_queries_respect_driver_paramstyle(self):
        query_qmark = db.queries['set_user_role'].query('user', 'role',
                                                        paramstyle='qmark')
        query_numeric = db.queries['set_user_role'].query('user', 'role',
                                                        paramstyle='numeric')
        query_named = db.queries['set_user_role'].query('user', 'role',
                                                        paramstyle='named')

        assert query_qmark[0] == "update users set role = ? where email = ?"
        assert query_numeric[0] == "update users set role = :1 where email = :2"
        assert query_named[0] == "update users set role = :a where email = :b"

        assert query_qmark[1] == ('role', 'user')
        assert query_numeric[1] == ('role', 'user')
        assert query_named[1] == {'a': 'role', 'b': 'user'}

    def test_db_queries_on_unsupported_paramstyle_raises(self):
        mock_driver = self.mocker.mock()
        expect(mock_driver.paramstyle).result('pyformat').count(1, None)
        self.mocker.replay()

        conn = db.Connection(driver=mock_driver)
        self.assertRaises(UnsupportedParamStyle,
                          conn.get_user, 'someone@isnomore.net')
    
    def test_query_methods_are_generated_on_the_fly(self):
        conn = db.Connection()
        mock_res = self.mocker.mock()
        mock_exec = self.mocker.replace(conn.execute)
        mocker.expect(mock_exec(mocker.ARGS)).result(mock_res).count(1, None)
        mocker.expect(mock_res.fetchall()).result([(42,)]).count(1, None)
        self.mocker.replay()

        try:
            conn.get_meaning_of_life()
        except AttributeError: 
            pass
        else:
            self.fail()
        
        db.queries['get_meaning_of_life'] = db.Query('get_meaning_of_life',
                                                     'unique',
                                                     'select * from answer')
        a = conn.get_meaning_of_life()
        assert a == 42
        db.queries.pop('get_meaning_of_life')


class TestUserActivation(mocker.MockerTestCase):
    def test_activate_requires_registration_key_and_connection(self):
        self.assertRaises(TypeError, activate)
        self.assertRaises(TypeError, activate, 'some_key')

    def test_activate_with_non_existent_key_raises(self):
        mock_conn = self.mocker.mock()
        expect(mock_conn.get_pending_user_by_key(mocker.ANY)).result([])
        self.mocker.replay()

        self.assertRaises(InvalidRegistrationKeyError,
                          activate, 'some key', mock_conn)

    def test_activate_inserts_into_table_users_removes_from_pending(self):
        mock_conn = self.mocker.mock()
        mock_conn.get_pending_user_by_key('some key')
        self.mocker.result((u'user@isnomore.net', 'hashed password'))
        mock_conn.save_user(u'user@isnomore.net', 'hashed password')
        mock_conn.delete_pending_user(u'user@isnomore.net')
        self.mocker.replay()

        activate('some key', mock_conn)


class TestUserAuthentication(mocker.MockerTestCase):
    def test_authenticate_non_existent_email_raises(self):
        mock_conn = self.mocker.mock()
        expect(mock_conn.get_user('someone@isnomore.net')).result(None)
        self.mocker.replay()

        self.assertRaises(AuthenticationError, authenticate,
                          'someone@isnomore.net', 'password', mock_conn)

    def test_authenticate_wrong_password_raises(self):
        mock_conn = self.mocker.mock()
        mock_conn.get_user('someone@isnomore.net')
        hashed = users.mkhash('correct password')
        self.mocker.result(['someone@isnomore.net', hashed,
                            0, None])
        mock_conn.set_failed_login_attempts(mocker.ARGS, mocker.KWARGS)
        self.mocker.replay()

        self.assertRaises(AuthenticationError, authenticate,
                          'someone@isnomore.net', 'wrong password', mock_conn)

    def test_authenticate_wrong_email_raises(self):
        mock_conn = self.mocker.mock()
        mock_conn.get_user('someone@isnomore.net')
        hashed_password = users.mkhash('a password')
        self.mocker.result(['someone_else@isnomore.net', hashed_password,
                            0, None])
        mock_conn.set_failed_login_attempts(mocker.ARGS, mocker.KWARGS)
        self.mocker.replay()

        self.assertRaises(AuthenticationError, authenticate,
                          'someone@isnomore.net', 'a password', mock_conn)
        
    def test_authenticate_password_with_salted_hash(self):
        hashed = users.mkhash('password')
        mock_conn = self.mocker.mock()
        mock_mkhash = self.mocker.replace(users.mkhash)
        mock_conn.get_user('someone@isnomore.net')
        self.mocker.result(['someone@isnomore.net', hashed, 0, None])
        expect(mock_mkhash('password', salt=hashed.salt)).passthrough()
        self.mocker.replay()

        assert authenticate('someone@isnomore.net', 'password', mock_conn)


class TestAccessControl(mocker.MockerTestCase):
    def test_access_control_with_invalid_email_fails(self):
        mock_conn = self.mocker.mock()
        expect(mock_conn.get_user('someone@isnomore.net')).result(None)
        self.mocker.replay()

        @access_control('a role')
        def foo(): return 42

        self.assertRaises(UnauthorizedAccessError,
                          foo, 'someone@isnomore.net', mock_conn)

    def test_access_control_for_valid_user_with_wrong_role_fails(self):
        mock_conn = self.mocker.mock()
        mock_conn.get_user('someone@isnomore.net')
        self.mocker.result(['someone@isnomore.net', 'password', 0, None])
        mock_conn.get_user_role('someone@isnomore.net')
        self.mocker.result('some role')
        self.mocker.replay()

        @access_control('another role')
        def foo(): return 42

        self.assertRaises(UnauthorizedAccessError,
                          foo, 'someone@isnomore.net', mock_conn)
        
    def test_access_control_valid_credentials_and_role_return_function(self):
        mock_conn = self.mocker.mock()
        mock_conn.get_user('someone@isnomore.net')
        self.mocker.result(['someone@isnomore.net', 'password', 0, None])
        mock_conn.get_user_role('someone@isnomore.net')
        self.mocker.result('a role')
        self.mocker.replay()

        @access_control('a role')
        def foo(): return 42

        assert foo('someone@isnomore.net', mock_conn) == 42

    def test_access_control_passes_on_function_arguments(self):
        mock_conn = self.mocker.mock()
        mock_conn.get_user('someone@isnomore.net')
        self.mocker.result(['someone@isnomore.net', 'password', 0, None])
        self.mocker.count(3)
        mock_conn.get_user_role('someone@isnomore.net')
        self.mocker.result('a role')
        self.mocker.count(3)
        self.mocker.replay()

        @access_control('a role')
        def foo(a): return 42 + a

        assert foo('someone@isnomore.net', mock_conn, 10) == 52
        
        @access_control('a role')
        def bar(b=5): return 42 * b

        assert bar('someone@isnomore.net', mock_conn, b=3) == 126

        @access_control('a role')
        def baz(a, b, c=10, d=15):
            return a + b + c + d

        assert baz('someone@isnomore.net', mock_conn, 5, 7, d=20) == 42
