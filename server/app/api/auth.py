from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import ACCESS_TTL, REFRESH_TTL, create_token
from app.db.session import get_db
from app.schemas.auth import CodeResponse, LoginResponse, RequestCode, VerifyCode
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Вход"])


def set_token_cookie(response, user_id, token_type):
    response.set_cookie(
        f"{token_type}_token",
        create_token(user_id, token_type),
        max_age=ACCESS_TTL if token_type == "access" else REFRESH_TTL,
        path="/" if token_type == "access" else "/api/v1/auth",
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
    )


@router.post("/request-code", response_model=CodeResponse)
def request_code(body: RequestCode, request: Request, db: Session = Depends(get_db)):
    return AuthService(db).request_code(body.email, request.client.host if request.client else "unknown")


@router.post("/verify-code", response_model=LoginResponse)
def verify_code(body: VerifyCode, request: Request, response: Response, db: Session = Depends(get_db)):
    user, is_new = AuthService(db).verify_code(
        body.code_id, body.code, request.client.host if request.client else "unknown"
    )
    set_token_cookie(response, user.id, "access")
    set_token_cookie(response, user.id, "refresh")
    return {"user": user, "is_new_user": is_new}


@router.post("/refresh", status_code=204)
def refresh(request: Request, db: Session = Depends(get_db)):
    user = AuthService(db).refresh(request.cookies.get("refresh_token", ""))
    response = Response(status_code=204)
    set_token_cookie(response, user.id, "access")
    return response


@router.post("/logout", status_code=204)
def logout():
    response = Response(status_code=204)
    response.delete_cookie("access_token", path="/", httponly=True, secure=get_settings().cookie_secure, samesite="lax")
    response.delete_cookie(
        "refresh_token", path="/api/v1/auth", httponly=True, secure=get_settings().cookie_secure, samesite="lax"
    )
    return response
