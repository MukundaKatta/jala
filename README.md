# JALA - Smart Irrigation System

JALA is an intelligent irrigation management system that computes optimal watering
schedules using the FAO-56 Penman-Monteith reference evapotranspiration (ET0) model.
It minimizes water usage while ensuring crops receive adequate moisture based on
real-time sensor data, soil properties, and weather forecasts.

## Features

- **Penman-Monteith ET0**: Full FAO-56 implementation for reference evapotranspiration
- **Zone Management**: Configure irrigation zones with soil type, crop coefficients, and sensor bindings
- **Moisture Monitoring**: Track soil moisture against field capacity and wilting point thresholds
- **Weather Integration**: Adjust schedules based on rainfall forecasts to avoid unnecessary watering
- **Water Budget Optimization**: Minimize total water usage while satisfying crop water requirements
- **Flow Metering**: Track water consumption per zone with leak detection
- **Simulation**: Run multi-day irrigation simulations with configurable weather scenarios
- **Reporting**: Generate rich terminal reports on water usage, efficiency, and zone status

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Run a 7-day irrigation simulation
jala simulate --days 7

# Show current zone status
jala status

# Generate a water usage report
jala report --days 30

# Compute today's ET0
jala et0 --temp-max 32 --temp-min 18 --humidity 45 --wind-speed 2.0 --solar-rad 22
```

## Architecture

```
src/jala/
  irrigation/    Zone, valve, and scheduler logic
  sensors/       Moisture, weather, and flow sensors
  optimizer/     Water budget and forecast integration
  models.py      Pydantic data models
  simulator.py   Multi-day simulation engine
  report.py      Rich terminal reporting
  cli.py         Click CLI entry point
```

## References

- Allen, R.G., et al. (1998). *Crop evapotranspiration - Guidelines for computing
  crop water requirements*. FAO Irrigation and Drainage Paper 56.
