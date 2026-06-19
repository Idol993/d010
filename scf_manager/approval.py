from datetime import datetime

from .models import ApprovalStep, ApprovalWorkflow, ApprovalRole, ApprovalStatus, RiskLevel
from .config import RISK_LEVEL_APPROVAL_ORDER, DEFAULT_APPROVERS


class ApprovalWorkflowGenerator:

    def generate(self, release_id: str, risk_level: RiskLevel) -> ApprovalWorkflow:
        order = RISK_LEVEL_APPROVAL_ORDER[risk_level]
        steps = []
        for role in order:
            steps.append(
                ApprovalStep(
                    release_id=release_id,
                    role=role,
                    approver_name=DEFAULT_APPROVERS[role],
                    status=ApprovalStatus.PENDING,
                )
            )
        return ApprovalWorkflow(
            release_id=release_id,
            risk_level=risk_level,
            steps=steps,
            current_step_index=0,
            created_at=datetime.now(),
        )

    def approve_step(self, workflow: ApprovalWorkflow, step_index: int, comment: str = "") -> ApprovalWorkflow:
        step = workflow.steps[step_index]
        step.status = ApprovalStatus.APPROVED
        step.approved_at = datetime.now()
        step.comment = comment
        workflow.current_step_index = step_index + 1
        return workflow

    def reject_step(self, workflow: ApprovalWorkflow, step_index: int, comment: str = "") -> ApprovalWorkflow:
        step = workflow.steps[step_index]
        step.status = ApprovalStatus.REJECTED
        step.approved_at = datetime.now()
        step.comment = comment
        return workflow

    def is_fully_approved(self, workflow: ApprovalWorkflow) -> bool:
        return all(step.status == ApprovalStatus.APPROVED for step in workflow.steps)
