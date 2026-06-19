
from scf_manager.engine import SCFReleaseManager
import datetime

m = SCFReleaseManager()
print("=" * 60)
print("第四轮功能验证")
print("=" * 60)

print()
print("[1/6] 历史周报列表")
reports = m.list_weekly_reports()
print(f"  ✓ 共 {len(reports)} 份历史周报")

print()
print("[2/6] 审计时间线（选第一条发布）")
r = m._releases[0] if m._releases else None
if r:
    events = m.show_audit_timeline(r.id)
    print(f"  ✓ 时间线事件数: {len(events)}")

print()
print("[3/6] 导出审计时间线 CSV")
if r:
    path = m.export_audit_timeline_csv(r.id)
    if path:
        print(f"  ✓ 导出成功: {path}")

print()
print("[4/6] 补录回滚报告")
rolled_back = [x for x in m._releases if x.rolled_back_at or x.status.value in ("已回滚", "已恢复稳定版本")]
if rolled_back:
    print(f"  找到 {len(rolled_back)} 条已回滚发布，选第一条测试")
    result = m.supplement_rollback_report(rolled_back[0].id)
    if result:
        print(f"  ✓ 补录完成: {result.id}")
        print(f"    TXT: {result.report_path}")
        if hasattr(result, 'report_pdf_path') and result.report_pdf_path:
            print(f"    PDF: {result.report_pdf_path}")
else:
    print("  - 跳过: 没有已回滚的发布记录")

print()
print("[5/6] 通知重发（重发失败通知）")
failed = m._notification_manager.query(status="发送失败")
if failed:
    print(f"  找到 {len(failed)} 条失败通知，测试重发第一条")
    resent = m.resend_notification(failed[0].id)
    print(f"  ✓ 重发完成: {len(resent)} 条新记录")
else:
    print("  - 跳过: 没有失败通知（失败率只有 5%）")

print()
print("[6/6] 重新生成历史周报（另存模式）")
if reports:
    ws = reports[0]["week_start"]
    print(f"  重新生成 {ws.strftime('%Y-%m-%d')} 周期周报 (另存模式)")
    result = m.regenerate_weekly_report(ws, mode="save_as")
    if result:
        print(f"  ✓ 重新生成成功")
        print(f"    PDF: {result['pdf']}")
        print(f"    Excel: {result['excel']}")

print()
print("=" * 60)
print("所有验证完成!")
print("=" * 60)
