# ControlCheck AI — Enterprise Production Operations Runbook

This runbook provides complete operational procedures, configuration requirements, security checklists, deployment guides, and disaster recovery procedures for **ControlCheck AI** in production environments.

---

## 1. System Architecture & Topology

```
                  ┌────────────────────────────────────────────────────────┐
                  │                Internet / Client Traffic               │
                  └───────────────────────────┬────────────────────────────┘
                                              │ HTTPS (443) / HTTP (80)
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │                 Nginx Reverse Proxy                    │
                  │   - SSL/TLS Termination & HTTP/2                       │
                  │   - Security Headers (HSTS, CSP, X-Frame-Options)      │
                  │   - Rate Limiting (Auth: 10r/m, API: 50r/s)            │
                  │   - Gzip & Static Asset Caching                        │
                  └───────────────────────────┬────────────────────────────┘
                                              │ Reverse Proxy (Internal Net)
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │              ControlCheck API Service                  │
                  │   - FastAPI + Uvicorn Multi-Worker ASGI                │
                  │   - Non-root System User (UID 10001)                   │
                  │   - Auto-Alembic Migration on Container Startup        │
                  │   - Prometheus Metrics Exporter (/metrics)             │
                  └───────────────┬────────────────────────┬───────────────┘
                                  │                        │
                   SQLAlchemy     │                        │ S3 Protocol
                   Connection     │                        │
                   Pool (5432)    ▼                        ▼
      ┌───────────────────────────────────────┐  ┌─────────────────────────┐
      │         PostgreSQL 16 Engine          │  │   Object Storage (S3)   │
      │  - Encrypted Persistent Volumes       │  │  - Encrypted Buckets    │
      │  - Automated Nightly Gzip Dumps       │  │  - Retention Policies   │
      └───────────────────────────────────────┘  └─────────────────────────┘
```

---

## 2. Pre-Deployment Security Checklist

1. **Production Secrets Generated**:
   - `CONTROLCHECK_JWT_SECRET`: Must be generated with `openssl rand -hex 32` (minimum 32 characters; default dev keys are strictly rejected in production mode).
   - `POSTGRES_PASSWORD`: Strong random alphanumeric string (>16 characters).
2. **CORS Domains Whitelisted**:
   - Set `CONTROLCHECK_CORS_ORIGINS` to exact production domain(s), e.g., `https://app.controlcheck.ai`. Wildcards (`*`) are disallowed with credentials.
   - Set `CONTROLCHECK_TRUSTED_HOSTS` to exact API hostnames without schemes, e.g., `controlcheck-api.onrender.com`. Missing or wildcard production hosts fail startup.
3. **Database Connectivity & Storage Backend**:
   - Ensure PostgreSQL 16 is provisioned with persistent storage.
   - If using AWS S3 / MinIO, verify bucket existence, IAM credentials, and network egress permissions.
4. **Container Image Built & Verified**:
   - Multi-stage build executed (`Dockerfile`).
   - Verified non-root UID `10001:10001` execution.

---

## 3. Deployment Procedures

### Option A: Standard Production Deployment (Docker Compose)

```bash
# 1. Clone repository to production host
git clone https://github.com/EkoSuryaHadi/ControlCheck-AI.git /opt/controlcheck
cd /opt/controlcheck

# 2. Configure production environment
cp .env.production.example .env
nano .env

# 3. Build & launch stack with Nginx, FastAPI, and PostgreSQL
docker compose -f docker-compose.prod.yml up -d --build

# 4. Verify cluster health status
curl -i http://localhost/health/ready
```

### Option B: Kubernetes / Helm Deployment
- **Liveness Probe**: `GET http://<pod>:8000/health/live` (initialDelaySeconds: 10, periodSeconds: 15)
- **Readiness Probe**: `GET http://<pod>:8000/health/ready` (initialDelaySeconds: 15, periodSeconds: 10)
- **Prometheus Metrics**: `GET http://<pod>:8000/metrics` (scrape_interval: 15s)
- **Pre-sync Hook**: Automatically executed via container `docker/entrypoint.sh` or explicit K8s Job.

### Option C: Render Baseline Manifest

`render.yaml` defines the Render Free `controlcheck-api` web service in Singapore, runs migrations before Uvicorn starts, and probes `/health/ready`. It uses only canonical `CONTROLCHECK_*` application settings. Render generates `CONTROLCHECK_JWT_SECRET`; operators must provide the Supabase Session Pooler URL on port 5432 as `CONTROLCHECK_DATABASE_URL`, the account-specific Cloudflare R2 S3 endpoint as `CONTROLCHECK_S3_ENDPOINT_URL`, and scoped `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` values as secrets. The committed R2 bucket is `controlcheck-beta-workbooks` with region `auto`; the committed exact CORS origin and trusted API host must be changed if the deployed public hostnames differ. Render is treated as a production runtime and cannot start with local storage, wildcard hosts/origins, or missing durable configuration.

---

## 4. Backup & Disaster Recovery (DR)

### Automated Nightly Backup Script
Backups are created automatically using `tools/db_backup.sh` and compressed with `gzip -9`.

```bash
# Manual execution
./tools/db_backup.sh /opt/controlcheck/var/backups 14

# Production Crontab Setup (Runs daily at 02:00 AM)
0 2 * * * /opt/controlcheck/tools/db_backup.sh /opt/controlcheck/var/backups 14 >> /var/log/controlcheck_backup.log 2>&1
```

### Disaster Recovery Restore Drill
```bash
# Restore from a specific backup snapshot
./tools/db_restore.sh /opt/controlcheck/var/backups/controlcheck_backup_20260822_020000.sql.gz
```

---

## 5. Monitoring, Observability & Health Probes

### Endpoints
| Path | Purpose | Success Code | Sample Response / Format |
|---|---|---|---|
| `/health/live` | Process Liveness | 200 OK | `{"status": "live", "engine_version": "0.2.0"}` |
| `/health/ready` | Full System Readiness | 200 OK (503 on error) | `{"status": "ready", "checks": {"database": "connected", "storage": "ready", "catalogue": "loaded"}}` |
| `/metrics` | Prometheus Metrics | 200 OK | Prometheus Text Exporter format (`controlcheck_http_requests_total`, etc.) |

### Key Prometheus Metrics to Alert On
- `controlcheck_http_requests_total{status="500"}`: Alert if 5xx rate > 1% over 5 minutes.
- `controlcheck_http_request_duration_seconds_sum / controlcheck_http_request_duration_seconds_count`: Alert if average latency > 1500ms.
- `controlcheck_active_requests`: Alert if sustained > 50 on single worker node.

---

## 6. Incident Response & Troubleshooting Playbook

| Symptom / Alert | Root Cause | Remediation Procedure |
|---|---|---|
| `/health/ready` returns HTTP 503 (`database: unreachable`) | PostgreSQL container crashed, connection pool exhausted, or invalid DB credentials | 1. Check `docker logs controlcheck-postgres`<br/>2. Verify DB connection string in `.env`<br/>3. Inspect active connections: `SELECT count(*) FROM pg_stat_activity;` |
| HTTP 429 `Too Many Requests` | Client exceeded Nginx rate limiting thresholds (Auth: 10r/m, API: 50r/s) | Verify if legitimate spike or brute-force attempt. Adjust `limit_req_zone` in `docker/nginx.conf` if needed. |
| HTTP 401 `invalid_token` on all clients | `CONTROLCHECK_JWT_SECRET` was modified or differs across instances | Ensure consistent JWT secret across all API replica containers. |
| HTTP 413 `file_too_large` | Excel workbook exceeds 25 MB max limit | Verify client file size or increase `CONTROLCHECK_MAX_UPLOAD_BYTES` and Nginx `client_max_body_size`. |
| High CPU during analysis runs | Complex workbook parsing with many WBS nodes | Scale backend worker replicas (`WEB_CONCURRENCY=4`) or configure asynchronous background Celery/RQ workers. |

---

## 7. Operational Escalation Contacts
- **DevOps & Infrastructure**: `devops@controlcheck.ai`
- **Core Platform Engineering**: `engineering@controlcheck.ai`
- **Security & Compliance**: `security@controlcheck.ai`
