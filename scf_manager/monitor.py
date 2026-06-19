import datetime
import random
import threading
import time
import json
import os

from .models import MonitoringMetrics, ReleaseRecord, ReleaseStatus
from .config import MONITOR_INTERVAL_SECONDS, THRESHOLDS


class FundMonitor:
    def __init__(self):
        self._monitoring_data: list[MonitoringMetrics] = []
        self._active_monitors: dict[str, threading.Thread] = {}
        self._stop_flags: dict[str, bool] = {}
        self._data_file = "scf_manager/data/monitoring.json"
        self._load()

    def start_monitoring(self, release_id: str, enterprise_id: str, on_threshold_breach: callable = None) -> None:
        self._stop_flags[release_id] = False

        def _monitor_loop():
            while not self._stop_flags.get(release_id, True):
                metrics = self._collect_metrics(release_id, enterprise_id)
                is_breached, breach_details = self.check_thresholds(metrics)
                if is_breached:
                    metrics.alert_triggered = True
                self._monitoring_data.append(metrics)
                try:
                    self._save()
                except Exception as _e:
                    pass
                if is_breached and on_threshold_breach:
                    try:
                        on_threshold_breach(release_id, metrics)
                    except Exception as _e:
                        pass
                time.sleep(MONITOR_INTERVAL_SECONDS)

        thread = threading.Thread(target=_monitor_loop, daemon=True)
        self._active_monitors[release_id] = thread
        thread.start()

    def stop_monitoring(self, release_id: str) -> None:
        self._stop_flags[release_id] = True
        thread = self._active_monitors.pop(release_id, None)
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5)

    def stop_all(self) -> None:
        for release_id in list(self._active_monitors.keys()):
            self.stop_monitoring(release_id)

    def get_latest_metrics(self, release_id: str, count: int = 5) -> list:
        matched = [m for m in self._monitoring_data if m.release_id == release_id]
        return matched[-count:]

    def check_thresholds(self, metrics: MonitoringMetrics) -> tuple:
        breaches = []
        if metrics.loan_success_rate < THRESHOLDS["loan_success_rate_min"]:
            breaches.append(
                f"loan_success_rate {metrics.loan_success_rate:.2f}% below minimum {THRESHOLDS['loan_success_rate_min']}%"
            )
        if metrics.fund_arrival_delay_min > THRESHOLDS["fund_arrival_delay_max"]:
            breaches.append(
                f"fund_arrival_delay {metrics.fund_arrival_delay_min:.2f}min exceeds maximum {THRESHOLDS['fund_arrival_delay_max']}min"
            )
        if metrics.ar_anomaly_rate > THRESHOLDS["ar_anomaly_rate_max"]:
            breaches.append(
                f"ar_anomaly_rate {metrics.ar_anomaly_rate:.2f}% exceeds maximum {THRESHOLDS['ar_anomaly_rate_max']}%"
            )
        if metrics.overdue_risk_score > THRESHOLDS["overdue_risk_score_max"]:
            breaches.append(
                f"overdue_risk_score {metrics.overdue_risk_score:.2f} exceeds maximum {THRESHOLDS['overdue_risk_score_max']}"
            )
        return (len(breaches) > 0, breaches)

    def _collect_metrics(self, release_id: str, enterprise_id: str) -> MonitoringMetrics:
        return MonitoringMetrics(
            release_id=release_id,
            enterprise_id=enterprise_id,
            timestamp=datetime.datetime.now(),
            loan_success_rate=round(random.uniform(88, 100), 2),
            fund_arrival_delay_min=round(random.uniform(0, 45), 2),
            ar_anomaly_rate=round(random.uniform(0, 8), 2),
            overdue_risk_score=round(random.uniform(20, 90), 2),
        )

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._data_file), exist_ok=True)
        data = []
        for m in self._monitoring_data:
            data.append({
                "id": m.id,
                "release_id": m.release_id,
                "enterprise_id": m.enterprise_id,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "loan_success_rate": m.loan_success_rate,
                "fund_arrival_delay_min": m.fund_arrival_delay_min,
                "ar_anomaly_rate": m.ar_anomaly_rate,
                "overdue_risk_score": m.overdue_risk_score,
                "alert_triggered": m.alert_triggered,
            })
        with open(self._data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        if not os.path.exists(self._data_file):
            return
        with open(self._data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            self._monitoring_data.append(MonitoringMetrics(
                id=item.get("id", ""),
                release_id=item.get("release_id", ""),
                enterprise_id=item.get("enterprise_id", ""),
                timestamp=datetime.datetime.fromisoformat(item["timestamp"]) if item.get("timestamp") else None,
                loan_success_rate=item.get("loan_success_rate", 0.0),
                fund_arrival_delay_min=item.get("fund_arrival_delay_min", 0.0),
                ar_anomaly_rate=item.get("ar_anomaly_rate", 0.0),
                overdue_risk_score=item.get("overdue_risk_score", 0.0),
                alert_triggered=item.get("alert_triggered", False),
            ))
