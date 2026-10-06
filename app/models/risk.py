"""Учебная модель на правилах, заменяющая обученную ML-модель."""

from app.schemas.prediction import FarmRequest

MODEL_NAME = "agro-risk-model"
MODEL_VERSION = "1.1"
MODEL_TYPE = "risk-scoring"
MODEL_READY = True


def calculate_risk(data: FarmRequest) -> float:
    """
    Реализует простую логику оценки риска по финансовым показателям
    и отраслевым факторам.
    """

    score = 0.1

    # Длительная просрочка увеличивает риск
    if data.payment_delay_days > 30:
        score += 0.3

    # Наличие предыдущих дефолтов увеличивает риск
    if data.previous_defaults > 0:
        score += 0.3

    # Большая задолженность увеличивает риск
    if data.debt > 5_000_000:
        score += 0.2

    # Малое количество осадков условно увеличивает
    # аграрный риск
    if data.precipitation_mm < 100:
        score += 0.1

    # Небольшое дополнение: экстремальная средняя температура.
    if data.temperature_avg < 5 or data.temperature_avg > 35:
        score += 0.05

    # Ограничиваем значение диапазоном от 0 до 1
    score = min(score, 1.0)

    return round(score, 2)
