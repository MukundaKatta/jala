"""Irrigation scheduler computing optimal watering times and amounts.

Uses ET0 from the Penman-Monteith model, zone-specific crop coefficients,
and soil moisture state to decide when and how much to irrigate.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from jala.models import (
    WeatherReading,
    IrrigationEvent,
    DailyWaterBudget,
    CROP_COEFFICIENTS,
)
from jala.irrigation.zones import IrrigationZone
from jala.irrigation.valves import ValveController
from jala.sensors.weather import WeatherStation


class IrrigationScheduler:
    """Decides when and how much to irrigate each zone.

    The scheduler uses a soil-water-balance approach:
        1. Compute daily ET0 via Penman-Monteith.
        2. For each zone, compute crop ET (ETc = Kc * ET0).
        3. Subtract effective rainfall.
        4. Check if soil moisture has fallen below the refill threshold.
        5. If yes, schedule irrigation to bring moisture back to field capacity.

    Parameters
    ----------
    weather_station : WeatherStation
        Source of ET0 calculations.
    zones : list[IrrigationZone]
        Managed irrigation zones.
    valve_controller : ValveController
        Controls physical valve operations.
    """

    def __init__(
        self,
        weather_station: WeatherStation,
        zones: list[IrrigationZone],
        valve_controller: Optional[ValveController] = None,
    ) -> None:
        self.weather = weather_station
        self.zones = {z.zone_id: z for z in zones}
        self.valve = valve_controller or ValveController()
        self.daily_budgets: list[DailyWaterBudget] = []

    def compute_daily_budget(
        self,
        zone: IrrigationZone,
        et0_mm: float,
        rain_mm: float = 0.0,
        current_date: Optional[datetime] = None,
    ) -> DailyWaterBudget:
        """Compute the daily water budget for one zone.

        Parameters
        ----------
        zone : IrrigationZone
            Target zone.
        et0_mm : float
            Reference evapotranspiration for the day (mm).
        rain_mm : float
            Rainfall for the day (mm).
        current_date : datetime, optional
            Date for the budget entry.
        """
        dt = current_date or datetime.now()
        etc_mm = zone.crop_et(et0_mm)
        # Effective rain = 80% of gross rainfall (simple USDA-SCS approximation)
        effective_rain = 0.8 * rain_mm if rain_mm > 2.0 else 0.0

        soil_start = zone.moisture_monitor.current_vwc

        # Apply ET loss
        zone.apply_et_mm(etc_mm)
        # Apply rainfall gain
        if effective_rain > 0:
            zone.apply_rain_mm(effective_rain)

        # Determine if irrigation is needed
        irrigation_mm = 0.0
        if zone.needs_irrigation():
            irrigation_mm = zone.required_depth_mm()

        soil_end = zone.moisture_monitor.current_vwc
        deficit = max(etc_mm - effective_rain - irrigation_mm, 0.0)

        budget = DailyWaterBudget(
            date=dt.date() if isinstance(dt, datetime) else dt,
            zone_id=zone.zone_id,
            et0_mm=et0_mm,
            etc_mm=etc_mm,
            effective_rain_mm=effective_rain,
            irrigation_mm=irrigation_mm,
            soil_moisture_start=soil_start,
            soil_moisture_end=soil_end,
            deficit_mm=deficit,
        )
        self.daily_budgets.append(budget)
        return budget

    def run_day(
        self,
        weather_reading: WeatherReading,
        day_of_year: int = 180,
        current_time: Optional[datetime] = None,
    ) -> list[IrrigationEvent]:
        """Execute one day of scheduling for all zones.

        Returns a list of irrigation events that were executed.
        """
        et0 = self.weather.compute_et0(weather_reading, day_of_year)
        self.weather.record(weather_reading)
        rain_mm = weather_reading.rainfall_mm
        now = current_time or datetime.now()

        events: list[IrrigationEvent] = []

        for zone in self.zones.values():
            budget = self.compute_daily_budget(zone, et0, rain_mm, now)

            if budget.irrigation_mm > 0:
                duration = (
                    budget.irrigation_mm
                    * zone.config.area_m2
                    / zone.config.max_flow_rate_lpm
                )
                event = self.valve.irrigate(zone, duration, start_time=now)
                events.append(event)
                # Update budget with actual irrigation
                budget.irrigation_mm = event.depth_mm

        return events

    def get_zone(self, zone_id: str) -> IrrigationZone:
        """Retrieve a zone by ID."""
        return self.zones[zone_id]
