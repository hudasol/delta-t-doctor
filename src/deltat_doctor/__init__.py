"""delta-t-doctor: diagnose low delta-T syndrome from utility meter data only."""

__version__ = "1.2.0"

CP_KJ_KG_K = 4.186  # specific heat of chilled water, kJ/(kg K); single source for every module

CAUSES = ("fouling", "passing_valves", "constant_flow", "overflow")

CAUSE_LABELS = {
    "fouling": "Fouled coils / heat exchanger",
    "passing_valves": "Leaking or passing valves (water flowing through idle coils)",
    "constant_flow": "Constant-flow coils (3-way valves or stuck-open actuators)",
    "overflow": "Over-flow at part load (excess differential pressure, oversized or hunting valves)",
}
