# service/auth.py
from __future__ import annotations
import hashlib
from dataclasses import dataclass

# 개발용 매우 단순 스텁. 운영 전 교체 필수.
_SALT = "dev-only"

def hash_password(raw: str) -> str:
    return hashlib.sha256((raw + _SALT).encode("utf-8")).hexdigest()

def verify_password(raw: str, hashed: str) -> bool:
    return hash_password(raw) == hashed

@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

def issue_tokens(user_id: int) -> dict:
    return {
        "access_token": f"dev-access-{user_id}",
        "refresh_token": f"dev-refresh-{user_id}",
        "token_type": "bearer",
    }

def get_current_session_id():
    # DI용 헬퍼가 필요하면 구현. 현재 endpoints는 deps.get_current_session_id 사용
    return None
