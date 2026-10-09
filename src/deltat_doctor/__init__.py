"""delta-t-doctor: diagnose low delta-T syndrome from utility meter data only."""

__version__ = "0.4.0"

CAUSES = ("fouling", "passing_valves", "constant_flow", "overflow")

CAUSE_LABELS = {
    "fouling": "Fouled coils / heat exchanger",
    "passing_valves": "Leaking or passing valves (water flowing through idle coils)",
    "constant_flow": "Constant-flow coils (3-way valves or stuck-open actuators)",
    "overflow": "Over-flow at part load (excess differential pressure, oversized or hunting valves)",
}
