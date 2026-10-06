from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "postgresql+psycopg2://postgres:Melisa5@127.0.0.1:5432/hukukai_db"

engine = create_engine(DATABASE_URL)

# Veritabanı bağlantısını test et
try:
    with engine.connect() as conn:
        print("✅ VERİTABANI BAĞLANDI")
        print(conn.execute(text("SELECT version()")).fetchone())
except Exception as e:
    print("❌ VERİTABANI HATASI:")
    print(e)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()