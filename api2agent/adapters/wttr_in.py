from time import perf_counter
from typing import Any
from urllib.parse import quote

import httpx

from api2agent.adapters.models import AdapterResult, CostEstimate
from api2agent.errors import StandardErrorType, error_type_for_status


class WttrInWeatherAdapter:
    capability_id = "weather.get"
    provider_id = "wttr_in"
    tool_id = "get_current_weather"

    def __init__(self, client: Any | None = None) -> None:
        self.client = client or httpx.Client(timeout=20)

    def estimate_cost(self, input: dict[str, Any]) -> CostEstimate:
        return CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared")

    def call(self, input: dict[str, Any]) -> AdapterResult:
        start = perf_counter()
        city = str(input.get("city") or "").strip()
        if not city:
            return self._error(StandardErrorType.INVALID_REQUEST, "Missing required input: city", start)

        try:
            response = self.client.get(f"https://wttr.in/{quote(city)}", params={"format": "j1"})
        except httpx.TimeoutException as exc:
            return self._error(StandardErrorType.TIMEOUT, str(exc), start)
        except httpx.HTTPError as exc:
            return self._error(StandardErrorType.PROVIDER_ERROR, str(exc), start)

        if not response.is_success:
            return self._error(error_type_for_status(response.status_code), f"HTTP {response.status_code}", start, response.status_code)

        try:
            output = self._normalize(city, response.json())
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return self._error(StandardErrorType.NORMALIZATION_ERROR, str(exc), start, response.status_code)

        return AdapterResult(
            ok=True,
            capability_id=self.capability_id,
            provider_id=self.provider_id,
            output=output,
            status_code=response.status_code,
            latency_ms=(perf_counter() - start) * 1000,
            cost=self.estimate_cost(input),
        )

    def _normalize(self, city: str, body: dict[str, Any]) -> dict[str, Any]:
        current = body["current_condition"][0]
        nearest_area = (body.get("nearest_area") or [{}])[0]
        return {
            "city": nearest_area.get("areaName", [{"value": city}])[0].get("value"),
            "country": nearest_area.get("country", [{"value": None}])[0].get("value"),
            "latitude": _float_or_none(nearest_area.get("latitude")),
            "longitude": _float_or_none(nearest_area.get("longitude")),
            "time": current.get("localObsDateTime") or current.get("observation_time"),
            "temperature_2m": _float_or_none(current.get("temp_C")),
            "temperature_unit": "°C",
            "wind_speed_10m": _float_or_none(current.get("windspeedKmph")),
            "wind_speed_unit": "km/h",
            "weather_code": _int_or_none(current.get("weatherCode")),
        }

    def _error(
        self,
        error_type: StandardErrorType,
        message: str,
        start: float,
        status_code: int | None = None,
    ) -> AdapterResult:
        return AdapterResult(
            ok=False,
            capability_id=self.capability_id,
            provider_id=self.provider_id,
            status_code=status_code,
            latency_ms=(perf_counter() - start) * 1000,
            cost=CostEstimate(estimated_cost=0.0, observed_cost=0.0, cost_source="provider_declared"),
            error_type=error_type.value,
            error_message=message,
        )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
