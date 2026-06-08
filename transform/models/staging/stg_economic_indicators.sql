-- Standardize raw FRED economic indicator data
with source as (
    select * from {{ source('raw', 'economic_indicators') }}
),

renamed as (
    select
        series_id,
        cast(observation_date as date)              as observation_date,
        try_cast(nullif(value::varchar, '.') as double) as value,
        realtime_start,
        realtime_end,
        loaded_at
    from source
    where try_cast(nullif(value::varchar, '.') as double) is not null
)

select * from renamed
