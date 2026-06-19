
import sys
sys.path.insert(0, '.')
from scf_manager.engine import SCFReleaseManager
from scf_manager.models import RiskLevel, ReleaseStatus
import datetime

print("=" * 60)
print("第三轮功能验证 (稳健版)")
print("=" * 60)

manager = SCFReleaseManager()

print(f"\n[1/7] 数据加载验证")
print(f"  ✓ 企业数: {len(manager._enterprises)}")
print(f"  ✓ 发布数: {len(manager._releases)}")
print(f"  ✓ 回滚数: {len(manager._rollback_engine.get_records())}")
print(f"  ✓ 通知数: {len(manager._notification_manager.query())}")

print(f"\n[2/7] 历史发布时间筛选验证")
all_count = len(manager._releases)
# 全时间范围筛选，应该只包含已发布的
time_filtered = manager._history.query(
    records=manager._releases,
    start_time=datetime.datetime(2000, 1, 1),
    end_time=datetime.datetime(2099, 12, 31),
)
unreleased = [r for r in time_filtered if r.released_at is None]
print(f"  ✓ 总发布数: {all_count}")
print(f"  ✓ 时间筛选后: {len(time_filtered)} 条 (已发布)")
print(f"  ✓ 未发布混入: {len(unreleased)} 条 (应为 0)")

print(f"\n[3/7] 通知流水验证")
notifs = manager._notification_manager.query()
print(f"  ✓ 总通知数: {len(notifs)}")
if notifs:
    n = notifs[0]
    print(f"  ✓ 示例: {n.notification_type.value} -> {n.recipient_role} ({n.recipient_name})")
    print(f"    状态: {n.status.value}, 结果: {n.delivery_result}")
    print(f"    时间: {n.sent_at}")

print(f"\n[4/7] 风险看板验证")
manager.show_risk_dashboard()
print(f"  ✓ 风险看板显示正常")

print(f"\n[5/7] 风险看板 Excel 导出")
path = manager.export_dashboard_excel()
if path:
    print(f"  ✓ 导出成功: {path}")

print(f"\n[6/7] 自定义周报 + Top榜单")
week_start = datetime.datetime.now() - datetime.timedelta(days=90)
week_end = datetime.datetime.now()
result = manager.generate_weekly_report_by_date(week_start, week_end)
if result and result.get('stats'):
    stats = result['stats']
    print(f"  ✓ 周报生成成功")
    print(f"    周期: {stats.week_start.date()} ~ {stats.week_end.date()}")
    print(f"    发布数: {stats.total_releases}, 回滚数: {stats.rollback_count}")
    print(f"    Top回滚企业: {len(stats.top_rollback_enterprises)} 个")
    for i, item in enumerate(stats.top_rollback_enterprises[:3], 1):
        print(f"      {i}. {item['enterprise']} ({item['rollback_count']}次)")
    print(f"    Top告警模块: {len(stats.top_alert_modules)} 个")
    for i, item in enumerate(stats.top_alert_modules[:3], 1):
        print(f"      {i}. {item['module']} ({item['alert_count']}次)")

print(f"\n[7/7] 回滚报告重生成 (如果有回滚记录)")
rollbacks = manager._rollback_engine.get_records()
if rollbacks:
    rb = rollbacks[0]
    # 找一个有对应发布记录的回滚
    release = None
    for r in rollbacks:
        release = manager._find_release(r.release_id)
        if release:
            rb = r
            break
    if release:
        print(f"  找到回滚记录: {rb.id} (发布: {release.id})")
        result_rb = manager.regenerate_rollback_report(rollback_id=rb.id)
        if result_rb:
            print(f"  ✓ 报告重新生成成功")
            print(f"    TXT: {result_rb.report_path}")
            print(f"    PDF: {result_rb.report_pdf_path}")
    else:
        print(f"  - 跳过: 回滚记录无对应发布记录")
else:
    print(f"  - 跳过: 无回滚记录")

print("\n" + "=" * 60)
print("验证完成!")
print("=" * 60)
