"""
Unified Execution Orchestrator & Backend Server
Author: Enterprise AI Engineering Team
Description: Full pipeline execution orchestrator and CORS-enabled HTTP server.
             Ingests multi-format files, generates analytics/reports,
             audits governance compliance, and serves REST APIs for the UI Console.
"""

import json
import os
import sys
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional

# Standardize project relative imports
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from src.ingestion import UniversalIngestionEngine
from src.analytics import UniversalAnalyticsEngine
from src.generator import DynamicReportGenerator
from src.review import DynamicGovernanceEngine
from src.review_status_manager import ReviewStatusManager


CURRENT_DATASET_PATH: Optional[str] = None


def run_pipeline(input_file: Optional[str] = None) -> Dict[str, Any]:
    """Runs the complete end-to-end dynamic processing pipeline."""
    global CURRENT_DATASET_PATH
    project_dir = Path(__file__).parent.resolve()

    if not input_file:
        metrics_file = project_dir / "metrics.json"
        report_file = project_dir / "report_output.md"
        review_file = project_dir / "review_status.json"
        
        # If state files don't exist yet, return uninitialized
        if not metrics_file.exists():
            return {"status": "AWAITING_UPLOAD", "dataset_name": None}

        metrics_data = {}
        if metrics_file.exists():
            with open(metrics_file, "r", encoding="utf-8") as f:
                metrics_data = json.load(f)

        review_data = {}
        if review_file.exists():
            with open(review_file, "r", encoding="utf-8") as f:
                review_data = json.load(f)

        return {
            "status": "LOADED",
            "dataset_name": CURRENT_DATASET_PATH,
            "metrics": metrics_data,
            "review_status": review_data
        }

    CURRENT_DATASET_PATH = input_file
    target_path = project_dir / input_file if not Path(input_file).is_absolute() else Path(input_file)

    if not target_path.exists():
        raise FileNotFoundError(f"Target dataset file missing: {input_file}")

    print(f"\n[1/4] Ingesting multi-format file: {target_path.name}")
    parsed_data = UniversalIngestionEngine.parse_file(target_path)

    print(f"[2/4] Running dynamic analytics engine...")
    analytics_engine = UniversalAnalyticsEngine(parsed_data)
    metrics_payload = analytics_engine.run()

    metrics_file = project_dir / "metrics.json"
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2, default=str)

    print(f"[3/4] Rendering adaptive narrative report (report_output.md)...")
    generator = DynamicReportGenerator(metrics_payload)
    report_content = generator.generate_full_report()

    report_file = project_dir / "report_output.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"[4/4] Auditing governance compliance & SHA-256 hashes...")
    gov_engine = DynamicGovernanceEngine(metrics_payload, raw_data_path=str(target_path))
    audit_data = gov_engine.run_compliance_audit(
        report_path=str(report_file),
        metrics_path=str(metrics_file)
    )

    review_file = project_dir / "review_status.json"
    with open(review_file, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2, default=str)

    # 21 CFR Part 11 Digital Sign-off update
    mgr = ReviewStatusManager(str(review_file))
    mgr.update_document_hashes(str(report_file), str(metrics_file))
    mgr.execute_sign_off()

    print(f"[OK] Pipeline complete! Dataset '{target_path.name}' synchronized successfully.\n")

    return {
        "status": "SUCCESS",
        "dataset_name": target_path.name,
        "metrics": metrics_payload,
        "report_content": report_content,
        "review_status": audit_data
    }


class CORSRequestHandler(SimpleHTTPRequestHandler):
    """CORS-enabled HTTP Request Handler serving static UI and REST endpoints."""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-File-Name")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "OK")
        self.end_headers()

    def do_GET(self):
        url_path = urllib.parse.urlparse(self.path).path
        project_dir = Path(__file__).parent.resolve()

        if url_path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            metrics_file = project_dir / "metrics.json"
            review_file = project_dir / "review_status.json"

            metrics_data = {}
            if metrics_file.exists():
                with open(metrics_file, "r", encoding="utf-8") as f:
                    metrics_data = json.load(f)

            review_data = {}
            if review_file.exists():
                with open(review_file, "r", encoding="utf-8") as f:
                    review_data = json.load(f)

            res = {
                "dataset_name": CURRENT_DATASET_PATH,
                "metrics": metrics_data,
                "review_status": review_data
            }
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        super().do_GET()

    def do_POST(self):
        url_path = urllib.parse.urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        project_dir = Path(__file__).parent.resolve()

        if url_path == "/api/upload":
            try:
                filename_header = self.headers.get("X-File-Name", "uploaded_dataset.xlsx")
                saved_file_path = project_dir / filename_header

                with open(saved_file_path, "wb") as f:
                    f.write(body_bytes)

                pipeline_res = run_pipeline(str(saved_file_path))

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(pipeline_res).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        elif url_path == "/api/sync":
            try:
                pipeline_res = run_pipeline(CURRENT_DATASET_PATH)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(pipeline_res).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


def start_server(port: int = 8000):
    """Starts the local CORS-enabled HTTP server."""
    os.chdir(Path(__file__).parent.resolve())
    server_address = ("", port)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    print(f"============================================================")
    print(f" GenAR Enterprise Safety Console Server Running!")
    print(f" Local Dashboard:  http://localhost:{port}")
    print(f" REST API Ready:   http://localhost:{port}/api/status")
    print(f"============================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Server shutting down.")
        httpd.server_close()


if __name__ == "__main__":
    if "--server" in sys.argv or "-s" in sys.argv or len(sys.argv) == 1:
        start_server(8000)
