import os
from cryptography.fernet import Fernet

# В production SECRET_KEY должен быть установлен в ENV
# Dev fallback только для локального тестирования
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    print("WARNING: SECRET_KEY not set in ENV. Using temporary dev key!")
    SECRET_KEY = Fernet.generate_key()

fernet = Fernet(SECRET_KEY if isinstance(SECRET_KEY, bytes) else SECRET_KEY.encode())


def encrypt_secret(value: str) -> str:
    """Шифруем секрет"""
    return fernet.encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Расшифровываем секрет"""
    return fernet.decrypt(token.encode()).decode()
