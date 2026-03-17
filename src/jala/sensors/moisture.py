"""Soil moisture monitoring with field capacity threshold logic."""

from __future__ import annotations

from typing import Optional

import numpy as np

from jala.models import (
    MoistureReading,
    SoilType,
    SOIL_HYDRAULIC_PROPERTIES,
)


class SoilMoistureMonitor:
    """Monitors soil moisture for a zone and evaluates irrigation need.

    Tracks volumetric water content (VWC) relative to field capacity (FC),
    wilting point (WP), and a management-allowed depletion (MAD) threshold.
    """

    def __init__(
        self,
        zone_id: str,
        soil_type: SoilType = SoilType.LOAM,
        management_allowed_depletion: float = 0.50,
    ) -> None:
        self.zone_id = zone_id
        self.soil_type = soil_type
        self.management_allowed_depletion = management_allowed_depletion
        self.readings: list[MoistureReading] = []

        props = SOIL_HYDRAULIC_PROPERTIES[soil_type]
        self.field_capacity = props["field_capacity"]
        self.wilting_point = props["wilting_point"]
        self.saturation = props["saturation"]

    @property
    def total_available_water(self) -> float:
        """Total available water (TAW) = FC - WP (m3/m3)."""
        return self.field_capacity - self.wilting_point

    @property
    def readily_available_water(self) -> float:
        """Readily available water (RAW) = MAD * TAW (m3/m3)."""
        return self.management_allowed_depletion * self.total_available_water

    @property
    def refill_threshold(self) -> float:
        """VWC threshold below which irrigation is triggered."""
        return self.field_capacity - self.readily_available_water

    def record(self, reading: MoistureReading) -> None:
        """Store a moisture reading."""
        self.readings.append(reading)

    @property
    def latest(self) -> Optional[MoistureReading]:
        return self.readings[-1] if self.readings else None

    @property
    def current_vwc(self) -> float:
        """Current volumetric water content, or field capacity if no data."""
        if self.readings:
            return self.readings[-1].volumetric_water_content
        return self.field_capacity

    def depletion_fraction(self) -> float:
        """Fraction of TAW currently depleted (0 = at FC, 1 = at WP)."""
        vwc = self.current_vwc
        depleted = self.field_capacity - vwc
        return np.clip(depleted / self.total_available_water, 0.0, 1.0)

    def needs_irrigation(self) -> bool:
        """Return True if current moisture is below the refill threshold."""
        return self.current_vwc < self.refill_threshold

    def irrigation_depth_mm(self, root_depth_m: float) -> float:
        """Depth of water (mm) needed to refill the root zone to field capacity.

        Parameters
        ----------
        root_depth_m : float
            Effective root zone depth in meters.

        Returns
        -------
        float
            Required irrigation depth in mm.
        """
        deficit_m3m3 = max(self.field_capacity - self.current_vwc, 0.0)
        # depth (m) of water = deficit (m3/m3) * root_depth (m)
        # convert to mm: * 1000
        return deficit_m3m3 * root_depth_m * 1000.0

    def moving_average(self, window: int = 5) -> float:
        """Smoothed VWC over the last *window* readings."""
        if not self.readings:
            return self.field_capacity
        values = [r.volumetric_water_content for r in self.readings[-window:]]
        return float(np.mean(values))

    def trend(self, window: int = 10) -> float:
        """Linear trend (slope) of VWC over the last *window* readings.

        Returns a positive value when moisture is increasing, negative when drying.
        """
        if len(self.readings) < 2:
            return 0.0
        values = np.array(
            [r.volumetric_water_content for r in self.readings[-window:]]
        )
        x = np.arange(len(values), dtype=float)
        coeffs = np.polyfit(x, values, 1)
        return float(coeffs[0])
