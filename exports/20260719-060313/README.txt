Dataset export: 20260719-060313

Files:
- products.csv: product master data with canonical name, brand/category, listing count and price range.
- listings.csv: raw/canonical matched listings with source, marketplace, price and store fields.
- price_history.csv: time series price points per listing.
- space_time_observations.csv: product price observations with province/city/store/time fields.
- product_attributes.csv: extracted product attributes.
- sources_status.csv: source manager status, category, queue counts and latest data timestamp.

Source system: Collection-Price local PostgreSQL via Docker.
