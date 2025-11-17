# core/security.py
import hashlib
import secrets
import os
import json
import hmac
import base64

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


# ============================
# 서명 토큰 (이메일 인증용 등)
# ============================

# 이메일 인증/기타 서명용 시크릿 키
# 실제 환경에서는 EMAIL_TOKEN_SECRET 또는 SECRET_KEY 를 .env 에 꼭 설정해줘야 함
_EMAIL_TOKEN_SECRET = os.getenv("EMAIL_TOKEN_SECRET") or os.getenv("SECRET_KEY") or "change-me-in-prod"


def _b64url_encode(raw: bytes) -> str:
    """
    RFC 7515 스타일 base64url 인코딩 (padding 제거).
    """
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """
    base64url 디코딩. 패딩 자동 보정.
    """
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def sign_payload(data: dict) -> str:
    """
    dict -> JSON 직렬화 -> HMAC-SHA256 서명 -> base64url(payload).base64url(signature)

    - data 는 JSON 직렬화 가능한 dict 여야 함
    - exp(만료)는 여기서 체크하지 않고, 호출하는 쪽에서 data["exp"]를 보고 판단
    """
    if not isinstance(data, dict):
        raise TypeError("payload must be a dict")

    # JSON 직렬화 (정렬+압축해서 서명 입력 고정)
    payload_json = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")

    # HMAC-SHA256 서명
    secret = _EMAIL_TOKEN_SECRET.encode("utf-8")
    signature = hmac.new(secret, payload_json, hashlib.sha256).digest()

    # 토큰: base64url(payload).base64url(signature)
    token = f"{_b64url_encode(payload_json)}.{_b64url_encode(signature)}"
    return token


def verify_signed_payload(token: str) -> dict:
    """
    sign_payload 로 생성한 토큰을 검증하고, payload dict 를 반환.

    - 형식: base64url(payload).base64url(signature)
    - 서명 불일치/형식 오류 시 ValueError 발생
    """
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        raise ValueError("invalid token format")

    try:
        payload_json = _b64url_decode(payload_b64)
        signature = _b64url_decode(sig_b64)
    except Exception:
        raise ValueError("invalid base64 encoding")

    # 서명 재계산
    secret = _EMAIL_TOKEN_SECRET.encode("utf-8")
    expected_sig = hmac.new(secret, payload_json, hashlib.sha256).digest()

    # 서명 비교 (타이밍 공격 방지용 compare_digest)
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("invalid token signature")

    # payload 복원
    try:
        data = json.loads(payload_json.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("invalid payload json")

    if not isinstance(data, dict):
        raise ValueError("invalid payload type")

    return data
