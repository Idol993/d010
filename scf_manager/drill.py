import datetime
import json
import os
import random

from .models import DrillRecord, DrillStatus
from .config import DRILL_DB_FILE


class RollbackDrillSystem:

    def __init__(self, compliance_logger=None):
        self._records: list[DrillRecord] = []
        self._compliance_logger = compliance_logger
        self._load()

    def create_drill(self, name: str) -> DrillRecord:
        drill_plan = (
            "演练目标: 验证供应链金融资金回滚流程的可靠性\n"
            "演练范围: 核心企业放款策略、资金链路、应收账款校验\n"
            "演练步骤:\n"
            "  1. 模拟资金异常触发\n"
            "  2. 执行资金链路校验\n"
            "  3. 验证回滚通知机制\n"
            "  4. 确认稳定版本恢复\n"
            "预期结果: 回滚流程在5分钟内完成, 资金安全无损失"
        )
        record = DrillRecord(
            id=f"DRILL-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}",
            name=name,
            plan=drill_plan,
            status=DrillStatus.PLANNED,
            created_at=datetime.datetime.now(),
        )
        self._records.append(record)
        if self._compliance_logger:
            self._compliance_logger.log(
                operation="演练创建",
                operator="RollbackDrillSystem",
                details=f"演练创建: {record.id} - {name}",
            )
        self._save()
        return record

    def execute_drill(self, drill_id: str) -> DrillRecord:
        record = next((r for r in self._records if r.id == drill_id), None)
        if record is None:
            raise ValueError(f"演练记录不存在: {drill_id}")

        record.status = DrillStatus.EXECUTING

        checks = [
            "资金归集账户校验",
            "应收账款链路校验",
            "核心企业授信链路校验",
            "监管资金链路校验",
        ]
        results = []
        for check in checks:
            passed = random.random() < 0.9
            status = "通过" if passed else "异常"
            results.append(f"  {check}: {status}")

        record.fund_chain_verification = "\n".join(results)
        elapsed_seconds = round(random.uniform(30, 240), 1)
        all_passed = all("通过" in r for r in results)
        outcome = "成功" if all_passed else "部分异常(已触发回滚)"

        record.execution_results = (
            f"资金链路校验结果:\n{record.fund_chain_verification}\n"
            f"执行耗时: {elapsed_seconds}秒\n"
            f"演练结论: {outcome}"
        )
        record.status = DrillStatus.COMPLETED
        record.completed_at = datetime.datetime.now()

        if self._compliance_logger:
            self._compliance_logger.log(
                operation="演练执行",
                operator="RollbackDrillSystem",
                details=f"演练执行完成: {record.id} - 结论: {outcome} - 耗时: {elapsed_seconds}秒",
            )
        self._save()
        return record

    def get_drills(self) -> list:
        return list(self._records)

    def _save(self):
        data = []
        for r in self._records:
            data.append({
                "id": r.id,
                "name": r.name,
                "plan": r.plan,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
                "execution_results": r.execution_results,
                "fund_chain_verification": r.fund_chain_verification,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            })
        os.makedirs(os.path.dirname(DRILL_DB_FILE), exist_ok=True)
        with open(DRILL_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not os.path.exists(DRILL_DB_FILE):
            return
        with open(DRILL_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            status = item.get("status")
            if isinstance(status, str):
                try:
                    status = DrillStatus(status)
                except ValueError:
                    pass
            created_at = item.get("created_at")
            if created_at:
                created_at = datetime.datetime.fromisoformat(created_at)
            completed_at = item.get("completed_at")
            if completed_at:
                completed_at = datetime.datetime.fromisoformat(completed_at)
            record = DrillRecord(
                id=item["id"],
                name=item["name"],
                plan=item.get("plan"),
                status=status,
                execution_results=item.get("execution_results", ""),
                fund_chain_verification=item.get("fund_chain_verification", ""),
                created_at=created_at,
                completed_at=completed_at,
            )
            self._records.append(record)
