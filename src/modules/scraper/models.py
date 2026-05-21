from dataclasses import dataclass, asdict


@dataclass
class Product:
    product_name: str = ""
    brand: str = ""
    category: str = ""
    alcohol_percent: str = ""
    volume_ml: str = ""
    price: str = ""
    price_numeric: float = 0.0
    old_price: str = ""
    stock_status: str = ""
    rating: str = ""
    review_count: str = ""
    image_url: str = ""
    product_url: str = ""
    source_site: str = ""
    page_number: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Branch:
    branch_name: str = ""
    branch_url: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    district: str = ""
    city: str = ""
    source_site: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompanyProfile:
    company_name: str = ""
    company_address: str = ""
    company_phone: str = ""
    company_email: str = ""
    company_logo: str = ""
    source_site: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
