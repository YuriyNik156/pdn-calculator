from fastapi import HTTPException, Header

def require_admin(x_api_key: str = Header(...)):
    if x_api_key != "secret-admin-key":
        raise HTTPException(status_code=403, detail="Forbidden: admin access required")
