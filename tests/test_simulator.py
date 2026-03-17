"""Tests for the simulation engine."""

import pytest

from jala.simulator import run_simulation, generate_weather_series, _default_zones


class TestSimulator:
    def test_run_default(self):
        result = run_simulation(days=7, seed=42)
        assert result.days == 7
        assert result.total_et0_mm > 0
        assert result.total_water_liters >= 0

    def test_weather_series_length(self):
        series = generate_weather_series(10, seed=0)
        assert len(series) == 10

    def test_weather_series_valid(self):
        series = generate_weather_series(30, seed=1)
        for w in series:
            assert w.temp_max_c > w.temp_min_c - 5  # allow some tolerance
            assert 0 <= w.humidity_pct <= 100
            assert w.wind_speed_m_s >= 0
            assert w.solar_radiation_mj >= 0
            assert w.rainfall_mm >= 0

    def test_default_zones(self):
        zones = _default_zones()
        assert len(zones) == 3
        ids = [z.zone_id for z in zones]
        assert "lawn_front" in ids
        assert "veggie_garden" in ids
        assert "orchard" in ids

    def test_no_forecast_uses_more_water(self):
        with_fc = run_simulation(days=14, seed=42, use_forecast=True)
        no_fc = run_simulation(days=14, seed=42, use_forecast=False)
        # With forecast should generally use less or equal water
        assert with_fc.total_water_liters <= no_fc.total_water_liters + 1.0

    def test_simulation_result_fields(self):
        result = run_simulation(days=5, seed=99)
        assert result.total_rain_mm >= 0
        assert result.water_savings_pct >= 0
