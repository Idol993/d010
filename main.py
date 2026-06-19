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
    print("  10. 生成周报 (PDF + Excel)")
    print("  11. 查询历史发布记录")
    print("  12. 批量导出记录")
    print("  13. 查看资金合规日志")
    print("  14. 运行完整演示流程")
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
        choice = input("\n请选择操作 (0-14): ").strip()

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
            print("查询条件 (留空跳过):")
            ent = input("核心企业名称: ").strip()
            ver = input("版本号: ").strip()
            module = input("产业链模块: ").strip()
            kwargs = {}
            if ent:
                kwargs["enterprise_name"] = ent
            if ver:
                kwargs["version"] = ver
            if module:
                kwargs["industry_chain_module"] = module
            manager.query_history(**kwargs)

        elif choice == "12":
            print("导出条件 (留空导出全部):")
            ent = input("核心企业名称: ").strip()
            kwargs = {}
            if ent:
                kwargs["enterprise_name"] = ent
            manager.export_records(**kwargs)

        elif choice == "13":
            rid = input("发布ID (留空查看全部): ").strip()
            manager.list_compliance_logs(release_id=rid)

        elif choice == "14":
            run_demo(manager)

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
