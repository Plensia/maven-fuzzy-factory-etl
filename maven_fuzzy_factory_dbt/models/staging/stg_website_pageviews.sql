with source as(
    select * from {{ source('maven_fuzzy_factory', 'website_pageviews')}}
)

select
    website_pageviews_id,
    created_at,
    website_session_id,
    pageview_url
from source