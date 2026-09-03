#!/usr/bin/env python3
"""Regression test: synchronous upload path (small workbook ≤4MiB, multipart).
Verifies the existing beta flow still works alongside the new async worker."""
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
from uuid import uuid4

BASE = "http://localhost:8010"
ROOT = Path("/home/ubuntu/ControlCheck-AI-Core")
WORKBOOK = ROOT / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"

BOUNDARY = "----TestBoundary7MA4YWxkTrZu0gW"


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


def multipart_upload(project_id, token, path: Path):
    """Manual multipart/form-data POST — same shape as frontend api.runs.upload."""
    content = path.read_bytes()
    body = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
    ).encode() + content + f"\r\n--{BOUNDARY}--\r\n".encode()
    req = urllib.request.Request(
        BASE + f"/v1/projects/{project_id}/analysis-runs", method="POST", data=body
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={BOUNDARY}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def decode_jwt_payload(token: str) -> dict:
    import base64
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def main():
    suffix = uuid4().hex[:8]
    status, reg = call("POST", "/v1/auth/register", {
        "email": f"sync_{suffix}@test.local", "password": "Password123!",
        "full_name": "Sync Tester", "organization_name": f"Sync Org {suffix}",
    })
    assert status in (200, 201), f"register failed: {reg}"
    token = reg["access_token"]
    org_id = decode_jwt_payload(token).get("org_id")
    print(f"1. Register OK — org={org_id}")

    status, project = call("POST", f"/v1/organizations/{org_id}/projects", {
        "code": "SYNC-TEST", "name": "Sync Test Project", "currency": "IDR",
    }, token)
    assert status in (200, 201), f"project failed: {project}"
    project_id = project["id"]
    print(f"2. Project OK — {project_id}")

    # Synchronous multipart upload (the pre-worker beta path)
    status, run = multipart_upload(project_id, token, WORKBOOK)
    assert status in (200, 201, 202), f"sync upload failed ({status}): {run}"
    run_status = run.get("status")
    print(f"3. Sync upload → HTTP {status}, run status={run_status}")
    assert str(run_status).lower() in ("succeeded", "completed", "running"), (
        f"unexpected run status: {run_status}"
    )

    # If completed inline, findings should be visible right away.
    run_id = run.get("id")
    status, health = call("GET", f"/v1/analysis-runs/{run_id}/health", token=token)
    print(f"4. Health: overall={health.get('overall_score')} band={health.get('score_band')}")

    # Job list endpoint must exist and be empty for this project (sync run creates no job)
    status, jobs = call("GET", f"/v1/projects/{project_id}/analysis-jobs", token=token)
    print(f"5. Job list: total={jobs.get('total')} (sync path → 0, no job queued)")
    assert jobs.get("total") == 0

    print("\n✅ SYNC PATH REGRESSION PASSED")


if __name__ == "__main__":
    main()
