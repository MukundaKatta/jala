"""Tests for the WeatherStation and Penman-Monteith ET0 calculation."""

import math
import pytest

from jala.models import WeatherReading
from jala.sensors.weather import WeatherStation


@pytest.fixture
def station() -> WeatherStation:
    return WeatherStation(altitude_m=100.0, latitude_deg=30.0)


@pytest.fixture
def typical_summer_reading() -> WeatherReading:
    """FAO-56 Example 18 (approx): hot, dry, sunny day."""
    return WeatherReading(
        temp_max_c=34.8,
        temp_min_c=19.2,
        humidity_pct=45.0,
        wind_speed_m_s=2.0,
        solar_radiation_mj=22.0,
    )


class TestSaturationVapourPressure:
    def test_known_values(self):
        # At 20 C, e0 should be ~2.338 kPa (FAO-56 Table 2.3)
        e0 = WeatherStation.saturation_vapour_pressure(20.0)
        assert abs(e0 - 2.338) < 0.01

    def test_increases_with_temperature(self):
        e_low = WeatherStation.saturation_vapour_pressure(10.0)
        e_high = WeatherStation.saturation_vapour_pressure(30.0)
        assert e_high > e_low

    def test_zero_degrees(self):
        e0 = WeatherStation.saturation_vapour_pressure(0.0)
        assert abs(e0 - 0.6108) < 0.01


class TestSlopeVapourPressureCurve:
    def test_positive(self):
        delta = WeatherStation.slope_vapour_pressure_curve(25.0)
        assert delta > 0

    def test_increases_with_temperature(self):
        d1 = WeatherStation.slope_vapour_pressure_curve(10.0)
        d2 = WeatherStation.slope_vapour_pressure_curve(30.0)
        assert d2 > d1


class TestPsychrometricConstant:
    def test_sea_level(self):
        station = WeatherStation(altitude_m=0.0)
        gamma = station.psychrometric_constant()
        # At sea level, gamma ~0.0674 kPa/C
        assert abs(gamma - 0.0674) < 0.002

    def test_decreases_with_altitude(self):
        low = WeatherStation(altitude_m=0.0).psychrometric_constant()
        high = WeatherStation(altitude_m=1000.0).psychrometric_constant()
        assert high < low


class TestExtraterrestrialRadiation:
    def test_positive(self, station: WeatherStation):
        ra = station.extraterrestrial_radiation(180)
        assert ra > 0

    def test_summer_higher_than_winter_northern(self):
        station = WeatherStation(latitude_deg=40.0)
        ra_summer = station.extraterrestrial_radiation(172)  # ~June 21
        ra_winter = station.extraterrestrial_radiation(355)  # ~Dec 21
        assert ra_summer > ra_winter


class TestET0:
    def test_positive_et0(self, station: WeatherStation, typical_summer_reading: WeatherReading):
        et0 = station.compute_et0(typical_summer_reading, day_of_year=180)
        assert et0 > 0

    def test_reasonable_range(self, station: WeatherStation, typical_summer_reading: WeatherReading):
        """ET0 for a hot summer day should be 3-10 mm/day."""
        et0 = station.compute_et0(typical_summer_reading, day_of_year=180)
        assert 3.0 < et0 < 10.0

    def test_higher_temp_higher_et0(self, station: WeatherStation):
        cool = WeatherReading(
            temp_max_c=22.0, temp_min_c=12.0,
            humidity_pct=60.0, wind_speed_m_s=1.5, solar_radiation_mj=15.0,
        )
        hot = WeatherReading(
            temp_max_c=38.0, temp_min_c=24.0,
            humidity_pct=30.0, wind_speed_m_s=3.0, solar_radiation_mj=28.0,
        )
        assert station.compute_et0(hot, 180) > station.compute_et0(cool, 180)

    def test_high_humidity_lower_et0(self, station: WeatherStation):
        dry = WeatherReading(
            temp_max_c=30.0, temp_min_c=18.0,
            humidity_pct=25.0, wind_speed_m_s=2.0, solar_radiation_mj=20.0,
        )
        humid = WeatherReading(
            temp_max_c=30.0, temp_min_c=18.0,
            humidity_pct=85.0, wind_speed_m_s=2.0, solar_radiation_mj=20.0,
        )
        assert station.compute_et0(dry, 180) > station.compute_et0(humid, 180)

    def test_from_latest(self, station: WeatherStation, typical_summer_reading: WeatherReading):
        station.record(typical_summer_reading)
        et0 = station.compute_et0_from_latest(180)
        assert et0 > 0

    def test_no_readings_raises(self, station: WeatherStation):
        with pytest.raises(ValueError):
            station.compute_et0_from_latest()
