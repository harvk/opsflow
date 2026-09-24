-- Execute with psql -X -A -t -P pager=off so each result is one line.
-- Output: schema.table|exact_row_count. No user data is printed.
SELECT format(
  'SELECT %L, count(*)::bigint FROM %I.%I;',
  schemaname || '.' || tablename,
  schemaname,
  tablename
)
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename
\gexec
