-- Monthly trends per indicator with lag features for forecasting
with base as (
    select * from {{ ref('stg_economic_indicators') }}
),

with_lags as (
    select
        series_id,
        observation_date,
        value,
        lag(value, 1)  over (partition by series_id order by observation_date) as value_lag_1m,
        lag(value, 3)  over (partition by series_id order by observation_date) as value_lag_3m,
        lag(value, 12) over (partition by series_id order by observation_date) as value_lag_12m,
        avg(value)     over (partition by series_id order by observation_date
                             rows between 11 preceding and current row)        as rolling_12m_avg
    from base
)

select
    *,
    round((value - value_lag_1m) / nullif(value_lag_1m, 0) * 100, 4) as mom_pct_change,
    round((value - value_lag_12m) / nullif(value_lag_12m, 0) * 100, 4) as yoy_pct_change
from with_lags
