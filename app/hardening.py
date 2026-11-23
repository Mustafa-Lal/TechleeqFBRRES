"""Audit persistence, response boundaries and frontend configuration."""

from contextvars import ContextVar
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app import core
from app.features import *

actor = core.audit_actor


@app.middleware("http")
async def access_boundary(request: Request, call_next):
    identity = None
    if request.headers.get("authorization"):
        try:
            identity = core.current(request.headers["authorization"])
        except HTTPException:
            pass
    token = actor.set(identity["id"] if identity else None)
    try:
        response = await call_next(request)
        if (
            identity
            and identity["role"] == "cashier"
            and request.url.path.startswith("/orders")
            and response.headers.get("content-type", "").startswith("application/json")
        ):
            raw = b"".join([chunk async for chunk in response.body_iterator])

            def redact(value):
                if isinstance(value, dict):
                    return {
                        k: redact(v)
                        for k, v in value.items()
                        if k not in ("cost", "recipe", "consumption", "value")
                    }
                if isinstance(value, list):
                    return [redact(v) for v in value]
                return value

            headers = {
                k: v
                for k, v in response.headers.items()
                if k not in ("content-length", "content-type")
            }
            return JSONResponse(
                redact(json.loads(raw)),
                status_code=response.status_code,
                headers=headers,
            )
        return response
    finally:
        actor.reset(token)


@app.get("/audit/records")
def records_audit(
    entity: str | None = None,
    record_id: int | None = None,
    limit: int = 100,
    user=Depends(manager),
):
    with core.db() as c:
        rows = c.execute(
            "SELECT * FROM record_history WHERE (? IS NULL OR entity=?) AND (? IS NULL OR record_id=?) ORDER BY id DESC LIMIT ?",
            (entity, entity, record_id, record_id, min(max(limit, 1), 1000)),
        )
        return [
            {
                **dict(row),
                "previous": json.loads(row["previous"]),
                "current": json.loads(row["current"]),
            }
            for row in rows
        ]


origins = [
    value.strip()
    for value in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)
