from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictBool

class Turn(BaseModel):
    role: Literal["user","assistant"]
    text: str = Field(max_length=8000)
class Message(BaseModel):
    model_config=ConfigDict(extra="forbid")
    session_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{16,128}$")
    text: str = Field(min_length=1,max_length=4000)
    history: list[Turn] = Field(default_factory=list,max_length=40)
class Action(BaseModel):
    model_config=ConfigDict(extra="forbid")
    type: Literal["add_to_cart"] = "add_to_cart"
    product_id: str = Field(min_length=1,max_length=128)
    qty: StrictInt = Field(gt=0,le=1000000)
class Decision(BaseModel):
    model_config=ConfigDict(extra="forbid")
    confirmed: StrictBool
    product_id: str | None
    qty: StrictInt | None
    injection_detected: StrictBool
class SearchArgs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    q:str=Field(min_length=1,max_length=256)
    limit:StrictInt=Field(default=5,ge=1,le=50)
class ProductArgs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    product_id:str=Field(min_length=1,max_length=128)
class AnalogArgs(ProductArgs):
    limit:StrictInt=Field(default=5,ge=1,le=50)
