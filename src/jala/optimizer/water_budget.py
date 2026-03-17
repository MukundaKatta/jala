"""Water budget optimizer minimizing usage while meeting crop needs.

Uses scipy.optimize to find the minimum irrigation allocation across zones
subject to the constraint that each zone's soil moisture must stay above
its management-allowed depletion threshold.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.optimize import linprog, minimize

from jala.irrigation.zones import IrrigationZone
from jala.models import CROP_COEFFICIENTS, ROOT_ZONE_DEPTH


class WaterBudgetOptimizer:
    """Optimizes daily irrigation allocation across multiple zones.

    The objective is to minimize total water applied while ensuring
    no zone falls below its critical depletion threshold.

    Parameters
    ----------
    zones : list[IrrigationZone]
        Zones to optimize over.
    daily_et0_mm : float
        Reference ET0 for the optimization day.
    forecast_rain_mm : float
        Expected effective rainfall (mm).
    max_total_liters : float, optional
        System-wide water budget cap (liters). None = unlimited.
    """

    def __init__(
        self,
        zones: list[IrrigationZone],
        daily_et0_mm: float,
        forecast_rain_mm: float = 0.0,
        max_total_liters: Optional[float] = None,
    ) -> None:
        self.zones = zones
        self.daily_et0_mm = daily_et0_mm
        self.forecast_rain_mm = forecast_rain_mm
        self.max_total_liters = max_total_liters

    def _zone_demand(self, zone: IrrigationZone) -> float:
        """Net irrigation demand (mm) for a single zone after rain credit."""
        etc = zone.crop_et(self.daily_et0_mm)
        net_demand = etc - self.forecast_rain_mm
        return max(net_demand, 0.0)

    def _zone_max_depth(self, zone: IrrigationZone) -> float:
        """Maximum useful irrigation depth (mm): refill to field capacity."""
        return zone.required_depth_mm()

    def optimize_linear(self) -> dict[str, float]:
        """Solve the allocation as a linear program.

        Minimize: sum(x_i * area_i)  [total volume in liters]
        Subject to:
            x_i >= demand_i   for each zone (meet crop needs)
            x_i <= max_i      for each zone (don't over-water)
            sum(x_i * area_i) <= max_total_liters  (optional cap)

        Returns
        -------
        dict[str, float]
            Mapping of zone_id to irrigation depth (mm).
        """
        n = len(self.zones)
        if n == 0:
            return {}

        zones = list(self.zones)
        areas = np.array([z.config.area_m2 for z in zones])

        # Objective: minimize total volume = sum(depth_mm * area_m2)
        # (depth in mm on area in m2 gives liters)
        c = areas.copy()

        # Bounds: demand_i <= x_i <= max_i
        bounds = []
        for z in zones:
            lo = self._zone_demand(z)
            hi = max(self._zone_max_depth(z), lo)
            bounds.append((lo, hi))

        # Optional total-volume constraint: sum(x_i * area_i) <= budget
        a_ub = None
        b_ub = None
        if self.max_total_liters is not None:
            a_ub = [areas.tolist()]
            b_ub = [self.max_total_liters]

        result = linprog(c, A_ub=a_ub, b_ub=b_ub, bounds=bounds, method="highs")

        if result.success:
            return {z.zone_id: float(result.x[i]) for i, z in enumerate(zones)}
        else:
            # Fallback: give each zone its demand
            return {z.zone_id: self._zone_demand(z) for z in zones}

    def optimize_quadratic(self) -> dict[str, float]:
        """Solve with a quadratic penalty for over-irrigation.

        Minimize: sum(area_i * x_i) + lambda * sum((x_i - demand_i)^2)

        This smoothly penalizes excess water beyond the minimum demand,
        producing a more conservative schedule.
        """
        n = len(self.zones)
        if n == 0:
            return {}

        zones = list(self.zones)
        areas = np.array([z.config.area_m2 for z in zones])
        demands = np.array([self._zone_demand(z) for z in zones])
        maxes = np.array([max(self._zone_max_depth(z), d) for z, d in zip(zones, demands)])

        penalty = 0.5  # regularization weight

        def objective(x: np.ndarray) -> float:
            volume = float(np.dot(areas, x))
            excess_penalty = penalty * float(np.sum((x - demands) ** 2))
            return volume + excess_penalty

        bounds = [(d, m) for d, m in zip(demands, maxes)]

        constraints = []
        if self.max_total_liters is not None:
            constraints.append({
                "type": "ineq",
                "fun": lambda x: self.max_total_liters - float(np.dot(areas, x)),
            })

        x0 = demands.copy()
        result = minimize(objective, x0, bounds=bounds, constraints=constraints, method="SLSQP")

        if result.success:
            return {z.zone_id: float(result.x[i]) for i, z in enumerate(zones)}
        else:
            return {z.zone_id: float(d) for z, d in zip(zones, demands)}

    def summary(self) -> dict:
        """Run optimization and return a summary dict."""
        allocation = self.optimize_linear()
        total_liters = sum(
            depth * z.config.area_m2
            for z, depth in ((self.zones[i], d) for i, (_, d) in enumerate(allocation.items()))
        )
        # Recompute properly
        total_liters = 0.0
        zone_list = list(self.zones)
        for z in zone_list:
            depth = allocation.get(z.zone_id, 0.0)
            total_liters += depth * z.config.area_m2

        naive_liters = sum(
            z.crop_et(self.daily_et0_mm) * z.config.area_m2 for z in zone_list
        )
        savings = (1 - total_liters / naive_liters) * 100 if naive_liters > 0 else 0.0

        return {
            "allocation": allocation,
            "total_liters": total_liters,
            "naive_liters": naive_liters,
            "savings_pct": max(savings, 0.0),
        }
