import logging
from datetime import datetime

logger = logging.getLogger("pdn_audit")
logger.setLevel(logging.INFO)
handler = logging.FileHandler("audit.log")
formatter = logging.Formatter('%(asctime)s | %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def log_request(request_data: dict):
    """Логируем входной запрос без ПДН и с псевдонимизацией client_id"""
    data_copy = request_data.copy()
    if "meta" in data_copy and "client_id" in data_copy["meta"]:
        client_id = data_copy["meta"]["client_id"]
        data_copy["meta"]["client_id"] = f"{hash(client_id) & 0xffffffff:08x}"
    logger.info(f"REQUEST: {data_copy}")

def log_response(request_id: str, response_data: dict):
    """Логируем ответ без ПДН"""
    response_copy = response_data.copy()
    response_copy.pop("pdn_percent", None)
    response_copy.pop("breakdown", None)
    logger.info(f"RESPONSE ({request_id}): {response_copy}")

def get_audit_by_request(request_id: str, log_file="audit.log"):
    """Ищет все записи аудита по request_id"""
    results = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if request_id in line:
                    results.append(line.strip())
    except FileNotFoundError:
        return []
    return results