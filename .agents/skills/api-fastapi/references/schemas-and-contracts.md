# API reference: schemas and contracts

Keep ORM entities separate from Pydantic response schemas. Declare public fields, `snake_case` names, and nullability explicitly; do not expose internal columns, credentials, SQL, paths, or `__dict__`. Every endpoint declares a response model, allowing FastAPI to filter responses to the approved contract.

Use explicit service mapping for complex responses. `ConfigDict(from_attributes=True)` is suitable only for simple, fully loaded entities. Never trigger lazy loads while serializing or access relationships after the Session closes; select required relationships deliberately.

Health has a small explicit contract:

```python
class HealthResponse(BaseModel):
    status: Literal["ok"]
```

Collection contracts conceptually contain `items`, `page`, `page_size`, and `total`. A generic Pydantic implementation is optional when it would complicate the implementation.
