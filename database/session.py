# database/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core import config
import psycopg2
import os

# -----------------------------------------------------------------------------------
# 1) DB URL 설정
#    - 우선순위:
#      1) 환경변수 DATABASE_URL
#      2) core.config.VECTOR_DB_CONNECTION
#      3) DB, DB_USER, DB_PASSWORD, DB_SERVER, DB_PORT, DB_NAME 조합
# -----------------------------------------------------------------------------------
env_db_url = os.getenv("DATABASE_URL")

if env_db_url:
    DATABASE_URL = env_db_url
elif config.VECTOR_DB_CONNECTION:
    # 예: "postgresql://user:pw@host:5432/db"
    DATABASE_URL = config.VECTOR_DB_CONNECTION
else:
    # 개별 설정값이 다 있는 경우에만 직접 조립
    if all([config.DB_USER, config.DB_PASSWORD, config.DB_SERVER, config.DB_NAME]):
        # DB 기본값은 "postgresql" 이라서 아래처럼 사용 가능
        # (psycopg2 도 "postgresql://..." URI 지원)
        DATABASE_URL = (
            f"{config.DB}://"
            f"{config.DB_USER}:{config.DB_PASSWORD}"
            f"@{config.DB_SERVER}:{config.DB_PORT}/{config.DB_NAME}"
        )
    else:
        DATABASE_URL = None

if not DATABASE_URL:
    raise RuntimeError(
        "DB 접속 정보가 없습니다. "
        "환경변수 DATABASE_URL 또는 .env 의 DB_USER/DB_PASSWORD/DB_SERVER/DB_NAME 을 확인해줘."
    )

# -----------------------------------------------------------------------------------
# 2) SQLAlchemy Engine / SessionLocal
# -----------------------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    echo=True,        # 기존처럼 SQL 로그 보고 싶으면 True 유지
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# FastAPI Depends(get_db) 에서 쓸 세션 팩토리
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------------------------------
# 3) psycopg2 raw connection
#    - DATABASE_URL 을 그대로 사용 (postgresql://user:pw@host:port/db 형태)
# -----------------------------------------------------------------------------------
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)
