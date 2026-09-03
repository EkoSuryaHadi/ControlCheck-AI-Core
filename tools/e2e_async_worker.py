#!/usr/bin/env python3
"""E2E test: async analysis job flow (API → queue → Celery worker → result)."""
import json
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

BASE = "http://localhost:8010"
ROOT = Path("/home/ubuntu/ControlCheck-AI-Core")
WORKBOOK = ROOT / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def decode_jwt_payload(token: str) -> dict:
    import base64
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def main():
    # 1. Register + token
    suffix = uuid4().hex[:8]
    email = f"e2e_{suffix}@test.local"
    status, reg = call("POST", "/v1/auth/register", {
        "email": email, "password": "Password123!",
        "full_name": "E2E Async", "organization_name": f"E2E Async Org {suffix}",
    })
    assert status in (200, 201), f"register failed: {reg}"
    token = reg["access_token"]
    org_id = decode_jwt_payload(token).get("org_id")
    assert org_id, f"org_id not in token payload: {decode_jwt_payload(token).keys()}"
    print(f"1. Register OK — org={org_id}")

    # 2. Create project
    status, project = call("POST", f"/v1/organizations/{org_id}/projects", {
        "code": "E2E-ASYNC", "name": "E2E Async Project", "currency": "IDR",
    }, token)
    assert status in (200, 201), f"project failed: {project}"
    project_id = project["id"]
    print(f"2. Project OK — {project_id}")

    # 3. Place workbook into local storage at a key the job will reference.
    sys.path.insert(0, str(ROOT / "src"))
    from controlcheck.storage import LocalFileStorage
    storage = LocalFileStorage(ROOT / "var" / "uploads")
    data = WORKBOOK.read_bytes()
    stored = storage.put(uuid4(), uuid4(), WORKBOOK.name, data)  # placeholder org/project
    print(f"3. Workbook staged at storage key: {stored.key} ({len(data)} bytes)")

    # 4. Queue the async run (small sync path would work too, but exercise worker)
    status, job = call("POST", f"/v1/projects/{project_id}/analysis-runs/async", {
        "storage_key": stored.key,
        "filename": WORKBOOK.name,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "file_size_bytes": len(data),
        "workbook_sha256": None,
    }, token)
    assert status in (200, 201, 202), f"async create failed ({status}): {job}"
    job_id = job["id"]
    print(f"4. Job queued — {job_id} status={job['status']}")

    # 5. Poll until worker completes.
    deadline = time.time() + 90
    final = None
    while time.time() < deadline:
        time.sleep(3)
        status, final = call("GET", f"/v1/analysis-jobs/{job_id}", token=token)
        if final["status"] in ("completed", "failed"):
            break
        print(f"   ... job status: {final['status']}")
    assert final and final["status"] == "completed", f"job did not complete: {final}"
    print(f"5. Job COMPLETED — analysis_run_id={final['analysis_run_id']} attempts={final['attempts']}")

    # 6. Fetch the run + findings
    run_id = final["analysis_run_id"]
    status, run = call("GET", f"/v1/analysis-runs/{run_id}", token=token)
    print(f"6. Run: status={run.get('status')} findings={run.get('finding_count')} rules={run.get('rule_count')}")

    status, health = call("GET", f"/v1/analysis-runs/{run_id}/health", token=token)
    print(f"   Health: overall={health.get('overall_score')} band={health.get('score_band')}")

    # 7. Transient upload copy should be cleaned up.
    from controlcheck.storage import LocalFileStorage
    fs = LocalFileStorage(ROOT / "var" / "uploads")
    cleaned = not fs.exists(stored.key)
    print(f"7. Cleanup transient upload: {'OK (deleted)' if cleaned else 'STILL PRESENT'}")

    print("\n✅ E2E ASYNC WORKER FLOW PASSED")


if __name__ == "__main__":
    main()
