"""Valve controller simulating zone activation and deactivation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from jala.models import IrrigationEvent, FlowReading
from jala.irrigation.zones import IrrigationZone


class ValveController:
    """Simulates opening and closing irrigation valves for zones.

    Only one zone valve may be open at a time (single-station controller).
    """

    def __init__(self) -> None:
        self._active_zone: Optional[str] = None
        self._open_time: Optional[datetime] = None
        self.history: list[IrrigationEvent] = []

    @property
    def is_active(self) -> bool:
        return self._active_zone is not None

    @property
    def active_zone_id(self) -> Optional[str]:
        return self._active_zone

    def open_valve(self, zone: IrrigationZone, timestamp: Optional[datetime] = None) -> None:
        """Open the valve for a zone.

        Raises
        ------
        RuntimeError
            If another zone's valve is already open.
        """
        if self._active_zone is not None:
            raise RuntimeError(
                f"Cannot open valve for {zone.zone_id}: "
                f"zone {self._active_zone} is already active"
            )
        self._active_zone = zone.zone_id
        self._open_time = timestamp or datetime.now()

    def close_valve(
        self,
        zone: IrrigationZone,
        timestamp: Optional[datetime] = None,
    ) -> IrrigationEvent:
        """Close the valve and record the irrigation event.

        Returns
        -------
        IrrigationEvent
            Details of the completed irrigation.
        """
        if self._active_zone != zone.zone_id:
            raise RuntimeError(
                f"Zone {zone.zone_id} is not the active zone "
                f"(active: {self._active_zone})"
            )
        close_time = timestamp or datetime.now()
        duration_min = (close_time - self._open_time).total_seconds() / 60.0
        volume = zone.config.max_flow_rate_lpm * duration_min
        depth_mm = volume / zone.config.area_m2  # 1 L / 1 m2 = 1 mm

        event = IrrigationEvent(
            zone_id=zone.zone_id,
            start_time=self._open_time,
            duration_minutes=max(duration_min, 0.01),
            volume_liters=volume,
            depth_mm=depth_mm,
        )
        self.history.append(event)

        # Update the flow meter
        prev_total = zone.flow_meter.cumulative_liters
        zone.flow_meter.record(
            FlowReading(
                zone_id=zone.zone_id,
                flow_rate_lpm=zone.config.max_flow_rate_lpm,
                total_liters=prev_total + volume,
                timestamp=close_time,
            )
        )

        self._active_zone = None
        self._open_time = None
        return event

    def irrigate(
        self,
        zone: IrrigationZone,
        duration_minutes: float,
        start_time: Optional[datetime] = None,
    ) -> IrrigationEvent:
        """Convenience: open, wait, close in one call (simulated)."""
        start = start_time or datetime.now()
        self.open_valve(zone, timestamp=start)
        end = start + timedelta(minutes=duration_minutes)
        event = self.close_valve(zone, timestamp=end)

        # Apply the irrigation to the zone's soil moisture
        zone.apply_irrigation_mm(event.depth_mm)
        return event

    def total_volume_liters(self) -> float:
        """Total water delivered across all events."""
        return sum(e.volume_liters for e in self.history)
