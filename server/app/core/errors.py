from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, *, details=None, fields=None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        self.fields = fields or []


def error_response(error: ApiError) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if "retry_after" in error.details:
        headers["Retry-After"] = str(error.details["retry_after"])
    return JSONResponse(
        status_code=error.status,
        headers=headers,
        content={
            "error": {"code": error.code, "message": error.message, "fields": error.fields, "details": error.details}
        },
    )


async def api_error_handler(request: Request, error: ApiError):
    return error_response(error)


async def validation_error_handler(request: Request, error: RequestValidationError):
    fields = [{"path": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in error.errors()]
    return error_response(ApiError(422, "VALIDATION_ERROR", "Проверьте поля запроса", fields=fields))
