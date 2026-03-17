"""Irrigation zone management combining soil, crop, and sensor data."""

from __future__ import annotations

from jala.models import (
    ZoneConfig,
    SoilType,
    CropType,
    SOIL_HYDRAULIC_PROPERTIES,
    CROP_COEFFICIENTS,
    ROOT_ZONE_DEPTH,
)
from jala.sensors.moisture import SoilMoistureMonitor
from jala.sensors.flow import FlowMeter


class IrrigationZone:
    """Represents a single irrigation zone with soil, crop, and sensor state.

    Attributes
    ----------
    config : ZoneConfig
        Static zone configuration.
    moisture_monitor : SoilMoistureMonitor
        Real-time soil moisture tracking.
    flow_meter : FlowMeter
        Water delivery metering.
    """

    def __init__(self, config: ZoneConfig) -> None:
        self.config = config
        self.moisture_monitor = SoilMoistureMonitor(
            zone_id=config.zone_id,
            soil_type=config.soil_type,
            management_allowed_depletion=config.management_allowed_depletion,
        )
        self.flow_meter = FlowMeter(
            zone_id=config.zone_id,
            expected_flow_lpm=config.max_flow_rate_lpm,
        )

    @property
    def zone_id(self) -> str:
        return self.config.zone_id

    @property
    def crop_coefficient(self) -> float:
        """Kc for the zone's crop type."""
        return CROP_COEFFICIENTS[self.config.crop_type]

    @property
    def root_depth_m(self) -> float:
        """Effective root zone depth (m)."""
        return ROOT_ZONE_DEPTH[self.config.crop_type]

    @property
    def field_capacity(self) -> float:
        return SOIL_HYDRAULIC_PROPERTIES[self.config.soil_type]["field_capacity"]

    @property
    def wilting_point(self) -> float:
        return SOIL_HYDRAULIC_PROPERTIES[self.config.soil_type]["wilting_point"]

    def crop_et(self, et0_mm: float) -> float:
        """Crop evapotranspiration ETc = Kc * ET0 (mm/day)."""
        return self.crop_coefficient * et0_mm

    def needs_irrigation(self) -> bool:
        """Check if the zone needs water based on moisture status."""
        return self.moisture_monitor.needs_irrigation()

    def required_depth_mm(self) -> float:
        """Irrigation depth (mm) to refill root zone to field capacity."""
        return self.moisture_monitor.irrigation_depth_mm(self.root_depth_m)

    def required_volume_liters(self) -> float:
        """Volume of water (liters) to refill the zone.

        volume (L) = depth (mm) * area (m2) / 1000 * 1000 = depth * area
        because 1 mm on 1 m2 = 1 liter.
        """
        return self.required_depth_mm() * self.config.area_m2

    def irrigation_duration_minutes(self) -> float:
        """Minutes of irrigation at max flow to deliver the required volume."""
        volume = self.required_volume_liters()
        if self.config.max_flow_rate_lpm <= 0:
            return 0.0
        return volume / self.config.max_flow_rate_lpm

    def apply_irrigation_mm(self, depth_mm: float) -> None:
        """Simulate applying irrigation by increasing the moisture level."""
        if not self.moisture_monitor.readings:
            return
        current = self.moisture_monitor.current_vwc
        # Convert mm back to VWC increment
        delta_vwc = depth_mm / (self.root_depth_m * 1000.0)
        new_vwc = min(current + delta_vwc, self.field_capacity)
        from datetime import datetime
        from jala.models import MoistureReading

        self.moisture_monitor.record(
            MoistureReading(
                zone_id=self.zone_id,
                volumetric_water_content=new_vwc,
                timestamp=datetime.now(),
            )
        )

    def apply_et_mm(self, etc_mm: float) -> None:
        """Simulate moisture loss from evapotranspiration."""
        current = self.moisture_monitor.current_vwc
        delta_vwc = etc_mm / (self.root_depth_m * 1000.0)
        new_vwc = max(current - delta_vwc, self.wilting_point)
        from datetime import datetime
        from jala.models import MoistureReading

        self.moisture_monitor.record(
            MoistureReading(
                zone_id=self.zone_id,
                volumetric_water_content=new_vwc,
                timestamp=datetime.now(),
            )
        )

    def apply_rain_mm(self, rain_mm: float) -> None:
        """Simulate moisture gain from rainfall."""
        self.apply_irrigation_mm(rain_mm)
