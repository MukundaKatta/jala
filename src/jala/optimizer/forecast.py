"""Weather forecast integrator for proactive irrigation scheduling.

Adjusts irrigation schedules based on upcoming rain probability and
expected precipitation amounts, reducing unnecessary watering.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import numpy as np

from jala.models import ForecastDay, WeatherReading


class WeatherForecastIntegrator:
    """Integrates multi-day weather forecasts into irrigation decisions.

    When rain is forecast with sufficient probability and volume, irrigation
    is deferred or reduced to avoid waste.

    Parameters
    ----------
    rain_threshold_probability : float
        Minimum probability to credit forecast rain (default 0.60).
    rain_credit_factor : float
        Fraction of forecast rain to credit (default 0.70), accounting for
        uncertainty and runoff losses.
    lookahead_days : int
        Number of forecast days to consider (default 3).
    """

    def __init__(
        self,
        rain_threshold_probability: float = 0.60,
        rain_credit_factor: float = 0.70,
        lookahead_days: int = 3,
    ) -> None:
        self.rain_threshold_probability = rain_threshold_probability
        self.rain_credit_factor = rain_credit_factor
        self.lookahead_days = lookahead_days
        self.forecasts: list[ForecastDay] = []

    def update_forecast(self, forecasts: list[ForecastDay]) -> None:
        """Replace the current forecast with fresh data."""
        self.forecasts = sorted(forecasts, key=lambda f: f.date)

    def expected_rain_mm(self, target_date: Optional[date] = None) -> float:
        """Compute the credited rainfall for a single forecast day.

        Only rain with probability above the threshold is credited, and
        the credit is reduced by the rain_credit_factor.
        """
        if target_date is None:
            target_date = date.today()

        for f in self.forecasts:
            if f.date == target_date:
                if f.rain_probability >= self.rain_threshold_probability:
                    return f.expected_rain_mm * self.rain_credit_factor
                return 0.0
        return 0.0

    def cumulative_expected_rain_mm(self, start_date: Optional[date] = None) -> float:
        """Total credited rain over the lookahead window."""
        if start_date is None:
            start_date = date.today()
        total = 0.0
        for i in range(self.lookahead_days):
            d = start_date + timedelta(days=i)
            total += self.expected_rain_mm(d)
        return total

    def should_defer_irrigation(
        self,
        irrigation_depth_mm: float,
        start_date: Optional[date] = None,
    ) -> bool:
        """Decide whether to defer irrigation based on upcoming rain.

        Irrigation is deferred if the expected rain over the lookahead
        window covers at least 80% of the planned irrigation depth.
        """
        rain = self.cumulative_expected_rain_mm(start_date)
        return rain >= 0.8 * irrigation_depth_mm

    def adjusted_irrigation_mm(
        self,
        base_depth_mm: float,
        target_date: Optional[date] = None,
    ) -> float:
        """Reduce the planned irrigation depth by the forecast rain credit.

        Parameters
        ----------
        base_depth_mm : float
            Originally computed irrigation depth (mm).
        target_date : date, optional
            Date of planned irrigation.

        Returns
        -------
        float
            Adjusted irrigation depth (mm), >= 0.
        """
        rain_credit = self.cumulative_expected_rain_mm(target_date)
        return max(base_depth_mm - rain_credit, 0.0)

    def generate_synthetic_forecast(
        self,
        start_date: Optional[date] = None,
        days: int = 7,
        base_rain_prob: float = 0.3,
        base_rain_mm: float = 5.0,
        seed: Optional[int] = None,
    ) -> list[ForecastDay]:
        """Generate a synthetic weather forecast for simulation purposes.

        Parameters
        ----------
        start_date : date
            First forecast day.
        days : int
            Number of days to forecast.
        base_rain_prob : float
            Average daily rain probability.
        base_rain_mm : float
            Average rain amount on rainy days (mm).
        seed : int, optional
            Random seed for reproducibility.
        """
        rng = np.random.default_rng(seed)
        if start_date is None:
            start_date = date.today()

        forecasts = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            prob = float(np.clip(rng.normal(base_rain_prob, 0.15), 0, 1))
            rain = float(rng.exponential(base_rain_mm)) if prob > 0.3 else 0.0
            forecasts.append(
                ForecastDay(
                    date=d,
                    rain_probability=round(prob, 2),
                    expected_rain_mm=round(rain, 1),
                    temp_max_c=round(float(rng.normal(32, 3)), 1),
                    temp_min_c=round(float(rng.normal(20, 2)), 1),
                    humidity_pct=round(float(np.clip(rng.normal(50, 15), 15, 95)), 1),
                    wind_speed_m_s=round(float(np.clip(rng.normal(2.0, 0.8), 0.3, 6)), 1),
                    solar_radiation_mj=round(float(np.clip(rng.normal(20, 4), 5, 30)), 1),
                )
            )

        self.forecasts = forecasts
        return forecasts
