# Glorp's Battery Optimization

Home Assistant custom integration that adds battery charge/discharge optimization
(zero-export matching, solar surplus charging, off-peak night charging, SOC safety
limits) on top of whatever integration already talks to your battery.

## Why this exists

It started as a layer over [zendure_ha](https://github.com/Zendure/Zendure-HA):
`zendure_ha`'s own "manager" abstraction (the aggregated `manual` mode driven by a
signed `manual_power` number) does not reliably translate its internal charge/discharge
decisions into commands the device actually executes, at least on a SolarFlow 1600 AC+.
The device's own per-device entities (`select.<device>_ac_mode`, `number.<device>_input_limit`,
`number.<device>_output_limit`) do work reliably, so this integration drives those
directly and never touches the manager entities.

Since then it's grown a second, generic **control mode** so it can drive other brands
too: any battery integration that exposes a single signed power number (positive/negative
= charge/discharge, either convention) instead of a mode select plus two separate limits.
See [Requirements](#requirements) below for the two shapes.

See [`docs/superpowers/specs/2026-08-21-zendure-optimization-design.md`](docs/superpowers/specs/2026-08-21-zendure-optimization-design.md)
for the full design rationale.

## Requirements

A sensor reporting the battery's state of charge (0-100), and a sensor reporting grid
power (positive = importing from the grid, negative = exporting) are needed either way.
Beyond that, pick the control mode that matches how your battery integration exposes
charge/discharge control:

- **Two commands** (the `zendure_ha` case above) — a mode select entity with two option
  values plus two separate, unsigned power-limit number entities. On `zendure_ha`,
  confirm `select.<device>_ac_mode`, `number.<device>_input_limit` and
  `number.<device>_output_limit` actually respond (test with a manual
  `select.select_option` / `number.set_value` call) before relying on this integration.
- **Single command** — one signed power number entity, with either sign convention
  (positive = charge or positive = discharge — you pick which in the config flow).

## Installation

Via HACS: add this repository as a custom repository (category: Integration), then
install "Glorp's Battery Optimization".

Manually: copy `custom_components/glorp_battery_optimization` into your `config/custom_components/`
directory and restart Home Assistant.

Then go to **Settings → Devices & services → Add integration → Glorp's Battery Optimization**
and select the required entities.

## What it does

Every time the configured grid power sensor changes state, the integration re-evaluates
(in priority order):

1. **SOC safety** — never discharges below the configured minimum SOC, never charges
   above the configured maximum SOC.
2. **Night charge** — during a configurable off-peak time window, charges at a
   configurable soft power if the SOC is below a configurable threshold.
3. **Solar surplus charging** — charges to match grid export.
4. **Zero-export discharge** — discharges to match grid import.

Each of the last three is toggled by its own switch entity; SOC safety is always on. A
master switch cuts all writes at once, handing control back to the Zendure app.

All thresholds (SOC min/max, night charge window/threshold/power, command deadband,
charge/discharge switch hysteresis) are exposed as regular `number`/`time` entities —
adjustable from any dashboard, no YAML or reconfiguration needed. The switch hysteresis
sets a power band (in W) that grid import/export must clear before the battery flips
direction, so it doesn't flap the AC mode relay when the grid reading oscillates around
zero; it's separate from the deadband, which only smooths small changes in magnitude
within the same direction.

## Development

The decision logic (`decision.py`, deciding *what* to do) and the command builder
(`commands.py`, translating that into service calls for the configured control mode) are
both pure functions with no Home Assistant dependency, tested with plain `pytest`:

```
pip install pytest
pytest tests/
```

## Branding

`icon.png` / `logo.png` at the repo root are the Glorp brand mark, reused from
[osc-pra](https://osc-pra.osc-tests.fr) (another glorp-fr project). HACS reads these for
its own store listing; they don't automatically appear on the Home Assistant
Settings → Integrations page — that icon comes from the separate
[home-assistant/brands](https://github.com/home-assistant/brands) repo, which only
covers integrations submitted there.
