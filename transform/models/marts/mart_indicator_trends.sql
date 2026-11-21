-- Trend features per indicator.
--
-- Lags are by DATE, not by row: "12 rows back" is 12 months for a monthly series but 3 years for
-- GDP (quarterly) and 12 days for T10Y2Y (daily). Each lag takes the latest observation on or
-- before (date - N months), so the same columns mean the same thing for every series.
with base as (
    select * from {{ ref('stg_economic_indicators') }}
),

shifted as (
    select
        *,
        observation_date - interval 1 month  as d_1m,
        observation_date - interval 3 month  as d_3m,
        observation_date - interval 12 month as d_12m
    from base
),

with_lags as (
    select
        s.series_id,
        s.observation_date,
        s.value,
        l1.value  as value_lag_1m,
        l3.value  as value_lag_3m,
        l12.value as value_lag_12m
    from shifted s
    asof left join base l1  on s.series_id = l1.series_id  and s.d_1m  >= l1.observation_date
    asof left join base l3  on s.series_id = l3.series_id  and s.d_3m  >= l3.observation_date
    asof left join base l12 on s.series_id = l12.series_id and s.d_12m >= l12.observation_date
),

rolling as (
    select
        w.series_id,
        w.observation_date,
        avg(b.value) as rolling_12m_avg
    from base w
    join base b
      on b.series_id = w.series_id
     and b.observation_date >  w.observation_date - interval 12 month
     and b.observation_date <= w.observation_date
    group by w.series_id, w.observation_date
)

select
    t.*,
    r.rolling_12m_avg,
    round((t.value - t.value_lag_1m)  / nullif(t.value_lag_1m, 0)  * 100, 4) as mom_pct_change,
    round((t.value - t.value_lag_12m) / nullif(t.value_lag_12m, 0) * 100, 4) as yoy_pct_change
from with_lags t
join rolling r using (series_id, observation_date)
