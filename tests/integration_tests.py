"""
Integration tests
==================

Setup:

>>> import os
>>> import time
>>> import sqlite3
>>> import smtplib
>>> from mocker import Mocker, expect, ANY, ARGS
>>> 
>>> tmp_dir = 'tmp'
>>> tmp_db = os.path.join(tmp_dir, 'tmpdb.sqlite')
>>> create_tmp = not os.path.isdir(tmp_dir)
>>> if create_tmp:
...     os.mkdir(tmp_dir)
>>> if os.path.exists(tmp_db):
...     os.unlink(tmp_db)



First of all, let's make sure that our SQL schema is at least valid:

>>> schema = open('schema.sql').read()
>>> sqlite_conn = sqlite3.connect(tmp_db)
>>> sqlite_cursor = sqlite_conn.cursor()
>>> sqlite_cursor.executescript(schema) #doctest: +ELLIPSIS
<sqlite3.Cursor...>


Now, let's register a user:

>>> from .. import users
>>> from .. import db
>>> conn = db.Connection(tmp_db, driver=sqlite3)
>>> conn.connect()
>>> before_reg = int(time.time())
>>> reg_key = users.register_user('rbp@isnomore.net', 'foobar', conn)
>>> results = sqlite_cursor.execute('''
...           select email, password, registration_key, registration_date
...           from pending_users''').fetchall()
>>> len(results)
1
>>> username, password, key, date = results[0]
>>> print username
rbp@isnomore.net
>>> password != 'foobar'
True
>>> password == users.mkhash('foobar', users.Hash(password).salt)
True
>>> len(key) > 0
True
>>> reg_key == key
True
>>> date >= before_reg
True


Trying to register a user that is already pending registration
triggers an IntegrityError:

>>> key = users.register_user('anxious_user@isnomore.net', 'passwd', conn)
>>> users.register_user('anxious_user@isnomore.net', 'whatever', conn)
Traceback (most recent call last):
  ...
IntegrityError: column email is not unique


However, if the pending user has been registered for longer than a
certain (configurable) period, the old record is purged and a new
registration takes place:

>>> from .. config import options
>>> now = time.time()
>>> mocker = Mocker()
>>> mock_time = mocker.mock()
>>> _ = expect(mock_time.time()).result(now)
>>> mock_time.time() #doctest: +ELLIPSIS
<mocker.Mock ...
>>> mocker.result(now + options.registration_expiration + 1)
>>> mocker.replay()
>>> t = users.time
>>> users.time = mock_time


So, the user registers for the first time:

>>> key = users.register_user('late_user@isnomore.net', 'passwd', conn)
>>> old = conn.get_pending_user('late_user@isnomore.net') #doctest: +ELLIPSIS
>>> print old[0]
late_user@isnomore.net
>>> old[3] == int(now)
True


And then again, options.registration_expiration + 1 seconds later:

>>> key = users.register_user('late_user@isnomore.net', 'passwd', conn)
>>> new = conn.get_pending_user('late_user@isnomore.net') #doctest: +ELLIPSIS
>>> print new[0]
late_user@isnomore.net
>>> new[3] == int(now + options.registration_expiration + 1)
True
>>> mocker.verify()
>>> mocker.restore()
>>> users.time = t


The registration key for a user must not be in use. Trying to insert
an already existing key will trigger an IntegrityError:

>>> r = users.registration_key
>>> users.registration_key = lambda u: 'a single reg key'
>>> key = users.register_user('someone@isnomore.net', 'foobar', conn)
>>> users.register_user('someone_else@isnomore.net', 'foobar', conn)
Traceback (most recent call last):
  ...
IntegrityError: column registration_key is not unique
>>> users.registration_key = r


The mailer.py script should be run periodically to query the database
for pending users and send confirmation messages as needed. First of
all, mailer has to grab a list of users that haven't been sent
confirmation emails yet:

>>> sqlite_cursor.execute('delete from pending_users') #doctest: +ELLIPSIS
<sqlite3.Cursor ...>
>>> sqlite_conn.commit()
>>> conn.get_pending_users_unmailed()
[]
>>> key1 = users.register_user('someone@isnomore.net', 'a password', conn)
>>> key2 = users.register_user('someone_else@isnomore.net', 'another one', conn)
>>> to_mail = conn.get_pending_users_unmailed()
>>> to_mail  #doctest: +ELLIPSIS,+NORMALIZE_WHITESPACE
[(u'someone@isnomore.net', ...),
(u'someone_else@isnomore.net', ...)]


get_pending_users_unmailed returns a list of (email, registration key)
tuples:

>>> r = users.registration_key
>>> users.registration_key = lambda u: 'fixed registration key'
>>> key = users.register_user('another@isnomore.net', 'a password', conn)
>>> to_mail_again = conn.get_pending_users_unmailed()
>>> new = (set(to_mail) ^ set(to_mail_again)).pop()
>>> new
(u'another@isnomore.net', u'fixed registration key')
>>> users.registration_key = r


Only users whose confirmation email hasn't been sent yet should be
returned by get_pending_users_unmailed:

>>> sqlite_cursor.execute('''
...     update pending_users set confirmation_sent = 1
...     where email = 'someone_else@isnomore.net' ''') #doctest: +ELLIPSIS
<sqlite3.Cursor ...>
>>> sqlite_conn.commit()
>>> really_to_mail = conn.get_pending_users_unmailed()
>>> len(really_to_mail)
2
>>> really_to_mail  #doctest: +ELLIPSIS,+NORMALIZE_WHITESPACE
[(u'someone@isnomore.net', u'...'),
(u'another@isnomore.net', u'fixed registration key')]


Given a list of email addresses (and each one's respective
registration key), mailer should send a confirmation message to each
of them. Mailer uses config.options to determine the SMTP server,
"From" name and address, subject and email message template file.

First mailer builds the message, an object from the Python builtin
email module:

>>> from .. import mailer
>>> msg = mailer.create_message('someone@isnomore.net', 'a_registration_key')
>>> options.reg_confirmation_from in msg['from']
True
>>> '<{0}>'.format(options.reg_confirmation_from_addr) in msg['from']
True
>>> print msg['to']
someone@isnomore.net
>>> msg['subject'] == options.reg_confirmation_subject
True
>>> template = open(options.reg_confirmation_template).read()
>>> msg.get_payload() == template.replace('{registration_key}',
...                                       'a_registration_key')
True


Once the message is built, mailer sends it:

>>> mocker = Mocker()
>>> mock_smtplib = mocker.mock()
>>> mock_smtp = mocker.mock()
>>> _ = expect(mock_smtplib.SMTP(options.smtp_server)).result(mock_smtp)
>>> mock_smtp.sendmail(options.reg_confirmation_from_addr,
...                    'someone@isnomore.net',
...                    msg.as_string())                    #doctest:+ELLIPSIS
<mocker.Mock ...>
>>> mock_smtp.quit() #doctest: +ELLIPSIS
<mocker.Mock ...>
>>> l = mailer.smtplib 
>>> mailer.smtplib = mock_smtplib
>>> with mocker:
...     mailer.mail_confirmation('someone@isnomore.net', msg.as_string())
>>> mailer.smtplib = l


Now, putting it all together:

>>> mocker = Mocker()
>>> mock_create_msg = mocker.replace(mailer.create_message)
>>> mock_confirmation = mocker.mock()
>>> mock_options = mocker.replace(options)
>>> to_mail = conn.get_pending_users_unmailed()
>>> user1, user2 = to_mail
>>>
>>> _ = expect(mock_create_msg(user1[0], user1[1])).passthrough()
>>> _ = expect(mock_create_msg(user2[0], user2[1])).passthrough()
>>> mock_confirmation(user1[0], ANY) #doctest: +ELLIPSIS
<mocker.Mock ...>
>>> mock_confirmation(user2[0], ANY) #doctest: +ELLIPSIS
<mocker.Mock ...>
>>> _ = expect(mock_options.db_driver).result(sqlite3)
>>> _ = expect(mock_options.db_params).result(tmp_db)
>>> mc = mailer.mail_confirmation
>>> mailer.mail_confirmation = mock_confirmation
>>> with mocker:
...     results = mailer.send_pending_confirmations()
>>> results['failed']
[]
>>> mailer.mail_confirmation = mc


After emails are sent, the affected pending users are marked as such:

>>> conn.get_pending_users_unmailed()
[]


If an error occurs while sending a message, that users is not marked
has having been sent the confirmation email:

>>> mocker = Mocker()
>>> mock_confirmation = mocker.replace(mailer.mail_confirmation)
>>> mock_options = mocker.replace(options)
>>> _ = expect(mock_confirmation(ARGS)).throw(smtplib.SMTPSenderRefused(0, '', 
...                                           'user_with_error@isnomore.net'))
>>> mock_confirmation(ARGS) #doctest: +ELLIPSIS
<mocker.Mock ...>
>>> _ = expect(mock_options.db_driver).result(sqlite3)
>>> _ = expect(mock_options.db_params).result(tmp_db)
>>>
>>> key1 = users.register_user('user_with_error@isnomore.net', 'foobar', conn)
>>> key2 = users.register_user('user_ok@isnomore.net', 'foobar', conn)
>>> with mocker:
...     results = mailer.send_pending_confirmations()
>>> still_pending = conn.get_pending_users_unmailed()
>>> len(still_pending)
1
>>> print still_pending[0][0]
user_with_error@isnomore.net


Also, mailer.send_pending_confirmations returns a dictionary whose
'failed' key points to a list of tuples (email, exception args):

>>> results['failed']
[(u'user_with_error@isnomore.net', (0, '', 'user_with_error@isnomore.net'))]


Once registered, the user can click on the URL contained on the email
they are sent, which activates that user, given a registration key

>>> r = sqlite_cursor.execute('''select registration_key
...                              from pending_users
...                              where email = 'user_ok@isnomore.net' ''')
>>> key = r.fetchall()[0][0]
>>> sqlite_cursor.execute('''select email from users 
...                       where email = 'user_ok@isnomore.net' ''').fetchall()
[]
>>> users.activate(key, conn)


And, once the user is activated, it's moved to the users table, with
the same password, and removed from the pending_users table:

>>> r = sqlite_cursor.execute('''select email, password from users 
...                        where email = 'user_ok@isnomore.net' ''').fetchall()
>>> email, passwd = r[0]
>>> email
u'user_ok@isnomore.net'
>>> passwd == users.mkhash('foobar', passwd[:users.Hash._salt_len])
True
>>> sqlite_cursor.execute('''select email from pending_users 
...                       where email = 'user_ok@isnomore.net' ''').fetchall()
[]


Trying to re-register a user that is already active raises an error:

>>> users.register_user('user_ok@isnomore.net', 'secret', conn)
Traceback (most recent call last):
  ...
UserAlreadyActiveError: user 'user_ok@isnomore.net' already exists


Users that remain on the pending_users table beyond an expiration
period will eventually be collected and deleted. All users registered
before "now - options.registration_expiration" are considered to be
expired, but we'll use a fake time (one hour into the future) here
to exemplify deleting users.

>>> mocker = Mocker()
>>> mock_time = mocker.replace("time.time")
>>> future_time = now + options.registration_expiration + 3600
>>> _ = expect(mock_time()).result(future_time)
>>> old = conn.get_pending_users_registered_before(future_time)
>>> set(old) == set([u'another@isnomore.net', u'someone@isnomore.net',
...             u'someone_else@isnomore.net', u'user_with_error@isnomore.net'])
True
>>> from .. import clear_pending_users
>>> with mocker:
...     results = clear_pending_users.delete_expired_pending_users(conn)
>>> results['failed']
[]
>>> conn.get_pending_users_registered_before(future_time)
[]


Active users can be authenticated with their email and password:

>>> sqlite_cursor.execute('delete from users') #doctest: +ELLIPSIS
<sqlite3.Cursor ...>
>>> sqlite_conn.commit()
>>> key = users.register_user('a_new_user@isnomore.net', '1337 p455w0rd', conn)
>>> users.activate(key, conn)
>>> users.authenticate('a_new_user@isnomore.net', '1337 p455w0rd', conn)
True
>>> users.authenticate('non_user@isnomore.net', '1337 p455w0rd', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials
>>> users.authenticate('a_new_user@isnomore.net', 'l4m3 p455w0rd', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials


After a configurable number of failed authentication attempts,
authentication is disabled for that user:

>>> key = users.register_user('mistyper@isnomore.net', 'secret', conn)
>>> users.activate(key, conn)
>>> users.authenticate('mistyper@isnomore.net', 'secret', conn)
True
>>> options.failed_auth_limit
3
>>> users.authenticate('mistyper@isnomore.net', 'sceret', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials
>>> users.authenticate('mistyper@isnomore.net', 'aecret', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials

>>> now = int(time.time())
>>> mocker = Mocker()
>>> mock_time = mocker.replace('time.time')
>>> _ = expect(mock_time()).result(now)
>>> with mocker:
...     users.authenticate('mistyper@isnomore.net', 'SECRET', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials


The account is now locked, the user can't authenticate even with the
correct password:

>>> users.authenticate('mistyper@isnomore.net', 'secret', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials


The user is locked out for a period of time, after which they are
allowed in once again:

>>> options.login_suspended_period
300
>>> suspended_until = sqlite_cursor.execute('''select suspended_until
...                                      from users 
...                                      where email = 'mistyper@isnomore.net'
... ''').fetchall()[0][0]
>>> suspended_until == now + options.login_suspended_period
True

>>> mocker = Mocker()
>>> mock_time = mocker.replace('time.time')
>>> _ = expect(mock_time()).result(now + options.login_suspended_period//2)
>>> _ = expect(mock_time()).result(now + options.login_suspended_period - 1)
>>> _ = expect(mock_time()).result(now + options.login_suspended_period)
>>> _ = expect(mock_time()).result(now + options.login_suspended_period + 1)
>>> mocker.replay()
>>>
>>> users.authenticate('mistyper@isnomore.net', 'secret', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials
>>> users.authenticate('mistyper@isnomore.net', 'secret', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials
>>> users.authenticate('mistyper@isnomore.net', 'secret', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials
>>> users.authenticate('mistyper@isnomore.net', 'secret', conn)
True
>>> mocker.restore()
>>> mocker.verify()


A valid authentication attempt (while the user is not suspended)
clears out previous failed ones:

>>> key = users.register_user('biggles@isnomore.net', 'secret', conn)
>>> users.activate(key, conn)
>>> options.failed_auth_limit
3
>>> users.authenticate('biggles@isnomore.net', 'wrong one', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials
>>> users.authenticate('biggles@isnomore.net', 'still wrong', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials


Here, another incorrect attempt will suspend the user. However, a
valid one will reset the count:

>>> users.authenticate('biggles@isnomore.net', 'secret', conn)
True


The following error now counts as the first one, and doesn't lock the
user out:

>>> users.authenticate('biggles@isnomore.net', 'wrong one', conn)
Traceback (most recent call last):
  ...
AuthenticationError: invalid authentication credentials
>>> users.authenticate('biggles@isnomore.net', 'secret', conn)
True


Some resources are only available to certain groups of users. These
groups are represented as "roles". Each user can be assigned a
role:

>>> key = users.register_user('brian@isnomore.net', 'secret', conn)
>>> users.activate(key, conn)
>>> users.authenticate('brian@isnomore.net', 'secret', conn)
True
>>> conn.get_user_role('brian@isnomore.net') is None
True
>>> conn.set_user_role('brian@isnomore.net', 'naughty boy')
>>> conn.get_user_role('brian@isnomore.net')
u'naughty boy'


Each resource (represented by a function) can be marked as requiring
users with a certain role. Functions are decorated with the
@access_control decorator, which accepts an email and connection
object as first parameters, and then any parameters that the function
might receive. It is assumed that the front-end has already
authenticated the user.

>>> @users.access_control('messiah')
... def bless(people):
...     return True

>>> bless('brian@isnomore.net', conn, 'the meek')
Traceback (most recent call last):
  ...
UnauthorizedAccessError: User does not have the role required by this resource

>>> @users.access_control('naughty boy')
... def look_on_the_bright_side_of_life(when):
...     return '{0} look on the bright side of life'.format(when)

>>> look_on_the_bright_side_of_life('brian@isnomore.net', conn, 'Always')
'Always look on the bright side of life'



Cleaning up:

>>> os.unlink(tmp_db)
>>> if create_tmp:
...     os.rmdir(tmp_dir)

"""
