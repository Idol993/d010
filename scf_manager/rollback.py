import json
import os
from datetime import datetime

from .models import RollbackRecord, RollbackStatus, ReleaseRecord, ReleaseStatus, ApprovalRole, NotificationType
from .config import NOTIFICATION_ROLES_ON_ROLLBACK, DEFAULT_APPROVERS, ROLLBACK_DB_FILE, DATA_DIR


class RollbackEngine:

    def __init__(self, compliance_logger=None, notification_manager=None):
        self._records: list[RollbackRecord] = []
        self._compliance_logger = compliance_logger
        self._notification_manager = notification_manager
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

        notified = []
        for role in NOTIFICATION_ROLES_ON_ROLLBACK:
            notified.append(role.value)
        notified.append("核心企业对接人")
        record.notified_roles = notified

        report = self._generate_report(record, release, monitoring_metrics)
        os.makedirs(DATA_DIR, exist_ok=True)
        report_path = f"{DATA_DIR}/rollback_report_{record.id}.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        record.report_path = report_path
        record.status = RollbackStatus.COMPLETED
        record.completed_at = datetime.now()

        if self._notification_manager:
            notification_type = NotificationType.MANUAL_ROLLBACK if "手动" in trigger_reason else NotificationType.AUTO_ROLLBACK
            if "自动" in trigger_reason:
                notification_type = NotificationType.AUTO_ROLLBACK
            elif "手动" in trigger_reason:
                notification_type = NotificationType.MANUAL_ROLLBACK
            else:
                notification_type = NotificationType.AUTO_ROLLBACK
            self._notification_manager.send_batch(
                release_id=release.id,
                notification_type=notification_type,
                roles=NOTIFICATION_ROLES_ON_ROLLBACK + ["核心企业对接人"],
                content_summary=f"回滚原因: {trigger_reason}; 影响范围: {record.impact_scope[:50]}",
            )

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

    def regenerate_report(
        self,
        rollback_id: str,
        release: ReleaseRecord,
        monitoring_metrics=None,
    ) -> RollbackRecord:
        record = next((r for r in self._records if r.id == rollback_id), None)
        if not record:
            raise ValueError(f"回滚记录不存在: {rollback_id}")

        if monitoring_metrics is None:
            monitoring_metrics = []

        if not record.impact_scope:
            record.impact_scope = (
                f"核心企业 {release.enterprise_name} 相关放款策略, "
                f"涉及产业链模块 {release.industry_chain_module}"
            )
        if not record.fund_anomaly_reason:
            record.fund_anomaly_reason = self._analyze_fund_anomaly(monitoring_metrics)

        report = self._generate_report(record, release, monitoring_metrics)
        os.makedirs(DATA_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_path = f"{DATA_DIR}/rollback_report_{record.id}_regen_{ts}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report)
        record.report_path = txt_path

        pdf_path = self._generate_pdf_report(record, release, monitoring_metrics)
        if pdf_path:
            record.report_pdf_path = pdf_path

        if self._compliance_logger:
            self._compliance_logger.log(
                operation="回滚报告重新生成",
                operator="RollbackEngine",
                details=f"回滚 {record.id} 报告已重新生成 (TXT+PDF)",
                release_id=release.id,
            )

        self._save()
        return record

    def has_rollback_for_release(self, release_id: str) -> bool:
        return any(r.release_id == release_id for r in self._records)

    def get_records(self, release_id: str = "") -> list:
        if release_id:
            return [r for r in self._records if r.release_id == release_id]
        return list(self._records)

    def supplement_rollback_from_release(
        self,
        release: ReleaseRecord,
        monitoring_metrics=None,
    ) -> RollbackRecord:
        if self.has_rollback_for_release(release.id):
            existing = [r for r in self._records if r.release_id == release.id]
            return existing[0]

        if release.status not in (ReleaseStatus.ROLLED_BACK, ReleaseStatus.STABLE_RESTORED) and not release.rolled_back_at:
            raise ValueError(f"发布 {release.id} 未回滚，无法补录回滚记录")

        if monitoring_metrics is None:
            monitoring_metrics = []

        record = RollbackRecord(
            id=f"sb_{release.id}_补录",
            release_id=release.id,
            trigger_reason="历史数据补录",
            status=RollbackStatus.COMPLETED,
            created_at=release.rolled_back_at or datetime.now(),
            completed_at=release.rolled_back_at or datetime.now(),
            is_supplementary=True,
        )

        record.impact_scope = (
            f"核心企业 {release.enterprise_name} 相关放款策略, "
            f"涉及产业链模块 {release.industry_chain_module}"
        )

        record.fund_anomaly_reason = self._analyze_fund_anomaly(monitoring_metrics)

        record.compliance_risk_desc = (
            f"历史数据补录回滚, 原稳定版本: {release.stable_version or '未知'}"
        )

        notified = []
        for role in NOTIFICATION_ROLES_ON_ROLLBACK:
            notified.append(role.value)
        notified.append("核心企业对接人")
        record.notified_roles = notified

        report = self._generate_report(record, release, monitoring_metrics)
        os.makedirs(DATA_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_path = f"{DATA_DIR}/rollback_report_{record.id}_supp_{ts}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report)
        record.report_path = txt_path

        pdf_path = self._generate_pdf_report(record, release, monitoring_metrics)
        if pdf_path:
            record.report_pdf_path = pdf_path

        self._records.append(record)
        self._save()

        if self._compliance_logger:
            self._compliance_logger.log(
                operation="回滚记录补录",
                operator="RollbackEngine",
                details=f"为发布 {release.id} 补录回滚记录并生成报告",
                release_id=release.id,
            )

        return record

    def _generate_pdf_report(self, record, release, monitoring_metrics) -> str:
        try:
            from fpdf import FPDF
        except ImportError:
            print("[警告] fpdf2 未安装，跳过 PDF 报告生成")
            return ""

        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 10, txt="Supply Chain Finance Rollback Report", ln=True, align="C")
            pdf.ln(5)
            pdf.set_font("Arial", size=10)
            pdf.cell(0, 8, txt=f"Rollback ID: {record.id}", ln=True)
            pdf.cell(0, 8, txt=f"Release ID: {record.release_id}", ln=True)
            pdf.cell(0, 8, txt=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
            pdf.ln(3)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, txt="1. Trigger Info", ln=True)
            pdf.set_font("Arial", size=10)
            pdf.multi_cell(0, 6, txt=f"Reason: {record.trigger_reason}")
            pdf.cell(0, 8, txt=f"Status: {record.status.value}", ln=True)
            pdf.ln(3)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, txt="2. Impact Scope", ln=True)
            pdf.set_font("Arial", size=10)
            pdf.multi_cell(0, 6, txt=record.impact_scope)
            pdf.ln(3)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, txt="3. Fund Anomaly Analysis", ln=True)
            pdf.set_font("Arial", size=10)
            pdf.multi_cell(0, 6, txt=record.fund_anomaly_reason)
            pdf.ln(3)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, txt="4. Compliance Risk", ln=True)
            pdf.set_font("Arial", size=10)
            pdf.multi_cell(0, 6, txt=record.compliance_risk_desc)
            pdf.ln(3)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, txt="5. Notified Roles", ln=True)
            pdf.set_font("Arial", size=10)
            for role in record.notified_roles:
                pdf.cell(0, 6, txt=f"  - {role}", ln=True)
            pdf.ln(3)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, txt="6. Release Info", ln=True)
            pdf.set_font("Arial", size=10)
            pdf.cell(0, 6, txt=f"  Version: {release.version}", ln=True)
            pdf.cell(0, 6, txt=f"  Enterprise: {release.enterprise_name}", ln=True)
            pdf.cell(0, 6, txt=f"  Module: {release.industry_chain_module}", ln=True)
            pdf.cell(0, 6, txt=f"  Amount: {release.loan_amount:,.2f}", ln=True)
            pdf.cell(0, 6, txt=f"  Stable Version: {release.stable_version}", ln=True)
            if monitoring_metrics:
                pdf.ln(3)
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 8, txt="7. Monitoring Metrics", ln=True)
                pdf.set_font("Arial", size=10)
                for i, m in enumerate(monitoring_metrics, 1):
                    ts = m.timestamp.strftime('%Y-%m-%d %H:%M:%S') if m.timestamp else "unknown"
                    pdf.cell(0, 6, txt=f"  Metrics #{i} ({ts}):", ln=True)
                    pdf.cell(0, 6, txt=f"    Loan Success Rate: {m.loan_success_rate:.2f}%", ln=True)
                    pdf.cell(0, 6, txt=f"    Fund Arrival Delay: {m.fund_arrival_delay_min:.2f} min", ln=True)
                    pdf.cell(0, 6, txt=f"    AR Anomaly Rate: {m.ar_anomaly_rate:.2f}%", ln=True)
                    pdf.cell(0, 6, txt=f"    Overdue Risk Score: {m.overdue_risk_score:.2f}", ln=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_path = f"{DATA_DIR}/rollback_report_{record.id}_regen_{ts}.pdf"
            pdf.output(pdf_path)
            return pdf_path
        except Exception as e:
            print(f"[警告] 生成 PDF 报告失败: {e}")
            return ""

    def _analyze_fund_anomaly(self, monitoring_metrics) -> str:
        if not monitoring_metrics:
            return "未提供监控指标数据, 无法分析资金异常原因"

        from .config import THRESHOLDS

        triggered_metrics = [m for m in monitoring_metrics if m.alert_triggered]
        analysis_list = triggered_metrics if triggered_metrics else list(monitoring_metrics)

        reasons = []
        for m in analysis_list:
            metric_reasons = []
            if m.loan_success_rate < THRESHOLDS["loan_success_rate_min"]:
                metric_reasons.append(
                    f"放款成功率低({m.loan_success_rate:.2f}%/阈值{THRESHOLDS['loan_success_rate_min']}%)"
                )
            if m.fund_arrival_delay_min > THRESHOLDS["fund_arrival_delay_max"]:
                metric_reasons.append(
                    f"资金到账延迟高({m.fund_arrival_delay_min:.2f}分/阈值{THRESHOLDS['fund_arrival_delay_max']}分)"
                )
            if m.ar_anomaly_rate > THRESHOLDS["ar_anomaly_rate_max"]:
                metric_reasons.append(
                    f"应收账款异常率高({m.ar_anomaly_rate:.2f}%/阈值{THRESHOLDS['ar_anomaly_rate_max']}%)"
                )
            if m.overdue_risk_score > THRESHOLDS["overdue_risk_score_max"]:
                metric_reasons.append(
                    f"逾期风险高(评分{m.overdue_risk_score:.2f}/阈值{THRESHOLDS['overdue_risk_score_max']})"
                )
            if metric_reasons:
                ts = m.timestamp.strftime('%H:%M:%S') if m.timestamp else ''
                reasons.append(f"[{ts}] " + "、".join(metric_reasons))

        if not reasons:
            return "监控指标未超阈值, 但因其他原因触发回滚"

        return "检测到以下资金异常:\n  - " + "\n  - ".join(reasons)

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
                "report_pdf_path": record.report_pdf_path,
                "created_at": record.created_at.isoformat() if record.created_at else "",
                "completed_at": record.completed_at.isoformat() if record.completed_at else "",
                "notified_roles": record.notified_roles,
                "is_supplementary": record.is_supplementary,
            })
        with open(ROLLBACK_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not os.path.exists(ROLLBACK_DB_FILE):
            self._records = []
            return
        try:
            with open(ROLLBACK_DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[警告] 加载回滚记录失败: {e}")
            self._records = []
            return
        self._records = []
        status_map = {s.value: s for s in RollbackStatus}
        for item in data:
            try:
                created_at = item.get("created_at", "")
                completed_at = item.get("completed_at", "")
                if isinstance(created_at, str) and created_at:
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except (ValueError, TypeError):
                        created_at = None
                else:
                    created_at = None
                if isinstance(completed_at, str) and completed_at:
                    try:
                        completed_at = datetime.fromisoformat(completed_at)
                    except (ValueError, TypeError):
                        completed_at = None
                else:
                    completed_at = None
                self._records.append(RollbackRecord(
                    id=item.get("id", ""),
                    release_id=item.get("release_id", ""),
                    trigger_reason=item.get("trigger_reason", ""),
                    impact_scope=item.get("impact_scope", ""),
                    fund_anomaly_reason=item.get("fund_anomaly_reason", ""),
                    compliance_risk_desc=item.get("compliance_risk_desc", ""),
                    status=status_map.get(item.get("status", ""), RollbackStatus.TRIGGERED),
                    report_path=item.get("report_path", ""),
                    report_pdf_path=item.get("report_pdf_path", ""),
                    created_at=created_at,
                    completed_at=completed_at,
                    notified_roles=item.get("notified_roles", []),
                    is_supplementary=item.get("is_supplementary", False),
                ))
            except Exception as e:
                print(f"[警告] 跳过回滚记录 {item.get('id','?')}: {e}")
                continue
