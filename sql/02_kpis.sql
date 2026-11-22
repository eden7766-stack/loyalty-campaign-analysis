-- =====================================================================
-- 02_kpis.sql  |  The three SMART KPIs (targets derived from history)
-- =====================================================================

-- KPI 1 - Enrollment: joiners Feb-Apr 2018 vs target = Feb-Apr 2017 * 1.25
WITH feb_apr AS (
    SELECT enroll_year, COUNT(*) AS joiners
    FROM members
    WHERE enroll_month BETWEEN 2 AND 4 AND enroll_year IN (2017, 2018)
    GROUP BY enroll_year
)
SELECT
    'KPI 1 - Enrollment'                                   AS kpi,
    MAX(joiners) FILTER (WHERE enroll_year = 2018)         AS actual,
    ROUND(MAX(joiners) FILTER (WHERE enroll_year = 2017) * 1.25) AS target_min,
    actual >= target_min                                   AS met
FROM feb_apr;

-- KPI 2 - Retention: cumulative % cancelled within N months of joining,
-- campaign cohort vs standard Feb-Apr 2017 cohort (the ceiling)
WITH cohorts AS (
    SELECT
        CASE WHEN is_promo THEN 'Campaign 2018' ELSE 'Standard Feb-Apr 2017' END AS cohort,
        cancel_idx - enroll_idx AS months_to_cancel
    FROM members
    WHERE is_promo
       OR (NOT is_promo AND enroll_year = 2017 AND enroll_month BETWEEN 2 AND 4)
),
horizon AS (SELECT range AS m FROM range(0, 11))
SELECT
    c.cohort,
    h.m AS months_since_joining,
    ROUND(100.0 * COUNT(*) FILTER (WHERE c.months_to_cancel <= h.m) / COUNT(*), 1) AS cum_cancel_pct
FROM cohorts c CROSS JOIN horizon h
GROUP BY ALL
ORDER BY c.cohort, h.m;

-- KPI 3 - Activity: flights per active member per month, Jun-Aug, 2018 vs 2017 * 1.10
WITH summer AS (
    SELECT yr, SUM(flights) * 1.0 / COUNT(*) AS flights_per_member
    FROM active_months
    WHERE mon BETWEEN 6 AND 8
    GROUP BY yr
)
SELECT
    'KPI 3 - Activity'                                                    AS kpi,
    ROUND(MAX(flights_per_member) FILTER (WHERE yr = 2018), 2)            AS actual,
    ROUND(MAX(flights_per_member) FILTER (WHERE yr = 2017) * 1.10, 2)     AS target_min,
    actual >= target_min                                                  AS met
FROM summer;
