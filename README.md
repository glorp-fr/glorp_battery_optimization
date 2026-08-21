# Glorp's Battery Optimization

Home Assistant custom integration that adds battery charge/discharge optimization
(zero-export matching, solar surplus charging, off-peak night charging, SOC safety
limits) on top of the [zendure_ha](https://github.com/Zendure/Zendure-HA) integration.

## Why this exists

`zendure_ha`'s own "manager" abstraction (the aggregated `manual` mode driven by a
signed `manual_power` number) does not reliably translate its internal charge/discharge
decisions into commands the device actually executes, at least on a SolarFlow 1600 AC+.
The device's own per-device entities (`select.<device>_ac_mode`, `number.<device>_input_limit`,
`number.<device>_output_limit`) do work reliably. This integration drives those entities
directly and never touches the manager entities.

See [`docs/superpowers/specs/2026-08-21-zendure-optimization-design.md`](docs/superpowers/specs/2026-08-21-zendure-optimization-design.md)
for the full design rationale.

## Requirements

- A working [`zendure_ha`](https://github.com/Zendure/Zendure-HA) installation, with
  the device's `select.<device>_ac_mode`, `number.<device>_input_limit` and
  `number.<device>_output_limit` entities confirmed to actually respond (test with a
  manual `select.select_option` / `number.set_value` call before relying on this
  integration).
- A sensor reporting the battery's state of charge (0-100).
- A sensor reporting grid power (positive = importing from the grid, negative =
  exporting).

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

All thresholds (SOC min/max, night charge window/threshold/power, command deadband) are
exposed as regular `number`/`time` entities — adjustable from any dashboard, no YAML or
reconfiguration needed.

## Development

The decision logic (`custom_components/glorp_battery_optimization/decision.py`) is a pure
function with no Home Assistant dependency, tested with plain `pytest`:

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
