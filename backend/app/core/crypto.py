import base64
import hashlib
from cryptography.fernet import Fernet
from app.core.config import settings

# Fernet key derive de SECRET_KEY -- meme pattern que provisioning.py (admin_password
# des telephones physiques) et ClientAccess cote ERPCRM.
_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()))


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet.decrypt(value.encode()).decode()
    except Exception:
        return ""
