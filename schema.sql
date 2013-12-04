CREATE TABLE pending_users (
    email text PRIMARY KEY,
    password text NOT NULL,
    registration_key text KEY UNIQUE,
    registration_date integer,
    confirmation_sent integer DEFAULT 0
);

CREATE TABLE users (
    email text PRIMARY KEY,
    password text NOT NULL,
    failed_login_attempts integer DEFAULT 0,
    suspended_until integer,
    role text
);
