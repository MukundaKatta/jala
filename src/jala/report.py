"""Rich terminal reporting for irrigation simulation results."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from jala.models import SimulationResult, IrrigationEvent, DailyWaterBudget


def print_simulation_report(result: SimulationResult, console: Console | None = None) -> None:
    """Print a comprehensive simulation report to the terminal."""
    if console is None:
        console = Console()

    # Header
    header = Text("JALA Irrigation Simulation Report", style="bold cyan")
    console.print(Panel(header, box=box.DOUBLE))

    # Summary table
    summary = Table(title="Simulation Summary", box=box.ROUNDED, show_header=False)
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")

    summary.add_row("Duration", f"{result.days} days")
    summary.add_row("Total ET0", f"{result.total_et0_mm:.1f} mm")
    summary.add_row("Total Rainfall", f"{result.total_rain_mm:.1f} mm")
    summary.add_row("Total Irrigation", f"{result.total_irrigation_mm:.1f} mm")
    summary.add_row("Total Water Used", f"{result.total_water_liters:.0f} liters")

    savings_style = "green" if result.water_savings_pct > 0 else "red"
    summary.add_row(
        "Water Savings vs Naive",
        Text(f"{result.water_savings_pct:.1f}%", style=savings_style),
    )
    console.print(summary)
    console.print()

    # Irrigation events table
    if result.events:
        events_table = Table(
            title="Irrigation Events", box=box.SIMPLE_HEAVY, show_lines=False
        )
        events_table.add_column("Zone", style="cyan")
        events_table.add_column("Time", style="dim")
        events_table.add_column("Duration (min)", justify="right")
        events_table.add_column("Volume (L)", justify="right")
        events_table.add_column("Depth (mm)", justify="right")

        for event in result.events:
            events_table.add_row(
                event.zone_id,
                event.start_time.strftime("%Y-%m-%d %H:%M"),
                f"{event.duration_minutes:.1f}",
                f"{event.volume_liters:.0f}",
                f"{event.depth_mm:.1f}",
            )
        console.print(events_table)
        console.print()

    # Per-zone summary
    if result.events:
        zone_summary = Table(title="Per-Zone Summary", box=box.ROUNDED)
        zone_summary.add_column("Zone", style="cyan")
        zone_summary.add_column("Events", justify="right")
        zone_summary.add_column("Total Volume (L)", justify="right")
        zone_summary.add_column("Total Depth (mm)", justify="right")
        zone_summary.add_column("Avg Depth (mm)", justify="right")

        zone_ids = sorted(set(e.zone_id for e in result.events))
        for zid in zone_ids:
            zone_events = [e for e in result.events if e.zone_id == zid]
            total_vol = sum(e.volume_liters for e in zone_events)
            total_depth = sum(e.depth_mm for e in zone_events)
            avg_depth = total_depth / len(zone_events) if zone_events else 0
            zone_summary.add_row(
                zid,
                str(len(zone_events)),
                f"{total_vol:.0f}",
                f"{total_depth:.1f}",
                f"{avg_depth:.1f}",
            )
        console.print(zone_summary)

    console.print()
    console.print(
        Panel(
            "[dim]Powered by FAO-56 Penman-Monteith ET0[/dim]",
            box=box.ROUNDED,
            style="dim",
        )
    )


def print_zone_status(
    zones: list,
    console: Console | None = None,
) -> None:
    """Print current status of all irrigation zones."""
    if console is None:
        console = Console()

    table = Table(title="Zone Status", box=box.ROUNDED)
    table.add_column("Zone", style="cyan")
    table.add_column("Crop", style="green")
    table.add_column("Soil", style="yellow")
    table.add_column("VWC", justify="right")
    table.add_column("FC", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Needs Water", justify="center")

    for zone in zones:
        vwc = zone.moisture_monitor.current_vwc
        fc = zone.field_capacity
        threshold = zone.moisture_monitor.refill_threshold
        needs = zone.needs_irrigation()

        status_text = Text("YES", style="bold red") if needs else Text("no", style="green")
        table.add_row(
            zone.config.name,
            zone.config.crop_type.value,
            zone.config.soil_type.value,
            f"{vwc:.3f}",
            f"{fc:.3f}",
            f"{threshold:.3f}",
            status_text,
        )

    console.print(table)
