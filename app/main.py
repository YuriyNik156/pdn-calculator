from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from pydantic import ValidationError
from pathlib import Path

from app.models import PDNRequestSchema, BusinessInput, BusinessResult
from app.services import calculate_pdn, calc_business_metrics, get_config, update_config
from app.audit import get_audit_by_request
from app.docs.openapi_overrides import custom_openapi
from app.auth import require_admin
from app.utils import mask_sensitive  # Функция маскирования персональных данных в логах

APP_VERSION = "v1.0"

app = FastAPI(title="PDN Calculator MVP")

# -----------------------
# Middleware и CORS
# -----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# SlowAPI лимитирование
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests"}
    )

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# -----------------------
# Статика
# -----------------------
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(static_dir / "index.html")

# -----------------------
# Расчёт ПДН для физических лиц
# -----------------------
@app.post("/pdn/calc")
async def pdn_calc(request: PDNRequestSchema):
    try:
        masked_request = mask_sensitive(request.dict())
        result = calculate_pdn(request)
        return JSONResponse(content=result, headers={"X-PDN-Calc-Version": APP_VERSION})
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=ve.errors())
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")

# -----------------------
# Расчёт ПДН для бизнеса
# -----------------------
@app.post("/pdn/calc/business", response_model=BusinessResult, tags=["Business PDN"])
def pdn_calc_business(data: BusinessInput):
    try:
        masked_data = mask_sensitive(data.dict())
        return calc_business_metrics(data)
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=ve.errors())
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")

# -----------------------
# Конфигурация
# -----------------------
@app.get("/pdn/config")
def read_config():
    return JSONResponse(content=get_config(), headers={"X-PDN-Calc-Version": APP_VERSION})

@app.post("/admin/pdn/config")
def update_admin_config(new_conf: dict, _: None = Depends(require_admin)):
    return JSONResponse(content=update_config(new_conf), headers={"X-PDN-Calc-Version": APP_VERSION})

# -----------------------
# Аудит
# -----------------------
@app.get("/admin/pdn/audit")
def audit_logs(request_id: str = Query(..., description="ID запроса для поиска")):
    logs = get_audit_by_request(request_id)
    if not logs:
        return JSONResponse(
            content={"request_id": request_id, "logs": [], "message": "Записи не найдены"},
            headers={"X-PDN-Calc-Version": APP_VERSION}
        )
    return JSONResponse(content={"request_id": request_id, "logs": logs}, headers={"X-PDN-Calc-Version": APP_VERSION})

# -----------------------
# Кастомное OpenAPI
# -----------------------
app.openapi = lambda: custom_openapi(app)

# -----------------------
# Health check с лимитом
# -----------------------
@app.get("/health")
@limiter.limit("10/minute")
async def health_check():
    return {"status": "ok"}
