"""Context-aware spacecraft Decision Support System."""
FEATURE_COLUMNS = [
    "batt_voltage", "batt_current", "batt_soc",
    "bus_voltage", "bus_current",
    "sa_voltage", "sa_current", "solar_flux",
    "temp_batt", "temp_tx", "temp_obc", "temp_rw", "temp_structure", "obc_temp",
    "heater_state",
    "tx_power", "tx_temp", "rx_rssi", "data_rate", "comm_link_status",
    "rw_speed", "rw_current", "rw_torque",
    "pointing_error",
    "cpu_usage", "mem_usage",
]

TEST_MISSIONS = ["M02", "M03", "M04", "M05"]
