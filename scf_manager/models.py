from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid


class RiskLevel(Enum):
    ROUTINE = "常规放款迭代"
    EMERGENCY = "紧急资金故障"
    CORE_RISK = "核心企业风险"


class ReleaseStatus(Enum):
    PENDING_CHECK = "待前置检查"
    CHECK_FAILED = "前置检查未通过"
    PENDING_APPROVAL = "待审批"
    APPROVAL_REJECTED = "审批未通过"
    GRAYSCALE_ROLLOUT = "灰度推送中"
    FULLY_RELEASED = "全量发布"
    MONITORING = "监控中"
    ROLLING_BACK = "回滚中"
    ROLLED_BACK = "已回滚"
    STABLE_RESTORED = "已恢复稳定版本"


class ApprovalRole(Enum):
    BUSINESS = "业务审批人"
    RISK_CONTROL = "风控审批人"
    FUND = "资金审批人"
    COMPLIANCE = "合规审批人"


class ApprovalStatus(Enum):
    PENDING = "待审批"
    APPROVED = "已通过"
    REJECTED = "已拒绝"


class RollbackStatus(Enum):
    TRIGGERED = "已触发"
    EXECUTING = "执行中"
    COMPLETED = "已完成"


class DrillStatus(Enum):
    PLANNED = "已规划"
    EXECUTING = "执行中"
    COMPLETED = "已完成"


class CheckItemStatus(Enum):
    PENDING = "待检查"
    PASS = "通过"
    FAIL = "未通过"
    WARNING = "警告"


@dataclass
class CoreEnterprise:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    credit_limit: float = 0.0
    credit_used: float = 0.0
    risk_rating: str = "A"
    industry_chain: str = ""
    grayscale_phase: int = 0


@dataclass
class CheckItem:
    name: str = ""
    status: CheckItemStatus = CheckItemStatus.PENDING
    detail: str = ""
    checked_at: Optional[datetime] = None


@dataclass
class PreCheckResult:
    release_id: str = ""
    items: list = field(default_factory=list)
    passed: bool = False
    checked_at: Optional[datetime] = None


@dataclass
class ApprovalStep:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    release_id: str = ""
    role: ApprovalRole = ApprovalRole.BUSINESS
    approver_name: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    comment: str = ""
    approved_at: Optional[datetime] = None


@dataclass
class ApprovalWorkflow:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    release_id: str = ""
    risk_level: RiskLevel = RiskLevel.ROUTINE
    steps: list = field(default_factory=list)
    current_step_index: int = 0
    created_at: Optional[datetime] = None


@dataclass
class ReleaseRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    version: str = ""
    enterprise_id: str = ""
    enterprise_name: str = ""
    industry_chain_module: str = ""
    risk_level: RiskLevel = RiskLevel.ROUTINE
    status: ReleaseStatus = ReleaseStatus.PENDING_CHECK
    pre_check_result: Optional[PreCheckResult] = None
    approval_workflow: Optional[ApprovalWorkflow] = None
    grayscale_phase: int = 0
    loan_amount: float = 0.0
    description: str = ""
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    stable_version: str = ""


@dataclass
class MonitoringMetrics:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    release_id: str = ""
    enterprise_id: str = ""
    timestamp: Optional[datetime] = None
    loan_success_rate: float = 0.0
    fund_arrival_delay_min: float = 0.0
    ar_anomaly_rate: float = 0.0
    overdue_risk_score: float = 0.0
    alert_triggered: bool = False


@dataclass
class RollbackRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    release_id: str = ""
    trigger_reason: str = ""
    impact_scope: str = ""
    fund_anomaly_reason: str = ""
    compliance_risk_desc: str = ""
    status: RollbackStatus = RollbackStatus.TRIGGERED
    report_path: str = ""
    report_pdf_path: str = ""
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notified_roles: list = field(default_factory=list)
    is_supplementary: bool = False


@dataclass
class DrillRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    plan: str = ""
    fund_chain_verification: str = ""
    execution_results: str = ""
    status: DrillStatus = DrillStatus.PLANNED
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ComplianceLogEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    operation: str = ""
    operator: str = ""
    details: str = ""
    release_id: str = ""
    timestamp: Optional[datetime] = None


class NotificationType(Enum):
    AUTO_ROLLBACK = "自动回滚通知"
    MANUAL_ROLLBACK = "手动回滚通知"
    DRILL_TRIGGER = "演练触发通知"
    RELEASE_APPROVAL = "发布审批通知"


class NotificationStatus(Enum):
    SENT = "已发送"
    SEND_FAILED = "发送失败"
    READ = "已读"
    UNREAD = "未读"


@dataclass
class NotificationRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    release_id: str = ""
    drill_id: str = ""
    notification_type: NotificationType = NotificationType.AUTO_ROLLBACK
    recipient_role: str = ""
    recipient_name: str = ""
    status: NotificationStatus = NotificationStatus.SENT
    content_summary: str = ""
    sent_at: Optional[datetime] = None
    delivery_result: str = "成功"
    parent_id: str = ""
    is_resend: bool = False


@dataclass
class WeeklyStats:
    week_start: Optional[datetime] = None
    week_end: Optional[datetime] = None
    total_releases: int = 0
    successful_releases: int = 0
    failed_releases: int = 0
    rollback_count: int = 0
    loan_overdue_rate: float = 0.0
    avg_loan_success_rate: float = 0.0
    avg_fund_delay: float = 0.0
    release_success_rate: float = 0.0
    top_rollback_enterprises: list = field(default_factory=list)
    top_alert_modules: list = field(default_factory=list)
