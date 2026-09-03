-- BhoomiRakshak — Phase 1 exit-criterion verification.
-- Run:  psql "$DATABASE_URL" -f scripts/verify_phase1.sql
-- Every block prints a PASS/FAIL verdict; no block may print FAIL.

\echo '== 1. PostGIS + schema =='
SELECT postgis_lib_version() AS postgis_version;
SELECT count(*) AS tables_created
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

\echo '== 2. Row counts =='
SELECT 'projects' AS table_name, count(*) AS rows, 900 AS expected FROM projects
UNION ALL SELECT 'admin_units', count(*), 768 FROM admin_units
UNION ALL SELECT 'risk_history', count(*), 4500 FROM risk_history
UNION ALL SELECT 'status_log', count(*), 4518 FROM status_log
UNION ALL SELECT 'succession_claims', count(*), 927 FROM succession_claims
UNION ALL SELECT 'succession_risk', count(*), 362 FROM succession_risk
UNION ALL SELECT 'project_dependencies', count(*), 628 FROM project_dependencies
UNION ALL SELECT 'officers', count(*), 41 FROM officers
ORDER BY 1;

\echo '== 3. geom is a real point inside its own district =='
SELECT p.ulpin, p.district, ST_AsText(p.geom) AS geom_wkt,
       ST_Within(p.geom, d.geom) AS inside_own_district
FROM projects p
JOIN district_boundaries d ON d.state = p.state AND d.district = p.district
LIMIT 1;

SELECT CASE WHEN count(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS pins_inside_district,
       count(*) AS offenders
FROM projects p
JOIN district_boundaries d ON d.state = p.state AND d.district = p.district
WHERE NOT ST_Within(p.geom, d.geom);

\echo '== 4. State statistics panel =='
SELECT count(DISTINCT state)                       AS states,
       count(DISTINCT (state, district))           AS districts,
       count(DISTINCT tehsildar)                   AS tehsildars,
       count(DISTINCT (state, district, taluk, village)) AS villages,
       count(DISTINCT ri_circle)                   AS ri_circles,
       sum(no_plots)                               AS plots,
       sum(no_khatiyans)                           AS khatiyans,
       sum(no_tenants)                             AS tenants
FROM admin_units;

SELECT CASE WHEN states = 8 AND districts = 32 AND tehsildars = 128 AND villages = 768
             AND ri_circles = 256 AND plots = 2293187 AND khatiyans = 1612419
             AND tenants = 573899
            THEN 'PASS' ELSE 'FAIL' END AS statistics_match
FROM (
    SELECT count(DISTINCT state) AS states,
           count(DISTINCT (state, district)) AS districts,
           count(DISTINCT tehsildar) AS tehsildars,
           count(DISTINCT (state, district, taluk, village)) AS villages,
           count(DISTINCT ri_circle) AS ri_circles,
           sum(no_plots) AS plots,
           sum(no_khatiyans) AS khatiyans,
           sum(no_tenants) AS tenants
    FROM admin_units
) s;

\echo '== 5. Passwords are bcrypt, no SHA-256 survives =='
SELECT count(*) FILTER (WHERE password_hash LIKE '$2%') AS bcrypt_rows,
       count(*) FILTER (WHERE password_hash ~ '^[0-9a-f]{64}$') AS sha256_rows,
       CASE WHEN count(*) = count(*) FILTER (WHERE password_hash LIKE '$2%')
            THEN 'PASS' ELSE 'FAIL' END AS verdict
FROM officers;

\echo '== 6. issue_resolutions view — cleared dates for a closed project =='
SELECT r.ulpin, r.issue_class, r.cleared_on, r.status, r.days_from_notification
FROM issue_resolutions r
JOIN projects p USING (ulpin)
WHERE p.is_closed_project
  AND r.cleared_on IS NOT NULL
ORDER BY r.ulpin, r.sort_order
LIMIT 6;

SELECT CASE WHEN count(*) > 0 THEN 'PASS' ELSE 'FAIL' END AS view_returns_cleared_dates,
       count(*) AS cleared_rows_for_closed_projects
FROM issue_resolutions r
JOIN projects p USING (ulpin)
WHERE p.is_closed_project AND r.cleared_on IS NOT NULL;

\echo '== 7. Every foreign key has an index =='
-- Scoped to `public`. Supabase ships auth/storage/realtime schemas whose own tables
-- carry unindexed foreign keys; those are not ours and must not fail our check.
SELECT CASE WHEN count(*) FILTER (WHERE NOT indexed) = 0 AND count(*) > 0
            THEN 'PASS' ELSE 'FAIL' END AS every_fk_indexed,
       count(*) FILTER (WHERE NOT indexed) AS unindexed_fks,
       count(*) AS public_fks_total
FROM (
    SELECT EXISTS (
               SELECT 1 FROM pg_index i
               WHERE i.indrelid = c.conrelid
                 AND (i.indkey::int2[])[0:array_length(c.conkey, 1) - 1] = c.conkey
           ) AS indexed
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE c.contype = 'f' AND n.nspname = 'public'
) fks;

\echo '== 8. Geometry columns have a GiST index =='
SELECT CASE WHEN count(*) = 3 THEN 'PASS' ELSE 'FAIL' END AS gist_indexes_present,
       count(*) AS gist_index_count
FROM pg_index i
JOIN pg_class c ON c.oid = i.indexrelid
JOIN pg_am am ON am.oid = c.relam
WHERE am.amname = 'gist';
