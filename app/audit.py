import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

AUDIT_FILE = Path("audit.log")


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Маскирует персональные данные (PII) в JSON."""
    masked = {}
    for k, v in data.items():
        if k.lower() in {"user", "username", "email", "phone"}:
            masked[k] = "***masked***"
        elif isinstance(v, dict):
            masked[k] = mask_sensitive_data(v)
        elif isinstance(v, list):
            masked[k] = [mask_sensitive_data(i) if isinstance(i, dict) else i for i in v]
        else:
            masked[k] = v
    return masked


def write_audit_log(request_id: str, endpoint: str, payload: Dict[str, Any], result: Dict[str, Any]):
    """Пишет строку в audit.log."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "endpoint": endpoint,
        "payload": mask_sensitive_data(payload),
        "result": result,
    }

    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_audit_by_request_id(request_id: str):
    """Возвращает лог-записи по request_id."""
    if not AUDIT_FILE.exists():
        return []

    with AUDIT_FILE.open("r", encoding="utf-8") as f:
        logs = [json.loads(line) for line in f.readlines()]

    return [log for log in logs if log.get("request_id") == request_id]
