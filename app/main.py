from fastapi import FastAPI, Header, Request, HTTPException
from fastapi.responses import JSONResponse
from app.services.pdn_service import calculate_pdn
from datetime import datetime
import logging
import time
import uuid

# Инициализация FastAPI
app = FastAPI(
    title="PDN Calculator API",
    description="API для расчёта показателя долговой нагрузки (PDN)",
    version="1.0"
)

# Логирование
logger = logging.getLogger("pdn_logger")
logging.basicConfig(level=logging.INFO)

# Конфигурация (можно вынести позже в отдельный модуль)
CONFIG = {
    "risk_bands": ["low", "medium", "high"],
    "cc_default_rate": 0.35,
    "calc_version": "1.0"
}


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
            "meta": {"ts": datetime.utcnow().isoformat()}
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
            "meta": {"ts": datetime.utcnow().isoformat()}
        }
    )


# --- POST /pdn/calc ---
@app.post("/pdn/calc")
async def pdn_calc(request: Request, x_pdn_calc_version: str = Header(default="v1.0")):
    """
    Рассчитывает PDN по входным данным.
    Читает X-PDN-Calc-Version, вызывает бизнес-логику и пишет аудит.
    """
    request_id = str(uuid.uuid4())
    start = time.time()

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    try:
        # Вызов сервиса расчёта PDN
        pdn_result = calculate_pdn(payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    duration_ms = int((time.time() - start) * 1000)
    ts = datetime.utcnow().isoformat()

    # Аудит (без PII)
    audit_data = {
        "request_id": request_id,
        "client_id": payload.get("client_id"),
        "calc_version": x_pdn_calc_version,
        "scenario": payload.get("scenario"),
        "pdn_percent": pdn_result.get("pdn_percent"),
        "ts": ts,
        "duration_ms": duration_ms
    }
    logger.info(f"AUDIT_LOG: {audit_data}")

    # Ответ
    return {
        "data": pdn_result,
        "meta": {"ts": ts}
    }


# --- GET /pdn/config ---
@app.get("/pdn/config")
async def get_config():
    """
    Возвращает текущие параметры расчёта PDN.
    """
    return {
        "data": CONFIG,
        "meta": {"ts": datetime.utcnow().isoformat()}
    }
