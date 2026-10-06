from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, nullable=False)
    soyad = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    sifre = Column(String, nullable=False)