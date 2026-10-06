from sqlalchemy.orm import Session
from passlib.context import CryptContext

from models import User
from schemas import UserCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_sifre(sifre: str):
    return pwd_context.hash(sifre)


def verify_sifre(duz_sifre, hashli_sifre):
    return pwd_context.verify(duz_sifre, hashli_sifre)


def create_user(db: Session, user: UserCreate):
    yeni_kullanici = User(
        ad=user.ad,
        soyad=user.soyad,
        email=user.email,
        sifre=hash_sifre(user.sifre)
    )

    db.add(yeni_kullanici)
    db.commit()
    db.refresh(yeni_kullanici)

    return yeni_kullanici


def authenticate_user(db: Session, email: str, sifre: str):
    kullanici = db.query(User).filter(User.email == email).first()

    if not kullanici:
        return None

    if not verify_sifre(sifre, kullanici.sifre):
        return None

    return kullanici