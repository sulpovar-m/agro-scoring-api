"""Хранение результатов в памяти одного процесса."""

from threading import Lock

from app.schemas.prediction import PredictionResponse, RiskLevel


class PredictionRepository:
    """Сохраняет прогнозы и возвращает новые записи первыми."""

    def __init__(self) -> None:
        self._items: dict[str, PredictionResponse] = {}
        self._lock = Lock()

    def save(self, prediction: PredictionResponse) -> None:
        """Сохранить результат по уникальному идентификатору."""
        with self._lock:
            self._items[prediction.request_id] = prediction

    def get(self, request_id: str) -> PredictionResponse | None:
        """Найти результат или вернуть None."""
        with self._lock:
            return self._items.get(request_id)

    def list_recent(
        self, limit: int, risk_level: RiskLevel | None = None
    ) -> list[PredictionResponse]:
        """Сначала отфильтровать результаты, затем ограничить их количество."""
        with self._lock:
            values = list(reversed(self._items.values()))
        if risk_level is not None:
            values = [item for item in values if item.risk_level == risk_level]
        return values[:limit]
