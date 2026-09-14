-- =========================================================
-- OPSFLOW POSTGRESQL DATABASE INITIALIZATION
-- =========================================================
--
-- This script is safe to execute repeatedly.
--
-- During first-time PostgreSQL initialization it creates the
-- additional OpsFlow logical databases.
--
-- Docker Compose also executes it through the one-shot
-- provision-databases service so existing volumes receive
-- any databases introduced after initial creation.
-- =========================================================


\set ON_ERROR_STOP on


-- =========================================================
-- CORE BACKEND TEST DATABASE
-- =========================================================

SELECT
    'CREATE DATABASE opsflow_test OWNER '
    || quote_ident(current_user)
WHERE NOT EXISTS (
    SELECT
        1
    FROM
        pg_database
    WHERE
        datname = 'opsflow_test'
)
\gexec

COMMENT ON DATABASE opsflow_test IS
    'Isolated database used by the Core Backend test suite';


-- =========================================================
-- INCIDENT SERVICE APPLICATION DATABASE
-- =========================================================

SELECT
    'CREATE DATABASE opsflow_incidents OWNER '
    || quote_ident(current_user)
WHERE NOT EXISTS (
    SELECT
        1
    FROM
        pg_database
    WHERE
        datname = 'opsflow_incidents'
)
\gexec

COMMENT ON DATABASE opsflow_incidents IS
    'Application database owned by OpsFlow Incident Management';


-- =========================================================
-- INCIDENT SERVICE TEST DATABASE
-- =========================================================

SELECT
    'CREATE DATABASE opsflow_incidents_test OWNER '
    || quote_ident(current_user)
WHERE NOT EXISTS (
    SELECT
        1
    FROM
        pg_database
    WHERE
        datname = 'opsflow_incidents_test'
)
\gexec

COMMENT ON DATABASE opsflow_incidents_test IS
    'Isolated database used by the Incident Service test suite';