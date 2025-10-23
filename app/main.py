from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from pathlib import Path

from app.models import PDNRequestSchema, BusinessInput, BusinessResult
from app.services import calculate_pdn, calc_business_metrics, get_config, update_config
from app.audit import get_audit_by_request
from app.docs.openapi_overrides import custom_openapi
from app.auth import require_admin

APP_VERSION = "v1.0"

app = FastAPI(title="PDN Calculator MVP")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Главная страница
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(static_dir / "index.html")

# Расчёт ПДН для физических лиц
@app.post("/pdn/calc")
async def pdn_calc(request: PDNRequestSchema):
    try:
        result = calculate_pdn(request)
        return JSONResponse(content=result, headers={"X-PDN-Calc-Version": APP_VERSION})
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=ve.errors())
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")

# Расчёт ПДН для бизнеса
@app.post("/pdn/calc/business", response_model=BusinessResult, tags=["Business PDN"])
def pdn_calc_business(data: BusinessInput):
    try:
        return calc_business_metrics(data)  # возвращаем сам объект Pydantic
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=ve.errors())
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal calculation error")


# Чтение конфигурации
@app.get("/pdn/config")
def read_config():
    return JSONResponse(content=get_config(), headers={"X-PDN-Calc-Version": APP_VERSION})

# Обновление конфигурации (RBAC)
@app.post("/admin/pdn/config")
def update_admin_config(new_conf: dict, _: None = Depends(require_admin)):
    return JSONResponse(content=update_config(new_conf), headers={"X-PDN-Calc-Version": APP_VERSION})

# Аудит
@app.get("/admin/pdn/audit")
def audit_logs(request_id: str = Query(..., description="ID запроса для поиска")):
    logs = get_audit_by_request(request_id)
    if not logs:
        return JSONResponse(
            content={"request_id": request_id, "logs": [], "message": "Записи не найдены"},
            headers={"X-PDN-Calc-Version": APP_VERSION}
        )
    return JSONResponse(content={"request_id": request_id, "logs": logs}, headers={"X-PDN-Calc-Version": APP_VERSION})

# Кастомное OpenAPI
app.openapi = lambda: custom_openapi(app)
