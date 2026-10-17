# The Personal Morning Paper
Read BLUEPRINT.md before every step. Build only the current step.
For each step: backend code + pytest tests, frontend code + Vitest tests,
run `cd backend && pytest -q` and `cd frontend && npm test -- --run`,
fix until green, then tell me exactly what to check in the browser.
Do not commit until I confirm the browser check.
Mock all network and AI calls in tests. Never commit .env or store.json.
CopilotKit APIs change between versions: check the installed version's
docs before writing CopilotKit code.
