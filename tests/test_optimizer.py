"""Tests for the water budget optimizer and forecast integrator."""

import pytest
from datetime import date, timedelta

from jala.models import (
    ZoneConfig, SoilType, CropType, MoistureReading, ForecastDay,
)
from jala.irrigation.zones import IrrigationZone
from jala.optimizer.water_budget import WaterBudgetOptimizer
from jala.optimizer.forecast import WeatherForecastIntegrator


def _make_zone(zone_id: str, vwc: float = 0.20) -> IrrigationZone:
    config = ZoneConfig(
        zone_id=zone_id,
        name=zone_id,
        area_m2=100.0,
        soil_type=SoilType.LOAM,
        crop_type=CropType.VEGETABLES,
        max_flow_rate_lpm=10.0,
    )
    z = IrrigationZone(config)
    z.moisture_monitor.record(
        MoistureReading(zone_id=zone_id, volumetric_water_content=vwc)
    )
    return z


class TestWaterBudgetOptimizer:
    def test_linear_allocation_meets_demand(self):
        zones = [_make_zone("z1"), _make_zone("z2")]
        opt = WaterBudgetOptimizer(zones, daily_et0_mm=5.0)
        result = opt.optimize_linear()
        for z in zones:
            demand = z.crop_et(5.0)
            assert result[z.zone_id] >= demand - 0.01

    def test_rain_reduces_allocation(self):
        zones = [_make_zone("z1")]
        no_rain = WaterBudgetOptimizer(zones, daily_et0_mm=5.0, forecast_rain_mm=0.0)
        with_rain = WaterBudgetOptimizer(zones, daily_et0_mm=5.0, forecast_rain_mm=4.0)
        r1 = no_rain.optimize_linear()
        r2 = with_rain.optimize_linear()
        assert r2["z1"] <= r1["z1"]

    def test_budget_cap(self):
        zones = [_make_zone("z1", vwc=0.15), _make_zone("z2", vwc=0.15)]
        opt = WaterBudgetOptimizer(zones, daily_et0_mm=5.0, max_total_liters=500.0)
        result = opt.optimize_linear()
        total = sum(result[z.zone_id] * z.config.area_m2 for z in zones)
        assert total <= 500.0 + 1.0  # small tolerance

    def test_quadratic_returns_results(self):
        zones = [_make_zone("z1")]
        opt = WaterBudgetOptimizer(zones, daily_et0_mm=5.0)
        result = opt.optimize_quadratic()
        assert "z1" in result
        assert result["z1"] >= 0

    def test_summary(self):
        zones = [_make_zone("z1")]
        opt = WaterBudgetOptimizer(zones, daily_et0_mm=5.0)
        summary = opt.summary()
        assert "allocation" in summary
        assert "total_liters" in summary
        assert summary["total_liters"] >= 0


class TestWeatherForecastIntegrator:
    @pytest.fixture
    def integrator(self) -> WeatherForecastIntegrator:
        return WeatherForecastIntegrator(
            rain_threshold_probability=0.60,
            rain_credit_factor=0.70,
            lookahead_days=3,
        )

    def test_rain_credit_above_threshold(self, integrator: WeatherForecastIntegrator):
        today = date(2025, 7, 1)
        integrator.update_forecast([
            ForecastDay(date=today, rain_probability=0.80, expected_rain_mm=10.0),
        ])
        credit = integrator.expected_rain_mm(today)
        assert abs(credit - 7.0) < 0.01  # 10 * 0.70

    def test_no_credit_below_threshold(self, integrator: WeatherForecastIntegrator):
        today = date(2025, 7, 1)
        integrator.update_forecast([
            ForecastDay(date=today, rain_probability=0.40, expected_rain_mm=10.0),
        ])
        assert integrator.expected_rain_mm(today) == 0.0

    def test_defer_irrigation(self, integrator: WeatherForecastIntegrator):
        today = date(2025, 7, 1)
        forecasts = [
            ForecastDay(
                date=today + timedelta(days=i),
                rain_probability=0.80,
                expected_rain_mm=6.0,
            )
            for i in range(3)
        ]
        integrator.update_forecast(forecasts)
        # cumulative credit = 3 * 6 * 0.7 = 12.6 mm
        assert integrator.should_defer_irrigation(10.0, today)
        assert not integrator.should_defer_irrigation(20.0, today)

    def test_adjusted_depth(self, integrator: WeatherForecastIntegrator):
        today = date(2025, 7, 1)
        integrator.update_forecast([
            ForecastDay(date=today, rain_probability=0.80, expected_rain_mm=5.0),
        ])
        adjusted = integrator.adjusted_irrigation_mm(10.0, today)
        assert adjusted < 10.0
        assert adjusted >= 0.0

    def test_synthetic_forecast(self, integrator: WeatherForecastIntegrator):
        forecasts = integrator.generate_synthetic_forecast(
            start_date=date(2025, 7, 1), days=7, seed=42,
        )
        assert len(forecasts) == 7
        assert all(0 <= f.rain_probability <= 1 for f in forecasts)
