# RUN_LOCAL.md - Huong dan chay Lab 04 Analytics Service

Tai lieu nay giup nguoi khac clone repo sach va chay lai Analytics Service trong Docker.

## 1. Cai dependencies cho Newman/Prism/Spectral

```bash
npm install
```

## 2. Build Docker image

```bash
docker build -t fit4110/analytics-service:lab04 .
```

Hoac dung Makefile:

```bash
make build
```

## 3. Run container

```bash
docker run --rm --name fit4110-analytics-lab04 -p 8000:8000 --env-file .env.example fit4110/analytics-service:lab04
```

Hoac:

```bash
make run
```

## 4. Kiem tra health

Mo terminal khac va chay:

```bash
curl http://localhost:8000/health
```

Ket qua mong doi:

```json
{
  "status": "ok",
  "service": "analytics-service",
  "time": "2026-05-26T10:00:00Z"
}
```

## 5. Chay Newman test tren container

```bash
npm run test:local
```

Report sinh tai:

```text
reports/newman-lab04-local.xml
reports/newman-lab04-local.html
```

## 6. Dung container

Neu container dang chay o terminal rieng:

```bash
docker stop fit4110-analytics-lab04
```
