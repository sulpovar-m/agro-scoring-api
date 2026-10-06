"""Сборка приложения и измерение времени HTTP-запросов."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.api.routes import router
from app.repositories.predictions import PredictionRepository


def create_app() -> FastAPI:
    """Создать приложение с собственным хранилищем в памяти."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
    )
    application = FastAPI(
        title="Agro Scoring API",
        description="Учебный REST API оценки риска сельскохозяйственных предприятий.",
        version="1.1.0",
        swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    )
    application.state.predictions = PredictionRepository()

    @application.middleware("http")
    async def add_process_time(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Добавить длительность обработки и записать HTTP-результат в журнал."""
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        response.headers["X-Process-Time"] = f"{elapsed:.6f}"
        logging.getLogger(__name__).info(
            "%s %s | status=%s | time=%.6f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

    application.include_router(router)
    return application


app = create_app()
