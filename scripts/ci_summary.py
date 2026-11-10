"""Summarise JUnit reports as a Markdown table for the GitHub Actions run page.

    python3 scripts/ci_summary.py reports/*.xml >> "$GITHUB_STEP_SUMMARY"

Known bugs (pytest xfail) are counted separately from skips, so the page shows
how many tests are waiting on an open bug issue. Vitest's JUnit reporter records
`it.fails` tests as passed, so frontend known bugs appear under "passed".
Standard library only, so it runs on the runner's system Python.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

COLUMNS = ("passed", "failed", "skipped", "known bugs")


def classify(case: ET.Element) -> str:
    if case.find("failure") is not None or case.find("error") is not None:
        return "failed"
    skipped = case.find("skipped")
    if skipped is not None:
        # pytest writes xfail as <skipped type="pytest.xfail">.
        return "known bugs" if skipped.get("type") == "pytest.xfail" else "skipped"
    return "passed"


def summarise(path: Path) -> tuple[dict[str, int], list[str]]:
    counts = dict.fromkeys(COLUMNS, 0)
    failures = []
    for case in ET.parse(path).getroot().iter("testcase"):
        outcome = classify(case)
        counts[outcome] += 1
        if outcome == "failed":
            failures.append(f"{case.get('classname', '')}::{case.get('name', '')}".strip(":"))
    return counts, failures


def render(paths: list[Path]) -> str:
    lines = ["| Report | " + " | ".join(COLUMNS) + " |", "| --- |" + " ---: |" * len(COLUMNS)]
    all_failures = []
    for path in paths:
        if not path.is_file():
            lines.append(f"| `{path.name}` | not produced (the step did not run) |" + " |" * (len(COLUMNS) - 1))
            continue
        try:
            counts, failures = summarise(path)
        except ET.ParseError as error:
            lines.append(f"| `{path.name}` | unreadable: {error} |" + " |" * (len(COLUMNS) - 1))
            continue
        lines.append(f"| `{path.stem}` | " + " | ".join(str(counts[c]) for c in COLUMNS) + " |")
        all_failures += failures
    if all_failures:
        lines += ["", "**Failed tests**", ""] + [f"- `{name}`" for name in all_failures]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: ci_summary.py REPORT.xml [REPORT.xml ...]")
    print(render([Path(arg) for arg in sys.argv[1:]]))
