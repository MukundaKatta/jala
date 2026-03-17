"""JALA CLI - Smart Irrigation System command-line interface."""

from __future__ import annotations

import click
from rich.console import Console

from jala.models import WeatherReading
from jala.sensors.weather import WeatherStation
from jala.simulator import run_simulation, _default_zones
from jala.report import print_simulation_report, print_zone_status

console = Console()


@click.group()
@click.version_option(package_name="jala")
def cli() -> None:
    """JALA - Smart Irrigation System.

    Computes optimal irrigation schedules using the FAO-56 Penman-Monteith
    reference evapotranspiration model.
    """


@cli.command()
@click.option("--days", default=14, help="Number of days to simulate.")
@click.option("--seed", default=42, help="Random seed for reproducibility.")
@click.option("--latitude", default=30.0, help="Site latitude (degrees).")
@click.option("--altitude", default=100.0, help="Site altitude (meters).")
@click.option("--no-forecast", is_flag=True, help="Disable forecast-based deferral.")
def simulate(days: int, seed: int, latitude: float, altitude: float, no_forecast: bool) -> None:
    """Run a multi-day irrigation simulation."""
    console.print(f"[bold cyan]Running {days}-day simulation...[/bold cyan]")
    result = run_simulation(
        days=days,
        seed=seed,
        latitude=latitude,
        altitude=altitude,
        use_forecast=not no_forecast,
    )
    print_simulation_report(result, console)


@cli.command()
def status() -> None:
    """Show current zone status with moisture levels."""
    zones = _default_zones()
    print_zone_status(zones, console)


@cli.command()
@click.option("--days", default=14, help="Number of days for the report period.")
@click.option("--seed", default=42, help="Random seed.")
def report(days: int, seed: int) -> None:
    """Generate a water usage report."""
    result = run_simulation(days=days, seed=seed)
    print_simulation_report(result, console)


@cli.command()
@click.option("--temp-max", required=True, type=float, help="Max temperature (C).")
@click.option("--temp-min", required=True, type=float, help="Min temperature (C).")
@click.option("--humidity", required=True, type=float, help="Relative humidity (%).")
@click.option("--wind-speed", required=True, type=float, help="Wind speed at 2m (m/s).")
@click.option("--solar-rad", required=True, type=float, help="Solar radiation (MJ/m2/day).")
@click.option("--latitude", default=30.0, help="Site latitude (degrees).")
@click.option("--altitude", default=100.0, help="Site altitude (meters).")
@click.option("--day-of-year", default=180, help="Julian day of year.")
def et0(
    temp_max: float,
    temp_min: float,
    humidity: float,
    wind_speed: float,
    solar_rad: float,
    latitude: float,
    altitude: float,
    day_of_year: int,
) -> None:
    """Compute reference evapotranspiration (ET0) using Penman-Monteith."""
    station = WeatherStation(altitude_m=altitude, latitude_deg=latitude)
    reading = WeatherReading(
        temp_max_c=temp_max,
        temp_min_c=temp_min,
        humidity_pct=humidity,
        wind_speed_m_s=wind_speed,
        solar_radiation_mj=solar_rad,
    )
    result = station.compute_et0(reading, day_of_year)
    console.print(f"[bold]ET0:[/bold] [green]{result:.2f} mm/day[/green]")
    console.print(f"[dim]Using FAO-56 Penman-Monteith at lat={latitude}, alt={altitude}m[/dim]")


if __name__ == "__main__":
    cli()
