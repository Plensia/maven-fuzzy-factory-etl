with source as(
    select * from {{ source('maven_fuzzy_factory', 'order_items')}}
)

select
    order_item_id,
    created_at,
    order_id,
    product_id,
    case when is_primary_item = 1 then true else false end as is_primary_item,
    price_usd,
    cogs_usd
from source