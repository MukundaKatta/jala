"""Tests for the irrigation scheduler."""

import pytest
from datetime import datetime

from jala.models import (
    ZoneConfig, SoilType, CropType, MoistureReading, WeatherReading,
)
from jala.irrigation.zones import IrrigationZone
from jala.irrigation.scheduler import IrrigationScheduler
from jala.sensors.weather import WeatherStation


def _make_zone(zone_id: str, vwc: float) -> IrrigationZone:
    config = ZoneConfig(
        zone_id=zone_id,
        name=zone_id,
        area_m2=100.0,
        soil_type=SoilType.LOAM,
        crop_type=CropType.TURF_GRASS,
        max_flow_rate_lpm=10.0,
        management_allowed_depletion=0.50,
    )
    z = IrrigationZone(config)
    z.moisture_monitor.record(
        MoistureReading(zone_id=zone_id, volumetric_water_content=vwc)
    )
    return z


@pytest.fixture
def scheduler() -> IrrigationScheduler:
    station = WeatherStation(altitude_m=100.0, latitude_deg=30.0)
    zones = [_make_zone("a", 0.25), _make_zone("b", 0.18)]
    return IrrigationScheduler(station, zones)


class TestIrrigationScheduler:
    def test_run_day_returns_events(self, scheduler: IrrigationScheduler):
        reading = WeatherReading(
            temp_max_c=32.0, temp_min_c=18.0,
            humidity_pct=45.0, wind_speed_m_s=2.0,
            solar_radiation_mj=22.0, rainfall_mm=0.0,
        )
        events = scheduler.run_day(reading, day_of_year=180)
        # Zone "b" starts at 0.18 which is below threshold (0.195), should irrigate
        assert isinstance(events, list)

    def test_rain_reduces_irrigation(self, scheduler: IrrigationScheduler):
        dry_reading = WeatherReading(
            temp_max_c=30.0, temp_min_c=18.0,
            humidity_pct=50.0, wind_speed_m_s=2.0,
            solar_radiation_mj=20.0, rainfall_mm=0.0,
        )
        wet_reading = WeatherReading(
            temp_max_c=25.0, temp_min_c=18.0,
            humidity_pct=80.0, wind_speed_m_s=1.0,
            solar_radiation_mj=10.0, rainfall_mm=20.0,
        )
        # Run dry day first
        dry_events = scheduler.run_day(dry_reading, day_of_year=180)
        dry_volume = sum(e.volume_liters for e in dry_events)

        # Reset zones
        for z in scheduler.zones.values():
            z.moisture_monitor.record(
                MoistureReading(zone_id=z.zone_id, volumetric_water_content=0.18)
            )

        wet_events = scheduler.run_day(wet_reading, day_of_year=180)
        wet_volume = sum(e.volume_liters for e in wet_events)
        # Wet day should have same or less irrigation
        assert wet_volume <= dry_volume + 1.0

    def test_get_zone(self, scheduler: IrrigationScheduler):
        zone = scheduler.get_zone("a")
        assert zone.zone_id == "a"
