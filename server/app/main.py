import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.api import auth, library, private_works, recommendations, users, works
from app.core.config import get_settings
from app.core.errors import ApiError, api_error_handler, error_response, validation_error_handler


async def check_request(request: Request):
    route = request.scope["route"]
    path = route.path
    allowed = set()
    for parameter in route.dependant.query_params:
        annotation = parameter.field_info.annotation
        allowed.update(annotation.model_fields if hasattr(annotation, "model_fields") else [parameter.alias])
    if set(request.query_params) - allowed:
        raise ApiError(422, "VALIDATION_ERROR", "Неизвестный query-параметр")
    multiple = {"types", "genre_ids", "statuses", "tag_ids", "exclude_tag_ids"}
    if any(len(request.query_params.getlist(key)) > 1 for key in request.query_params if key not in multiple):
        raise ApiError(422, "VALIDATION_ERROR", "Параметр передан несколько раз")
    no_body = request.method in ("GET", "DELETE") or path.endswith(("/logout", "/refresh", "/retry")) or "/hidden/" in path
    if no_body and await request.body():
        raise ApiError(422, "VALIDATION_ERROR", "Тело запроса не требуется")
    if request.method == "PUT" and path.endswith("/cover"):
        form = await request.form()
        if list(form.keys()) != ["file"] or len(form.getlist("file")) != 1:
            raise ApiError(422, "VALIDATION_ERROR", "Передайте один файл в поле file")


app = FastAPI(
    title="Библиотека и рекомендации",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    dependencies=[Depends(check_request)],
)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)


@app.exception_handler(Exception)
async def unexpected_error(request, error):
    logging.getLogger(__name__).error("Необработанная ошибка: %s", type(error).__name__)
    return error_response(ApiError(500, "INTERNAL_ERROR", "Не удалось выполнить запрос"))


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return error_response(
        ApiError(error.status_code, "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR", str(error.detail))
    )


@app.middleware("http")
async def request_policy(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.headers.get("origin") not in get_settings().allowed_origins:
            return error_response(ApiError(403, "ORIGIN_FORBIDDEN", "Недопустимый Origin"))
    if request.method in ("POST", "PUT", "PATCH"):
        length = request.headers.get("content-length")
        try:
            too_large = length is not None and int(length) > 11 * 1024 * 1024
        except ValueError:
            return error_response(ApiError(422, "VALIDATION_ERROR", "Некорректный Content-Length"))
        if too_large:
            return error_response(ApiError(413, "FILE_TOO_LARGE", "Слишком большой запрос"))
    response = await call_next(request)
    if response.status_code == 413:
        return error_response(ApiError(413, "FILE_TOO_LARGE", "Слишком большой запрос"))
    if "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response


for router in (auth.router, users.router, works.router, library.router, private_works.router, recommendations.router):
    app.include_router(router, prefix="/api/v1", max_body_size=11 * 1024 * 1024)
