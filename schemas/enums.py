# schemas/enums.py
from enum import Enum

# -----------------------------
# 공통/조직/사용자
# -----------------------------
class Status(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    draft = "draft"
    archived = "archived"

class UserStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    invited = "invited"
    deleted = "deleted"

class OrgStatus(str, Enum):
    active = "active"
    trial = "trial"
    inactive = "inactive"
    suspended = "suspended"

# -----------------------------
# 파트너 도메인: 과정/분반/수강/학생
# -----------------------------
class CourseStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"

class ClassStatus(str, Enum):
    planned = "planned"
    ongoing = "ongoing"
    ended = "ended"

class EnrollmentStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    completed = "completed"
    dropped = "dropped"

class StudentStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"

# -----------------------------
# 알림/보안
# -----------------------------
class EmailSubscriptionType(str, Enum):
    weekly_digest = "weekly_digest"
    alerts = "alerts"
    marketing = "marketing"

class MfaMethod(str, Enum):
    totp = "totp"
    sms = "sms"
    email = "email"

# -----------------------------
# 결제/정산
# -----------------------------
class AccountDeletionStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    rejected = "rejected"

class TransactionStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"
    canceled = "canceled"

# 모델과 일치: draft|issued|paid|overdue|void
class InvoiceStatus(str, Enum):
    draft = "draft"
    issued = "issued"
    paid = "paid"
    overdue = "overdue"
    void = "void"

# 모델과 일치: pending|processing|paid|failed|canceled
class PayoutStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    paid = "paid"
    failed = "failed"
    canceled = "canceled"

class Currency(str, Enum):
    KRW = "KRW"
    USD = "USD"
    JPY = "JPY"
    EUR = "EUR"

# -----------------------------
# AI/모델 카탈로그/프로바이더
# -----------------------------
class Modality(str, Enum):
    chat = "chat"
    embedding = "embedding"
    stt = "stt"
    image = "image"
    tts = "tts"
    rerank = "rerank"

class ProductType(str, Enum):
    llm = "llm"
    embedding = "embedding"
    stt = "stt"

class ProviderName(str, Enum):
    openai = "openai"
    anthropic = "anthropic"
    google = "google"
    upstage = "upstage"
    friendli = "friendli"
    naver_clova = "naver_clova"
    azure_openai = "azure_openai"

# -----------------------------
# 비교 실행
# -----------------------------
class ComparisonRunStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"

class ComparisonItemStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    error = "error"

# -----------------------------
# 세션/메시지(파트너 측)
# -----------------------------
class SessionStatus(str, Enum):
    active = "active"
    completed = "completed"
    canceled = "canceled"
    error = "error"

class SessionMode(str, Enum):
    single = "single"
    parallel = "parallel"

class SessionMessageType(str, Enum):
    text = "text"
    image = "image"
    audio = "audio"
    file = "file"
    tool = "tool"

class SenderType(str, Enum):
    student = "student"
    staff = "staff"
    system = "system"

# -----------------------------
# 대화 메시지(일반 LLM 인터페이스용)
# -----------------------------
class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"
