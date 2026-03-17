"""Tests for irrigation zones."""

import pytest

from jala.models import ZoneConfig, SoilType, CropType, MoistureReading
from jala.irrigation.zones import IrrigationZone


@pytest.fixture
def veggie_zone() -> IrrigationZone:
    config = ZoneConfig(
        zone_id="veggie",
        name="Vegetable Garden",
        area_m2=100.0,
        soil_type=SoilType.LOAM,
        crop_type=CropType.VEGETABLES,
        max_flow_rate_lpm=10.0,
    )
    zone = IrrigationZone(config)
    zone.moisture_monitor.record(
        MoistureReading(zone_id="veggie", volumetric_water_content=0.25)
    )
    return zone


class TestIrrigationZone:
    def test_crop_coefficient(self, veggie_zone: IrrigationZone):
        assert veggie_zone.crop_coefficient == 1.05

    def test_root_depth(self, veggie_zone: IrrigationZone):
        assert veggie_zone.root_depth_m == 0.40

    def test_crop_et(self, veggie_zone: IrrigationZone):
        et0 = 5.0
        etc = veggie_zone.crop_et(et0)
        assert abs(etc - 5.25) < 0.01

    def test_required_depth(self, veggie_zone: IrrigationZone):
        # VWC = 0.25, FC = 0.27, deficit = 0.02
        # depth = 0.02 * 0.40 * 1000 = 8 mm
        depth = veggie_zone.required_depth_mm()
        assert abs(depth - 8.0) < 0.1

    def test_required_volume(self, veggie_zone: IrrigationZone):
        # depth 8mm * 100 m2 = 800 liters
        vol = veggie_zone.required_volume_liters()
        assert abs(vol - 800.0) < 10.0

    def test_irrigation_duration(self, veggie_zone: IrrigationZone):
        # 800 L / 10 LPM = 80 minutes
        dur = veggie_zone.irrigation_duration_minutes()
        assert abs(dur - 80.0) < 1.0

    def test_apply_et_reduces_moisture(self, veggie_zone: IrrigationZone):
        before = veggie_zone.moisture_monitor.current_vwc
        veggie_zone.apply_et_mm(5.0)
        after = veggie_zone.moisture_monitor.current_vwc
        assert after < before

    def test_apply_irrigation_increases_moisture(self, veggie_zone: IrrigationZone):
        veggie_zone.apply_et_mm(10.0)
        before = veggie_zone.moisture_monitor.current_vwc
        veggie_zone.apply_irrigation_mm(5.0)
        after = veggie_zone.moisture_monitor.current_vwc
        assert after > before
