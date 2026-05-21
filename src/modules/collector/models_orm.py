from .database import Base
from sqlalchemy import Column, Integer, String, Float, Text

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Float)
    description = Column(Text)
    url = Column(String)
    source = Column(String)
    # Thêm các trường khác nếu cần
