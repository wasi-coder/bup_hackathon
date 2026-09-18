"""Call the real service and check interpretation, replay, cost, and latency."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from gridwise.models import Plan, Scenario, validate_directives
from gridwise.replay import replay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', default='test-results/live-samples.json')
    parser.add_argument('--cases', help='Optional alternate case file with input and expected_output directives')
    args = parser.parse_args()
    source = Path(args.cases) if args.cases else next(Path(__file__).resolve().parents[1].glob('*Sample_Cases.json'))
    cases = json.loads(source.read_text())['cases']
    results = []
    with httpx.Client(timeout=30, trust_env=False) as client:
        health = client.get(args.url.rstrip('/') + '/health')
        health.raise_for_status()
        assert health.json() == {'status': 'ok'}
        for case in cases:
            start = time.perf_counter()
            response = None
            try:
                response = client.post(args.url.rstrip('/') + '/optimize-energy', json=case['input'])
                elapsed = time.perf_counter() - start
                response.raise_for_status()
                plan = Plan.model_validate(response.json())
                scenario = Scenario.model_validate(case['input'])
                truth = validate_directives({'directive_interpretation': case['expected_output']['directive_interpretation']}, scenario)
                assert len(plan.directive_interpretation) == len(truth), 'Interpretation count mismatch'
                for actual, expected in zip(plan.directive_interpretation, truth):
                    assert actual.note_index == expected.note_index and actual.applies == expected.applies, 'Note mapping mismatch'
                    assert actual.directive_type == expected.directive_type, 'Directive type mismatch'
                    a, b = actual.structured_adjustment, expected.structured_adjustment
                    if b is None:
                        assert a is None, 'No-op adjustment mismatch'
                    else:
                        assert a is not None and a.hours == b.hours, 'Directive hours mismatch'
                        for field, value in b.model_dump(exclude={'hours'}).items():
                            assert abs(getattr(a, field) - value) <= .000001, 'Directive value mismatch'
                replay(scenario, plan, truth, tolerance=.01)
                reference_cost = case['expected_output'].get('total_cost_bdt')
                if reference_cost is not None:
                    assert plan.total_cost_bdt <= reference_cost + .01, 'Suboptimal cost'
                assert elapsed < 30, 'Deadline exceeded'
                result = {'case': case['id'], 'passed': True, 'seconds': round(elapsed, 3),
                          'cost_bdt': plan.total_cost_bdt, 'response': plan.model_dump()}
            except Exception as error:
                result = {'case': case['id'], 'passed': False, 'seconds': round(time.perf_counter()-start, 3),
                          'error': str(error)}
                if response is not None:
                    try:
                        result['response'] = response.json()
                    except ValueError:
                        result['response'] = 'Non-JSON response'
            results.append(result)
            print(f"{result['case']}: {'PASS' if result['passed'] else 'FAIL'} ({result['seconds']}s)", flush=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding='utf-8')
    count = sum(r['passed'] for r in results)
    print(f'{count}/{len(results)} passed; report: {output}')
    latencies = sorted(r['seconds'] for r in results)
    import math
    print(f'P95 latency: {latencies[math.ceil(.95 * len(latencies))-1]:.3f}s')
    return 0 if count == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
