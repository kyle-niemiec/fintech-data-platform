-- Creates runtime login users on first DB initialization.
-- Runs automatically via docker-entrypoint-initdb.d after 04_create_roles.sql.
--
-- Credentials are injected via docker-compose environment and read here with \getenv.
-- Idempotent: roles that already exist are skipped.

\getenv operator_user OPERATOR_DB_USER
\getenv operator_pass OPERATOR_DB_PASSWORD
\getenv observer_user OBSERVER_DB_USER
\getenv observer_pass OBSERVER_DB_PASSWORD

CREATE ROLE :"operator_user" LOGIN PASSWORD :'operator_pass';
GRANT control_plane_writer TO :"operator_user";

CREATE ROLE :"observer_user" LOGIN PASSWORD :'observer_pass';
GRANT control_plane_reader TO :"observer_user";
