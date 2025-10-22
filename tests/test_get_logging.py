from fastapi.testclient import TestClient
from app.main import app
from app.logger import logger

client = TestClient(app)

def test_get_root_logging():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    # Проверяем наличие X-Request-ID в заголовках
    assert "X-Request-ID" in response.headers
    print("X-Request-ID:", response.headers["X-Request-ID"])
