"""Constants for the Glorp's Battery Optimization integration."""

DOMAIN = "glorp_battery_optimization"

# --- Config entry data (set at setup, changed via reconfigure) ---
CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"
CONF_SOC_ENTITY = "soc_entity"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_MAX_CHARGE_W = "max_charge_w"
CONF_MAX_DISCHARGE_W = "max_discharge_w"
CONF_CAPACITY_KWH = "capacity_kwh"

# AC mode option values written to the device's ac_mode select entity.
AC_MODE_INPUT = "input"
AC_MODE_OUTPUT = "output"

# --- Live-adjustable settings (owned by our number/switch entities) ---
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_NIGHT_CHARGE_SOC_THRESHOLD = "night_charge_soc_threshold"
SETTING_NIGHT_CHARGE_POWER = "night_charge_power"
SETTING_OFF_PEAK_START = "off_peak_start"
SETTING_OFF_PEAK_END = "off_peak_end"
SETTING_DEADBAND_W = "deadband_w"

SETTING_ENABLE_NIGHT_CHARGE = "enable_night_charge"
SETTING_ENABLE_SOLAR_CHARGE = "enable_solar_charge"
SETTING_ENABLE_ZERO_EXPORT = "enable_zero_export"
SETTING_MASTER_ENABLE = "master_enable"

DEFAULT_SOC_MIN = 10
DEFAULT_SOC_MAX = 95
DEFAULT_NIGHT_CHARGE_SOC_THRESHOLD = 50
DEFAULT_NIGHT_CHARGE_POWER = 500
DEFAULT_OFF_PEAK_START = "22:30:00"
DEFAULT_OFF_PEAK_END = "06:30:00"
DEFAULT_DEADBAND_W = 20

# Decision reasons exposed on sensor.<entry>_decision_reason.
REASON_SOC_MIN_PROTECT = "soc_min_protect"
REASON_SOC_MAX_PROTECT = "soc_max_protect"
REASON_NIGHT_CHARGE = "night_charge"
REASON_SOLAR_SURPLUS = "solar_surplus"
REASON_ZERO_EXPORT = "zero_export"
REASON_IDLE = "idle"
REASON_MASTER_DISABLED = "master_disabled"
REASON_ENTITY_UNAVAILABLE = "entity_unavailable"

PLATFORMS = ["sensor", "number", "switch", "time"]
