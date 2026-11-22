-- =====================================================================
-- 01_cleaning.sql  |  Build clean tables from the raw CSVs (DuckDB SQL)
-- =====================================================================

-- Raw files
CREATE OR REPLACE TABLE raw_members AS
SELECT * FROM read_csv_auto('data/Customer_Loyalty_History.csv', header = true);

CREATE OR REPLACE TABLE raw_flights AS
SELECT * FROM read_csv_auto('data/Customer_Flight_Activity.csv', header = true);

-- Data-quality checks (run before cleaning)
SELECT 'exact duplicate activity rows' AS check_name,
       COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM raw_flights)) AS n
FROM raw_flights
UNION ALL
SELECT 'negative salaries', COUNT(*) FROM raw_members WHERE "Salary" < 0
UNION ALL
SELECT 'missing salaries', COUNT(*) FROM raw_members WHERE "Salary" IS NULL
UNION ALL
SELECT 'members with no cancellation (= active)', COUNT(*) FROM raw_members WHERE "Cancellation Year" IS NULL;

-- Clean members: absolute salary (sign typo), month index for date math, campaign flag.
-- Missing salary stays NULL: it is systematic (all 'College'), so a mean would bias it.
CREATE OR REPLACE TABLE members AS
SELECT
    "Loyalty Number"                                   AS member_id,
    "Province"                                         AS province,
    "Gender"                                           AS gender,
    "Education"                                        AS education,
    ABS("Salary")                                      AS salary,
    "Loyalty Card"                                     AS card,
    "Enrollment Year"                                  AS enroll_year,
    "Enrollment Month"                                 AS enroll_month,
    "Cancellation Year"                                AS cancel_year,
    "Enrollment Year" * 12 + "Enrollment Month" - 1    AS enroll_idx,
    "Cancellation Year" * 12 + "Cancellation Month" - 1 AS cancel_idx,
    "Enrollment Type" = '2018 Promotion'               AS is_promo
FROM raw_members;

-- Clean activity: drop exact duplicates, then collapse several rows per member-month into one
CREATE OR REPLACE TABLE flights AS
WITH dedup AS (SELECT DISTINCT * FROM raw_flights)
SELECT
    "Loyalty Number"            AS member_id,
    "Year"                      AS yr,
    "Month"                     AS mon,
    "Year" * 12 + "Month" - 1   AS month_idx,
    SUM("Total Flights")        AS flights,
    SUM("Distance")             AS distance,
    SUM("Points Accumulated")   AS points
FROM dedup
GROUP BY ALL;

-- Member-month rows where the member was ACTIVE: enrolled by that month and not cancelled before it
CREATE OR REPLACE TABLE active_months AS
SELECT f.*, m.is_promo
FROM flights f
JOIN members m USING (member_id)
WHERE f.month_idx >= m.enroll_idx
  AND (m.cancel_idx IS NULL OR f.month_idx <= m.cancel_idx);
