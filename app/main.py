from fastapi import FastAPI, Header, Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import time
import uuid
import logging

from app.models import PDNRequest
from app.services import calculate_pdn
from app.logger import logger
from app.audit import write_audit_log, read_audit_by_request_id

# --- Инициализация FastAPI ---
app = FastAPI(
    title="PDN Calculator API",
    description="API для расчёта показателя долговой нагрузки (PDN)",
    version="1.0"
)

# --- Конфигурация ---
CONFIG = {
    "risk_bands": ["low", "medium", "high"],
    "cc_default_rate": 0.35,
    "calc_version": "1.0"
}


# --- Middleware: добавляем request_id и базовое логирование ---
@app.middleware("http")
async def add_request_id_and_logging(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    logger.info(f"Request {request_id} started: {request.method} {request.url}")
    start_time = time.time()

    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception(f"Unhandled error in request {request_id}: {e}")
        raise

    duration_ms = int((time.time() - start_time) * 1000)
    logger.info(f"Request {request_id} completed in {duration_ms}ms with status {response.status_code}")

    response.headers["X-Request-ID"] = request_id
    return response


# --- Обработчики ошибок ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail
            },
            "meta": {"ts": datetime.now(timezone.utc).isoformat()}
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unexpected error: %s", str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal Server Error"
            },
            "meta": {"ts": datetime.now(timezone.utc).isoformat()}
        }
    )


# --- GET / (Health check) ---
@app.get("/")
async def root():
    return {"message": "PDN Calculator API is running!"}


# --- POST /pdn/calc ---
@app.post("/pdn/calc")
async def pdn_calc(request: Request, x_pdn_calc_version: str = Header(default="v1.0")):
    """
    Рассчитывает PDN по входным данным.
    Пишет аудит в файл audit.log.
    """
    request_id = request.state.request_id
    start = time.time()

    try:
        payload_dict = await request.json()
        payload = PDNRequest(**payload_dict)  # ✅ Преобразуем в объект модели
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")

    try:
        pdn_result = calculate_pdn(payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except AttributeError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка структуры данных: {e}")

    duration_ms = int((time.time() - start) * 1000)
    ts = datetime.now(timezone.utc).isoformat()

    audit_data = {
        "request_id": request_id,
        "client_id": payload.client_id,
        "calc_version": x_pdn_calc_version,
        "scenario": getattr(payload, "scenario", None),
        "pdn_percent": pdn_result.get("pdn_percent"),
        "ts": ts,
        "duration_ms": duration_ms
    }

    # ✅ Пишем лог в консоль и в audit.log
    logger.info(f"AUDIT_LOG: {audit_data}")
    write_audit_log(request_id, "/pdn/calc", payload_dict, pdn_result)

    return {"data": pdn_result, "meta": {"ts": ts, "request_id": request_id}}


# --- GET /pdn/config ---
@app.get("/pdn/config")
async def get_config():
    """
    Возвращает текущие параметры расчёта PDN.
    """
    return {"data": CONFIG, "meta": {"ts": datetime.now(timezone.utc).isoformat()}}


# --- GET /admin/pdn/audit ---
@app.get("/admin/pdn/audit")
async def get_audit(request_id: str):
    """
    Возвращает audit-запись по request_id.
    ⚠️ В продакшене сюда нужен RBAC (например, роль ADMIN).
    """
    logs = read_audit_by_request_id(request_id)
    if not logs:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return {"data": logs, "meta": {"ts": datetime.now(timezone.utc).isoformat()}}
