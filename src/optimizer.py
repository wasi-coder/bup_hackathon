"""Continuous linear program. One signed battery flow prevents simultaneous actions."""
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy.optimize import linprog

from .models import Directive, Plan, PlanHour, Scenario

# Keep HiGHS on a stable worker: native solver state must not be torn down with
# short-lived HTTP/test threads, and concurrent requests must not race its scheduler.
_SOLVER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gridwise-solver")


class InfeasibleError(Exception):
    pass


def optimize(scenario: Scenario, directives: list[Directive]) -> Plan:
    b = scenario.battery
    solar = [h.solar_kwh for h in scenario.hours]
    reserve = [b.minimum_energy_kwh] * 24
    charge = [b.max_charge_kwh_per_hour] * 24
    discharge = [b.max_discharge_kwh_per_hour] * 24
    cap = [None] * 24
    for d in directives:
        a = d.structured_adjustment
        if a is None:
            continue
        for h in a.hours:
            if d.directive_type == "solar_reduction":
                solar[h] = min(solar[h], scenario.hours[h].solar_kwh * a.factor)
            elif d.directive_type == "minimum_battery_reserve":
                reserve[h] = max(reserve[h], a.minimum_energy_kwh)
            elif d.directive_type == "no_charge_window":
                charge[h] = 0
            elif d.directive_type == "no_discharge_window":
                discharge[h] = 0
            elif d.directive_type == "max_grid_window":
                cap[h] = min(cap[h], a.max_grid_kwh) if cap[h] is not None else a.max_grid_kwh

    # Blocks: grid[0:24], solar[24:48], signed charge[48:72], energy[72:96].
    objective = np.zeros(96)
    objective[:24] = [h.tariff_bdt_per_kwh for h in scenario.hours]
    equalities = np.zeros((49, 96))
    rhs = np.zeros(49)
    for h in range(24):
        equalities[h, h] = equalities[h, 24 + h] = 1
        equalities[h, 48 + h] = -1
        rhs[h] = scenario.hours[h].demand_kwh
        equalities[24 + h, 72 + h] = 1
        equalities[24 + h, 48 + h] = -1
        if h:
            equalities[24 + h, 71 + h] = -1
        else:
            rhs[24] = b.initial_energy_kwh
    equalities[48, 95] = 1
    rhs[48] = b.initial_energy_kwh
    bounds = ([(0, v) for v in cap] + [(0, v) for v in solar]
              + [(-discharge[h], charge[h]) for h in range(24)]
              + [(v, b.capacity_kwh) for v in reserve])
    result = _SOLVER.submit(linprog, objective, A_eq=equalities, b_eq=rhs, bounds=bounds,
                            method="highs", options={"time_limit": 3.0}).result(timeout=5)
    if result.status == 2:
        raise InfeasibleError("The interpreted constraints have no feasible schedule")
    if not result.success:
        raise RuntimeError("Optimizer did not converge")

    def clean(value):
        return max(0.0, float(value))

    rows = []
    for h in range(24):
        delta = float(result.x[48 + h])
        rows.append(PlanHour(hour=h, grid_kwh=clean(result.x[h]),
                             solar_used_kwh=clean(result.x[24 + h]),
                             battery_action="charge" if delta > 0 else "discharge" if delta < 0 else "idle",
                             battery_kwh=abs(delta), battery_energy_after_kwh=clean(result.x[72 + h])))
    plan = Plan(scenario_id=scenario.scenario_id, directive_interpretation=directives,
                hourly_plan=rows, total_grid_kwh=sum(r.grid_kwh for r in rows),
                total_cost_bdt=sum(r.grid_kwh * scenario.hours[r.hour].tariff_bdt_per_kwh for r in rows),
                peak_grid_kwh=max(r.grid_kwh for r in rows),
                plan_summary=f"Minimum-cost 24-hour dispatch applying {sum(d.applies for d in directives)} "
                             "operator directives, with solar curtailment when needed and final battery energy "
                             "equal to its starting level.")
    from .replay import replay
    replay(scenario, plan, directives)
    return plan
