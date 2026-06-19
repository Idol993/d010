from .models import ReleaseRecord, ReleaseStatus, RiskLevel
from .config import GRAYSCALE_PHASES


class GrayscaleRolloutEngine:

    def __init__(self):
        self._phase_tracking: dict[str, int] = {}

    def start_grayscale(self, release: ReleaseRecord) -> ReleaseRecord:
        release.status = ReleaseStatus.GRAYSCALE_ROLLOUT
        release.grayscale_phase = 1
        self._phase_tracking[release.id] = 1
        return release

    def advance_phase(self, release: ReleaseRecord) -> ReleaseRecord:
        current = release.grayscale_phase
        next_phase = current + 1

        if next_phase < 4:
            release.grayscale_phase = next_phase
            self._phase_tracking[release.id] = next_phase
            percentage = GRAYSCALE_PHASES[next_phase]
            print(f"灰度推进: 阶段 {next_phase}, 流量比例 {percentage:.0%}")
        elif next_phase == 4:
            release.grayscale_phase = 4
            release.status = ReleaseStatus.FULLY_RELEASED
            self._phase_tracking[release.id] = 4
            percentage = GRAYSCALE_PHASES[4]
            print(f"灰度推进: 阶段 4, 流量比例 {percentage:.0%} — 全量发布")
        else:
            print("已在全量发布阶段，无法继续推进")

        return release

    def get_phase_percentage(self, phase: int) -> float:
        return GRAYSCALE_PHASES.get(phase, 0.0)

    def can_advance(self, release: ReleaseRecord, monitoring_metrics: list) -> bool:
        if not monitoring_metrics:
            return True

        recent = monitoring_metrics[-3:]
        avg_loan_success_rate = sum(m.loan_success_rate for m in recent) / len(recent)
        avg_ar_anomaly_rate = sum(m.ar_anomaly_rate for m in recent) / len(recent)

        return avg_loan_success_rate >= 95.0 and avg_ar_anomaly_rate <= 5.0
