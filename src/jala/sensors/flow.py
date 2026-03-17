"""Flow meter tracking water usage per irrigation zone."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from jala.models import FlowReading


class FlowMeter:
    """Tracks cumulative water delivery and detects anomalies.

    Each zone has its own FlowMeter that records instantaneous flow rate
    and cumulative volume delivered.
    """

    def __init__(
        self,
        zone_id: str,
        expected_flow_lpm: float = 20.0,
        leak_threshold_factor: float = 1.5,
    ) -> None:
        self.zone_id = zone_id
        self.expected_flow_lpm = expected_flow_lpm
        self.leak_threshold_factor = leak_threshold_factor
        self.readings: list[FlowReading] = []
        self._cumulative_liters: float = 0.0

    def record(self, reading: FlowReading) -> None:
        """Store a flow reading and update cumulative volume."""
        self._cumulative_liters = reading.total_liters
        self.readings.append(reading)

    @property
    def latest(self) -> Optional[FlowReading]:
        return self.readings[-1] if self.readings else None

    @property
    def cumulative_liters(self) -> float:
        return self._cumulative_liters

    def volume_delivered(self, flow_rate_lpm: float, duration_minutes: float) -> float:
        """Compute volume in liters for a given flow rate and duration."""
        return flow_rate_lpm * duration_minutes

    def detect_leak(self) -> bool:
        """Return True if the latest flow exceeds the leak threshold."""
        if not self.readings:
            return False
        return (
            self.readings[-1].flow_rate_lpm
            > self.expected_flow_lpm * self.leak_threshold_factor
        )

    def usage_since(self, since: datetime) -> float:
        """Total liters consumed since a given timestamp."""
        relevant = [r for r in self.readings if r.timestamp >= since]
        if len(relevant) < 2:
            return 0.0
        return relevant[-1].total_liters - relevant[0].total_liters

    def daily_usage(self, target_date: Optional[datetime] = None) -> float:
        """Total liters consumed on a specific date."""
        if target_date is None:
            target_date = datetime.now()
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_readings = [
            r for r in self.readings if day_start <= r.timestamp < day_end
        ]
        if len(day_readings) < 2:
            return 0.0
        return day_readings[-1].total_liters - day_readings[0].total_liters
