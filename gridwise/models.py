from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

Number = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
HourIndex = Annotated[StrictInt, Field(ge=0, le=23)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Hour(Model):
    hour: HourIndex
    demand_kwh: Number
    solar_kwh: Number
    tariff_bdt_per_kwh: Number


class Battery(Model):
    capacity_kwh: Number
    initial_energy_kwh: Number
    minimum_energy_kwh: Number
    max_charge_kwh_per_hour: Number
    max_discharge_kwh_per_hour: Number

    @model_validator(mode="after")
    def bounds(self):
        if not self.minimum_energy_kwh <= self.initial_energy_kwh <= self.capacity_kwh:
            raise ValueError("Battery requires minimum <= initial <= capacity")
        return self


class Scenario(Model):
    scenario_id: str
    operator_notes: Annotated[list[str], Field(min_length=1, max_length=3)]
    hours: Annotated[list[Hour], Field(min_length=24, max_length=24)]
    battery: Battery

    @model_validator(mode="after")
    def validate_scenario(self):
        if not self.scenario_id.strip() or any(not n.strip() for n in self.operator_notes):
            raise ValueError("Identifier and notes must be nonempty")
        if sorted(h.hour for h in self.hours) != list(range(24)):
            raise ValueError("Exactly one entry for each hour 0..23 is required")
        self.hours.sort(key=lambda h: h.hour)
        return self


class Window(Model):
    hours: Annotated[list[HourIndex], Field(min_length=1, max_length=24)]

    @model_validator(mode="after")
    def ordered_hours(self):
        if self.hours != sorted(set(self.hours)):
            raise ValueError("Hours must be unique and ascending")
        return self


class Solar(Window):
    factor: Annotated[Number, Field(le=1)]


class Reserve(Window):
    minimum_energy_kwh: Number


class GridCap(Window):
    max_grid_kwh: Number


class Directive(Model):
    note_index: Annotated[StrictInt, Field(ge=0)]
    applies: StrictBool
    directive_type: Literal["solar_reduction", "minimum_battery_reserve", "no_charge_window",
                            "no_discharge_window", "max_grid_window", "no_op"]
    structured_adjustment: Solar | Reserve | GridCap | Window | None
    explanation: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def exact_shape(self):
        expected = {"solar_reduction": Solar, "minimum_battery_reserve": Reserve,
                    "max_grid_window": GridCap, "no_charge_window": Window,
                    "no_discharge_window": Window, "no_op": type(None)}[self.directive_type]
        if type(self.structured_adjustment) is not expected:
            raise ValueError("Adjustment does not match directive type")
        if self.applies != (self.directive_type != "no_op"):
            raise ValueError("Invalid applies semantics")
        return self


class Interpretation(Model):
    directive_interpretation: list[Directive]


def validate_directives(raw: dict, scenario: Scenario) -> list[Directive]:
    directives = Interpretation.model_validate(raw).directive_interpretation
    if [d.note_index for d in directives] != list(range(len(scenario.operator_notes))):
        raise ValueError("Each note must occur exactly once, in order")
    for d in directives:
        if isinstance(d.structured_adjustment, Reserve):
            if d.structured_adjustment.minimum_energy_kwh > scenario.battery.capacity_kwh:
                raise ValueError("Reserve exceeds battery capacity")
    return directives


class PlanHour(Model):
    hour: HourIndex
    grid_kwh: Number
    solar_used_kwh: Number
    battery_action: Literal["charge", "discharge", "idle"]
    battery_kwh: Number
    battery_energy_after_kwh: Number


class Plan(Model):
    scenario_id: str
    directive_interpretation: list[Directive]
    hourly_plan: Annotated[list[PlanHour], Field(min_length=24, max_length=24)]
    total_grid_kwh: Number
    total_cost_bdt: Number
    peak_grid_kwh: Number
    plan_summary: str
