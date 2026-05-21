from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime
from modules.collector.backend.db.database import Base

class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    normalized_url = Column(String, index=True)
    original_url = Column(String)
    user_id = Column(String)
    visited_at = Column(DateTime, default=datetime.utcnow)
    load_time_ms = Column(Integer, nullable=True)
    page_type = Column(String)
    month_key = Column(String, index=True) # e.g., "2024-03" for easy month filtering

class SavedPage(Base):
    __tablename__ = "saved_pages"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True)
    url = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    tags = Column(JSON, default=[])
    page_type = Column(String)
    metadata_json = Column(JSON) # Store full meta

class Source(Base):
    __tablename__ = "sources"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    url = Column(String, unique=True, index=True)
    type = Column(String) # Loại hình (E-commerce, Brand, etc)
    category = Column(String) # Danh mục chính (Rượu bia, Thuốc lá, Sữa)
    note = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
