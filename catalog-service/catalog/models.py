from pydantic import BaseModel, Field, StrictInt, StrictBool, ConfigDict

class Item(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    specs: dict[str, str] = Field(default_factory=dict)
    price: float = Field(ge=0, allow_inf_nan=False)
    stock: int = Field(ge=0)
    certificate_url: str | None = None

class AddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{16,128}$")
    product_id: str = Field(min_length=1, max_length=128)
    qty: StrictInt = Field(gt=0, le=1000000)
    confirmed: StrictBool = False
