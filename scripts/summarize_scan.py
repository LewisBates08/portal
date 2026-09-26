"""Summarize an image scan without suppressing or reclassifying findings."""

import json
import os
from pathlib import Path

report = Path(os.environ["REPORT_PATH"])
with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
    summary.write(f"## {report.name}\n\n")
    if not report.exists():
        summary.write(
            "Scan report missing: scanner did not finish. This is not a clean result.\n"
        )
    else:
        data = json.loads(report.read_text())
        findings = [
            (
                v["VulnerabilityID"],
                v["PkgName"],
                v["InstalledVersion"],
                v.get("FixedVersion") or "No fix listed",
                v["Severity"],
            )
            for result in data.get("Results", [])
            for v in result.get("Vulnerabilities", [])
        ]
        summary.write(f"{len(findings)} reported HIGH/CRITICAL findings.\n\n")
        if findings:
            summary.write(
                "| Advisory | Package | Installed | Fixed | Severity |\n|---|---|---|---|---|\n"
            )
            for row in sorted(set(findings)):
                summary.write(
                    "| " + " | ".join(str(x).replace("|", "/") for x in row) + " |\n"
                )
