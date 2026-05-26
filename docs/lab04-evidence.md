# Lab 04 Evidence - Analytics Service

## Team

- Team name: team-analytics
- Service: Smart Campus Analytics Service
- Local image tag: `fit4110/analytics-service:lab04`
- Registry image tag: `ghcr.io/connectivity-services-ad-pt/team-analytics:v0.1.0-team-analytics`

## Submitted Artifacts

- `Dockerfile`
- `.dockerignore`
- `.env.example`
- `RUN_LOCAL.md`
- `contracts/analytics.openapi.yaml`
- `postman/collections/FIT4110_lab04_analytics_docker.postman_collection.json`
- `postman/environments/FIT4110_lab04_local.postman_environment.json`
- `reports/newman-lab04-local.xml`
- `reports/newman-lab04-local.html`

## Build Evidence

Command:

```bash
docker build -t fit4110/analytics-service:lab04 .
```

Result:

```text
Image built successfully.
Image tag: fit4110/analytics-service:lab04
```

## Run Evidence

Command:

```bash
docker run -d --rm --name fit4110-analytics-lab04 -p 8000:8000 --env-file .env.example fit4110/analytics-service:lab04
```

Result:

```text
Container starts successfully.
Container name: fit4110-analytics-lab04
Docker health status: healthy
Container user: uid=100(appuser) gid=101(appgroup)
```

## Health Evidence

Command:

```bash
curl http://localhost:8000/health
```

Result:

```json
{
  "status": "ok",
  "service": "analytics-service",
  "time": "2026-05-26T10:10:10.587108Z"
}
```

The service also supports `HEAD /health` so the GitHub Actions `wait-on` step can verify readiness.

## Newman Evidence

Command:

```bash
npm run test:local
```

Result:

```text
requests: 14 executed, 0 failed
assertions: 19 executed, 0 failed
```

Report paths:

```text
reports/newman-lab04-local.xml
reports/newman-lab04-local.html
```

## Image Push Evidence

GitHub Actions pushes the verified image on every push to `main` after build, health check, and Newman tests pass.

Pushed image tag:

```text
ghcr.io/connectivity-services-ad-pt/team-analytics:v0.1.0-team-analytics
```

Manual push from this machine requires GHCR login. The local unauthenticated attempt returned `denied`, so the repository workflow uses `GITHUB_TOKEN` with `packages: write`.
