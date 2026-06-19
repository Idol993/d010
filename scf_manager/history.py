import datetime
import json
import os
import csv

from .models import ReleaseRecord, RiskLevel, ReleaseStatus
from .config import RELEASE_DB_FILE, DATA_DIR


_RISK_LEVEL_CSV_MAP = {
    RiskLevel.ROUTINE: "常规放款迭代",
    RiskLevel.EMERGENCY: "紧急资金故障",
    RiskLevel.CORE_RISK: "核心企业风险",
}

_STATUS_CSV_MAP = {
    ReleaseStatus.PENDING_CHECK: "待前置检查",
    ReleaseStatus.CHECK_FAILED: "前置检查未通过",
    ReleaseStatus.PENDING_APPROVAL: "待审批",
    ReleaseStatus.APPROVAL_REJECTED: "审批未通过",
    ReleaseStatus.GRAYSCALE_ROLLOUT: "灰度推送中",
    ReleaseStatus.FULLY_RELEASED: "全量发布",
    ReleaseStatus.MONITORING: "监控中",
    ReleaseStatus.ROLLING_BACK: "回滚中",
    ReleaseStatus.ROLLED_BACK: "已回滚",
    ReleaseStatus.STABLE_RESTORED: "已恢复稳定版本",
}


def _dt_to_str(dt):
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _record_to_dict(record):
    d = {}
    for f in record.__dataclass_fields__:
        val = getattr(record, f)
        if isinstance(val, datetime.datetime):
            val = _dt_to_str(val)
        elif isinstance(val, (RiskLevel, ReleaseStatus)):
            val = val.value
        elif hasattr(val, "__dataclass_fields__"):
            val = _nested_to_dict(val)
        elif isinstance(val, list):
            val = [_nested_to_dict(item) if hasattr(item, "__dataclass_fields__") else item for item in val]
        d[f] = val
    return d


def _nested_to_dict(obj):
    d = {}
    for f in obj.__dataclass_fields__:
        val = getattr(obj, f)
        if isinstance(val, datetime.datetime):
            val = _dt_to_str(val)
        elif isinstance(val, (RiskLevel, ReleaseStatus)):
            val = val.value
        elif hasattr(val, "__dataclass_fields__"):
            val = _nested_to_dict(val)
        elif isinstance(val, list):
            val = [_nested_to_dict(item) if hasattr(item, "__dataclass_fields__") else item for item in val]
        d[f] = val
    return d


class HistoryQuery:
    def __init__(self):
        self._records = []
        self._load()

    def query(
        self,
        start_time: datetime.datetime = None,
        end_time: datetime.datetime = None,
        enterprise_name: str = "",
        industry_chain_module: str = "",
        version: str = "",
        risk_level: str = "",
        status: str = "",
    ) -> list:
        result = self._records

        if start_time is not None:
            result = [r for r in result if r.created_at is not None and r.created_at >= start_time]

        if end_time is not None:
            result = [r for r in result if r.created_at is not None and r.created_at <= end_time]

        if enterprise_name:
            result = [r for r in result if enterprise_name.lower() in r.enterprise_name.lower()]

        if industry_chain_module:
            result = [r for r in result if industry_chain_module.lower() in r.industry_chain_module.lower()]

        if version:
            result = [r for r in result if r.version == version]

        if risk_level:
            result = [r for r in result if r.risk_level.value == risk_level]

        if status:
            result = [r for r in result if r.status.value == status]

        return result

    def export_csv(self, records: list, file_path: str = "") -> str:
        if not file_path:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"{DATA_DIR}/export_{ts}.csv"

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        headers = [
            "发布ID", "版本号", "核心企业", "产业链模块",
            "风险级别", "状态", "放款金额", "创建时间",
            "审批时间", "发布时间", "回滚时间",
        ]

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in records:
                writer.writerow([
                    r.id,
                    r.version,
                    r.enterprise_name,
                    r.industry_chain_module,
                    _RISK_LEVEL_CSV_MAP.get(r.risk_level, r.risk_level.value),
                    _STATUS_CSV_MAP.get(r.status, r.status.value),
                    r.loan_amount,
                    _dt_to_str(r.created_at),
                    _dt_to_str(r.approved_at),
                    _dt_to_str(r.released_at),
                    _dt_to_str(r.rolled_back_at),
                ])

        return file_path

    def export_json(self, records: list, file_path: str = "") -> str:
        if not file_path:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"{DATA_DIR}/export_{ts}.json"

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        data = [_record_to_dict(r) for r in records]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return file_path

    def batch_export(self, records: list, export_dir: str = "") -> dict:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if export_dir:
            csv_path = f"{export_dir}/export_{ts}.csv"
            json_path = f"{export_dir}/export_{ts}.json"
        else:
            csv_path = f"{DATA_DIR}/export_{ts}.csv"
            json_path = f"{DATA_DIR}/export_{ts}.json"

        self.export_csv(records, csv_path)
        self.export_json(records, json_path)

        return {"csv_path": csv_path, "json_path": json_path}

    def _save(self):
        os.makedirs(os.path.dirname(RELEASE_DB_FILE), exist_ok=True)
        data = [_record_to_dict(r) for r in self._records]
        with open(RELEASE_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not os.path.exists(RELEASE_DB_FILE):
            self._records = []
            return

        with open(RELEASE_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._records = []
        for item in data:
            record = ReleaseRecord()
            for key, val in item.items():
                if not hasattr(record, key):
                    continue
                if key == "risk_level" and isinstance(val, str):
                    for rl in RiskLevel:
                        if rl.value == val:
                            val = rl
                            break
                elif key == "status" and isinstance(val, str):
                    for rs in ReleaseStatus:
                        if rs.value == val:
                            val = rs
                            break
                elif key in ("created_at", "approved_at", "released_at", "rolled_back_at") and isinstance(val, str) and val:
                    val = datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                elif key in ("created_at", "approved_at", "released_at", "rolled_back_at") and val == "":
                    val = None
                setattr(record, key, val)
            self._records.append(record)
