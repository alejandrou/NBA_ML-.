# API reference: errors and pagination

Use explicit 400/404 errors for invalid input or missing resources. Collection
responses expose stable `items`, `page`, `page_size`, and `total` fields.
Bounds must prevent unreasonably large page sizes.
