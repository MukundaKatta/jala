"""Pydantic data models for the JALA irrigation system."""

from __future__ import annotations

from datetime import datetime, date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SoilType(str, Enum):
    """Soil texture classification affecting water-holding capacity."""

    SAND = "sand"
    LOAMY_SAND = "loamy_sand"
    SANDY_LOAM = "sandy_loam"
    LOAM = "loam"
    SILT_LOAM = "silt_loam"
    CLAY_LOAM = "clay_loam"
    CLAY = "clay"


# Volumetric water content (m3/m3) at field capacity and wilting point by soil type.
SOIL_HYDRAULIC_PROPERTIES: dict[SoilType, dict[str, float]] = {
    SoilType.SAND: {"field_capacity": 0.10, "wilting_point": 0.05, "saturation": 0.43},
    SoilType.LOAMY_SAND: {"field_capacity": 0.15, "wilting_point": 0.07, "saturation": 0.44},
    SoilType.SANDY_LOAM: {"field_capacity": 0.22, "wilting_point": 0.10, "saturation": 0.45},
    SoilType.LOAM: {"field_capacity": 0.27, "wilting_point": 0.12, "saturation": 0.46},
    SoilType.SILT_LOAM: {"field_capacity": 0.33, "wilting_point": 0.13, "saturation": 0.47},
    SoilType.CLAY_LOAM: {"field_capacity": 0.36, "wilting_point": 0.20, "saturation": 0.48},
    SoilType.CLAY: {"field_capacity": 0.40, "wilting_point": 0.25, "saturation": 0.50},
}


class CropType(str, Enum):
    """Crop classification with associated Kc coefficients."""

    TURF_GRASS = "turf_grass"
    VEGETABLES = "vegetables"
    FRUIT_TREES = "fruit_trees"
    CEREALS = "cereals"
    LEGUMES = "legumes"
    ORNAMENTALS = "ornamentals"


# FAO-56 crop coefficients (Kc) for mid-season stage.
CROP_COEFFICIENTS: dict[CropType, float] = {
    CropType.TURF_GRASS: 0.85,
    CropType.VEGETABLES: 1.05,
    CropType.FRUIT_TREES: 0.95,
    CropType.CEREALS: 1.15,
    CropType.LEGUMES: 1.10,
    CropType.ORNAMENTALS: 0.75,
}

# Root zone depth in meters by crop type.
ROOT_ZONE_DEPTH: dict[CropType, float] = {
    CropType.TURF_GRASS: 0.15,
    CropType.VEGETABLES: 0.40,
    CropType.FRUIT_TREES: 1.00,
    CropType.CEREALS: 0.60,
    CropType.LEGUMES: 0.50,
    CropType.ORNAMENTALS: 0.30,
}


class WeatherReading(BaseModel):
    """A single weather observation or daily summary."""

    timestamp: datetime = Field(default_factory=datetime.now)
    temp_max_c: float = Field(..., description="Maximum temperature (C)")
    temp_min_c: float = Field(..., description="Minimum temperature (C)")
    humidity_pct: float = Field(..., ge=0, le=100, description="Mean relative humidity (%)")
    wind_speed_m_s: float = Field(..., ge=0, description="Wind speed at 2 m height (m/s)")
    solar_radiation_mj: float = Field(..., ge=0, description="Solar radiation (MJ/m2/day)")
    rainfall_mm: float = Field(default=0.0, ge=0, description="Rainfall (mm)")


class MoistureReading(BaseModel):
    """Soil moisture sensor reading."""

    timestamp: datetime = Field(default_factory=datetime.now)
    zone_id: str
    volumetric_water_content: float = Field(
        ..., ge=0, le=1, description="Volumetric water content (m3/m3)"
    )
    depth_cm: float = Field(default=20.0, description="Sensor depth (cm)")


class FlowReading(BaseModel):
    """Flow meter reading for a zone."""

    timestamp: datetime = Field(default_factory=datetime.now)
    zone_id: str
    flow_rate_lpm: float = Field(..., ge=0, description="Flow rate (liters per minute)")
    total_liters: float = Field(default=0.0, ge=0, description="Cumulative liters delivered")


class ZoneConfig(BaseModel):
    """Configuration for a single irrigation zone."""

    zone_id: str
    name: str
    area_m2: float = Field(..., gt=0, description="Zone area (m2)")
    soil_type: SoilType = SoilType.LOAM
    crop_type: CropType = CropType.TURF_GRASS
    max_flow_rate_lpm: float = Field(default=20.0, gt=0)
    management_allowed_depletion: float = Field(
        default=0.50, gt=0, le=1.0,
        description="Fraction of available water that may be depleted before irrigation",
    )


class IrrigationEvent(BaseModel):
    """Record of a single irrigation action."""

    zone_id: str
    start_time: datetime
    duration_minutes: float = Field(..., gt=0)
    volume_liters: float = Field(..., ge=0)
    depth_mm: float = Field(..., ge=0, description="Equivalent depth applied (mm)")


class DailyWaterBudget(BaseModel):
    """Daily water balance for one zone."""

    date: date
    zone_id: str
    et0_mm: float = Field(..., ge=0)
    etc_mm: float = Field(..., ge=0, description="Crop ET = Kc * ET0")
    effective_rain_mm: float = Field(default=0.0, ge=0)
    irrigation_mm: float = Field(default=0.0, ge=0)
    soil_moisture_start: float = Field(..., ge=0)
    soil_moisture_end: float = Field(..., ge=0)
    deficit_mm: float = Field(default=0.0, description="Unmet crop demand (mm)")


class ForecastDay(BaseModel):
    """Single-day weather forecast."""

    date: date
    rain_probability: float = Field(..., ge=0, le=1)
    expected_rain_mm: float = Field(default=0.0, ge=0)
    temp_max_c: float = 30.0
    temp_min_c: float = 18.0
    humidity_pct: float = 50.0
    wind_speed_m_s: float = 2.0
    solar_radiation_mj: float = 20.0


class SimulationResult(BaseModel):
    """Aggregate results of a multi-day simulation."""

    days: int
    total_et0_mm: float
    total_irrigation_mm: float
    total_rain_mm: float
    total_water_liters: float
    water_savings_pct: float = Field(
        default=0.0, description="Savings vs. naive timer-based schedule"
    )
    daily_budgets: list[DailyWaterBudget] = Field(default_factory=list)
    events: list[IrrigationEvent] = Field(default_factory=list)
