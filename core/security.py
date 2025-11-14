# core/security.py
import hashlib
import secrets

# ============================
# 비밀번호 해시
# ============================

def hash_password(password: str) -> str:
    """단순 SHA256 해시 (MVP용). 실제 서비스는 bcrypt 권장"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# ============================
# 토큰 발급 (MVP)
# ============================
class TokenBundle:
    def __init__(self, access_token: str, refresh_token: str = "", token_type: str = "bearer"):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type


def issue_tokens(user_id: int) -> TokenBundle:
    """
    MVP 단계: access_token = dev-access-<user_id>
    refresh_token = dev-refresh-<random>
    """
    access = f"dev-access-{user_id}"
    refresh = "dev-refresh-" + secrets.token_hex(8)
    return TokenBundle(access_token=access, refresh_token=refresh)
