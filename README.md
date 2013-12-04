auth
====

A simple authentication/authorisation module for a hypothetical
system. This was written a few years ago (2010), on request, and
hasn't really been revised since. Still, here it is :)

This README contains documentation of the process and design decisions adopted
while developing the package.


Structure
----------

This package contains:

- users.py: the main module, with the user-related code.
- db.py: database-related code.
- schema.sql: the database schema on which these modules work.
- mailer.py: script to send registration confirmation messages.
- clear\_pending\_users.py: script to delete pending users whose registration
                          has expired.
- exceptions.py: custom exceptions for this package.
- config.py: configuration module, exporting the "options" object.
- README.txt: this file.
- reg_confirmation.template: registration confirmation template.
- tests
    - unit_tests.py: unit tests
    - integration\_tests.py: integration tests, using sqlite3


Workflow summary
------------------

When a user registers on the website, the front-end code should call
users.register_user, passing the new user's email address and chosen
password. These are saved on the database, along with a generated
registration key. Then mailer.py, which should be run independently,
periodically, picks up all pending user registration and sends them a
message with a link containing the registration key. If the user clicks on
it, the front-end code should pass this key to users.activate function. If
it hasn't taken the user too long to click on the link, this function
creates a new, active user on the system (and removes the corresponding
pending one).

When one active user on the system wants to log in, they provide their email
address and password. The front-end code then passes them to
users.authenticate. If the wrong password is given to this function too many
times, the user is suspended for a period of time, during which all attempts
will fail as if the wrong credentials had been given. Once this period is
over, the user starts with a clean slate, and can authenticate again.

Some back-end functions can be limited to allow access only to users with a
certain role. These function should be decorated with
@access\_control(name\_of\_the role). The front-end code should call the
desired function, giving the user's email address as well as the function's
regular parameters. The code will raise an exception if access to that
function is requested for a user with an inappropriate role.

All of these functions should be called by the front-end with a connection
object. This is to avoid having to create a new connection for each of these
tasks. If necessary, a decorator could be created (and even applied
automatically to all the desired function on the users module) so that a
global connection object is used, or a new connection is created on each
function call.


Running the tests and the code
-------------------------------

This package was developed and tested using Python 2.6.5, on Ubuntu
10.4. The tests have also been run on a Mac OS X 10 with Python 2.7

The tests created during the development of this module were run using
"nosetests" (actually, nosetests was run automatically by "tdaemon"),
although they should probably run fine with unittest's default runner. All
the code was written using TDD, with unit and/or integration tests being
chosen as suitable. Integration tests were written using the doctest module,
and attempt to tell a story (or several stories) of users' life cycles.

I have also used Gustavo Niemeyer's Mocker library extensively. Mocker is
available at http://niemeyer.net/mocker (and at PyPI). Mocker does have its
limitations; for instance, it can be too verbose at times, several actions
return a mocker object (making it clumsy to use in doctests), and reusing a
Mocker object during a long doctest can be painful. However, it has several
advantages. Amongst others, it's very flexible on how to specify expected
actions and reactions on mock objects, it integrates well with the unittest
module, and it lets the user proxy and even replace the real objects as
needed. I have used release 1.0.



Design and implementation discussions
--------------------------------------


### Registering a new user

users.register_user's signature allows it to be called with no parameters
(setting them to None). This is so that we can raise more appropriate
exceptions (InvalidEmailError and InvalidPasswordError), which could also be
used for more in-depth checks, like password strength and email address
validity.

Regarding email address validation, its correct, strict implementation
(according to the relevant RFCs) is notoriously complex, and I think that,
whenever possible, an external, centralised resource should be used, instead
of a homegrown validator. For instance, if Django is available, we could
validate an email address with "django.core.validators.validate_email".

I have included a very crude validator in the current module, for
completeness. On the code as it is, this custom validate\_email function
would perhaps work better returning True or False (and called something like
"email\_is\_valid"), but I kept it the way it is (raising an exception) to
conform with Django's validate_email, as per this discussion. Incidentally,
for the time being the code also doesn't bother normalising all email to
lowercase (which would be essential on a real-world application).

Also related, I haven't implemented any password policies (length, strength
etc). Should this be desirable, it should resemble users.validate_email, in
that it should follow the verification that the password is not None, and
follow the same API (that is, raise InvalidPasswordError).


### Registration confirmation emails

The confirmation email to the recently-registered user is not sent by the
register_user function itself, but by a separate script that should be run
periodically (say, using a service such as Unix's cron). This is so that
slow or faulty SMTP servers don't interfere with the user's interface. Once
the registration data are written to the database, the user can be informed
that they will soon receive the confirmation email.

The implementation of the mailer module/script relies on the config
module. On an uncontrolled environment, it would make sense to hardcode
sensible default values on the mailer itself (such as "localhost" as SMTP
server, webmaster@local_domain as the message's "From" field etc).

Also, the base URL for the registration confirmation, currently embedded in
the message template, could be a configuration option as well.

One implementation detail on mailer.py: as it stands, a new connection to
the SMTP server is created (and closed) for every message sent. This is
obviously sub-optimal, and only one connection should be opened for the
whole batch. I've kept it this way simply to make the code more clear and
more easily testable.

Also, the mailer.py script could easily guard against concurrency problems
using a simple lock (say, a file on /var/run). However, if the number of
emails to send gets too big, it might be useful (or inescapable) to use a
distributed solution. Concurrency, in this case, could be dealt with by
setting a field on the database itself, marking the rows that each instance
was about to act on.


###  On testing random numbers and hashes

Since the registration_key function uses (the decimal portion of)
random.random(), we can't test for its return value directly. Instead, we
test for properties (i.e., return values vary) and keep the implementation
simple, so it's not completely a black box. We hash using SHA-256, which
should be more than enough for most applications (assuming random.random()
has enough precision, and Python implements it using C's double on most
platforms).

Also, we rely on it being statistically very unlikely that two identical
keys are generated for different users. It would be trivial to implement an
explicit verification, similar to checking that the user being registered is
not already on the pending_users table (with care to make it thread-safe, if
the application requires it). However, I feel that it will only add
complexity to the code at this point, so we simply raise the DB driver's
IntegrityError if such a collision occurs.

By the way, when a new user registration is requested, the code checks that
no such user already exists. In particular, if there is an entry for that
email on the pending\_users table, but whose registration date was over
"options.registration\_expiration" seconds ago, we assume that the old entry
simply hasn't been cleaned up yet. We then remove it and register the user
again. However, if the existing pending_users entry is recent, we raise an
exception. A reasonable alternative, involving the front-end, would be to
signal the user that a pending registration for that email already exists,
and ask them if they want a new registration key generated. If so, the code
proceeds as if the old registration had expired. It should be noted that
this also implies potentially changing the user's initially-chosen password.

Password hashing (for storing on the database) uses SHA-256 as well. This is
likely a bit of overkill, and SHA-1 or even MD5 would do fine for most
real-world applications (with shorter hash sizes, meaning less storage
needed). However, for the purposes of this implementation SHA-256 is
suitable, and is already being used for the registration key. The hash also
uses a salt (currently of 2 alphanumeric characters), to prevent
rainbow-table attacks.

Incidentally, password hashing and registration key generation are basically
the same function (as they are currently implemented): the SHA-256 digest of
the juxtaposition of a supplied string and a random salt. The code could
easily be adapted to use only one generic function instead of two
specialised ones. However, this would fulfil no useful purpose, and, as the
code stands, the implementation details of either function can be reasonably
changed.


### Activating a pending user

Activating (or re-registering) an already active user will raise an
exception. A commonly implemented alternative is to do nothing (that is,
silently fail). While this can be simple transparent to the user, I feel
that the decision of what to inform the user should be made closer to the
front-end. The user-interface code can decide between a more paranoid
behaviour (that is, assuming re-activation is indeed and error, and pointing
this to the user), and a more transparent one (carry on as though nothing
has happened, as the user is already active).

An implementation detail: as it is, the code will activate a user with the
correct key, even if the confirmation email hasn't been sent. This assumes a
policy leaning towards user convenience ("perhaps the script failed and
didn't update the database, or the link was given manually to the user by a
member of the staff"), rather than a more paranoid one ("the user couldn't
have this key if it hasn't been emailed yet, this must be an attack"). If
either policy must be strictly enforced, the proper tests for each case
should be written, and the code implemented (which is trivial, a "where"
condition on the appropriate db query).


### User authentication

When the user provides incorrect authentication details too many times, they
are locked out of the system for a pre-determined time. During this period,
the user is considered to be suspended, and all authentication requests will
fail. I have chosen to follow the Unix method and deny access raising the
same exception as the one used when the user provides incorrect
credentials. It would also be reasonable to raise a different exception in
this situation, so that the user can be notified by the front-end that their
account has been suspended. On the other hand, as it's currently implemented
the system provides fewer clues to possible attackers (which is what this
sort of account suspension tries to deter).

During the suspension period, failed attempts are still recorded, but the
user is not further penalised by them (that is, the suspension time isn't
prolonged by failed authentication in the meantime).

A correct authentication resets the failed attempt count.

One user-friendly option would be to only suspend the user if the previous
failed login was recent (for some definition of "recent"). This would lessen
inconvenience to the occasional user, and wouldn't leave the system more
vulnerable to attack.

The current implementation stores failed attempts on the database. However,
this can be very costly, especially if the failed attempts are the result of
an attack. A more robust, real-world solution would be to keep record of
failed attempts on an in-memory cache (like memcached) at the web
server. This would repel frequent attempts for the same user without
overloading the database.


### Authorisation, or access control

Authorisation is implemented as the @access\_control decorator from the users
module. Each user can be assigned a role (using
db.Connection.set\_user\_role). Each resource whose access needs
authorisation is represented by a function, that needs to be decorated with
@access_control('name of a role'). Only users with that role will be able to
access it (access by others will raise UnauthorizedAccessError). This design
assumes that the front-end has already authenticated the user, and will
always pass the user's email address and a valid database connection as the
first arguments to the decorated function. All other function arguments
(positional or keyword) should follow, as they would on the original
function.

I believe this is a nice, simple way of granting access to selected
resources. Moreover, it can be trivially expanded by allowing the decorator
to receive a list of roles, and/or by creating a separate table relating
users and several roles.


### Python DB API v2.0 conformance

The tests at TestExceptionDBAPIConformance are not meant to be
exhaustive. They are simply there to ensure that certain exceptions we
define on our module are valid Python DB API v2.0.

users.register_user raises ProgrammingError when no database connection
object is passed. The specific exception was chosen to conform with Python's
DB API v2.0 (and its token implementation on the stdlib sqlite3 module).


### Database connections

The db module encapsulates connections and operations on a database. Its
main class is db.Connection. It receives a "driver", which must be a DB API
v2.0 compatible Python module. Additionally, it may receive any number of
connection parameters, including keyword arguments, which are passed
directly to the driver. It's the calling code's responsibility to pass valid
(and all the necessary) parameters for the chosen driver, since the DB API
does not specify a standard for connection parameters. The current
implementation uses a single db.Connection class, which keeps hold of the
driver and makes standard DB API calls on it. An alternative approach would
have a separate subclass of a generic parent class for each specific
supported driver, and db.Connection would return the appropriate object
depending on the chosen driver.

One related, "thorny" issue is query parameter style. The DB API requires
the driver to declare its style using the "paramstyle" attribute. However,
different parameter styles integrate differently with their parameters
(i.e., positional versus named), and there's no fool-proof way to
automatically convert from one style to another. I have implemented the
skeleton of a general-purpose converter from qmark to different
paramstyles. Currently it translates only to numeric and named, as a proof
of concept. It goes together with a parameter-list converter. However, once
again, the only fool-proof way of converting would be to manually inspect
all queries, and list them, or to subclass db.Connection specifically for
each desired driver.

When an InternalError is raised by an invalid cursor (as defined by the DB
API), the db module will attempt to recover and get a new cursor, once. If
it raises again, the exception will be raised to the calling code. A more
complex, but possibly more robust or desirable solution, would be to attempt
reconnecting to the database, or to wait for a short period before
requesting a new cursor, up until a pre-determined number of failed
attempts. This might be useful when the code is being run somewhere out of
control (for instance, a customer's site), or when a lot of cursor failures
are expected (which should warn of more serious trouble).

The same reasoning applies to an error originating from the connection
itself (not the cursor). The code currently raises the exception to the
calling code, but all the previous discussion applies.

An (orthogonal) alternative to the current implementation would be not to
raise an exception, but to return a token value (such as None). However, I
generally prefer the approach of raising exceptions instead of having the
calling code always check return values (subject to the team's coding
practises, of course). The Python implementation of try/except is fast, and
I also think it's more coherent ("better ask for forgiveness than for
permission"). This also applies to other parts of this package. For
instance, user authentication raises an exception when the email/password
combination provided are invalid.


### Configuration

Configuration options (such as registration timeout, email template file
etc) are set at config.py. For what is likely such a simple set of options,
a Unix- or INI-style configuration file would certainly suffice. However, I
have decided to use a Python module, simply to illustrate that this can be a
powerful choice. For instance, some configuration options, such as database
credentials, could be fetched from another database, or derived from system
parameters, on the fly.

To keep interfaces familiar and interchangeable, the config.options object
is similar to that returned by the optparse module (and its recent
replacement, argparse). That is, an object whose configuration options are
attributes.


### Other minor considerations

Dates are represented as integers meaning "Unix Epoch Time", on the
database, so that it works across different database implementations (most
notably, sqlite, which doesn't have a date format).

mailer.py and clear\_pending\_users.py don't implement much error checking and
recovery, which would be needed in a production environment.

One flagrant omission in this program is logging. A proper, real-world
implementation should log most actions, and certainly all exceptions. I find
that Python's built-in logging module is usually very appropriate for most
purposes. However, I felt that it only added clutter to the code, without
adding to the purposes of this implementation, so I opted to leave it out
for this time.
