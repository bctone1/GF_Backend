# database/base.py
import os

import core.config as config

# 1) Base/metadata 는 models.base 의 것을 재사용
from models.base import Base, metadata  # 여기서 declarative_base() 절대 다시 만들지 말기

# 2) 여기서 모델 모듈 import 해서 Base.metadata 에 테이블들을 올려줌
import models.user.project  # noqa: F401
import models.user.prompt    # noqa: F401
# 필요하면 나중에 models.user.practice, models.partner.* 등도 추가

# 3) DATABASE_URL 구성
database = config.DB
user = config.DB_USER
pw = config.DB_PASSWORD
server = config.DB_SERVER
port = config.DB_PORT
name = config.DB_NAME

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"{database}://{user}:{pw}@{server}:{port}/{name}",
)
