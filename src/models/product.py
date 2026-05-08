from pydantic import BaseModel, Field, field_validator
from typing import Optional


class Product(BaseModel):
    name: str
    brand: Optional[str] = ""
    price: Optional[float] = 0.0
    unit: Optional[str] = ""
    category_tag: Optional[str] = ""
    image_url: Optional[str] = ""
    product_url: Optional[str] = ""
    rating: Optional[float] = 0.0
    sold_count: Optional[int] = 0

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v):
        if isinstance(v, str):
            cleaned = "".join(c for c in v if c.isdigit())
            return float(cleaned) if cleaned else 0.0
        return v or 0.0

    @field_validator("rating", mode="before")
    @classmethod
    def parse_rating(cls, v):
        try:
            return float(v or 0)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("sold_count", mode="before")
    @classmethod
    def parse_sold(cls, v):
        try:
            return int(v or 0)
        except (ValueError, TypeError):
            return 0


class ScrapeResult(BaseModel):
    site: str
    category: str
    products: list[Product] = Field(default_factory=list)
    raw: str = ""

    @property
    def product_count(self) -> int:
        return len(self.products)
