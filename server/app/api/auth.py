from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_token
from app.db.session import get_db
from app.schemas.auth import CodeResponse, LoginResponse, RequestCode, VerifyCode
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Вход"])


@router.post("/request-code", response_model=CodeResponse)
def request_code(body: RequestCode, request: Request, db: Session = Depends(get_db)):
    return AuthService(db).request_code(body.email, request.client.host if request.client else "unknown")


@router.post("/verify-code", response_model=LoginResponse)
def verify_code(body: VerifyCode, request: Request, response: Response, db: Session = Depends(get_db)):
    user, is_new = AuthService(db).verify_code(
        body.code_id, body.code, request.client.host if request.client else "unknown"
    )
    response.set_cookie(
        "access_token",
        create_token(user.id),
        max_age=86400,
        path="/",
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
    )
    return {"user": user, "is_new_user": is_new}


@router.post("/logout", status_code=204)
def logout():
    response = Response(status_code=204)
    response.delete_cookie("access_token", path="/", httponly=True, secure=get_settings().cookie_secure, samesite="lax")
    return response
