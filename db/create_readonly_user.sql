CREATE USER infra_readonly WITH PASSWORD 'infra_readonly_pwd';

GRANT CONNECT ON DATABASE aiops_sentinel TO infra_readonly;
GRANT USAGE ON SCHEMA public TO infra_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO infra_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO infra_readonly;
