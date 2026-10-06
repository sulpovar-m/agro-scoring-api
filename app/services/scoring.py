"""Бизнес-валидация и последовательность выполнения прогноза."""

import logging
from uuid import uuid4

from app.models import risk
from app.repositories.predictions import PredictionRepository
from app.schemas.prediction import FarmRequest, PredictionResponse, RiskLevel

logger = logging.getLogger(__name__)
ALLOWED_REGIONS = {"Krasnodar", "Rostov", "Stavropol"}


class UnknownRegionError(ValueError):
    """Регион не входит в бизнес-справочник."""


class ModelUnavailableError(RuntimeError):
    """Модель временно недоступна."""


def get_risk_level(score: float) -> RiskLevel:
    """
    Преобразует score в категорию риска.
    """

    if score < 0.3:
        return "low"

    if score < 0.7:
        return "medium"

    return "high"


# ------------------------------------------------------------
# ПОСТПРОЦЕССИНГ:
# ВЫДАЧА РЕКОМЕНДАЦИИ
# ------------------------------------------------------------


def get_recommendation(level: RiskLevel) -> str:
    """
    Возвращает рекомендацию в зависимости от категории риска.
    """

    if level == "low":
        return "Стандартное рассмотрение"

    if level == "medium":
        return "Требуется дополнительная проверка"

    return "Высокий риск. Требуется ручное рассмотрение"


def make_prediction(
    data: FarmRequest, repository: PredictionRepository
) -> PredictionResponse:
    """Проверить данные, вычислить риск и сохранить результат."""
    if not risk.MODEL_READY:
        raise ModelUnavailableError("Model is temporarily unavailable")
    if data.region not in ALLOWED_REGIONS:
        raise UnknownRegionError(
            f"Unknown region: {data.region}. Allowed regions: {sorted(ALLOWED_REGIONS)}"
        )
    request_id = str(uuid4())
    logger.info(
        "Prediction started | request_id=%s | farm_id=%s", request_id, data.farm_id
    )
    score = risk.calculate_risk(data)
    level = get_risk_level(score)
    result = PredictionResponse(
        request_id=request_id,
        farm_id=data.farm_id,
        risk_score=score,
        risk_level=level,
        recommendation=get_recommendation(level),
        model_version=risk.MODEL_VERSION,
    )
    repository.save(result)
    logger.info(
        "Prediction completed | request_id=%s | farm_id=%s | score=%s | level=%s",
        request_id,
        data.farm_id,
        score,
        level,
    )
    return result
