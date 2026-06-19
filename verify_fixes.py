import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime as dt

from scf_manager.engine import SCFReleaseManager

print("=" * 60)
print("修复验证 1: 加载带T+微秒的旧数据、非法数据容错")
print("=" * 60)
manager = SCFReleaseManager()

print(f"\n实际加载了 {len(manager._releases)} 条记录:")
for r in manager._releases:
    print(f"  {r.id} | 版本={r.version} | 企业={r.enterprise_name}")
    print(f"    创建时间: {r.created_at} (类型: {type(r.created_at).__name__})")
    print(f"    审批时间: {r.approved_at}")
    print(f"    发布时间: {r.released_at}")
    print(f"    回滚时间: {r.rolled_back_at}")
    print(f"    状态: {r.status.value}")
    print(f"    风险: {r.risk_level.value}")

print("\n" + "=" * 60)
print("修复验证 2: 查询历史记录 (多条件组合)")
print("=" * 60)

print("\n2a. 按企业模糊查询'华为':")
q1 = manager.query_history(enterprise_name="华为")
assert len(q1) == 1 and q1[0].enterprise_id == "ENT001", f"查询结果不符: {len(q1)}条"

print("\n2b. 按时间范围查询 2025-01-01 ~ 2025-06-30:")
q2 = manager.query_history(
    start_time=dt.datetime(2025, 1, 1),
    end_time=dt.datetime(2025, 6, 30),
)
print(f"   查询到 {len(q2)} 条")

print("\n2c. 按产业链模块'新能源'查询:")
q3 = manager.query_history(industry_chain_module="新能源")
assert len(q3) == 1 and "比亚迪" in q3[0].enterprise_name
print(f"   正确: {q3[0].enterprise_name}")

print("\n2d. 按精确版本号 'v1.0.0' 查询:")
q4 = manager.query_history(version="v1.0.0")
assert len(q4) == 1 and q4[0].id == "OLD-0001"
print(f"   正确: {q4[0].id}")

print("\n" + "=" * 60)
print("修复验证 3: 查询与批量导出一致性")
print("=" * 60)

records_q = manager.query_history(enterprise_name="比亚迪")
export_paths = manager.export_records(enterprise_name="比亚迪")
print(f"查询返回 {len(records_q)} 条")

import csv, json
csv_count = 0
with open(export_paths["csv_path"], "r", encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    next(reader)  # 跳过表头
    csv_count = sum(1 for _ in reader)
print(f"CSV 导出 {csv_count} 条")

with open(export_paths["json_path"], "r", encoding="utf-8") as f:
    json_data = json.load(f)
print(f"JSON 导出 {len(json_data)} 条")

assert csv_count == len(records_q) == len(json_data), \
    f"不一致! 查询={len(records_q)}, CSV={csv_count}, JSON={len(json_data)}"
print("✓ 三条数目一致")

print("\n" + "=" * 60)
print("修复验证 4: 回滚报告通知角色完整 + 资金异常分析准确")
print("=" * 60)

from scf_manager.models import ReleaseRecord, RiskLevel, ReleaseStatus
from scf_manager.rollback import RollbackEngine
from scf_manager.compliance_logger import ComplianceLogger
from scf_manager.models import MonitoringMetrics
from scf_manager.config import THRESHOLDS

fake_release = ReleaseRecord(
    id="TEST-RB-001",
    version="v9.0.0",
    enterprise_id="ENT001",
    enterprise_name="测试企业",
    industry_chain_module="测试产业链",
    risk_level=RiskLevel.ROUTINE,
    loan_amount=1000000,
    stable_version="v8.9.0",
)
bad_metric = MonitoringMetrics(
    id="M1",
    release_id="TEST-RB-001",
    enterprise_id="ENT001",
    timestamp=dt.datetime(2025, 6, 19, 14, 30, 0),
    loan_success_rate=THRESHOLDS["loan_success_rate_min"] - 3.2,  # 低于阈值
    fund_arrival_delay_min=THRESHOLDS["fund_arrival_delay_max"] + 15,  # 超
    ar_anomaly_rate=THRESHOLDS["ar_anomaly_rate_max"] + 2.5,  # 超
    overdue_risk_score=THRESHOLDS["overdue_risk_score_max"] + 18,  # 超
    alert_triggered=True,
)
good_metric = MonitoringMetrics(
    id="M2",
    release_id="TEST-RB-001",
    enterprise_id="ENT001",
    timestamp=dt.datetime(2025, 6, 19, 14, 28, 0),
    loan_success_rate=99.1,
    fund_arrival_delay_min=5.2,
    ar_anomaly_rate=1.0,
    overdue_risk_score=30.0,
    alert_triggered=False,
)

rb = RollbackEngine(ComplianceLogger())
rec = rb.execute_rollback(
    release=fake_release,
    trigger_reason="测试回滚",
    monitoring_metrics=[good_metric, bad_metric],
)

print(f"\n✓ 回滚记录: {rec.id}")
print(f"✓ 通知角色数: {len(rec.notified_roles)}")
print(f"  角色列表: {rec.notified_roles}")
assert "业务审批人" in rec.notified_roles
assert "风控审批人" in rec.notified_roles
assert "资金审批人" in rec.notified_roles
assert "核心企业对接人" in rec.notified_roles
print("✓ 业务、风控、资金、核心企业对接人 都在通知列表中")

print(f"\n资金异常原因分析:")
print(rec.fund_anomaly_reason)
assert "放款成功率低" in rec.fund_anomaly_reason
assert "资金到账延迟高" in rec.fund_anomaly_reason
assert "应收账款异常率高" in rec.fund_anomaly_reason
assert "逾期风险高" in rec.fund_anomaly_reason
print("✓ 4 项超限指标全部被正确识别")

print(f"\n回滚报告文件: {rec.report_path}")
with open(rec.report_path, "r", encoding="utf-8") as f:
    report = f.read()
assert "业务审批人" in report and "核心企业对接人" in report, "报告中缺通知角色"
assert "放款成功率低" in report, "报告中缺异常分析"
print("✓ 回滚报告中正确包含通知角色列表和资金异常原因")

print("\n" + "=" * 60)
print("修复验证 5: 调度器能正常启动/停止 (不崩溃)")
print("=" * 60)

import time as _tm
manager.start_weekly_scheduler()
_tm.sleep(2)
manager.stop_weekly_scheduler()
print("✓ 调度器启动 2 秒后正常停止")

print("\n" + "=" * 60)
print("全部 5 项修复验证通过 ✓")
print("=" * 60)
manager.shutdown()
