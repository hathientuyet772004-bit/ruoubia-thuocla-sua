from database import Base, engine
from models_orm import Product

# Tạo các bảng trong database
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")
