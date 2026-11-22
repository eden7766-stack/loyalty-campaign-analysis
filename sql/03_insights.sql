-- =====================================================================
-- 03_insights.sql  |  Deep-dive questions behind the recommendations
-- =====================================================================

-- Q1. How much of 2018 growth came from the campaign?
WITH joined_2018 AS (SELECT COUNT(*) AS n FROM members WHERE enroll_year = 2018),
     cancelled_2018 AS (SELECT COUNT(*) AS n FROM members WHERE cancel_year = 2018),
     promo_still_active AS (SELECT COUNT(*) AS n FROM members WHERE is_promo AND cancel_idx IS NULL)
SELECT
    ROUND(100.0 * (SELECT COUNT(*) FROM members WHERE is_promo) / j.n)  AS pct_of_2018_joiners,
    ROUND(100.0 * p.n / (j.n - c.n))                                   AS pct_of_net_growth,
    j.n - c.n                                                          AS net_growth_2018
FROM joined_2018 j, cancelled_2018 c, promo_still_active p;

-- Q2. Do campaign members keep flying after the bonus season? (Sep-Dec 2018)
SELECT
    CASE WHEN is_promo THEN 'Campaign' ELSE 'Standard' END AS segment,
    ROUND(SUM(flights) * 1.0 / COUNT(*), 2)                AS flights_per_active_member
FROM active_months
WHERE yr = 2018 AND mon BETWEEN 9 AND 12
GROUP BY ALL;

-- Q3. Which campaign members stop flying - and do they churn?
WITH sep_dec AS (
    SELECT member_id, SUM(flights) AS flights
    FROM flights
    WHERE yr = 2018 AND mon BETWEEN 9 AND 12
    GROUP BY member_id
),
grouped AS (
    SELECT
        m.member_id,
        m.cancel_idx IS NOT NULL AS cancelled,
        CASE WHEN COALESCE(s.flights, 0) = 0 THEN 'Stopped (0 flights)'
             WHEN s.flights < 5             THEN 'Low (1-4)'
             ELSE 'Continued (5+)' END      AS behaviour
    FROM members m
    LEFT JOIN sep_dec s USING (member_id)
    WHERE m.is_promo
)
SELECT
    behaviour,
    COUNT(*)                                                   AS members,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)         AS share_pct,
    ROUND(100.0 * AVG(cancelled::INT), 1)                      AS churn_pct
FROM grouped
GROUP BY behaviour
ORDER BY members DESC;

-- Q4. Who responded to the campaign? Adoption index by salary band (1.0 = average)
WITH banded AS (
    SELECT
        is_promo,
        CASE WHEN salary <= 50000  THEN '1. Under 50K'
             WHEN salary <= 75000  THEN '2. 50K-75K'
             WHEN salary <= 100000 THEN '3. 75K-100K'
             ELSE '4. 100K+' END AS salary_band
    FROM members
    WHERE salary IS NOT NULL
),
totals AS (
    SELECT (SELECT COUNT(*) FROM members WHERE is_promo) AS promo_total,
           (SELECT COUNT(*) FROM members)                AS all_total
)
SELECT
    salary_band,
    COUNT(*)                         AS members,
    SUM(is_promo::INT)               AS promo_joiners,
    ROUND((SUM(is_promo::INT) * 1.0 / t.promo_total) / (COUNT(*) * 1.0 / t.all_total), 2) AS adoption_index
FROM banded, totals t
GROUP BY salary_band, t.promo_total, t.all_total
ORDER BY salary_band;
