with source as(
    select * from {{ source('maven_fuzzy_factory', 'website_sessions')}}
)

select 
    website_session_id,
    created_at,
    user_id,
    case when is_repeat_session = 1 then true else false end as is_repeat_session,
    utm_source,
    utm_campaign,
    utm_content,
    device_type,
    http_referer
from source