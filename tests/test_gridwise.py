import asyncio
import copy
import json
import random
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from gridwise.api import create_app
from gridwise.llm import Interpreter, ModelError, Settings
from gridwise.models import Plan, Scenario, validate_directives
from gridwise.optimizer import InfeasibleError, optimize
from gridwise.replay import replay

CASES = json.loads(next(Path(__file__).resolve().parents[1].glob('*Sample_Cases.json')).read_text())['cases']


class FixtureInterpreter:
    """Test-only dependency injection. Never available through production configuration."""
    def __init__(self, raw):
        self.raw = raw

    async def ready(self):
        return True

    async def interpret(self, scenario):
        return validate_directives({'directive_interpretation': self.raw}, scenario)


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_public_api_and_optimal_cost(case):
    expected = case['expected_output']
    scenario = Scenario.model_validate(case['input'])
    raw = expected['directive_interpretation']
    with TestClient(create_app(FixtureInterpreter(raw))) as client:
        assert client.get('/health').json() == {'status': 'ok'}
        response = client.post('/optimize-energy', json=case['input'])
    assert response.status_code == 200, response.text
    plan = Plan.model_validate(response.json())
    replay(scenario, plan, validate_directives({'directive_interpretation': raw}, scenario))
    assert plan.total_cost_bdt == pytest.approx(expected['total_cost_bdt'], abs=.01)


@pytest.mark.parametrize('mutation', [
    lambda x: x.update(operator_notes=[]),
    lambda x: x.update(operator_notes=[' ']),
    lambda x: x.update(operator_notes=['a'] * 4),
    lambda x: x['hours'].pop(),
    lambda x: x['hours'][0].update(hour=1),
    lambda x: x['hours'][0].update(hour=True),
    lambda x: x['hours'][0].update(demand_kwh='100'),
    lambda x: x['hours'][0].update(solar_kwh=-1),
    lambda x: x['battery'].update(initial_energy_kwh=1e9),
    lambda x: x.update(unknown='not allowed'),
])
def test_bad_requests(mutation):
    raw = copy.deepcopy(CASES[0]['input'])
    mutation(raw)
    with TestClient(create_app(FixtureInterpreter([]))) as client:
        response = client.post('/optimize-energy', json=raw)
        assert response.status_code == 400
        assert 'traceback' not in response.text.lower()


def test_malformed_json_and_nonfinite():
    with TestClient(create_app(FixtureInterpreter([]))) as client:
        for raw in ['{broken', 'null', '[]', json.dumps(CASES[0]['input']).replace('0,', 'NaN,', 1)]:
            assert client.post('/optimize-energy', content=raw,
                               headers={'Content-Type': 'application/json'}).status_code == 400


@pytest.mark.parametrize('mutation', [
    lambda d: d[0].update(note_index=1),
    lambda d: d.pop(),
    lambda d: d[0].update(applies=False),
    lambda d: d[0].update(directive_type='invented'),
    lambda d: d[0]['structured_adjustment'].update(hours=[13, 12]),
    lambda d: d[0]['structured_adjustment'].update(hours=[12, 12]),
    lambda d: d[0]['structured_adjustment'].update(hours=[24]),
    lambda d: d[0]['structured_adjustment'].update(hours=[True]),
    lambda d: d[0]['structured_adjustment'].update(factor=1.1),
    lambda d: d[0]['structured_adjustment'].update(factor=float('nan')),
    lambda d: d[0]['structured_adjustment'].update(factor='0.5'),
    lambda d: d[0]['structured_adjustment'].update(demand_kwh=0),
    lambda d: d[1].update(structured_adjustment={'hours': [1]}),
])
def test_guardrails_reject_invalid_model_output(mutation):
    directives = copy.deepcopy(CASES[0]['expected_output']['directive_interpretation'])
    mutation(directives)
    with pytest.raises((ValueError, ValidationError)):
        validate_directives({'directive_interpretation': directives}, Scenario.model_validate(CASES[0]['input']))


def test_reserve_capacity_and_empty_hours():
    scenario = Scenario.model_validate(CASES[2]['input'])
    raw = copy.deepcopy(CASES[2]['expected_output']['directive_interpretation'])
    raw[0]['structured_adjustment']['minimum_energy_kwh'] = scenario.battery.capacity_kwh + 1
    with pytest.raises(ValueError):
        validate_directives({'directive_interpretation': raw}, scenario)
    raw[0]['structured_adjustment'] = {'hours': [], 'minimum_energy_kwh': 0}
    with pytest.raises(ValueError):
        validate_directives({'directive_interpretation': raw}, scenario)


def test_infeasible_grid_cap():
    raw = copy.deepcopy(CASES[4]['input'])
    raw['battery']['max_discharge_kwh_per_hour'] = 0
    scenario = Scenario.model_validate(raw)
    directives = validate_directives({'directive_interpretation': CASES[4]['expected_output']['directive_interpretation']}, scenario)
    with pytest.raises(InfeasibleError):
        optimize(scenario, directives)
    with TestClient(create_app(FixtureInterpreter(CASES[4]['expected_output']['directive_interpretation']))) as client:
        assert client.post('/optimize-energy', json=raw).status_code == 422


def test_zero_battery_and_solar_curtailment():
    raw = copy.deepcopy(CASES[0]['input'])
    raw['operator_notes'] = ['The menu changes tomorrow.']
    raw['battery'] = dict.fromkeys(raw['battery'], 0)
    for h in raw['hours']:
        h.update(solar_kwh=1000, demand_kwh=10, tariff_bdt_per_kwh=0)
    scenario = Scenario.model_validate(raw)
    directives = validate_directives({'directive_interpretation': [
        {'note_index': 0, 'applies': False, 'directive_type': 'no_op',
         'structured_adjustment': None, 'explanation': 'Unrelated.'}]}, scenario)
    plan = optimize(scenario, directives)
    replay(scenario, plan, directives)
    assert plan.total_cost_bdt == 0
    assert all(r.solar_used_kwh <= 10 for r in plan.hourly_plan)


def test_replay_detects_tampering():
    case = CASES[0]
    scenario = Scenario.model_validate(case['input'])
    directives = validate_directives({'directive_interpretation': case['expected_output']['directive_interpretation']}, scenario)
    plan = optimize(scenario, directives)
    plan.hourly_plan[12].solar_used_kwh += 1
    with pytest.raises(ValueError):
        replay(scenario, plan, directives)


def test_fractional_randomized_cases():
    rng = random.Random(2026)
    for _ in range(100):
        raw = copy.deepcopy(CASES[0]['input'])
        raw['operator_notes'] = ['Nothing relevant today.']
        cap = rng.uniform(.1, 500)
        minimum = rng.uniform(0, cap)
        raw['battery'].update(capacity_kwh=cap, minimum_energy_kwh=minimum,
                              initial_energy_kwh=rng.uniform(minimum, cap),
                              max_charge_kwh_per_hour=rng.uniform(0, 100),
                              max_discharge_kwh_per_hour=rng.uniform(0, 100))
        for h in raw['hours']:
            h.update(demand_kwh=rng.uniform(0, 400), solar_kwh=rng.uniform(0, 500),
                     tariff_bdt_per_kwh=rng.uniform(0, 50))
        rng.shuffle(raw['hours'])
        scenario = Scenario.model_validate(raw)
        directives = validate_directives({'directive_interpretation': [
            {'note_index': 0, 'applies': False, 'directive_type': 'no_op',
             'structured_adjustment': None, 'explanation': 'Unrelated.'}]}, scenario)
        plan = optimize(scenario, directives)
        replay(scenario, plan, directives)
        baseline = sum(max(0, h.demand_kwh-h.solar_kwh)*h.tariff_bdt_per_kwh for h in scenario.hours)
        assert plan.total_cost_bdt <= baseline + 1e-5


def test_llm_transport_retry_cache_and_capacity_key():
    async def run():
        calls = []
        raw = {'directive_interpretation': CASES[0]['expected_output']['directive_interpretation']}
        def handler(request):
            calls.append(json.loads(request.content))
            content = 'malformed' if len(calls) == 1 else json.dumps(raw)
            return httpx.Response(200, json={'message': {'content': content}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            interpreter = Interpreter(Settings(attempts=2), client)
            scenario = Scenario.model_validate(CASES[0]['input'])
            result = await interpreter.interpret(scenario)
            assert len(result) == 2 and len(calls) == 2
            assert 'schema' in calls[1]['messages'][-1]['content']
            await interpreter.interpret(scenario)
            assert len(calls) == 2
            scenario.battery.capacity_kwh += 1
            await interpreter.interpret(scenario)
            assert len(calls) == 3
    asyncio.run(run())


def test_provider_failure_is_controlled():
    class Broken:
        async def ready(self):
            return False
        async def interpret(self, scenario):
            raise ModelError('secret provider response')
    with TestClient(create_app(Broken())) as client:
        assert client.get('/health').status_code == 503
        response = client.post('/optimize-energy', json=CASES[0]['input'])
        assert response.status_code == 500 and 'secret' not in response.text


def test_model_rejects_unsupported_output_after_retry():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={'message': {'content': '{"directive_interpretation":[]}'}})
        )) as client:
            with pytest.raises(ModelError):
                await Interpreter(Settings(), client).interpret(Scenario.model_validate(CASES[0]['input']))
    asyncio.run(run())


def test_optimality_against_independent_discrete_dynamic_program():
    """Integral small instances have integral LP optima; enumerate battery states."""
    rng = random.Random(74)
    for _ in range(30):
        raw = copy.deepcopy(CASES[0]['input'])
        raw['operator_notes'] = ['Grid cap.', 'Reserve.', 'No charging.']
        raw['battery'] = dict(capacity_kwh=6, initial_energy_kwh=3, minimum_energy_kwh=1,
                              max_charge_kwh_per_hour=2, max_discharge_kwh_per_hour=2)
        for h in raw['hours']:
            h.update(demand_kwh=rng.randrange(1, 7), solar_kwh=rng.randrange(7),
                     tariff_bdt_per_kwh=rng.randrange(10))
        scenario = Scenario.model_validate(raw)
        directives = validate_directives({'directive_interpretation': [
            dict(note_index=0, applies=True, directive_type='max_grid_window',
                 structured_adjustment={'hours': [10, 11], 'max_grid_kwh': 4}, explanation='Grid cap.'),
            dict(note_index=1, applies=True, directive_type='minimum_battery_reserve',
                 structured_adjustment={'hours': [18, 19], 'minimum_energy_kwh': 4}, explanation='Reserve.'),
            dict(note_index=2, applies=True, directive_type='no_charge_window',
                 structured_adjustment={'hours': [4, 5],}, explanation='No charging.')
        ]}, scenario)
        states = {3: 0}
        for h in scenario.hours:
            following = {}
            for energy, cost in states.items():
                for delta in range(-2, 3):
                    after = energy + delta
                    if not (1 <= after <= 6) or h.demand_kwh + delta < 0:
                        continue
                    if h.hour in (4, 5) and delta > 0:
                        continue
                    if h.hour in (18, 19) and after < 4:
                        continue
                    grid = max(0, h.demand_kwh + delta - h.solar_kwh)
                    if h.hour in (10, 11) and grid > 4:
                        continue
                    value = cost + grid*h.tariff_bdt_per_kwh
                    following[after] = min(following.get(after, float('inf')), value)
            states = following
        if 3 not in states:
            with pytest.raises(InfeasibleError):
                optimize(scenario, directives)
        else:
            assert optimize(scenario, directives).total_cost_bdt == pytest.approx(states[3], abs=1e-6)


def test_overlapping_constraints_take_strongest_bound():
    raw = copy.deepcopy(CASES[0]['input'])
    raw['operator_notes'] = ['Solar 50%.', 'Solar 20%.']
    scenario = Scenario.model_validate(raw)
    directives = validate_directives({'directive_interpretation': [
        dict(note_index=i, applies=True, directive_type='solar_reduction',
             structured_adjustment={'hours': [12, 13], 'factor': factor}, explanation='Reduced solar.')
        for i, factor in enumerate([.5, .2])
    ]}, scenario)
    plan = optimize(scenario, directives)
    for h in (12, 13):
        assert plan.hourly_plan[h].solar_used_kwh <= scenario.hours[h].solar_kwh * .2 + 1e-6


def test_transport_timeout_and_http_failure():
    async def run():
        for failure in ('timeout', 'http'):
            def handler(request):
                if failure == 'timeout':
                    raise httpx.ReadTimeout('private endpoint credentials', request=request)
                return httpx.Response(503, text='private endpoint credentials')
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with pytest.raises(ModelError) as error:
                    await Interpreter(Settings(), client).interpret(Scenario.model_validate(CASES[0]['input']))
                assert 'private' not in str(error.value)
    asyncio.run(run())


def test_concurrent_solver_calls():
    from concurrent.futures import ThreadPoolExecutor
    def solve(case):
        scenario = Scenario.model_validate(case['input'])
        directives = validate_directives({'directive_interpretation': case['expected_output']['directive_interpretation']}, scenario)
        return optimize(scenario, directives).total_cost_bdt
    with ThreadPoolExecutor(max_workers=8) as pool:
        costs = list(pool.map(solve, CASES * 3))
    for actual, case in zip(costs, CASES * 3):
        assert actual == pytest.approx(case['expected_output']['total_cost_bdt'], abs=.01)
