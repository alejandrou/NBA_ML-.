from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Pydantic writes `Decimal` as a JSON string by default; the contract publishes
# every `Numeric` column as a JSON number, so OpenAPI shows `number` as well.
ApiDecimal = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
