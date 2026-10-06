"""HTTP-маршруты и преобразование бизнес-ошибок в HTTP-ответы."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.models import risk
from app.repositories.predictions import PredictionRepository
from app.schemas.prediction import (
    ErrorResponse,
    FarmRequest,
    HealthResponse,
    ModelInfoResponse,
    PredictionResponse,
    RiskLevel,
)
from app.services.scoring import (
    ModelUnavailableError,
    UnknownRegionError,
    make_prediction,
)

router = APIRouter()


def get_repository(request: Request) -> PredictionRepository:
    """Получить хранилище текущего экземпляра приложения."""
    return request.app.state.predictions


Repository = Annotated[PredictionRepository, Depends(get_repository)]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка работоспособности API",
    description="Проверяет, что процесс API отвечает на HTTP-запросы.",
)
def health() -> HealthResponse:
    """Проверить доступность API независимо от готовности модели."""
    return HealthResponse(status="ok")


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Информация о модели",
    description="Возвращает имя, версию, тип и готовность модели.",
)
def model_info() -> ModelInfoResponse:
    """Получить метаданные модели."""
    return ModelInfoResponse(
        model_name=risk.MODEL_NAME,
        model_version=risk.MODEL_VERSION,
        model_type=risk.MODEL_TYPE,
        status="ready" if risk.MODEL_READY else "unavailable",
    )


@router.post(
    "/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Оценка риска хозяйства",
    description="Выполняет прогноз и сохраняет его под новым request_id.",
    responses={
        400: {"model": ErrorResponse, "description": "Неизвестный регион"},
        503: {"model": ErrorResponse, "description": "Модель недоступна"},
    },
)
def predict(
    data: FarmRequest, response: Response, repository: Repository
) -> PredictionResponse:
    """Создать прогноз и указать адрес созданного ресурса."""
    try:
        result = make_prediction(data, repository)
    except UnknownRegionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ModelUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    response.headers["Location"] = f"/predictions/{result.request_id}"
    return result


@router.get(
    "/predictions",
    response_model=list[PredictionResponse],
    summary="Последние прогнозы",
    description="Возвращает новые результаты первыми с фильтрацией по уровню риска.",
)
def get_predictions(
    repository: Repository,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Количество результатов")
    ] = 10,
    risk_level: Annotated[
        RiskLevel | None, Query(description="Фильтр: low, medium или high")
    ] = None,
) -> list[PredictionResponse]:
    """Получить ограниченный список прогнозов."""
    return repository.list_recent(limit, risk_level)


@router.get(
    "/predictions/{request_id}",
    response_model=PredictionResponse,
    summary="Прогноз по идентификатору",
    description="Возвращает ранее сохраненный прогноз по request_id.",
    responses={404: {"model": ErrorResponse, "description": "Прогноз не найден"}},
)
def get_prediction(request_id: str, repository: Repository) -> PredictionResponse:
    """Найти прогноз или вернуть 404."""
    result = repository.get(request_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return result
