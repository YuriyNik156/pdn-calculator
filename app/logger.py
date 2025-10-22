import logging
import json
from datetime import datetime
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """Форматирует логи в JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }

        # Добавляем дополнительные поля, если они есть
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id

        return json.dumps(log_record, ensure_ascii=False)


def setup_logging():
    """Настраивает логирование в JSON-формате."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    logger.addHandler(handler)

    # Отключаем лишние логи Uvicorn
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    return logger


logger = setup_logging()