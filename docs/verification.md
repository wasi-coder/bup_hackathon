# Verification record

## Offline verification

Windows, Python 3.12, SciPy/HiGHS. The latest offline run passed **46 tests** in
3.61 seconds, including:

- Ten public cases through the HTTP application with test-only interpretation fixtures;
  every optimal cost matched the supplied reference within 0.01 BDT.
- 100 randomized fractional-energy schedules, independently replayed.
- 30 small integer instances checked against a separate dynamic-programming optimizer.
- Thirty concurrent solver calls across eight threads.
- Guardrail, malformed-input, infeasibility, provider-failure, and cache tests.

Fixtures are injected only in tests. These results do not establish LLM accuracy.
JUnit output: `test-results/offline.xml` (local generated artifact).

## Live local verification

Pending model download and real-model HTTP tests. This section will be updated
with measured results; no live success is assumed from the offline suite.

## Live HTTP failure handling

Before the model download completed, the running service returned 503 for health,
400 for malformed JSON, and a controlled 500 for model unavailability.
The OpenAPI schema and interactive documentation both returned HTTP 200.

## Not verified

Docker is unavailable on this machine. Container build/start, registry publication,
public Internet reachability, contest submission, and a recorded video are not
verified or completed. The repository includes Docker configuration and a video script.
