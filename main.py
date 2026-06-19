#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scf_manager.engine import SCFReleaseManager
from scf_manager.models import RiskLevel


def print_menu():
    print(f"\n{'='*60}")
    print("  供应链金融系统 - 放款策略发布与资金安全回滚管理")
    print(f"{'='*60}")
    print("  1.  提交发布申请")
    print("  2.  审批发布 (自动通过)")
    print("  3.  拒绝发布")
    print("  4.  灰度推进")
    print("  5.  查看核心企业列表")
    print("  6.  查看发布记录列表")
    print("  7.  查看发布详情")
    print("  8.  创建回滚演练")
    print("  9.  执行回滚演练")
    print("  10. 生成周报 (PDF + Excel) [手动]")
    print("  11. 指定日期范围生成周报")
    print("  12. 查询历史发布记录")
    print("  13. 批量导出记录")
    print("  14. 查看资金合规日志")
    print("  15. 查看通知流水")
    print("  16. 发布风险看板")
    print("  17. 导出风险看板 Excel")
    print("  18. 重新生成回滚报告 (PDF+TXT)")
    print("  19. 补录回滚报告 (从发布记录反推)")
    print("  20. 历史周报列表 (报表中心)")
    print("  21. 删除历史周报")
    print("  22. 重新生成历史周报 (覆盖/另存)")
    print("  23. 重发失败通知")
    print("  24. 重发指定通知")
    print("  25. 审计时间线 (按发布ID)")
    print("  26. 导出审计时间线 CSV")
    print("  27. 运行完整演示流程")
    print("  28. 启动每周一自动生成周报调度器")
    print("  29. 停止每周一自动生成周报调度器")
    print("  30. 切换到长期运行模式 (保持调度器、监控器活跃)")
    print("  0.  退出")
    print(f"{'='*60}")


def run_demo(manager: SCFReleaseManager):
    print(f"\n{'#'*60}")
    print("#  供应链金融系统完整演示流程")
    print(f"{'#'*60}")

    print("\n>>> 步骤1: 查看核心企业列表")
    manager.list_enterprises()

    print("\n>>> 步骤2: 提交常规放款发布申请")
    record1 = manager.submit_release(
        enterprise_id="ENT001",
        version="v3.2.0",
        industry_chain_module="通信-5G基站",
        loan_amount=5000000,
        risk_level=RiskLevel.ROUTINE,
        description="华为5G基站供应链融资-常规迭代",
    )

    if record1 and record1.pre_check_result and record1.pre_check_result.passed:
        print("\n>>> 步骤3: 自动审批通过")
        record1 = manager.approve_release(record1.id, auto_approve=True)

    print("\n>>> 步骤4: 提交紧急资金故障发布申请")
    record2 = manager.submit_release(
        enterprise_id="ENT002",
        version="v3.2.1-hotfix",
        industry_chain_module="新能源-电池",
        loan_amount=8000000,
        risk_level=RiskLevel.EMERGENCY,
        description="比亚迪电池供应链紧急融资",
    )

    if record2 and record2.pre_check_result and record2.pre_check_result.passed:
        print("\n>>> 步骤5: 紧急发布审批")
        record2 = manager.approve_release(record2.id, auto_approve=True)

    print("\n>>> 步骤6: 提交核心企业风险发布申请")
    record3 = manager.submit_release(
        enterprise_id="ENT004",
        version="v3.3.0-risk",
        industry_chain_module="工程机械-挖掘机",
        loan_amount=3000000,
        risk_level=RiskLevel.CORE_RISK,
        description="三一重工风险评级调整发布",
    )

    print("\n>>> 步骤7: 提交D级风险企业发布申请（预期前置检查不通过）")
    record4 = manager.submit_release(
        enterprise_id="ENT005",
        version="v3.3.1",
        industry_chain_module="化工-塑料",
        loan_amount=1000000,
        risk_level=RiskLevel.ROUTINE,
        description="D级风险企业融资申请",
    )

    print("\n>>> 步骤8: 灰度推进（如果条件允许）")
    if record1 and record1.status.value == "灰度推送中":
        manager.advance_grayscale(record1.id)
        manager.advance_grayscale(record1.id)

    print("\n>>> 步骤9: 创建并执行回滚演练")
    drill = manager.create_drill("供应链金融季度回滚演练")
    manager.execute_drill(drill.id)

    print("\n>>> 步骤10: 查看发布详情")
    if record1:
        manager.show_release_detail(record1.id)

    print("\n>>> 步骤11: 生成周报")
    manager.generate_weekly_report()

    print("\n>>> 步骤12: 查询历史记录")
    manager.query_history(enterprise_name="华为")

    print("\n>>> 步骤13: 查看资金合规日志")
    manager.list_compliance_logs()

    manager.shutdown()

    print(f"\n{'#'*60}")
    print("#  演示流程完成！")
    print(f"{'#'*60}")


def interactive_mode():
    manager = SCFReleaseManager()

    while True:
        print_menu()
        choice = input("\n请选择操作 (0-30): ").strip()

        if choice == "0":
            manager.shutdown()
            print("感谢使用，再见！")
            break

        elif choice == "1":
            manager.list_enterprises()
            eid = input("企业ID: ").strip()
            ver = input("版本号: ").strip()
            module = input("产业链模块: ").strip()
            amount = float(input("放款金额: ").strip())
            print("风险级别: 1-常规放款迭代  2-紧急资金故障  3-核心企业风险")
            rl_choice = input("选择 (1-3, 默认1): ").strip() or "1"
            rl_map = {"1": RiskLevel.ROUTINE, "2": RiskLevel.EMERGENCY, "3": RiskLevel.CORE_RISK}
            desc = input("描述 (可选): ").strip()
            manager.submit_release(
                enterprise_id=eid,
                version=ver,
                industry_chain_module=module,
                loan_amount=amount,
                risk_level=rl_map.get(rl_choice, RiskLevel.ROUTINE),
                description=desc,
            )

        elif choice == "2":
            rid = input("发布ID: ").strip()
            auto = input("自动审批全部步骤? (y/n, 默认y): ").strip().lower() != "n"
            manager.approve_release(rid, auto_approve=auto)

        elif choice == "3":
            rid = input("发布ID: ").strip()
            reason = input("拒绝原因: ").strip()
            manager.reject_release(rid, reason)

        elif choice == "4":
            rid = input("发布ID: ").strip()
            manager.advance_grayscale(rid)

        elif choice == "5":
            manager.list_enterprises()

        elif choice == "6":
            manager.list_releases()

        elif choice == "7":
            rid = input("发布ID: ").strip()
            manager.show_release_detail(rid)

        elif choice == "8":
            name = input("演练名称 (默认: 供应链金融回滚演练): ").strip() or "供应链金融回滚演练"
            manager.create_drill(name)

        elif choice == "9":
            manager.list_drills() if hasattr(manager, 'list_drills') else None
            did = input("演练ID: ").strip()
            manager.execute_drill(did)

        elif choice == "10":
            manager.generate_weekly_report()

        elif choice == "11":
            print("请输入周报日期范围:")
            start_s = input("起始日期 (YYYY-MM-DD): ").strip()
            end_s = input("结束日期 (YYYY-MM-DD, 留空则默认+7天): ").strip()
            import datetime as _dt
            week_start = None
            week_end = None
            for _fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    week_start = _dt.datetime.strptime(start_s, _fmt)
                    break
                except ValueError:
                    continue
            if not week_start:
                print("[错误] 起始日期格式不正确")
                continue
            if end_s:
                for _fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        week_end = _dt.datetime.strptime(end_s, _fmt)
                        break
                    except ValueError:
                        continue
            manager.generate_weekly_report_by_date(week_start, week_end)

        elif choice == "12":
            print("查询条件 (留空跳过):")
            start_s = input("发布起始时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS): ").strip()
            end_s = input("发布结束时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS): ").strip()
            ent = input("核心企业名称 (支持模糊): ").strip()
            module = input("产业链模块 (支持模糊): ").strip()
            ver = input("版本号 (精确匹配): ").strip()
            kwargs = {}
            import datetime as _dt
            if start_s:
                for _fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        kwargs["start_time"] = _dt.datetime.strptime(start_s, _fmt)
                        break
                    except ValueError:
                        continue
            if end_s:
                for _fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        kwargs["end_time"] = _dt.datetime.strptime(end_s, _fmt)
                        break
                    except ValueError:
                        continue
            if ent:
                kwargs["enterprise_name"] = ent
            if module:
                kwargs["industry_chain_module"] = module
            if ver:
                kwargs["version"] = ver
            manager.query_history(**kwargs)

        elif choice == "13":
            print("导出条件 (留空导出全部, 筛选条件与查询一致):")
            start_s = input("发布起始时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS): ").strip()
            end_s = input("发布结束时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS): ").strip()
            ent = input("核心企业名称 (支持模糊): ").strip()
            module = input("产业链模块 (支持模糊): ").strip()
            ver = input("版本号 (精确匹配): ").strip()
            kwargs = {}
            import datetime as _dt
            if start_s:
                for _fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        kwargs["start_time"] = _dt.datetime.strptime(start_s, _fmt)
                        break
                    except ValueError:
                        continue
            if end_s:
                for _fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        kwargs["end_time"] = _dt.datetime.strptime(end_s, _fmt)
                        break
                    except ValueError:
                        continue
            if ent:
                kwargs["enterprise_name"] = ent
            if module:
                kwargs["industry_chain_module"] = module
            if ver:
                kwargs["version"] = ver
            manager.export_records(**kwargs)

        elif choice == "14":
            rid = input("发布ID (留空查看全部): ").strip()
            manager.list_compliance_logs(release_id=rid)

        elif choice == "15":
            rid = input("发布ID (留空查看全部): ").strip()
            manager.list_notifications(release_id=rid)

        elif choice == "16":
            manager.show_risk_dashboard()

        elif choice == "17":
            manager.export_dashboard_excel()

        elif choice == "18":
            rid = input("发布ID (或回滚ID, 二选一): ").strip()
            if rid.startswith("rb") or rid.startswith("RB") or len(rid) < 6:
                manager.regenerate_rollback_report(rollback_id=rid)
            else:
                manager.regenerate_rollback_report(release_id=rid)

        elif choice == "19":
            rid = input("发布ID: ").strip()
            manager.supplement_rollback_report(rid)

        elif choice == "20":
            print("历史周报筛选 (留空跳过):")
            ws_from = input("周期起始从 (YYYY-MM-DD): ").strip()
            ws_to = input("周期起始至 (YYYY-MM-DD): ").strip()
            rtype = input("报表类型 (PDF/Excel, 留空全部): ").strip()
            import datetime as _dt
            kwargs = {}
            if ws_from:
                for _fmt in ("%Y-%m-%d", "%Y%m%d"):
                    try:
                        kwargs["week_start_from"] = _dt.datetime.strptime(ws_from, _fmt)
                        break
                    except ValueError:
                        continue
            if ws_to:
                for _fmt in ("%Y-%m-%d", "%Y%m%d"):
                    try:
                        kwargs["week_start_to"] = _dt.datetime.strptime(ws_to, _fmt)
                        break
                    except ValueError:
                        continue
            if rtype:
                kwargs["report_type"] = rtype
            reports = manager.list_weekly_reports(**kwargs)
            if reports:
                print("\n操作提示: 输入序号可打开对应文件路径")
                idx = input("序号 (留空跳过): ").strip()
                if idx and idx.isdigit():
                    i = int(idx) - 1
                    if 0 <= i < len(reports):
                        r = reports[i]
                        if r["pdf_path"]:
                            print(f"  PDF: {r['pdf_path']}")
                        if r["excel_path"]:
                            print(f"  Excel: {r['excel_path']}")

        elif choice == "21":
            date_str = input("要删除的周报周期起始日期 (YYYY-MM-DD): ").strip()
            import datetime as _dt
            week_start = None
            for _fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d"):
                try:
                    week_start = _dt.datetime.strptime(date_str, _fmt)
                    break
                except ValueError:
                    continue
            if week_start:
                manager.delete_weekly_report(week_start)
            else:
                print("[错误] 日期格式不正确")

        elif choice == "22":
            date_str = input("要重新生成的周报周期起始日期 (YYYY-MM-DD): ").strip()
            import datetime as _dt
            week_start = None
            for _fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d"):
                try:
                    week_start = _dt.datetime.strptime(date_str, _fmt)
                    break
                except ValueError:
                    continue
            if not week_start:
                print("[错误] 日期格式不正确")
                continue
            mode = input("重新生成模式: 1=覆盖原文件, 2=另存为新文件 (默认2): ").strip() or "2"
            mode_str = "overwrite" if mode == "1" else "save_as"
            manager.regenerate_weekly_report(week_start, mode=mode_str)

        elif choice == "23":
            rid = input("发布ID (留空重发所有失败通知): ").strip()
            manager.resend_failed_notifications(release_id=rid)

        elif choice == "24":
            nid = input("通知ID: ").strip()
            manager.resend_notification(nid)

        elif choice == "25":
            rid = input("发布ID: ").strip()
            manager.show_audit_timeline(rid)

        elif choice == "26":
            rid = input("发布ID: ").strip()
            manager.export_audit_timeline_csv(rid)

        elif choice == "27":
            run_demo(manager)

        elif choice == "28":
            manager.start_weekly_scheduler()
            print("每周一自动生成周报调度器已启动（每周一09:00自动运行）")

        elif choice == "29":
            manager.stop_weekly_scheduler()
            print("每周一自动生成周报调度器已停止")

        elif choice == "30":
            manager.start_weekly_scheduler()
            print("\n进入长期运行模式：")
            print("  - 每周一09:00 自动生成周报")
            print("  - 保持所有资金监控线程活跃")
            print("按 Ctrl+C 退出此模式并返回菜单\n")
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n已退出长期运行模式，返回菜单")

        else:
            print("无效选择，请重新输入")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        manager = SCFReleaseManager()
        run_demo(manager)
        manager.shutdown()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
