from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from .models import PDNRequestSchema
from .services import calculate_pdn
from .audit import get_audit_by_request

APP_VERSION = "v1.0"  # Версия формулы/сервиса

app = FastAPI(title="PDN Calculator MVP")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
