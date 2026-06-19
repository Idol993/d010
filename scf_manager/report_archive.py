
import datetime
import os
import re

from .config import WEEKLY_REPORT_DIR


class WeeklyReportArchive:
    def __init__(self, report_dir: str = ""):
        self._report_dir = report_dir or WEEKLY_REPORT_DIR
        os.makedirs(self._report_dir, exist_ok=True)

    def list_reports(self) -> list:
        reports = {}
        if not os.path.isdir(self._report_dir):
            return []

        for filename in os.listdir(self._report_dir):
            filepath = os.path.join(self._report_dir, filename)
            if not os.path.isfile(filepath):
                continue

            date_match = re.search(r"weekly_(?:report|data)_(\d{8})", filename)
            if not date_match:
                continue
            date_str = date_match.group(1)

            try:
                week_start = datetime.datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                continue

            if week_start not in reports:
                reports[week_start] = {
                    "week_start": week_start,
                    "week_end": week_start + datetime.timedelta(days=7),
                    "pdf_path": "",
                    "excel_path": "",
                    "generated_at": None,
                    "file_types": [],
                }

            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))

            if filename.endswith(".pdf"):
                reports[week_start]["pdf_path"] = filepath
                reports[week_start]["file_types"].append("PDF")
                if reports[week_start]["generated_at"] is None or mtime > reports[week_start]["generated_at"]:
                    reports[week_start]["generated_at"] = mtime
            elif filename.endswith(".xlsx"):
                reports[week_start]["excel_path"] = filepath
                reports[week_start]["file_types"].append("Excel")
                if reports[week_start]["generated_at"] is None or mtime > reports[week_start]["generated_at"]:
                    reports[week_start]["generated_at"] = mtime

        result = list(reports.values())
        result.sort(key=lambda r: r["week_start"], reverse=True)
        return result

    def query(
        self,
        week_start_from: datetime.datetime = None,
        week_start_to: datetime.datetime = None,
        report_type: str = "",
    ) -> list:
        all_reports = self.list_reports()
        results = all_reports

        if week_start_from:
            results = [r for r in results if r["week_start"] >= week_start_from]
        if week_start_to:
            results = [r for r in results if r["week_start"] <= week_start_to]
        if report_type:
            rt = report_type.lower()
            if rt == "pdf":
                results = [r for r in results if r["pdf_path"]]
            elif rt in ("excel", "xlsx"):
                results = [r for r in results if r["excel_path"]]

        return results

    def get_by_week_start(self, week_start: datetime.datetime):
        reports = self.list_reports()
        for r in reports:
            if r["week_start"] == week_start:
                return r
        return None

    def delete_report(self, week_start: datetime.datetime) -> int:
        deleted = 0
        report = self.get_by_week_start(week_start)
        if not report:
            return 0

        if report["pdf_path"] and os.path.exists(report["pdf_path"]):
            os.remove(report["pdf_path"])
            deleted += 1
        if report["excel_path"] and os.path.exists(report["excel_path"]):
            os.remove(report["excel_path"])
            deleted += 1

        return deleted

    def get_report_dir(self) -> str:
        return self._report_dir
