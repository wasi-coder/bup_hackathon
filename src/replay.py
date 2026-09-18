"""Independent validation of emitted plans; never trusts optimizer state or totals."""
import math

from .models import Directive, Plan, Scenario


def replay(scenario: Scenario, plan: Plan, directives: list[Directive], tolerance=1e-5):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def close(a, b):
        return abs(a - b) <= tolerance

    require(plan.scenario_id == scenario.scenario_id, "Scenario mismatch")
    require([r.hour for r in plan.hourly_plan] == list(range(24)), "Incomplete plan")
    energy = scenario.battery.initial_energy_kwh
    battery = scenario.battery
    for row, source in zip(plan.hourly_plan, scenario.hours):
        for value in (row.grid_kwh, row.solar_used_kwh, row.battery_kwh, row.battery_energy_after_kwh):
            require(math.isfinite(value) and value >= 0, "Invalid numeric value")
        charge = row.battery_kwh if row.battery_action == "charge" else 0
        discharge = row.battery_kwh if row.battery_action == "discharge" else 0
        require(row.battery_action != "idle" or row.battery_kwh == 0, "Nonzero idle")
        require(charge <= battery.max_charge_kwh_per_hour + tolerance, "Charge rate exceeded")
        require(discharge <= battery.max_discharge_kwh_per_hour + tolerance, "Discharge rate exceeded")
        energy += charge - discharge
        require(close(energy, row.battery_energy_after_kwh), "State transition mismatch")
        require(battery.minimum_energy_kwh - tolerance <= energy <= battery.capacity_kwh + tolerance,
                "Battery bound exceeded")
        require(close(row.grid_kwh + row.solar_used_kwh + discharge, source.demand_kwh + charge),
                "Energy balance mismatch")
        effective_solar = source.solar_kwh
        for directive in directives:
            adjustment = directive.structured_adjustment
            if adjustment is None or row.hour not in adjustment.hours:
                continue
            kind = directive.directive_type
            if kind == "solar_reduction":
                effective_solar = min(effective_solar, source.solar_kwh * adjustment.factor)
            elif kind == "minimum_battery_reserve":
                require(energy >= adjustment.minimum_energy_kwh - tolerance, "Reserve violated")
            elif kind == "no_charge_window":
                require(charge <= tolerance, "Charging prohibited")
            elif kind == "no_discharge_window":
                require(discharge <= tolerance, "Discharging prohibited")
            elif kind == "max_grid_window":
                require(row.grid_kwh <= adjustment.max_grid_kwh + tolerance, "Grid cap exceeded")
        require(row.solar_used_kwh <= effective_solar + tolerance, "Solar limit exceeded")
    require(close(energy, battery.initial_energy_kwh), "Final battery neutrality violated")
    require(close(sum(r.grid_kwh for r in plan.hourly_plan), plan.total_grid_kwh), "Grid total mismatch")
    require(close(sum(r.grid_kwh * h.tariff_bdt_per_kwh for r, h in zip(plan.hourly_plan, scenario.hours)),
                  plan.total_cost_bdt), "Cost total mismatch")
    require(close(max(r.grid_kwh for r in plan.hourly_plan), plan.peak_grid_kwh), "Peak mismatch")
