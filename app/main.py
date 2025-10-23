from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from pathlib import Path

from app.models import PDNRequestSchema
from app.services import calculate_pdn
from app.audit import get_audit_by_request
from app.docs.openapi_overrides import custom_openapi

APP_VERSION = "v1.0"  # Версия формулы/сервиса

app = FastAPI(title="PDN Calculator MVP")


# === 1. CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# === 2. Подключаем статику ===
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# === 3. Главная страница ===
@app.get("/", include_in_schema=False)
async def root():
    """Отдаёт страницу расчёта ПДН"""
    return FileResponse(static_dir / "index.html")


# === 4. Основной эндпоинт расчёта ===
@app.post("/pdn/calc")
async def pdn_calc(request: PDNRequestSchema):
    try:
        result = calculate_pdn(request)

        # Возвращаем результат с заголовком версии
        return JSONResponse(
            content=result,
            headers={"X-PDN-Calc-Version": APP_VERSION}
        )
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=ve.errors())
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal calculation error")

def calc_pdn(request: PDNRequestSchema):
    """Выполняет расчёт показателя долговой нагрузки (ПДН) на основе входных данных."""
    return calculate_pdn(request)


# === 5. Кастомное описание OpenAPI ===
app.openapi = lambda: custom_openapi(app)


# === 6. Аудит ===
@app.get("/admin/pdn/audit")
def audit_logs(request_id: str = Query(..., description="ID запроса для поиска")):
    """Возвращает аудит логов входа/выхода по конкретному request_id"""
    logs = get_audit_by_request(request_id)
    if not logs:
        return JSONResponse(
            content={"request_id": request_id, "logs": [], "message": "Записи не найдены"},
            headers={"X-PDN-Calc-Version": APP_VERSION}
        )
    return JSONResponse(
        content={"request_id": request_id, "logs": logs},
        headers={"X-PDN-Calc-Version": APP_VERSION}
    )
