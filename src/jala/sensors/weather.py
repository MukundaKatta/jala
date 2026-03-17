"""Weather station with FAO-56 Penman-Monteith ET0 calculation.

Reference:
    Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998).
    Crop evapotranspiration - Guidelines for computing crop water requirements.
    FAO Irrigation and Drainage Paper 56.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from jala.models import WeatherReading


class WeatherStation:
    """Collects weather data and computes reference evapotranspiration (ET0).

    The ET0 is computed using the full FAO-56 Penman-Monteith equation:

        ET0 = [0.408 * delta * (Rn - G) + gamma * (900 / (T+273)) * u2 * (es - ea)]
              / [delta + gamma * (1 + 0.34 * u2)]

    where:
        Rn  = net radiation at the crop surface (MJ/m2/day)
        G   = soil heat flux density (MJ/m2/day), ~0 for daily steps
        T   = mean daily air temperature (C)
        u2  = wind speed at 2 m height (m/s)
        es  = saturation vapour pressure (kPa)
        ea  = actual vapour pressure (kPa)
        delta = slope of the saturation vapour pressure curve (kPa/C)
        gamma = psychrometric constant (kPa/C)
    """

    def __init__(
        self,
        altitude_m: float = 0.0,
        latitude_deg: float = 30.0,
    ) -> None:
        self.altitude_m = altitude_m
        self.latitude_deg = latitude_deg
        self.readings: list[WeatherReading] = []

    def record(self, reading: WeatherReading) -> None:
        """Store a weather reading."""
        self.readings.append(reading)

    @property
    def latest(self) -> Optional[WeatherReading]:
        return self.readings[-1] if self.readings else None

    # ------------------------------------------------------------------
    # FAO-56 Penman-Monteith helper functions
    # ------------------------------------------------------------------

    @staticmethod
    def saturation_vapour_pressure(temp_c: float) -> float:
        """Saturation vapour pressure e0(T) in kPa (Eq. 11)."""
        return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))

    @staticmethod
    def slope_vapour_pressure_curve(temp_c: float) -> float:
        """Slope of the saturation vapour pressure curve delta (kPa/C) (Eq. 13)."""
        numerator = 4098 * 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
        return numerator / (temp_c + 237.3) ** 2

    def psychrometric_constant(self) -> float:
        """Psychrometric constant gamma (kPa/C) (Eq. 8).

        Uses atmospheric pressure estimated from altitude (Eq. 7).
        """
        # Atmospheric pressure (kPa) from altitude
        p = 101.3 * ((293 - 0.0065 * self.altitude_m) / 293) ** 5.26
        return 0.000665 * p

    def extraterrestrial_radiation(self, day_of_year: int) -> float:
        """Extraterrestrial radiation Ra (MJ/m2/day) (Eq. 21).

        Parameters
        ----------
        day_of_year : int
            Julian day of the year (1-365).
        """
        lat_rad = math.radians(self.latitude_deg)
        # Solar declination (Eq. 24)
        dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
        delta = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
        # Sunset hour angle (Eq. 25)
        ws = math.acos(-math.tan(lat_rad) * math.tan(delta))
        # Ra (Eq. 21)
        gsc = 0.0820  # solar constant MJ/m2/min
        ra = (
            (24 * 60 / math.pi)
            * gsc
            * dr
            * (
                ws * math.sin(lat_rad) * math.sin(delta)
                + math.cos(lat_rad) * math.cos(delta) * math.sin(ws)
            )
        )
        return max(ra, 0.0)

    def net_radiation(
        self,
        solar_radiation_mj: float,
        temp_max_c: float,
        temp_min_c: float,
        ea: float,
        day_of_year: int,
    ) -> float:
        """Net radiation Rn (MJ/m2/day) = Rns - Rnl.

        Parameters
        ----------
        solar_radiation_mj : float
            Incoming solar (shortwave) radiation Rs (MJ/m2/day).
        ea : float
            Actual vapour pressure (kPa).
        day_of_year : int
            Julian day of year.
        """
        ra = self.extraterrestrial_radiation(day_of_year)
        # Clear-sky solar radiation Rso (Eq. 37)
        rso = (0.75 + 2e-5 * self.altitude_m) * ra
        # Net shortwave radiation Rns (Eq. 38), albedo = 0.23
        rns = (1 - 0.23) * solar_radiation_mj
        # Net longwave radiation Rnl (Eq. 39)
        sigma = 4.903e-9  # Stefan-Boltzmann (MJ/K4/m2/day)
        tmax_k4 = (temp_max_c + 273.16) ** 4
        tmin_k4 = (temp_min_c + 273.16) ** 4
        # Cloudiness factor
        rs_rso_ratio = min(solar_radiation_mj / rso, 1.0) if rso > 0 else 0.5
        rnl = (
            sigma
            * ((tmax_k4 + tmin_k4) / 2)
            * (0.34 - 0.14 * math.sqrt(ea))
            * (1.35 * rs_rso_ratio - 0.35)
        )
        return rns - rnl

    def compute_et0(self, reading: WeatherReading, day_of_year: int = 180) -> float:
        """Compute FAO-56 Penman-Monteith reference ET0 (mm/day).

        Parameters
        ----------
        reading : WeatherReading
            Daily weather summary.
        day_of_year : int
            Julian day of year (default 180 = ~end of June).

        Returns
        -------
        float
            Reference evapotranspiration ET0 in mm/day.
        """
        t_mean = (reading.temp_max_c + reading.temp_min_c) / 2.0
        u2 = reading.wind_speed_m_s

        # Saturation vapour pressure (Eq. 12)
        es = (
            self.saturation_vapour_pressure(reading.temp_max_c)
            + self.saturation_vapour_pressure(reading.temp_min_c)
        ) / 2.0

        # Actual vapour pressure from relative humidity (Eq. 17)
        ea = (
            self.saturation_vapour_pressure(reading.temp_min_c) * (reading.humidity_pct / 100.0)
            + self.saturation_vapour_pressure(reading.temp_max_c) * (reading.humidity_pct / 100.0)
        ) / 2.0

        delta = self.slope_vapour_pressure_curve(t_mean)
        gamma = self.psychrometric_constant()

        rn = self.net_radiation(
            reading.solar_radiation_mj,
            reading.temp_max_c,
            reading.temp_min_c,
            ea,
            day_of_year,
        )

        # Soil heat flux G ~ 0 for daily time steps
        g = 0.0

        # FAO-56 Penman-Monteith (Eq. 6)
        numerator = (
            0.408 * delta * (rn - g)
            + gamma * (900.0 / (t_mean + 273.0)) * u2 * (es - ea)
        )
        denominator = delta + gamma * (1 + 0.34 * u2)

        et0 = numerator / denominator
        return max(et0, 0.0)

    def compute_et0_from_latest(self, day_of_year: int = 180) -> float:
        """Compute ET0 from the most recent weather reading."""
        if not self.readings:
            raise ValueError("No weather readings available")
        return self.compute_et0(self.readings[-1], day_of_year)
