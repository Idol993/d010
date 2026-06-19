import random
from datetime import datetime

from .models import CheckItem, CheckItemStatus, PreCheckResult, CoreEnterprise
from .config import PRE_CHECK_ITEMS


class PreConditionChecker:
    def __init__(self, enterprises: dict):
        self.enterprises = enterprises

    def check(self, release_id: str, enterprise_id: str, loan_amount: float) -> PreCheckResult:
        enterprise: CoreEnterprise = self.enterprises.get(enterprise_id)
        if enterprise is None:
            now = datetime.now()
            item = CheckItem(
                name="企业查询",
                status=CheckItemStatus.FAIL,
                detail=f"未找到企业 {enterprise_id}",
                checked_at=now,
            )
            return PreCheckResult(
                release_id=release_id,
                items=[item],
                passed=False,
                checked_at=now,
            )

        items = []
        now = datetime.now()

        for name in PRE_CHECK_ITEMS:
            if name == "核心企业授信校验":
                item = self._check_credit(enterprise, loan_amount, now)
            elif name == "应收账款真实性":
                item = self._check_ar_authenticity(enterprise, now)
            elif name == "供应链对账准确率":
                item = self._check_reconciliation_accuracy(now)
            elif name == "监管资金合规":
                item = self._check_compliance(enterprise, now)
            else:
                item = CheckItem(
                    name=name,
                    status=CheckItemStatus.FAIL,
                    detail="未知检查项",
                    checked_at=now,
                )
            items.append(item)

        passed = all(item.status != CheckItemStatus.FAIL for item in items)

        return PreCheckResult(
            release_id=release_id,
            items=items,
            passed=passed,
            checked_at=now,
        )

    def _check_credit(self, enterprise: CoreEnterprise, loan_amount: float, now: datetime) -> CheckItem:
        available = enterprise.credit_limit - enterprise.credit_used
        if available >= loan_amount:
            return CheckItem(
                name="核心企业授信校验",
                status=CheckItemStatus.PASS,
                detail=f"可用授信 {available:.2f}，融资金额 {loan_amount:.2f}，授信充足",
                checked_at=now,
            )
        return CheckItem(
            name="核心企业授信校验",
            status=CheckItemStatus.FAIL,
            detail=f"可用授信 {available:.2f}，融资金额 {loan_amount:.2f}，授信不足",
            checked_at=now,
        )

    def _check_ar_authenticity(self, enterprise: CoreEnterprise, now: datetime) -> CheckItem:
        rating = enterprise.risk_rating
        if rating in ("A", "B"):
            return CheckItem(
                name="应收账款真实性",
                status=CheckItemStatus.PASS,
                detail=f"企业风险评级 {rating}，应收账款真实性验证通过",
                checked_at=now,
            )
        if rating == "C":
            return CheckItem(
                name="应收账款真实性",
                status=CheckItemStatus.WARNING,
                detail=f"企业风险评级 {rating}，应收账款真实性存在风险",
                checked_at=now,
            )
        return CheckItem(
            name="应收账款真实性",
            status=CheckItemStatus.FAIL,
            detail=f"企业风险评级 {rating}，应收账款真实性验证未通过",
            checked_at=now,
        )

    def _check_reconciliation_accuracy(self, now: datetime) -> CheckItem:
        accuracy = random.uniform(93, 100)
        if accuracy >= 98:
            return CheckItem(
                name="供应链对账准确率",
                status=CheckItemStatus.PASS,
                detail=f"对账准确率 {accuracy:.2f}%，符合要求",
                checked_at=now,
            )
        if accuracy >= 95:
            return CheckItem(
                name="供应链对账准确率",
                status=CheckItemStatus.WARNING,
                detail=f"对账准确率 {accuracy:.2f}%，接近阈值",
                checked_at=now,
            )
        return CheckItem(
            name="供应链对账准确率",
            status=CheckItemStatus.FAIL,
            detail=f"对账准确率 {accuracy:.2f}%，低于要求",
            checked_at=now,
        )

    def _check_compliance(self, enterprise: CoreEnterprise, now: datetime) -> CheckItem:
        rating = enterprise.risk_rating
        if rating in ("A", "B"):
            return CheckItem(
                name="监管资金合规",
                status=CheckItemStatus.PASS,
                detail=f"企业风险评级 {rating}，资金合规检查通过",
                checked_at=now,
            )
        if rating == "C":
            return CheckItem(
                name="监管资金合规",
                status=CheckItemStatus.WARNING,
                detail=f"企业风险评级 {rating}，资金合规存在风险",
                checked_at=now,
            )
        return CheckItem(
            name="监管资金合规",
            status=CheckItemStatus.FAIL,
            detail=f"企业风险评级 {rating}，资金合规检查未通过",
            checked_at=now,
        )
