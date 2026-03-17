"""Tests for valve controller."""

import pytest
from datetime import datetime, timedelta

from jala.models import ZoneConfig, SoilType, CropType, MoistureReading
from jala.irrigation.zones import IrrigationZone
from jala.irrigation.valves import ValveController


@pytest.fixture
def zone() -> IrrigationZone:
    config = ZoneConfig(
        zone_id="test",
        name="Test Zone",
        area_m2=100.0,
        soil_type=SoilType.LOAM,
        crop_type=CropType.TURF_GRASS,
        max_flow_rate_lpm=10.0,
    )
    z = IrrigationZone(config)
    z.moisture_monitor.record(
        MoistureReading(zone_id="test", volumetric_water_content=0.20)
    )
    return z


@pytest.fixture
def valve() -> ValveController:
    return ValveController()


class TestValveController:
    def test_irrigate(self, valve: ValveController, zone: IrrigationZone):
        start = datetime(2025, 7, 1, 6, 0)
        event = valve.irrigate(zone, duration_minutes=10.0, start_time=start)
        assert event.zone_id == "test"
        assert event.duration_minutes == 10.0
        assert event.volume_liters == 100.0  # 10 LPM * 10 min
        assert event.depth_mm == 1.0  # 100 L / 100 m2

    def test_double_open_raises(self, valve: ValveController, zone: IrrigationZone):
        valve.open_valve(zone)
        with pytest.raises(RuntimeError):
            valve.open_valve(zone)

    def test_close_wrong_zone_raises(self, valve: ValveController, zone: IrrigationZone):
        other_config = ZoneConfig(
            zone_id="other", name="Other", area_m2=50.0,
            soil_type=SoilType.SAND, crop_type=CropType.TURF_GRASS,
        )
        other = IrrigationZone(other_config)
        valve.open_valve(zone)
        with pytest.raises(RuntimeError):
            valve.close_valve(other)

    def test_total_volume(self, valve: ValveController, zone: IrrigationZone):
        valve.irrigate(zone, 10.0, datetime(2025, 7, 1, 6, 0))
        valve.irrigate(zone, 5.0, datetime(2025, 7, 1, 7, 0))
        assert valve.total_volume_liters() == 150.0

    def test_flow_meter_updated(self, valve: ValveController, zone: IrrigationZone):
        valve.irrigate(zone, 10.0, datetime(2025, 7, 1, 6, 0))
        assert zone.flow_meter.cumulative_liters == 100.0
