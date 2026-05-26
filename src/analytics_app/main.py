import os
from datetime import datetime, timezone
from enum import Enum
from http import HTTPStatus
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


SERVICE_NAME = os.getenv("SERVICE_NAME", "analytics-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")


app = FastAPI(
    title="Smart Campus Analytics Service API",
    version=SERVICE_VERSION,
    description="Dockerized Analytics Service aligned with the Lab 04 OpenAPI contract.",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProblemDetails(StrictModel):
    type: str = "about:blank"
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: Optional[str] = None
    instance: Optional[str] = None


class HealthStatus(StrictModel):
    status: str
    service: str
    time: datetime


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Trend(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    STABLE = "STABLE"


class IoTEvent(StrictModel):
    deviceId: str
    metric: Optional[str] = None
    value: Optional[float] = None
    timestamp: datetime


class CameraEvent(StrictModel):
    eventType: str
    cameraId: str
    detectionId: Optional[UUID] = None
    confidenceScore: Optional[float] = None
    severity: Optional[Severity] = None
    imageRef: Optional[HttpUrl] = None
    timestamp: datetime
    correlationId: UUID


class DecisionResult(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REVIEW = "REVIEW"
    ESCALATE = "ESCALATE"


class BusinessEvent(StrictModel):
    eventType: str
    sourceModule: Optional[str] = None
    decisionId: UUID
    policyId: Optional[str] = None
    subjectId: Optional[str] = None
    result: Optional[DecisionResult] = None
    severity: Optional[Severity] = None
    riskScore: Optional[float] = Field(default=None, ge=0, le=100)
    analyticsRequired: Optional[bool] = None
    notificationRequired: Optional[bool] = None
    reason: Optional[str] = None
    timestamp: datetime
    correlationId: UUID


class Direction(str, Enum):
    IN = "IN"
    OUT = "OUT"


class AccessDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class AccessEvent(StrictModel):
    eventType: str
    gateId: str
    direction: Direction
    cardIdHash: Optional[str] = None
    decision: Optional[AccessDecision] = None
    timestamp: datetime
    correlationId: UUID


class AnalyticsResult(StrictModel):
    analyticsId: UUID
    resultType: str
    sourceService: str
    severity: Optional[Severity] = None
    confidenceScore: Optional[float] = None
    description: Optional[str] = None
    generatedAt: datetime
    correlationId: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None


class KPIStatistic(StrictModel):
    kpiId: UUID
    metricName: str
    value: float
    unit: str
    trend: Optional[Trend] = None
    calculatedAt: datetime
    description: Optional[str] = None


class DashboardMetric(StrictModel):
    metricName: Optional[str] = None
    currentValue: Optional[float] = None
    trend: Optional[Trend] = None
    updatedAt: Optional[datetime] = None


class AnalyticsPage(StrictModel):
    items: List[AnalyticsResult]
    total: int
    page: int
    pageSize: int


EVENTS: List[Dict[str, Any]] = []
SEEN_EVENT_KEYS: set[str] = set()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "about:blank",
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    return body


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        body = exc.detail
    else:
        body = problem(
            status_code=exc.status_code,
            title=HTTPStatus(exc.status_code).phrase,
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    body.setdefault("type", "about:blank")
    body.setdefault("title", HTTPStatus(exc.status_code).phrase)
    body.setdefault("status", exc.status_code)
    body.setdefault("detail", "Request failed")
    body.setdefault("instance", str(request.url.path))

    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = first_error.get("msg", "Request validation error")
    detail = f"{location}: {message}" if location else message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation error",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://smart-campus.local/problems/validation-error",
        ),
        media_type="application/problem+json",
    )


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Missing Authorization header",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )

    if authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Invalid bearer token",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )


def event_key(source: str, payload: StrictModel) -> str:
    data = payload.model_dump(mode="json")
    correlation_id = data.get("correlationId")
    if correlation_id:
        return f"{source}:{correlation_id}"
    return f"{source}:{data.get('deviceId')}:{data.get('timestamp')}"


def store_event(source: str, payload: StrictModel) -> None:
    key = event_key(source, payload)
    if key in SEEN_EVENT_KEYS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=problem(
                status_code=status.HTTP_409_CONFLICT,
                title="Conflict",
                detail="Duplicate event was already processed",
                problem_type="https://smart-campus.local/problems/duplicate-event",
            ),
        )

    SEEN_EVENT_KEYS.add(key)
    EVENTS.append(
        {
            "source": source,
            "payload": payload.model_dump(mode="json"),
            "receivedAt": now_utc().isoformat(),
        }
    )


def sample_analytics_result() -> AnalyticsResult:
    return AnalyticsResult(
        analyticsId=UUID("11111111-1111-4111-8111-111111111111"),
        resultType="ANOMALY_DETECTED",
        sourceService="analytics-service",
        severity=Severity.HIGH,
        confidenceScore=0.95,
        description="Synthetic analytics result for Lab 04 Docker verification.",
        generatedAt=now_utc(),
        correlationId=UUID("22222222-2222-4222-8222-222222222222"),
        metadata={"eventCount": len(EVENTS)},
    )


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok", service=SERVICE_NAME, time=now_utc())


@app.head("/health")
def health_head() -> None:
    return None


@app.post(
    "/analytics/iot-events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={401: {"model": ProblemDetails}, 409: {"model": ProblemDetails}, 422: {"model": ProblemDetails}},
)
def ingest_iot_event(payload: IoTEvent) -> None:
    store_event("iot", payload)


@app.post(
    "/analytics/camera-events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={401: {"model": ProblemDetails}, 409: {"model": ProblemDetails}, 422: {"model": ProblemDetails}},
)
def ingest_camera_event(payload: CameraEvent) -> None:
    store_event("camera", payload)


@app.post(
    "/analytics/business-events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={401: {"model": ProblemDetails}, 409: {"model": ProblemDetails}, 422: {"model": ProblemDetails}},
)
def ingest_business_event(payload: BusinessEvent) -> None:
    store_event("business", payload)


@app.post(
    "/analytics/access-events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={401: {"model": ProblemDetails}, 409: {"model": ProblemDetails}, 422: {"model": ProblemDetails}},
)
def ingest_access_event(payload: AccessEvent) -> None:
    store_event("access", payload)


@app.get(
    "/analytics/report/{id}",
    response_model=AnalyticsResult,
    dependencies=[Depends(verify_bearer_token)],
    responses={401: {"model": ProblemDetails}, 404: {"model": ProblemDetails}},
)
def get_analytics_report(id: UUID) -> AnalyticsResult:
    if id == UUID("11111111-1111-4111-8111-111111111111"):
        return sample_analytics_result()

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=problem(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail=f"Analytics report {id} does not exist",
            instance=f"/analytics/report/{id}",
            problem_type="https://smart-campus.local/problems/not-found",
        ),
    )


@app.get(
    "/analytics/events",
    response_model=AnalyticsPage,
    dependencies=[Depends(verify_bearer_token)],
)
def list_analytics_events() -> AnalyticsPage:
    items = [sample_analytics_result()]
    return AnalyticsPage(items=items, total=len(items), page=1, pageSize=10)


@app.get(
    "/analytics/kpi",
    response_model=List[KPIStatistic],
    dependencies=[Depends(verify_bearer_token)],
)
def get_kpi_statistics() -> List[KPIStatistic]:
    return [
        KPIStatistic(
            kpiId=UUID("33333333-3333-4333-8333-333333333333"),
            metricName="event-ingestion-count",
            value=float(len(EVENTS)),
            unit="events",
            trend=Trend.STABLE,
            calculatedAt=now_utc(),
            description="Number of accepted analytics input events in this process.",
        )
    ]


@app.get(
    "/analytics/dashboard",
    response_model=List[DashboardMetric],
    dependencies=[Depends(verify_bearer_token)],
)
def get_dashboard_metrics() -> List[DashboardMetric]:
    return [
        DashboardMetric(
            metricName="accepted-events",
            currentValue=float(len(EVENTS)),
            trend=Trend.UP if EVENTS else Trend.STABLE,
            updatedAt=now_utc(),
        ),
        DashboardMetric(
            metricName="active-sources",
            currentValue=float(len({event["source"] for event in EVENTS})),
            trend=Trend.STABLE,
            updatedAt=now_utc(),
        ),
    ]
