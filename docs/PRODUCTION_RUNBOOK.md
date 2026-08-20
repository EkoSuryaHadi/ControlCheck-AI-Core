# ControlCheck AI — Production Operations Runbook

This runbook outlines operational procedures, configuration guidelines, deployment steps, and disaster recovery runbooks for ControlCheck AI in production environments.

---

## 1. Pre-Deployment Checklist

1. **Secrets Provisioned**:
   - `CONTROLCHECK_JWT_SECRET` generated with `openssl rand -hex 32` (never use dev defaults).
   - `CONTROLCHECK_DATABASE_URL` pointing to hardened PostgreSQL 16 instance.
   - `CONTROLCHECK_CORS_ORIGINS` set to verified frontend domains.
2. **Database Migrations Ready**:
   - Verify `alembic upgrade head` executes with zero drift.
3. **Container Image Built & Scanned**:
   - Docker image built using `Dockerfile` (multi-stage, non-root user `10001:10001`).

---

## 2. Deployment Procedures

### Option A: Docker Compose Production Deployment
```bash
# 1. Clone repository and configure .env
git clone https://github.com/EkoSuryaHadi/ControlCheck-AI.git /opt/controlcheck
cd /opt/controlcheck
cp .env.example .env
nano .env

# 2. Start PostgreSQL service & apply migrations
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head

# 3. Start API service
docker compose -f docker-compose.prod.yml up -d app

# 4. Verify deployment health
curl -s http://127.0.0.1:8000/health/ready
```

### Option B: Kubernetes / Helm Deployment
- **Liveness Probe**: `GET http://<pod>:8000/health/live` (initialDelaySeconds: 10, periodSeconds: 15)
- **Readiness Probe**: `GET http://<pod>:8000/health/ready` (initialDelaySeconds: 15, periodSeconds: 10)
- **Pre-sync Hook**: Run `alembic upgrade head` in a Kubernetes Job prior to updating the Deployment replica set.

---

## 3. Backup and Disaster Recovery

### Automated PostgreSQL Backup
```bash
# Nightly backup script
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U controlcheck controlcheck | gzip > "/backup/controlcheck_${TIMESTAMP}.sql.gz"
```

### Database Restore Procedure
```bash
# Restore from gzipped SQL dump
gunzip < /backup/controlcheck_YYYYMMDD_HHMMSS.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U controlcheck controlcheck
```

---

## 4. Monitoring & Incident Response

| Alert / Symptom | Likely Cause | Recommended Action |
|---|---|---|
| `/health/ready` returns HTTP 503 | Database unreachable or connection pool exhausted | Check PostgreSQL service status, PgBouncer pool connections, and network firewall. |
| HTTP 401 `invalid_token` spikes | Secret mismatch or expired refresh tokens | Verify JWT signing secret consistency across replica instances. |
| HTTP 413 `file_too_large` | Upload exceeded 25 MB limit | Advise user or adjust `DEFAULT_MAX_UPLOAD_BYTES` in environment. |
| High CPU on `/v1/projects/{id}/analysis-runs` | Large Excel parsing | Ensure background worker scaling or worker replica pool increase. |

---

## 5. Contact & Escalation
- Infrastructure & Security: `devops@controlcheck.ai`
- Core Platform Engineering: `engineering@controlcheck.ai`
