"""
Dynamic PADER & Universal Report Generator
Author: Enterprise PV Engineering Team
Description: Generates fully formatted Markdown reports (report_output.md) 
             from any metrics payload or document state.
"""

import json
import os
import sys
from typing import Any, Dict

from src.generator import DynamicReportGenerator, PADERReportBuilder


def main():
    metrics_file = sys.argv[1] if len(sys.argv) > 1 else "metrics.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "report_output.md"

    if os.path.exists(metrics_file):
        with open(metrics_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"meta": {"data_type": "tabular"}, "kpi_cards": {"total_rows": 0}}

    builder = DynamicReportGenerator(data)
    report_content = builder.generate_full_report()

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"[OK] Safety report generated successfully at: '{output_file}'")


if __name__ == "__main__":
    main()