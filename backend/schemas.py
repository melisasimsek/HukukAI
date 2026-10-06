from pydantic import BaseModel

class UserCreate(BaseModel):
    ad: str
    soyad: str
    email: str
    sifre: str


class UserLogin(BaseModel):
    email: str
    sifre: str