
import csv
import datetime
import os


class AuditTimeline:
    def __init__(self, compliance_logger=None):
        self._compliance_logger = compliance_logger

    def build_timeline(
        self,
        release,
        rollbacks: list = None,
        monitoring_data: list = None,
        notifications: list = None,
        compliance_logs: list = None,
    ) -> list:
        events = []

        rollbacks = rollbacks or []
        monitoring_data = monitoring_data or []
        notifications = notifications or []
        compliance_logs = compliance_logs or []

        if release.created_at:
            events.append({
                "time": release.created_at,
                "type": "发布申请",
                "description": f"发布申请创建，版本 {release.version}",
                "details": f"企业: {release.enterprise_name}, 模块: {release.industry_chain_module}, 金额: {release.loan_amount}",
            })

        if release.pre_check_result and release.pre_check_result.checked_at:
            pcr = release.pre_check_result
            status_text = "通过" if pcr.passed else "未通过"
            events.append({
                "time": pcr.checked_at,
                "type": "前置检查",
                "description": f"前置条件检查{status_text}",
                "details": f"共 {len(pcr.items)} 项检查",
            })

        if release.approval_workflow and release.approval_workflow.steps:
            for step in release.approval_workflow.steps:
                if step.approved_at:
                    status_val = step.status.value if hasattr(step.status, 'value') else str(step.status)
                    status_text = "通过" if status_val == "已通过" else status_val
                    role_val = step.role.value if hasattr(step.role, 'value') else str(step.role)
                    events.append({
                        "time": step.approved_at,
                        "type": "审批",
                        "description": f"{role_val} 审批{status_text}",
                        "details": f"审批人: {step.approver_name}",
                    })

        if release.released_at:
            events.append({
                "time": release.released_at,
                "type": "发布",
                "description": "发布完成，进入全量发布",
                "details": f"灰度阶段: {release.grayscale_phase}",
            })

        for m in monitoring_data:
            if m.alert_triggered and m.timestamp:
                events.append({
                    "time": m.timestamp,
                    "type": "监控告警",
                    "description": "资金监控指标超阈值触发告警",
                    "details": f"放款成功率: {m.loan_success_rate}%, 到账延迟: {m.fund_arrival_delay_min}分",
                })

        for rb in rollbacks:
            if rb.created_at:
                status_val = rb.status.value if hasattr(rb.status, 'value') else str(rb.status)
                events.append({
                    "time": rb.created_at,
                    "type": "回滚触发",
                    "description": f"资金回滚触发: {rb.trigger_reason}",
                    "details": f"回滚ID: {rb.id}, 状态: {status_val}",
                })
            if rb.completed_at and rb.completed_at != rb.created_at:
                events.append({
                    "time": rb.completed_at,
                    "type": "回滚完成",
                    "description": "资金回滚执行完成",
                    "details": f"报告: {rb.report_path or '无'}",
                })

        for n in notifications:
            if n.sent_at:
                status_val = n.status.value if hasattr(n.status, 'value') else str(n.status)
                status_text = "成功" if status_val == "已发送" else "失败"
                type_val = n.notification_type.value if hasattr(n.notification_type, 'value') else str(n.notification_type)
                resend_tag = " (重发)" if n.is_resend else ""
                events.append({
                    "time": n.sent_at,
                    "type": "通知",
                    "description": f"{type_val}{resend_tag} {status_text}",
                    "details": f"接收人: {n.recipient_role} ({n.recipient_name}), 结果: {n.delivery_result}",
                })

        for log in compliance_logs:
            if log.timestamp:
                events.append({
                    "time": log.timestamp,
                    "type": "合规日志",
                    "description": f"{log.operation}",
                    "details": f"操作人: {log.operator}, 详情: {log.details}",
                })

        events.sort(key=lambda e: e["time"] or datetime.datetime.min)
        return events

    def print_timeline(self, events: list):
        if not events:
            print("  (暂无时间线事件)")
            return

        print(f"\n  时间线 ({len(events)} 个事件):")
        print(f"  {'-'*60}")
        for i, e in enumerate(events, 1):
            ts = e["time"].strftime("%Y-%m-%d %H:%M:%S") if e["time"] else "未知时间"
            print(f"  {i:2d}. [{ts}] {e['type']} - {e['description']}")
            if e.get("details"):
                print(f"       {e['details']}")

    def export_csv(self, events: list, file_path: str) -> str:
        dir_path = os.path.dirname(file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["序号", "时间", "类型", "描述", "详情"])
            for i, e in enumerate(events, 1):
                ts = e["time"].strftime("%Y-%m-%d %H:%M:%S") if e["time"] else ""
                writer.writerow([i, ts, e["type"], e["description"], e.get("details", "")])

        if self._compliance_logger:
            self._compliance_logger.log(
                operation="审计时间线导出",
                operator="AuditTimeline",
                details=f"导出时间线 CSV: {file_path}, 共 {len(events)} 条事件",
            )

        return file_path
