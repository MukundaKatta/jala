"""Multi-day irrigation simulation engine."""

from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Optional

import numpy as np

from jala.models import (
    WeatherReading,
    MoistureReading,
    ZoneConfig,
    SoilType,
    CropType,
    SimulationResult,
    IrrigationEvent,
    DailyWaterBudget,
)
from jala.irrigation.zones import IrrigationZone
from jala.irrigation.scheduler import IrrigationScheduler
from jala.irrigation.valves import ValveController
from jala.sensors.weather import WeatherStation
from jala.optimizer.forecast import WeatherForecastIntegrator
from jala.optimizer.water_budget import WaterBudgetOptimizer


def _default_zones() -> list[IrrigationZone]:
    """Create a set of example irrigation zones."""
    configs = [
        ZoneConfig(
            zone_id="lawn_front",
            name="Front Lawn",
            area_m2=200.0,
            soil_type=SoilType.SANDY_LOAM,
            crop_type=CropType.TURF_GRASS,
            max_flow_rate_lpm=15.0,
        ),
        ZoneConfig(
            zone_id="veggie_garden",
            name="Vegetable Garden",
            area_m2=50.0,
            soil_type=SoilType.LOAM,
            crop_type=CropType.VEGETABLES,
            max_flow_rate_lpm=10.0,
        ),
        ZoneConfig(
            zone_id="orchard",
            name="Fruit Orchard",
            area_m2=300.0,
            soil_type=SoilType.SILT_LOAM,
            crop_type=CropType.FRUIT_TREES,
            max_flow_rate_lpm=25.0,
        ),
    ]
    zones = []
    for cfg in configs:
        zone = IrrigationZone(cfg)
        # Initialize moisture at 90% of field capacity
        zone.moisture_monitor.record(
            MoistureReading(
                zone_id=cfg.zone_id,
                volumetric_water_content=zone.field_capacity * 0.90,
            )
        )
        zones.append(zone)
    return zones


def generate_weather_series(
    days: int,
    seed: Optional[int] = None,
    base_temp_max: float = 32.0,
    base_temp_min: float = 19.0,
    base_humidity: float = 50.0,
    base_wind: float = 2.0,
    base_solar: float = 22.0,
    rain_probability: float = 0.25,
) -> list[WeatherReading]:
    """Generate a synthetic daily weather series for simulation."""
    rng = np.random.default_rng(seed)
    readings = []
    for i in range(days):
        t_max = round(float(rng.normal(base_temp_max, 3)), 1)
        t_min = round(float(rng.normal(base_temp_min, 2)), 1)
        t_min = min(t_min, t_max - 2)
        humidity = round(float(np.clip(rng.normal(base_humidity, 12), 15, 95)), 1)
        wind = round(float(np.clip(rng.normal(base_wind, 0.7), 0.3, 6.0)), 1)
        solar = round(float(np.clip(rng.normal(base_solar, 4), 5, 30)), 1)

        rain = 0.0
        if rng.random() < rain_probability:
            rain = round(float(rng.exponential(8.0)), 1)

        readings.append(
            WeatherReading(
                temp_max_c=t_max,
                temp_min_c=t_min,
                humidity_pct=humidity,
                wind_speed_m_s=wind,
                solar_radiation_mj=solar,
                rainfall_mm=rain,
            )
        )
    return readings


def run_simulation(
    days: int = 14,
    zones: Optional[list[IrrigationZone]] = None,
    weather_series: Optional[list[WeatherReading]] = None,
    seed: int = 42,
    latitude: float = 30.0,
    altitude: float = 100.0,
    use_forecast: bool = True,
) -> SimulationResult:
    """Run a multi-day irrigation simulation.

    Parameters
    ----------
    days : int
        Number of days to simulate.
    zones : list[IrrigationZone], optional
        Zones to irrigate. Defaults to example zones.
    weather_series : list[WeatherReading], optional
        Daily weather data. Generated if not provided.
    seed : int
        Random seed for reproducibility.
    latitude : float
        Site latitude in degrees.
    altitude : float
        Site altitude in meters.
    use_forecast : bool
        Whether to use forecast-based deferral.

    Returns
    -------
    SimulationResult
        Aggregate results including daily budgets and events.
    """
    if zones is None:
        zones = _default_zones()
    if weather_series is None:
        weather_series = generate_weather_series(days, seed=seed)

    station = WeatherStation(altitude_m=altitude, latitude_deg=latitude)
    valve = ValveController()
    scheduler = IrrigationScheduler(station, zones, valve)

    forecast_integrator = WeatherForecastIntegrator() if use_forecast else None

    all_events: list[IrrigationEvent] = []
    start_date = datetime(2025, 6, 1, 6, 0, 0)

    for day_idx in range(days):
        current_time = start_date + timedelta(days=day_idx)
        day_of_year = current_time.timetuple().tm_yday
        reading = weather_series[day_idx]

        # Compute ET0
        et0 = station.compute_et0(reading, day_of_year)
        station.record(reading)

        # Check forecast deferral
        rain_credit = 0.0
        if forecast_integrator is not None and day_idx + 1 < days:
            # Peek ahead for rain
            future_rain = sum(
                w.rainfall_mm
                for w in weather_series[day_idx + 1 : day_idx + 4]
            )
            rain_credit = future_rain * 0.5  # conservative credit

        for zone in zones:
            etc = zone.crop_et(et0)
            effective_rain = 0.8 * reading.rainfall_mm if reading.rainfall_mm > 2 else 0.0

            # Apply daily ET and rain
            zone.apply_et_mm(etc)
            if effective_rain > 0:
                zone.apply_rain_mm(effective_rain)

            # Decide irrigation
            if zone.needs_irrigation():
                needed = zone.required_depth_mm()
                adjusted = max(needed - rain_credit, 0.0) if use_forecast else needed

                if adjusted > 0.5:  # minimum threshold to avoid micro-irrigations
                    duration = adjusted * zone.config.area_m2 / zone.config.max_flow_rate_lpm
                    event = valve.irrigate(zone, duration, start_time=current_time)
                    all_events.append(event)

    # Compute totals
    total_et0 = sum(
        station.compute_et0(w, (start_date + timedelta(days=i)).timetuple().tm_yday)
        for i, w in enumerate(weather_series)
    )
    total_rain = sum(w.rainfall_mm for w in weather_series)
    total_irrigation = sum(e.depth_mm for e in all_events)
    total_water = sum(e.volume_liters for e in all_events)

    # Compare with naive scheduling (irrigate ETc every day regardless)
    naive_water = sum(
        z.crop_et(total_et0 / days) * z.config.area_m2
        for z in zones
    ) * days
    savings = (1 - total_water / naive_water) * 100 if naive_water > 0 else 0.0

    return SimulationResult(
        days=days,
        total_et0_mm=round(total_et0, 2),
        total_irrigation_mm=round(total_irrigation, 2),
        total_rain_mm=round(total_rain, 2),
        total_water_liters=round(total_water, 2),
        water_savings_pct=round(max(savings, 0.0), 1),
        daily_budgets=scheduler.daily_budgets,
        events=all_events,
    )
