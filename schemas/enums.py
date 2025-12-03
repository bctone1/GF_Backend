# schemas/enums.py
from enum import Enum

# --------------------
# 공통 상태
# --------------------
class Status(str, Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    draft = "draft"
    archived = "archived"


# 사용자 전용
class UserStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    invited = "invited"
    deleted = "deleted"


# 조직/파트너 전용
class OrgStatus(str, Enum):
    active = "active"
    trial = "trial"
    inactive = "inactive"
    suspended = "suspended"


# 계정 삭제 요청
class AccountDeletionStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    rejected = "rejected"


# 결제/정산
class TransactionStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"
    canceled = "canceled"


class InvoiceStatus(str, Enum):
    draft = "draft"
    open = "open"
    paid = "paid"
    void = "void"
    uncollectible = "uncollectible"


class PayoutStatus(str, Enum):
    pending = "pending"
    in_transit = "in_transit"
    paid = "paid"
    failed = "failed"


# AI 사용량/프로바이더
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


# 대화 메시지
class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


# 작업 공통 상태(배치/인제스트 등)
class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


# 통화
class Currency(str, Enum):
    KRW = "KRW"
    USD = "USD"
    JPY = "JPY"


# ===== 코스/클래스/초대코드 =====
class CourseStatus(str, Enum):
    draft = "draft"        # 생성만 된 상태
    active = "active"      # 운영 중
    archived = "archived"  # 보관


class ClassStatus(str, Enum):
    planned = "planned"    # 개강 전
    active = "active"    # 진행 중
    ended = "ended"        # 종료


class InviteCodeStatus(str, Enum):
    active = "active"      # 사용 가능
    expired = "expired"    # 만료
    disabled = "disabled"  # 비활성화


class InviteTargetRole(str, Enum):
    instructor = "instructor"
    student = "student"


class InstructorRole(str, Enum):
    lead = "lead"
    assistant = "assistant"


# ===== 세션(실습) =====
class SessionMode(str, Enum):
    single = "single"
    parallel = "parallel"


class SessionStatus(str, Enum):
    active = "active"
    completed = "completed"
    canceled = "canceled"
    error = "error"


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


# ===== 비교(모델 비교 실험) =====
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


# ===== 학생/수강 상태 =====
class StudentStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    archived = "archived"


class EnrollmentStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    completed = "completed"
    dropped = "dropped"


# ===== 파트너 알림/보안 =====
class EmailSubscriptionType(str, Enum):
    weekly_digest = "weekly_digest"
    alerts = "alerts"
    marketing = "marketing"


class MfaMethod(str, Enum):
    totp = "totp"
    sms = "sms"
    email = "email"
