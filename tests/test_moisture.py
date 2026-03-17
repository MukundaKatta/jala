"""Tests for soil moisture monitoring."""

import pytest

from jala.models import MoistureReading, SoilType
from jala.sensors.moisture import SoilMoistureMonitor


@pytest.fixture
def monitor() -> SoilMoistureMonitor:
    return SoilMoistureMonitor(
        zone_id="test_zone",
        soil_type=SoilType.LOAM,
        management_allowed_depletion=0.50,
    )


class TestSoilMoistureMonitor:
    def test_hydraulic_properties(self, monitor: SoilMoistureMonitor):
        assert monitor.field_capacity == 0.27
        assert monitor.wilting_point == 0.12

    def test_total_available_water(self, monitor: SoilMoistureMonitor):
        assert abs(monitor.total_available_water - 0.15) < 1e-6

    def test_readily_available_water(self, monitor: SoilMoistureMonitor):
        assert abs(monitor.readily_available_water - 0.075) < 1e-6

    def test_refill_threshold(self, monitor: SoilMoistureMonitor):
        # FC - RAW = 0.27 - 0.075 = 0.195
        assert abs(monitor.refill_threshold - 0.195) < 1e-6

    def test_needs_irrigation_at_fc(self, monitor: SoilMoistureMonitor):
        monitor.record(MoistureReading(
            zone_id="test_zone", volumetric_water_content=0.27,
        ))
        assert not monitor.needs_irrigation()

    def test_needs_irrigation_below_threshold(self, monitor: SoilMoistureMonitor):
        monitor.record(MoistureReading(
            zone_id="test_zone", volumetric_water_content=0.18,
        ))
        assert monitor.needs_irrigation()

    def test_irrigation_depth(self, monitor: SoilMoistureMonitor):
        monitor.record(MoistureReading(
            zone_id="test_zone", volumetric_water_content=0.20,
        ))
        # deficit = 0.27 - 0.20 = 0.07 m3/m3
        # depth = 0.07 * 0.40 * 1000 = 28 mm (for vegetables root depth)
        # For loam with default root depth (turf = 0.15m in zone, but
        # monitor doesn't know crop), let's test with explicit root depth
        depth = monitor.irrigation_depth_mm(root_depth_m=0.40)
        assert abs(depth - 28.0) < 0.1

    def test_depletion_fraction(self, monitor: SoilMoistureMonitor):
        monitor.record(MoistureReading(
            zone_id="test_zone", volumetric_water_content=0.27,
        ))
        assert abs(monitor.depletion_fraction() - 0.0) < 1e-6

        monitor.record(MoistureReading(
            zone_id="test_zone", volumetric_water_content=0.12,
        ))
        assert abs(monitor.depletion_fraction() - 1.0) < 1e-6

    def test_moving_average(self, monitor: SoilMoistureMonitor):
        for v in [0.25, 0.24, 0.23, 0.22, 0.21]:
            monitor.record(MoistureReading(
                zone_id="test_zone", volumetric_water_content=v,
            ))
        avg = monitor.moving_average(window=5)
        assert abs(avg - 0.23) < 1e-6

    def test_trend_decreasing(self, monitor: SoilMoistureMonitor):
        for v in [0.27, 0.26, 0.25, 0.24, 0.23]:
            monitor.record(MoistureReading(
                zone_id="test_zone", volumetric_water_content=v,
            ))
        assert monitor.trend() < 0
