import logging
from pathlib import Path
from app.security import mask_sensitive

# Логгер аудита
logger = logging.getLogger("pdn_audit")
logger.setLevel(logging.INFO)
log_path = Path("audit.log")
log_path.touch(exist_ok=True)
handler = logging.FileHandler(log_path, encoding="utf-8")
formatter = logging.Formatter('%(asctime)s | %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def log_request(request_data: dict):
    """
    Логируем входной запрос без ПДН и с псевдонимизацией client_id и request_id.
    """
    masked_data = mask_sensitive(request_data)
    logger.info(f"REQUEST: {masked_data}")


def log_response(request_id: str, response_data: dict):
    """
    Логируем ответ без ПДН и breakdown, с маскировкой meta-полей.
    """
    response_copy = mask_sensitive(response_data)
    response_copy.pop("pdn_percent", None)
    response_copy.pop("breakdown", None)
    logger.info(f"RESPONSE ({request_id}): {response_copy}")


def get_audit_by_request(request_id: str, log_file="audit.log"):
    """
    Ищет все записи аудита по request_id
    """
    results = []
    try:
        # Чтение в UTF-8, fallback на cp1251
        try:
            with open(log_file, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(log_file, "r", encoding="cp1251", errors="ignore") as f:
                lines = f.readlines()

        for line in lines:
            if request_id in line:
                results.append(line.strip())

    except FileNotFoundError:
        return []

    return results
