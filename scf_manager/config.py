from .models import RiskLevel, ApprovalRole

MONITOR_INTERVAL_SECONDS = 120

THRESHOLDS = {
    "loan_success_rate_min": 95.0,
    "fund_arrival_delay_max": 30.0,
    "ar_anomaly_rate_max": 5.0,
    "overdue_risk_score_max": 70.0,
}

GRAYSCALE_PHASES = {
    1: 0.10,
    2: 0.30,
    3: 0.60,
    4: 1.00,
}

RISK_LEVEL_APPROVAL_ORDER = {
    RiskLevel.ROUTINE: [
        ApprovalRole.BUSINESS,
        ApprovalRole.RISK_CONTROL,
        ApprovalRole.FUND,
        ApprovalRole.COMPLIANCE,
    ],
    RiskLevel.EMERGENCY: [
        ApprovalRole.RISK_CONTROL,
        ApprovalRole.FUND,
        ApprovalRole.COMPLIANCE,
    ],
    RiskLevel.CORE_RISK: [
        ApprovalRole.RISK_CONTROL,
        ApprovalRole.COMPLIANCE,
        ApprovalRole.BUSINESS,
        ApprovalRole.FUND,
    ],
}

DEFAULT_APPROVERS = {
    ApprovalRole.BUSINESS: "业务主管-张明",
    ApprovalRole.RISK_CONTROL: "风控主管-李华",
    ApprovalRole.FUND: "资金主管-王强",
    ApprovalRole.COMPLIANCE: "合规主管-赵磊",
}

NOTIFICATION_ROLES_ON_ROLLBACK = [
    ApprovalRole.BUSINESS,
    ApprovalRole.RISK_CONTROL,
    ApprovalRole.FUND,
]

DATA_DIR = "scf_manager/data"

ENTERPRISE_DB_FILE = f"{DATA_DIR}/enterprises.json"
RELEASE_DB_FILE = f"{DATA_DIR}/releases.json"
MONITOR_DB_FILE = f"{DATA_DIR}/monitoring.json"
ROLLBACK_DB_FILE = f"{DATA_DIR}/rollbacks.json"
DRILL_DB_FILE = f"{DATA_DIR}/drills.json"
COMPLIANCE_LOG_FILE = f"{DATA_DIR}/compliance_logs.json"
WEEKLY_REPORT_DIR = f"{DATA_DIR}/reports"

PRE_CHECK_ITEMS = [
    "核心企业授信校验",
    "应收账款真实性",
    "供应链对账准确率",
    "监管资金合规",
]
