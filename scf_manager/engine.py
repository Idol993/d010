import json
import os
from datetime import datetime, timedelta

from .models import (
    CoreEnterprise,
    ReleaseRecord,
    ReleaseStatus,
    RiskLevel,
    MonitoringMetrics,
    PreCheckResult,
    ApprovalWorkflow,
    CheckItem,
    CheckItemStatus,
    ApprovalStep,
    ApprovalRole,
    ApprovalStatus,
    RollbackRecord,
)
from .config import ENTERPRISE_DB_FILE, RELEASE_DB_FILE, DATA_DIR
from .checker import PreConditionChecker
from .approval import ApprovalWorkflowGenerator
from .rollout import GrayscaleRolloutEngine
from .monitor import FundMonitor
from .rollback import RollbackEngine
from .drill import RollbackDrillSystem
from .reporter import WeeklyReporter
from .history import HistoryQuery
from .compliance_logger import ComplianceLogger
from .notification_manager import NotificationManager
from .dashboard import RiskDashboard
from .report_archive import WeeklyReportArchive
from .audit_timeline import AuditTimeline
import threading as _th


class SCFReleaseManager:
    def __init__(self, enable_scheduler: bool = False):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._compliance_logger = ComplianceLogger()
        self._enterprises: dict[str, CoreEnterprise] = {}
        self._releases: list[ReleaseRecord] = []
        self._checker = PreConditionChecker(self._enterprises)
        self._approval_gen = ApprovalWorkflowGenerator()
        self._rollout_engine = GrayscaleRolloutEngine()
        self._monitor = FundMonitor()
        self._notification_manager = NotificationManager(self._compliance_logger)
        self._rollback_engine = RollbackEngine(self._compliance_logger, self._notification_manager)
        self._drill_system = RollbackDrillSystem(self._compliance_logger, self._notification_manager)
        self._reporter = WeeklyReporter()
        self._history = HistoryQuery()
        self._dashboard = RiskDashboard()
        self._report_archive = WeeklyReportArchive()
        self._audit_timeline = AuditTimeline(self._compliance_logger)
        self._load_enterprises()
        self._rolled_back_releases = set()
        self._monitor_lock = _th.Lock()
        self._load_releases()
        self._scheduler_thread = None
        self._scheduler_stop = _th.Event()
        self._last_weekly_report_date = None
        if enable_scheduler:
            self.start_weekly_scheduler()

    def start_weekly_scheduler(self):
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return

        def _scheduler_loop():
            print("[调度器] 每周一自动生成周报 已启动 (每周一09:00运行)")
            while not self._scheduler_stop.is_set():
                try:
                    now = datetime.now()
                    is_monday = now.weekday() == 0
                    hour_match = now.hour == 9 and now.minute < 5
                    today_str = now.strftime("%Y-%m-%d")

                    should_run = is_monday and hour_match and (self._last_weekly_report_date != today_str)

                    if should_run:
                        print(f"\n[调度器] {today_str} 星期一09:00 自动生成周报...")
                        self.generate_weekly_report()
                        self._last_weekly_report_date = today_str
                except Exception as _err:
                    print(f"[调度器] 异常: {_err}")
                for _ in range(60):
                    if self._scheduler_stop.is_set():
                        break
                    import time as _tm
                    _tm.sleep(1)

        self._scheduler_thread = _th.Thread(target=_scheduler_loop, daemon=True)
        self._scheduler_thread.start()

    def stop_weekly_scheduler(self):
        self._scheduler_stop.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=3)

    def trigger_weekly_report_now(self):
        print("[调度器] 手动触发本周周报生成...")
        return self.generate_weekly_report()


    def _load_enterprises(self):
        if not os.path.exists(ENTERPRISE_DB_FILE):
            self._init_sample_enterprises()
            return
        with open(ENTERPRISE_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            ent = CoreEnterprise(
                id=item.get("id", ""),
                name=item.get("name", ""),
                credit_limit=item.get("credit_limit", 0.0),
                credit_used=item.get("credit_used", 0.0),
                risk_rating=item.get("risk_rating", "A"),
                industry_chain=item.get("industry_chain", ""),
                grayscale_phase=item.get("grayscale_phase", 0),
            )
            self._enterprises[ent.id] = ent
        self._checker = PreConditionChecker(self._enterprises)

    def _init_sample_enterprises(self):
        samples = [
            CoreEnterprise(id="ENT001", name="华为技术有限公司", credit_limit=50000000, credit_used=20000000, risk_rating="A", industry_chain="通信产业链"),
            CoreEnterprise(id="ENT002", name="比亚迪股份有限公司", credit_limit=30000000, credit_used=15000000, risk_rating="A", industry_chain="新能源产业链"),
            CoreEnterprise(id="ENT003", name="中兴通讯股份有限公司", credit_limit=20000000, credit_used=18000000, risk_rating="B", industry_chain="通信产业链"),
            CoreEnterprise(id="ENT004", name="三一重工股份有限公司", credit_limit=15000000, credit_used=12000000, risk_rating="C", industry_chain="工程机械产业链"),
            CoreEnterprise(id="ENT005", name="某D级风险企业", credit_limit=5000000, credit_used=4800000, risk_rating="D", industry_chain="化工产业链"),
        ]
        for ent in samples:
            self._enterprises[ent.id] = ent
        self._save_enterprises()
        self._checker = PreConditionChecker(self._enterprises)

    def _save_enterprises(self):
        os.makedirs(os.path.dirname(ENTERPRISE_DB_FILE), exist_ok=True)
        data = []
        for ent in self._enterprises.values():
            data.append({
                "id": ent.id,
                "name": ent.name,
                "credit_limit": ent.credit_limit,
                "credit_used": ent.credit_used,
                "risk_rating": ent.risk_rating,
                "industry_chain": ent.industry_chain,
                "grayscale_phase": ent.grayscale_phase,
            })
        with open(ENTERPRISE_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_releases(self):
        from .models import PreCheckResult, CheckItem, ApprovalWorkflow, ApprovalStep, ApprovalRole, ApprovalStatus
        if not os.path.exists(RELEASE_DB_FILE):
            self._releases = []
            return
        try:
            with open(RELEASE_DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[警告] 加载发布记录失败: {e}, 将从空记录开始")
            self._releases = []
            return
        self._releases = []
        for idx, item in enumerate(data):
            try:
                record = ReleaseRecord()
                for key, val in item.items():
                    if not hasattr(record, key):
                        continue
                    if key == "risk_level" and isinstance(val, str):
                        matched = False
                        for rl in RiskLevel:
                            if rl.value == val:
                                val = rl
                                matched = True
                                break
                        if not matched:
                            val = RiskLevel.ROUTINE
                    elif key == "status" and isinstance(val, str):
                        matched = False
                        for rs in ReleaseStatus:
                            if rs.value == val:
                                val = rs
                                matched = True
                                break
                        if not matched:
                            val = ReleaseStatus.PENDING_CHECK
                    elif key in ("created_at", "approved_at", "released_at", "rolled_back_at"):
                        if isinstance(val, str) and val:
                            val = self._safe_parse_datetime(val)
                        else:
                            val = None
                    elif key == "pre_check_result" and isinstance(val, dict):
                        val = self._deserialize_pre_check_result(val)
                    elif key == "approval_workflow" and isinstance(val, dict):
                        val = self._deserialize_approval_workflow(val)
                    setattr(record, key, val)
                self._releases.append(record)
            except Exception as e:
                print(f"[警告] 跳过第 {idx} 条发布记录加载: {e}")
                continue

    @staticmethod
    def _safe_parse_datetime(val):
        if not isinstance(val, str) or not val:
            return None
        try:
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        return None

    def _deserialize_pre_check_result(self, data: dict):
        from .models import CheckItem, CheckItemStatus
        items = []
        for item_data in data.get("items", []):
            status = item_data.get("status", "")
            if isinstance(status, str):
                matched = False
                for cs in CheckItemStatus:
                    if cs.value == status:
                        status = cs
                        matched = True
                        break
                if not matched:
                    status = CheckItemStatus.PENDING
            checked_at = item_data.get("checked_at")
            if isinstance(checked_at, str) and checked_at:
                checked_at = SCFReleaseManager._safe_parse_datetime(checked_at)
            items.append(CheckItem(
                name=item_data.get("name", ""),
                status=status if isinstance(status, CheckItemStatus) else CheckItemStatus.PENDING,
                detail=item_data.get("detail", ""),
                checked_at=checked_at,
            ))
        checked_at = data.get("checked_at")
        if isinstance(checked_at, str) and checked_at:
            checked_at = SCFReleaseManager._safe_parse_datetime(checked_at)
        return PreCheckResult(
            release_id=data.get("release_id", ""),
            items=items,
            passed=data.get("passed", False),
            checked_at=checked_at,
        )

    def _deserialize_approval_workflow(self, data: dict):
        from .models import ApprovalStep, ApprovalRole, ApprovalStatus, RiskLevel
        steps = []
        for step_data in data.get("steps", []):
            role = step_data.get("role", "")
            if isinstance(role, str):
                matched = False
                for ar in ApprovalRole:
                    if ar.value == role:
                        role = ar
                        matched = True
                        break
                if not matched:
                    role = ApprovalRole.BUSINESS
            status = step_data.get("status", "")
            if isinstance(status, str):
                matched = False
                for as_ in ApprovalStatus:
                    if as_.value == status:
                        status = as_
                        matched = True
                        break
                if not matched:
                    status = ApprovalStatus.PENDING
            approved_at = step_data.get("approved_at")
            if isinstance(approved_at, str) and approved_at:
                approved_at = SCFReleaseManager._safe_parse_datetime(approved_at)
            steps.append(ApprovalStep(
                id=step_data.get("id", ""),
                release_id=step_data.get("release_id", ""),
                role=role if isinstance(role, ApprovalRole) else ApprovalRole.BUSINESS,
                approver_name=step_data.get("approver_name", ""),
                status=status if isinstance(status, ApprovalStatus) else ApprovalStatus.PENDING,
                comment=step_data.get("comment", ""),
                approved_at=approved_at,
            ))
        risk_level = data.get("risk_level", "")
        if isinstance(risk_level, str):
            for rl in RiskLevel:
                if rl.value == risk_level:
                    risk_level = rl
                    break
        created_at = data.get("created_at")
        if isinstance(created_at, str) and created_at:
            created_at = SCFReleaseManager._safe_parse_datetime(created_at)
        return ApprovalWorkflow(
            id=data.get("id", ""),
            release_id=data.get("release_id", ""),
            risk_level=risk_level if isinstance(risk_level, RiskLevel) else RiskLevel.ROUTINE,
            steps=steps,
            current_step_index=data.get("current_step_index", 0),
            created_at=created_at,
        )

    def _serialize_value(self, val):
        from .models import CheckItemStatus, ApprovalStatus, ApprovalRole, RollbackStatus, DrillStatus
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.isoformat()
        if isinstance(val, (RiskLevel, ReleaseStatus, CheckItemStatus,
                            ApprovalStatus, ApprovalRole, RollbackStatus, DrillStatus)):
            return val.value
        if hasattr(val, "__dataclass_fields__"):
            d = {}
            for k in val.__dataclass_fields__:
                d[k] = self._serialize_value(getattr(val, k))
            return d
        if isinstance(val, list):
            return [self._serialize_value(item) for item in val]
        return val

    def _save_releases(self):
        os.makedirs(os.path.dirname(RELEASE_DB_FILE), exist_ok=True)
        data = []
        for r in self._releases:
            d = {}
            for f_name in r.__dataclass_fields__:
                val = getattr(r, f_name)
                d[f_name] = self._serialize_value(val)
            data.append(d)
        with open(RELEASE_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def submit_release(
        self,
        enterprise_id: str,
        version: str,
        industry_chain_module: str,
        loan_amount: float,
        risk_level: RiskLevel = RiskLevel.ROUTINE,
        description: str = "",
    ) -> ReleaseRecord:
        enterprise = self._enterprises.get(enterprise_id)
        if not enterprise:
            print(f"[错误] 未找到企业 {enterprise_id}")
            return None

        record = ReleaseRecord(
            version=version,
            enterprise_id=enterprise_id,
            enterprise_name=enterprise.name,
            industry_chain_module=industry_chain_module,
            risk_level=risk_level,
            loan_amount=loan_amount,
            description=description,
            status=ReleaseStatus.PENDING_CHECK,
            created_at=datetime.now(),
            stable_version=f"{version}-stable-backup",
        )

        self._compliance_logger.log(
            operation="提交发布申请",
            operator="SCFReleaseManager",
            details=f"企业: {enterprise.name}, 版本: {version}, 金额: {loan_amount}, 风险级别: {risk_level.value}",
            release_id=record.id,
        )

        print(f"\n{'='*60}")
        print(f"发布申请已提交 - {record.id}")
        print(f"核心企业: {enterprise.name}")
        print(f"版本: {version} | 金额: {loan_amount:,.2f} | 风险级别: {risk_level.value}")
        print(f"{'='*60}\n")

        check_result = self._checker.check(record.id, enterprise_id, loan_amount)
        record.pre_check_result = check_result

        print("前置条件检查结果:")
        for item in check_result.items:
            icon = {"通过": "✓", "未通过": "✗", "警告": "⚠", "待检查": "?"}.get(item.status.value, "?")
            print(f"  {icon} {item.name}: {item.detail}")

        if not check_result.passed:
            record.status = ReleaseStatus.CHECK_FAILED
            self._releases.append(record)
            self._save_releases()
            self._compliance_logger.log(
                operation="前置检查未通过",
                operator="SCFReleaseManager",
                details="发布申请因前置检查未通过被拒绝",
                release_id=record.id,
            )
            print("\n前置检查未通过，发布申请已拒绝。")
            return record

        print("\n前置检查通过，生成审批流程...")
        record.status = ReleaseStatus.PENDING_APPROVAL
        workflow = self._approval_gen.generate(record.id, risk_level)
        record.approval_workflow = workflow

        print(f"审批流程已生成 - 风险级别: {risk_level.value}")
        for i, step in enumerate(workflow.steps):
            print(f"  步骤 {i+1}: {step.role.value} - {step.approver_name}")

        self._releases.append(record)
        self._save_releases()
        self._compliance_logger.log(
            operation="审批流程生成",
            operator="SCFReleaseManager",
            details=f"风险级别: {risk_level.value}, 审批步骤: {len(workflow.steps)}",
            release_id=record.id,
        )

        return record

    def approve_release(self, release_id: str, auto_approve: bool = False) -> ReleaseRecord:
        record = self._find_release(release_id)
        if not record or not record.approval_workflow:
            print(f"[错误] 未找到发布记录或审批流程: {release_id}")
            return None

        workflow = record.approval_workflow
        if auto_approve:
            for i in range(len(workflow.steps)):
                if workflow.steps[i].status.value == "待审批":
                    self._approval_gen.approve_step(workflow, i, "自动审批通过")
            print("审批流程已自动完成全部步骤")
        else:
            current_idx = workflow.current_step_index
            if current_idx < len(workflow.steps):
                step = workflow.steps[current_idx]
                self._approval_gen.approve_step(workflow, current_idx, f"{step.approver_name} 审批通过")
                print(f"步骤 {current_idx+1} 已通过 - {step.role.value}: {step.approver_name}")

        if self._approval_gen.is_fully_approved(workflow):
            record.status = ReleaseStatus.GRAYSCALE_ROLLOUT
            record.approved_at = datetime.now()
            record = self._rollout_engine.start_grayscale(record)
            print(f"\n审批全部通过！灰度发布已启动 - 阶段 1 ({self._rollout_engine.get_phase_percentage(1):.0%})")

            self._compliance_logger.log(
                operation="审批通过-启动灰度",
                operator="SCFReleaseManager",
                details=f"发布 {record.id} 审批通过, 进入灰度阶段 1",
                release_id=record.id,
            )

            self._start_monitoring_with_rollback(record)

        self._save_releases()
        return record

    def reject_release(self, release_id: str, reason: str = "") -> ReleaseRecord:
        record = self._find_release(release_id)
        if not record or not record.approval_workflow:
            print(f"[错误] 未找到发布记录或审批流程: {release_id}")
            return None

        workflow = record.approval_workflow
        current_idx = workflow.current_step_index
        if current_idx < len(workflow.steps):
            self._approval_gen.reject_step(workflow, current_idx, reason)
            record.status = ReleaseStatus.APPROVAL_REJECTED
            print(f"审批已拒绝 - {reason}")

        self._compliance_logger.log(
            operation="审批拒绝",
            operator="SCFReleaseManager",
            details=f"发布 {record.id} 审批被拒绝, 原因: {reason}",
            release_id=record.id,
        )
        self._save_releases()
        return record

    def advance_grayscale(self, release_id: str) -> ReleaseRecord:
        record = self._find_release(release_id)
        if not record:
            print(f"[错误] 未找到发布记录: {release_id}")
            return None

        latest_metrics = self._monitor.get_latest_metrics(release_id, 3)
        if not self._rollout_engine.can_advance(record, latest_metrics):
            print("当前监控指标不满足灰度推进条件，请检查放款成功率和应收账款异常率")
            return record

        record = self._rollout_engine.advance_phase(record)

        if record.status == ReleaseStatus.FULLY_RELEASED:
            record.released_at = datetime.now()
            self._compliance_logger.log(
                operation="全量发布",
                operator="SCFReleaseManager",
                details=f"发布 {record.id} 已全量发布",
                release_id=record.id,
            )
        else:
            self._compliance_logger.log(
                operation="灰度推进",
                operator="SCFReleaseManager",
                details=f"发布 {record.id} 推进至灰度阶段 {record.grayscale_phase}",
                release_id=record.id,
            )

        self._save_releases()
        return record

    def _start_monitoring_with_rollback(self, release: ReleaseRecord):
        def on_breach(release_id, metrics):
            print(f"\n{'!'*60}")
            print(f"监控告警 - 发布 {release_id}")
            print(f"  放款成功率: {metrics.loan_success_rate:.2f}%")
            print(f"  资金到账延迟: {metrics.fund_arrival_delay_min:.2f} 分钟")
            print(f"  应收账款异常率: {metrics.ar_anomaly_rate:.2f}%")
            print(f"  逾期风险评分: {metrics.overdue_risk_score:.2f}")
            print(f"触发自动回滚...")
            print(f"{'!'*60}\n")
            self._execute_auto_rollback(release_id)

        self._monitor.start_monitoring(
            release.id,
            release.enterprise_id,
            on_threshold_breach=on_breach,
        )
        print(f"资金监控已启动 - 每 120 秒采集一次指标")

    def _execute_auto_rollback(self, release_id: str):
        with self._monitor_lock:
            if release_id in self._rolled_back_releases:
                return
            self._rolled_back_releases.add(release_id)

        record = self._find_release(release_id)
        if not record:
            return

        if record.status == ReleaseStatus.ROLLING_BACK or record.status == ReleaseStatus.STABLE_RESTORED:
            return

        self._monitor.stop_monitoring(release_id)

        record.status = ReleaseStatus.ROLLING_BACK

        latest_metrics = self._monitor.get_latest_metrics(release_id, 5)

        rollback_record = self._rollback_engine.execute_rollback(
            release=record,
            trigger_reason="监控指标超过阈值，自动触发资金回滚",
            monitoring_metrics=latest_metrics,
        )

        print(f"\n资金回滚报告已生成: {rollback_record.report_path}")
        print(f"影响范围: {rollback_record.impact_scope}")
        print(f"资金异常原因: {rollback_record.fund_anomaly_reason}")
        print(f"合规风险说明: {rollback_record.compliance_risk_desc}")
        print(f"已通知角色: {', '.join(rollback_record.notified_roles)}")

        record = self._rollback_engine.restore_stable_version(record)
        print(f"\n已恢复稳定版本: {record.stable_version}")

        with self._monitor_lock:
            self._rolled_back_releases.discard(release_id)

        self._start_monitoring_with_rollback(record)
        print("资金监控已重启")

        self._save_releases()

    def create_drill(self, name: str = "供应链金融回滚演练"):
        drill = self._drill_system.create_drill(name)
        print(f"\n回滚演练已创建: {drill.id}")
        print(f"演练计划:")
        print(drill.plan)
        return drill

    def execute_drill(self, drill_id: str):
        drill = self._drill_system.execute_drill(drill_id)
        print(f"\n演练执行完成: {drill.id}")
        print(f"演练结果:")
        print(drill.execution_results)
        return drill

    def generate_weekly_report(self):
        releases = self._releases
        rollbacks = self._rollback_engine.get_records()
        monitoring_data = self._monitor._monitoring_data

        stats = self._reporter.calculate_weekly_stats(releases, rollbacks, monitoring_data)
        print(f"\n{'='*60}")
        print(f"供应链金融资金安全周报")
        print(f"统计周期: {stats.week_start.strftime('%Y-%m-%d')} ~ {stats.week_end.strftime('%Y-%m-%d')}")
        print(f"{'='*60}")
        print(f"  发布总数: {stats.total_releases}")
        print(f"  成功发布: {stats.successful_releases}")
        print(f"  失败发布: {stats.failed_releases}")
        print(f"  回滚次数: {stats.rollback_count}")
        print(f"  发布成功率: {stats.release_success_rate:.1f}%")
        print(f"  平均放款成功率: {stats.avg_loan_success_rate:.1f}%")
        print(f"  放款逾期率: {stats.loan_overdue_rate:.1f}%")
        print(f"  平均到账延迟: {stats.avg_fund_delay:.1f} 分钟")

        pdf_path = self._reporter.generate_pdf_report(stats)
        if pdf_path:
            print(f"\nPDF 报告已生成: {pdf_path}")

        excel_path = self._reporter.generate_excel_report(
            releases, rollbacks, monitoring_data, stats,
            week_start=stats.week_start, week_end=stats.week_end,
        )
        if excel_path:
            print(f"Excel 报表已生成: {excel_path}")

        self._compliance_logger.log(
            operation="生成周报",
            operator="SCFReleaseManager",
            details=f"PDF: {pdf_path}, Excel: {excel_path}",
        )

        return {"pdf": pdf_path, "excel": excel_path, "stats": stats}

    def generate_weekly_report_by_date(self, week_start, week_end=None):
        releases = self._releases
        rollbacks = self._rollback_engine.get_records()
        monitoring_data = self._monitor._monitoring_data

        stats = self._reporter.calculate_weekly_stats(
            releases, rollbacks, monitoring_data,
            week_start=week_start, week_end=week_end,
        )
        print(f"\n{'='*60}")
        print(f"供应链金融资金安全周报 (自定义周期)")
        print(f"统计周期: {stats.week_start.strftime('%Y-%m-%d')} ~ {stats.week_end.strftime('%Y-%m-%d')}")
        print(f"{'='*60}")
        print(f"  发布总数: {stats.total_releases}")
        print(f"  成功发布: {stats.successful_releases}")
        print(f"  失败发布: {stats.failed_releases}")
        print(f"  回滚次数: {stats.rollback_count}")
        print(f"  发布成功率: {stats.release_success_rate:.1f}%")
        print(f"  平均放款成功率: {stats.avg_loan_success_rate:.1f}%")
        print(f"  放款逾期率: {stats.loan_overdue_rate:.1f}%")
        print(f"  平均到账延迟: {stats.avg_fund_delay:.1f} 分钟")

        if stats.top_rollback_enterprises:
            print(f"\n  回滚最多的核心企业 TOP{len(stats.top_rollback_enterprises)}:")
            for i, item in enumerate(stats.top_rollback_enterprises, 1):
                print(f"    {i}. {item['enterprise']} ({item['rollback_count']} 次)")

        if stats.top_alert_modules:
            print(f"\n  告警最多的产业链模块 TOP{len(stats.top_alert_modules)}:")
            for i, item in enumerate(stats.top_alert_modules, 1):
                print(f"    {i}. {item['module']} ({item['alert_count']} 次)")

        pdf_path = self._reporter.generate_pdf_report(stats)
        if pdf_path:
            print(f"\nPDF 报告已生成: {pdf_path}")

        excel_path = self._reporter.generate_excel_report(
            releases, rollbacks, monitoring_data, stats,
            week_start=stats.week_start, week_end=stats.week_end,
        )
        if excel_path:
            print(f"Excel 报表已生成: {excel_path}")

        self._compliance_logger.log(
            operation="生成自定义周期周报",
            operator="SCFReleaseManager",
            details=f"周期: {stats.week_start} ~ {stats.week_end}",
        )

        return {"pdf": pdf_path, "excel": excel_path, "stats": stats}

    def show_risk_dashboard(self):
        self._dashboard.set_data(
            releases=self._releases,
            rollbacks=self._rollback_engine.get_records(),
            monitoring_data=self._monitor._monitoring_data,
        )
        self._dashboard.print_dashboard()

    def export_dashboard_excel(self, file_path: str = "") -> str:
        self._dashboard.set_data(
            releases=self._releases,
            rollbacks=self._rollback_engine.get_records(),
            monitoring_data=self._monitor._monitoring_data,
        )
        path = self._dashboard.export_excel(file_path)
        if path:
            print(f"风险看板 Excel 已导出: {path}")
            self._compliance_logger.log(
                operation="导出风险看板",
                operator="SCFReleaseManager",
                details=f"导出路径: {path}",
            )
        return path

    def regenerate_rollback_report(self, rollback_id: str = "", release_id: str = ""):
        if rollback_id:
            rollback = next((r for r in self._rollback_engine.get_records() if r.id == rollback_id), None)
        elif release_id:
            rbs = self._rollback_engine.get_records(release_id)
            rollback = rbs[-1] if rbs else None
        else:
            print("[错误] 请指定回滚ID或发布ID")
            return None

        if not rollback:
            print(f"[错误] 未找到回滚记录")
            return None

        release = self._find_release(rollback.release_id)
        if not release:
            print(f"[错误] 未找到关联的发布记录")
            return None

        monitoring_data = self._monitor.get_latest_metrics(rollback.release_id, 10)

        rollback = self._rollback_engine.regenerate_report(
            rollback_id=rollback.id,
            release=release,
            monitoring_metrics=monitoring_data,
        )

        print(f"\n回滚报告已重新生成:")
        print(f"  TXT 报告: {rollback.report_path}")
        if rollback.report_pdf_path:
            print(f"  PDF 报告: {rollback.report_pdf_path}")

        return rollback

    def list_notifications(self, release_id: str = "", drill_id: str = ""):
        notifs = self._notification_manager.query(
            release_id=release_id, drill_id=drill_id,
        )
        print(f"\n通知流水 ({len(notifs)} 条):")
        for n in notifs:
            ts = n.sent_at.strftime("%Y-%m-%d %H:%M:%S") if n.sent_at else ""
            status_icon = "✓" if n.status.value == "已发送" else "✗"
            print(f"  {status_icon} [{ts}] {n.notification_type.value} -> {n.recipient_role} ({n.recipient_name}) [{n.delivery_result}]")
            if n.content_summary:
                print(f"    摘要: {n.content_summary[:80]}")
        return notifs

    def resend_notification(self, notification_id: str):
        try:
            resent = self._notification_manager.resend_notification(notification_id)
            print(f"\n通知重发完成，共生成 {len(resent)} 条新记录:")
            for n in resent:
                ts = n.sent_at.strftime("%Y-%m-%d %H:%M:%S") if n.sent_at else ""
                status_icon = "✓" if n.status.value == "已发送" else "✗"
                print(f"  {status_icon} [{ts}] {n.id} -> {n.recipient_role} [{n.delivery_result}]")
            return resent
        except ValueError as e:
            print(f"[错误] {e}")
            return []

    def resend_failed_notifications(self, release_id: str = ""):
        resent = self._notification_manager.resend_failed(release_id=release_id)
        print(f"\n失败通知重发完成，共重发 {len(resent)} 条")
        return resent

    def supplement_rollback_report(self, release_id: str):
        release = self._find_release(release_id)
        if not release:
            print(f"[错误] 未找到发布记录: {release_id}")
            return None

        if release.status not in (ReleaseStatus.ROLLED_BACK, ReleaseStatus.STABLE_RESTORED) and not release.rolled_back_at:
            print(f"[提示] 发布 {release_id} 未回滚，无需补录回滚报告")
            return None

        has_rb = self._rollback_engine.has_rollback_for_release(release_id)
        monitoring_data = self._monitor.get_latest_metrics(release_id, 20)

        if has_rb:
            rbs = self._rollback_engine.get_records(release_id)
            rb = rbs[-1]
            if rb.report_path:
                print(f"[提示] 发布 {release_id} 已有回滚报告，执行重新生成")
            else:
                print(f"[提示] 发布 {release_id} 有回滚记录但无报告，补生成报告")
            result = self._rollback_engine.regenerate_report(
                rollback_id=rb.id,
                release=release,
                monitoring_metrics=monitoring_data,
            )
        else:
            print(f"[提示] 发布 {release_id} 无独立回滚记录，从发布信息补录回滚并生成报告")
            result = self._rollback_engine.supplement_rollback_from_release(
                release=release,
                monitoring_metrics=monitoring_data,
            )

        print(f"\n回滚报告已生成:")
        print(f"  TXT: {result.report_path}")
        if hasattr(result, 'report_pdf_path') and result.report_pdf_path:
            print(f"  PDF: {result.report_pdf_path}")
        if hasattr(result, 'is_supplementary') and result.is_supplementary:
            print(f"  (注: 此为补录回滚记录)")

        return result

    def list_weekly_reports(self, **kwargs):
        if kwargs:
            reports = self._report_archive.query(**kwargs)
        else:
            reports = self._report_archive.list_reports()
        print(f"\n历史周报列表 ({len(reports)} 份):")
        print(f"{'='*70}")
        for i, r in enumerate(reports, 1):
            ws = r["week_start"].strftime("%Y-%m-%d") if r["week_start"] else "未知"
            we = r["week_end"].strftime("%Y-%m-%d") if r["week_end"] else "未知"
            gt = r["generated_at"].strftime("%Y-%m-%d %H:%M:%S") if r["generated_at"] else "未知"
            types = "/".join(r["file_types"])
            print(f"{i:2d}. 周期: {ws} ~ {we}")
            print(f"    生成时间: {gt}  |  类型: {types}")
        print(f"{'='*70}")
        return reports

    def delete_weekly_report(self, week_start):
        deleted = self._report_archive.delete_report(week_start)
        if deleted > 0:
            ws = week_start.strftime("%Y-%m-%d") if hasattr(week_start, 'strftime') else str(week_start)
            print(f"已删除 {ws} 周期的周报 ({deleted} 个文件)")
            self._compliance_logger.log(
                operation="删除历史周报",
                operator="SCFReleaseManager",
                details=f"删除周期 {ws} 的周报，共 {deleted} 个文件",
            )
        else:
            print("未找到对应周期的周报")
        return deleted

    def regenerate_weekly_report(self, week_start, mode: str = "save_as"):
        week_end = week_start + timedelta(days=7)
        releases = self._releases
        rollbacks = self._rollback_engine.get_records()
        monitoring_data = self._monitor._monitoring_data

        stats = self._reporter.calculate_weekly_stats(
            releases, rollbacks, monitoring_data,
            week_start=week_start, week_end=week_end,
        )

        existing = self._report_archive.get_by_week_start(week_start)

        if mode == "overwrite" and existing:
            self._report_archive.delete_report(week_start)

        pdf_path = self._reporter.generate_pdf_report(stats)
        excel_path = self._reporter.generate_excel_report(
            releases, rollbacks, monitoring_data, stats,
            week_start=week_start, week_end=week_end,
        )

        ws = week_start.strftime("%Y-%m-%d") if hasattr(week_start, 'strftime') else str(week_start)
        action = "覆盖" if mode == "overwrite" else "另存"
        print(f"\n周报已重新生成 ({action}):")
        if pdf_path:
            print(f"  PDF: {pdf_path}")
        if excel_path:
            print(f"  Excel: {excel_path}")

        self._compliance_logger.log(
            operation="重新生成周报",
            operator="SCFReleaseManager",
            details=f"重新生成周期 {ws} 的周报，模式: {mode}",
        )

        return {"pdf": pdf_path, "excel": excel_path, "stats": stats}

    def show_audit_timeline(self, release_id: str):
        release = self._find_release(release_id)
        if not release:
            print(f"[错误] 未找到发布记录: {release_id}")
            return []

        rollbacks = self._rollback_engine.get_records(release_id)
        monitoring_data = [m for m in self._monitor._monitoring_data if m.release_id == release_id]
        notifications = self._notification_manager.query(release_id=release_id)
        compliance_logs = [l for l in self._compliance_logger.query(release_id=release_id)]

        events = self._audit_timeline.build_timeline(
            release=release,
            rollbacks=rollbacks,
            monitoring_data=monitoring_data,
            notifications=notifications,
            compliance_logs=compliance_logs,
        )

        print(f"\n发布 {release_id} 审计时间线")
        print(f"{'='*60}")
        self._audit_timeline.print_timeline(events)
        return events

    def export_audit_timeline_csv(self, release_id: str, file_path: str = "") -> str:
        events = self.show_audit_timeline(release_id)
        if not events:
            return ""

        if not file_path:
            import datetime as _dt
            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"{DATA_DIR}/audit_timeline_{release_id}_{ts}.csv"

        path = self._audit_timeline.export_csv(events, file_path)
        print(f"\n审计时间线已导出: {path}")
        return path

    def query_history(self, **kwargs) -> list:
        results = self._history.query(records=self._releases, **kwargs)
        print(f"\n查询到 {len(results)} 条发布记录")
        for r in results:
            print(f"  {r.id} | {r.version} | {r.enterprise_name} | {r.status.value} | {r.risk_level.value}")
        return results

    def export_records(self, records: list = None, **query_kwargs) -> dict:
        if records is None:
            records = self._history.query(records=self._releases, **query_kwargs)
        paths = self._history.batch_export(records)
        print(f"\n批量导出完成:")
        print(f"  共 {len(records)} 条记录")
        print(f"  CSV: {paths['csv_path']}")
        print(f"  JSON: {paths['json_path']}")

        self._compliance_logger.log(
            operation="批量导出",
            operator="SCFReleaseManager",
            details=f"导出 {len(records)} 条记录",
        )
        return paths

    def list_enterprises(self):
        print(f"\n{'='*70}")
        print(f"{'ID':<10} {'企业名称':<25} {'授信额度':>15} {'已用额度':>15} {'评级':<5} {'产业链'}")
        print(f"{'-'*70}")
        for ent in self._enterprises.values():
            print(f"{ent.id:<10} {ent.name:<25} {ent.credit_limit:>15,.2f} {ent.credit_used:>15,.2f} {ent.risk_rating:<5} {ent.industry_chain}")
        print(f"{'='*70}")

    def list_releases(self):
        print(f"\n{'='*90}")
        print(f"{'ID':<10} {'版本':<12} {'企业':<20} {'模块':<15} {'风险级别':<12} {'状态':<15} {'金额':>12}")
        print(f"{'-'*90}")
        for r in self._releases:
            print(f"{r.id:<10} {r.version:<12} {r.enterprise_name:<20} {r.industry_chain_module:<15} {r.risk_level.value:<12} {r.status.value:<15} {r.loan_amount:>12,.2f}")
        print(f"{'='*90}")

    def list_compliance_logs(self, release_id: str = ""):
        logs = self._compliance_logger.query(release_id=release_id)
        print(f"\n{'='*80}")
        print(f"资金合规日志 ({len(logs)} 条)")
        print(f"{'-'*80}")
        for log in logs[-20:]:
            ts = log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""
            print(f"  [{ts}] {log.operation} | {log.operator} | {log.details}")
        if len(logs) > 20:
            print(f"  ... 共 {len(logs)} 条, 仅显示最近 20 条")
        print(f"{'='*80}")

    def show_release_detail(self, release_id: str):
        record = self._find_release(release_id)
        if not record:
            print(f"[错误] 未找到发布记录: {release_id}")
            return

        print(f"\n{'='*60}")
        print(f"发布详情 - {record.id}")
        print(f"{'='*60}")
        print(f"  版本: {record.version}")
        print(f"  核心企业: {record.enterprise_name} ({record.enterprise_id})")
        print(f"  产业链模块: {record.industry_chain_module}")
        print(f"  风险级别: {record.risk_level.value}")
        print(f"  状态: {record.status.value}")
        print(f"  放款金额: {record.loan_amount:,.2f}")
        print(f"  创建时间: {record.created_at}")
        print(f"  审批时间: {record.approved_at or '未审批'}")
        print(f"  发布时间: {record.released_at or '未发布'}")
        print(f"  回滚时间: {record.rolled_back_at or '未回滚'}")
        print(f"  灰度阶段: {record.grayscale_phase}")
        print(f"  稳定版本: {record.stable_version}")

        if record.pre_check_result:
            print(f"\n  前置检查结果:")
            for item in record.pre_check_result.items:
                print(f"    {item.status.value} - {item.name}: {item.detail}")

        if record.approval_workflow:
            print(f"\n  审批流程:")
            for i, step in enumerate(record.approval_workflow.steps):
                status_icon = {"已通过": "✓", "已拒绝": "✗", "待审批": "○"}.get(step.status.value, "?")
                print(f"    {status_icon} 步骤 {i+1}: {step.role.value} - {step.approver_name} [{step.status.value}]")

        latest = self._monitor.get_latest_metrics(release_id, 3)
        if latest:
            print(f"\n  最近监控指标:")
            for m in latest:
                ts = m.timestamp.strftime("%H:%M:%S") if m.timestamp else ""
                alert = " [告警]" if m.alert_triggered else ""
                print(f"    {ts} 成功率:{m.loan_success_rate:.1f}% 延迟:{m.fund_arrival_delay_min:.1f}分 异常率:{m.ar_anomaly_rate:.1f}% 逾期分:{m.overdue_risk_score:.1f}{alert}")

        rollbacks = self._rollback_engine.get_records(release_id)
        if rollbacks:
            print(f"\n  回滚记录 ({len(rollbacks)} 条):")
            for rb in rollbacks:
                supp_tag = " [补录]" if hasattr(rb, 'is_supplementary') and rb.is_supplementary else ""
                print(f"    {rb.id}{supp_tag} | 原因: {rb.trigger_reason} | 状态: {rb.status.value}")
                print(f"    影响范围: {rb.impact_scope}")
                print(f"    资金异常原因:")
                for line in rb.fund_anomaly_reason.split('\n'):
                    print(f"      {line}")
                print(f"    合规风险说明: {rb.compliance_risk_desc}")
                if rb.notified_roles:
                    print(f"    通知角色: {', '.join(rb.notified_roles)}")
                if rb.completed_at:
                    print(f"    完成时间: {rb.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
                if rb.report_path:
                    print(f"    TXT 报告: {rb.report_path}")
                if hasattr(rb, 'report_pdf_path') and rb.report_pdf_path:
                    print(f"    PDF 报告: {rb.report_pdf_path}")
                if not rb.report_path:
                    print(f"    [提示] 此回滚记录暂无报告，可使用菜单 [重新生成回滚报告] 补生成")
        else:
            if record.status in (ReleaseStatus.ROLLED_BACK, ReleaseStatus.STABLE_RESTORED) or record.rolled_back_at:
                print(f"\n  [提示] 发布已回滚但无独立回滚记录，可使用菜单 [重新生成回滚报告] 补录回滚并生成报告")

        notifications = self._notification_manager.query(release_id=release_id)
        if notifications:
            original_notifs = [n for n in notifications if not n.is_resend]
            resend_notifs = [n for n in notifications if n.is_resend]
            print(f"\n  通知流水 ({len(notifications)} 条, 其中原始 {len(original_notifs)} 条, 重发 {len(resend_notifs)} 条):")
            for n in original_notifs:
                ts = n.sent_at.strftime("%Y-%m-%d %H:%M:%S") if n.sent_at else ""
                status_icon = "✓" if n.status.value == "已发送" else "✗"
                resend_count = len([r for r in resend_notifs if r.parent_id == n.id])
                resend_info = f" (已重发 {resend_count} 次)" if resend_count > 0 else ""
                print(f"    {status_icon} [{ts}] {n.notification_type.value} -> {n.recipient_role} ({n.recipient_name}) [{n.delivery_result}]{resend_info}")
                # 显示重发记录
                children = [r for r in resend_notifs if r.parent_id == n.id]
                for child in children:
                    cts = child.sent_at.strftime("%Y-%m-%d %H:%M:%S") if child.sent_at else ""
                    cicon = "✓" if child.status.value == "已发送" else "✗"
                    print(f"      ↳ {cicon} [{cts}] 重发 [{child.delivery_result}] (ID: {child.id})")

        print(f"{'='*60}")

    def _find_release(self, release_id: str) -> ReleaseRecord:
        for r in self._releases:
            if r.id == release_id:
                return r
        return None

    def shutdown(self):
        self._monitor.stop_all()
        self.stop_weekly_scheduler()
        self._save_releases()
        self._save_enterprises()
        print("系统已安全关闭，所有监控、调度器已停止")
