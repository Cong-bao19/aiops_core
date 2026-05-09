import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("Chưa tìm thấy DATABASE_URL trong file .env!")

# Khởi tạo Engine
engine = create_engine(DATABASE_URL, echo=False)

# Khởi tạo Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Class gốc cho Models
Base = declarative_base()

# Dependency Injection cho FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()