# Metaweave

## Databricks Lakebase

The production database baseline uses Databricks Lakebase. Databricks Apps
supplies `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGSSLMODE` for its
primary `database` resource. [`app.yaml`](app.yaml) maps that resource to
`LAKEBASE_ENDPOINT`.

No Lakebase host, user, password, or token belongs in YAML. For every newly
opened asyncpg physical connection, the application uses its Databricks App
service principal and `WorkspaceClient().postgres.generate_database_credential`
to obtain a short-lived database token. Existing pooled connections are reused.

Local development remains SQLite through the ignored `server/config/config.dev.yaml`
overlay.
