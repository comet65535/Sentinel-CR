# Benchmark Usage

## Offline (default)
- `python benchmark/run_eval.py`

Offline mode does not require network, LLM provider, or API key.

## Live
- `python benchmark/run_eval.py --live --backend-base-url http://localhost:8080`

If live mode is not configured, output JSON remains schema-compatible and returns:
- `ok=false`
- `error.code=not_configured`

## Tool Metrics
- `python benchmark/tool_eval.py --input benchmark/results/latest_eval.json --output benchmark/results/latest_tool_eval.json`
