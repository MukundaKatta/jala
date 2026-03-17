"""Tests for flow meter."""

import pytest
from datetime import datetime

from jala.models import FlowReading
from jala.sensors.flow import FlowMeter


@pytest.fixture
def meter() -> FlowMeter:
    return FlowMeter(zone_id="test", expected_flow_lpm=20.0, leak_threshold_factor=1.5)


class TestFlowMeter:
    def test_volume_delivered(self, meter: FlowMeter):
        assert meter.volume_delivered(10.0, 5.0) == 50.0

    def test_cumulative(self, meter: FlowMeter):
        meter.record(FlowReading(
            zone_id="test", flow_rate_lpm=10.0, total_liters=100.0,
        ))
        assert meter.cumulative_liters == 100.0

    def test_leak_detection(self, meter: FlowMeter):
        meter.record(FlowReading(
            zone_id="test", flow_rate_lpm=35.0, total_liters=100.0,
        ))
        assert meter.detect_leak()

    def test_no_leak(self, meter: FlowMeter):
        meter.record(FlowReading(
            zone_id="test", flow_rate_lpm=18.0, total_liters=50.0,
        ))
        assert not meter.detect_leak()

    def test_usage_since(self, meter: FlowMeter):
        t1 = datetime(2025, 7, 1, 6, 0)
        t2 = datetime(2025, 7, 1, 7, 0)
        t3 = datetime(2025, 7, 1, 8, 0)
        meter.record(FlowReading(
            zone_id="test", flow_rate_lpm=10.0, total_liters=100.0, timestamp=t1,
        ))
        meter.record(FlowReading(
            zone_id="test", flow_rate_lpm=10.0, total_liters=200.0, timestamp=t2,
        ))
        meter.record(FlowReading(
            zone_id="test", flow_rate_lpm=10.0, total_liters=350.0, timestamp=t3,
        ))
        assert meter.usage_since(t2) == 150.0
