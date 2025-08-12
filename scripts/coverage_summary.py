#!/usr/bin/env python3
"""
Generate a coverage summary from coverage.json
"""

import json
import sys
from pathlib import Path


def main():
    coverage_file = Path("coverage.json")

    if not coverage_file.exists():
        print("❌ coverage.json not found. Run tests with coverage first:")
        print("   make coverage")
        sys.exit(1)

    with open(coverage_file) as f:
        data = json.load(f)

    totals = data.get("totals", {})
    covered_lines = totals.get("covered_lines", 0)
    missing_lines = totals.get("missing_lines", 0)
    total_lines = covered_lines + missing_lines

    if total_lines == 0:
        coverage_percent = 0
    else:
        coverage_percent = (covered_lines / total_lines) * 100

    branch_covered = totals.get("covered_branches", 0)
    branch_missing = totals.get("missing_branches", 0)
    total_branches = branch_covered + branch_missing

    if total_branches == 0:
        branch_percent = 0
    else:
        branch_percent = (branch_covered / total_branches) * 100

    print("📊 Coverage Summary")
    print("==================")
    print(f"Lines:    {covered_lines:4d}/{total_lines:4d} ({coverage_percent:5.1f}%)")
    print(f"Branches: {branch_covered:4d}/{total_branches:4d} ({branch_percent:5.1f}%)")

    # Color coding based on coverage
    if coverage_percent >= 90:
        status = "🟢 Excellent"
    elif coverage_percent >= 80:
        status = "🟡 Good"
    elif coverage_percent >= 70:
        status = "🟠 Fair"
    else:
        status = "🔴 Needs Improvement"

    print(f"Status:   {status}")

    # Show files with lowest coverage
    files = data.get("files", {})
    file_coverage = []

    for filepath, file_data in files.items():
        summary = file_data.get("summary", {})
        covered = summary.get("covered_lines", 0)
        missing = summary.get("missing_lines", 0)
        total = covered + missing

        if total > 0:
            percent = (covered / total) * 100
            file_coverage.append((filepath, percent, covered, total))

    # Sort by coverage percentage
    file_coverage.sort(key=lambda x: x[1])

    print("\n📈 Top 10 files needing attention:")
    print("==================================")
    for filepath, percent, covered, total in file_coverage[:10]:
        if percent < 80:  # Only show files below 80%
            print(f"{percent:5.1f}% - {filepath}")

    # Summary for badge generation
    badge_color = (
        "brightgreen"
        if coverage_percent >= 90
        else "green"
        if coverage_percent >= 80
        else "yellow"
        if coverage_percent >= 70
        else "orange"
        if coverage_percent >= 60
        else "red"
    )

    print(f"\n🏆 Badge: coverage-{coverage_percent:.0f}%25-{badge_color}")


if __name__ == "__main__":
    main()
