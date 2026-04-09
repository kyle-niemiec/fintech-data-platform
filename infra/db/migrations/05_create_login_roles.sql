-- Creates runtime login users on first DB initialization.
-- Runs automatically via docker-entrypoint-initdb.d after 04_create_roles.sql.
--
-- Credentials are injected via docker-compose environment and read here with \getenv.
-- Idempotent: roles that already exist are skipped.

\getenv kc_user KC_DB_USER
\getenv kc_pass KC_DB_PASSWORD
\getenv observer_user OBSERVER_DB_USER
\getenv observer_pass OBSERVER_DB_PASSWORD
\getenv operator_user OPERATOR_DB_USER
\getenv operator_pass OPERATOR_DB_PASSWORD
\getenv pipeline_user PIPELINE_DB_USER
\getenv pipeline_pass PIPELINE_DB_PASSWORD

CREATE ROLE :"operator_user" LOGIN PASSWORD :'operator_pass';
GRANT control_plane_writer TO :"operator_user";

CREATE ROLE :"observer_user" LOGIN PASSWORD :'observer_pass';
GRANT control_plane_reader TO :"observer_user";

CREATE ROLE :"pipeline_user" LOGIN PASSWORD :'pipeline_pass';
GRANT ingestion_writer TO :"pipeline_user";

-- Create separate Keycloak schema and user
CREATE ROLE :"kc_user" LOGIN PASSWORD :'kc_pass';
CREATE SCHEMA IF NOT EXISTS keycloak AUTHORIZATION :"kc_user";
