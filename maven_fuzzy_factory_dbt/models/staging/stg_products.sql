with source as(
    select * from {{ source('maven_fuzzy_factory', 'products')}}
)

select
    product_id,
    created_at,
    product_name
from source