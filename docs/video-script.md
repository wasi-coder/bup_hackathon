# Three-minute solution walkthrough

This is a recording script, not a completed video submission.

**0:00-0:25 — Problem.** GridWise schedules 24 hours of campus demand using solar,
grid power, and a battery. The goal is minimum electricity cost while respecting
operator notes and restoring the battery to its initial energy at the end of the day.

**0:25-1:00 — Language layer.** Show `gridwise/llm.py`. Qwen3 4B Instruct runs locally
through Ollama without a paid API. The model receives operator notes and battery
capacity, and returns one typed directive for each note. Explain start-inclusive,
end-exclusive windows, remaining solar fractions, and percentage reserves.

**1:00-1:30 — Guardrails.** Show `gridwise/models.py`. Validate exact types, note
indices, adjustment fields, finite numbers, and unique ordered hours. Reject invalid
model output rather than pretending an important note is irrelevant. There is no
phrase-matching fallback in the production service.

**1:30-2:05 — Optimization.** Show `gridwise/optimizer.py`. A 96-variable linear
program minimizes tariff times imported grid energy. A signed battery flow prevents
simultaneous charging and discharging. Energy balance, state transitions, reserves,
rate limits, solar limits, grid caps, and final neutrality are hard constraints.

**2:05-2:30 — Verification.** Show the independent replay in `gridwise/replay.py`.
Every schedule is checked before being returned. Show offline tests and the real-model
public sample report. State the actual pass count and measured latency, including
any limitations; do not describe fixture tests as language-model tests.

**2:30-3:00 — Demo.** Show `/health`, send a public sample to `/optimize-energy`,
and display the structured directives and total cost. Point to the README, local
launcher, Dockerfile, and container composition. Only claim deployment or Docker
verification if those steps have actually been performed.
