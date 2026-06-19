import json
import os
from datetime import datetime

from .models import RollbackRecord, RollbackStatus, ReleaseRecord, ReleaseStatus, ApprovalRole
from .config import NOTIFICATION_ROLES_ON_ROLLBACK, DEFAULT_APPROVERS, ROLLBACK_DB_FILE, DATA_DIR


class RollbackEngine:

    def __init__(self, compliance_logger=None):
        self._records: list[RollbackRecord] = []
        self._compliance_logger = compliance_logger
        self._load()

    def execute_rollback(self, release: ReleaseRecord, trigger_reason: str, monitoring_metrics=None) -> RollbackRecord:
        record = RollbackRecord(
            release_id=release.id,
            trigger_reason=trigger_reason,
            status=RollbackStatus.EXECUTING,
            created_at=datetime.now(),
        )

        record.impact_scope = (
            f"核心企业 {release.enterprise_name} 相关放款策略, "
            f"涉及产业链模块 {release.industry_chain_module}"
        )

        record.fund_anomaly_reason = self._analyze_fund_anomaly(monitoring_metrics)

        record.compliance_risk_desc = (
            f"资金回滚触发合规审查, 原因: {trigger_reason}, "
            f"需关注监管资金安全及应收账款真实性"
        )

        report = self._generate_report(record, release, monitoring_metrics)
        os.makedirs(DATA_DIR, exist_ok=True)
        report_path = f"{DATA_DIR}/rollback_report_{record.id}.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        record.report_path = report_path

        notified = []
        for role in NOTIFICATION_ROLES_ON_ROLLBACK:
            notified.append(role.value)
        notified.append("核心企业对接人")
        record.notified_roles = notified

        record.status = RollbackStatus.COMPLETED
        record.completed_at = datetime.now()

        if self._compliance_logger:
            self._compliance_logger.log(
                operation="回滚执行",
                operator="RollbackEngine",
                details=f"发布 {release.id} 已回滚, 原因: {trigger_reason}",
                release_id=release.id,
            )

        self._records.append(record)
        self._save()
        return record

    def restore_stable_version(self, release: ReleaseRecord) -> ReleaseRecord:
        release.status = ReleaseStatus.STABLE_RESTORED
        release.grayscale_phase = 0
        release.rolled_back_at = datetime.now()

        if self._compliance_logger:
            self._compliance_logger.log(
                operation="恢复稳定版本",
                operator="RollbackEngine",
                details=f"发布 {release.id} 已恢复至稳定版本 {release.stable_version}",
                release_id=release.id,
            )

        return release

    def get_records(self, release_id: str = "") -> list:
        if not release_id:
            return list(self._records)
        return [r for r in self._records if r.release_id == release_id]

    def _analyze_fund_anomaly(self, monitoring_metrics) -> str:
        if not monitoring_metrics:
            return "未提供监控指标数据, 无法分析资金异常原因"

        from .config import THRESHOLDS

        reasons = []
        for m in monitoring_metrics:
            if m.loan_success_rate < THRESHOLDS["loan_success_rate_min"]:
                reasons.append(
                    f"放款成功率 {m.loan_success_rate:.2f}% 低于阈值 {THRESHOLDS['loan_success_rate_min']}%"
                )
            if m.fund_arrival_delay_min > THRESHOLDS["fund_arrival_delay_max"]:
                reasons.append(
                    f"资金到账延迟 {m.fund_arrival_delay_min:.2f} 分钟超过阈值 {THRESHOLDS['fund_arrival_delay_max']} 分钟"
                )
            if m.ar_anomaly_rate > THRESHOLDS["ar_anomaly_rate_max"]:
                reasons.append(
                    f"应收账款异常率 {m.ar_anomaly_rate:.2f}% 超过阈值 {THRESHOLDS['ar_anomaly_rate_max']}%"
                )
            if m.overdue_risk_score > THRESHOLDS["overdue_risk_score_max"]:
                reasons.append(
                    f"逾期风险评分 {m.overdue_risk_score:.2f} 超过阈值 {THRESHOLDS['overdue_risk_score_max']}"
                )

        if not reasons:
            return "监控指标未超阈值, 但因其他原因触发回滚"

        return "检测到以下资金异常: " + "; ".join(reasons)

    def _generate_report(self, record: RollbackRecord, release: ReleaseRecord, monitoring_metrics) -> str:
        now = datetime.now()
        lines = [
            "=" * 60,
            "供应链金融回滚报告",
            "=" * 60,
            "",
            f"回滚编号: {record.id}",
            f"关联发布编号: {record.release_id}",
            f"生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "-" * 40,
            "一、回滚触发",
            "-" * 40,
            f"触发原因: {record.trigger_reason}",
            f"回滚状态: {record.status.value}",
            f"触发时间: {record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else ''}",
            "",
            "-" * 40,
            "二、影响范围",
            "-" * 40,
            record.impact_scope,
            "",
            "-" * 40,
            "三、资金异常分析",
            "-" * 40,
            record.fund_anomaly_reason,
            "",
        ]

        if monitoring_metrics:
            lines.extend([
                "-" * 40,
                "四、监控指标详情",
                "-" * 40,
            ])
            for i, m in enumerate(monitoring_metrics, 1):
                ts = m.timestamp.strftime('%Y-%m-%d %H:%M:%S') if m.timestamp else "未知"
                lines.extend([
                    f"  指标 #{i} ({ts}):",
                    f"    放款成功率: {m.loan_success_rate:.2f}%",
                    f"    资金到账延迟: {m.fund_arrival_delay_min:.2f} 分钟",
                    f"    应收账款异常率: {m.ar_anomaly_rate:.2f}%",
                    f"    逾期风险评分: {m.overdue_risk_score:.2f}",
                    "",
                ])
        else:
            lines.extend([
                "-" * 40,
                "四、监控指标详情",
                "-" * 40,
                "无监控指标数据",
                "",
            ])

        lines.extend([
            "-" * 40,
            "五、合规风险说明",
            "-" * 40,
            record.compliance_risk_desc,
            "",
            "-" * 40,
            "六、通知角色",
            "-" * 40,
        ])
        for role in record.notified_roles:
            lines.append(f"  - {role}")
        lines.append("")

        lines.extend([
            "-" * 40,
            "七、发布信息",
            "-" * 40,
            f"发布版本: {release.version}",
            f"核心企业: {release.enterprise_name}",
            f"产业链模块: {release.industry_chain_module}",
            f"融资金额: {release.loan_amount:.2f}",
            f"灰度阶段: {release.grayscale_phase}",
            f"稳定版本: {release.stable_version}",
            "",
            "=" * 60,
            "报告结束",
            "=" * 60,
        ])

        return "\n".join(lines)

    def _save(self):
        dir_path = os.path.dirname(ROLLBACK_DB_FILE)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        data = []
        for record in self._records:
            data.append({
                "id": record.id,
                "release_id": record.release_id,
                "trigger_reason": record.trigger_reason,
                "impact_scope": record.impact_scope,
                "fund_anomaly_reason": record.fund_anomaly_reason,
                "compliance_risk_desc": record.compliance_risk_desc,
                "status": record.status.value,
                "report_path": record.report_path,
                "created_at": record.created_at.isoformat() if record.created_at else "",
                "completed_at": record.completed_at.isoformat() if record.completed_at else "",
                "notified_roles": record.notified_roles,
            })
        with open(ROLLBACK_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not os.path.exists(ROLLBACK_DB_FILE):
            self._records = []
            return
        with open(ROLLBACK_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._records = []
        status_map = {s.value: s for s in RollbackStatus}
        for item in data:
            created_at = item.get("created_at", "")
            completed_at = item.get("completed_at", "")
            self._records.append(RollbackRecord(
                id=item.get("id", ""),
                release_id=item.get("release_id", ""),
                trigger_reason=item.get("trigger_reason", ""),
                impact_scope=item.get("impact_scope", ""),
                fund_anomaly_reason=item.get("fund_anomaly_reason", ""),
                compliance_risk_desc=item.get("compliance_risk_desc", ""),
                status=status_map.get(item.get("status", ""), RollbackStatus.TRIGGERED),
                report_path=item.get("report_path", ""),
                created_at=datetime.fromisoformat(created_at) if created_at else None,
                completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
                notified_roles=item.get("notified_roles", []),
            ))
