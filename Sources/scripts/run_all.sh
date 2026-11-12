#!/usr/bin/env bash
# HYU Compass — headless evaluation (PLAYBOOK Appendix G). Run from Sources/ with `conda activate RAG`.
#
#   caffeinate -i ./scripts/run_all.sh --split dev  --run-id dev-01
#   caffeinate -i ./scripts/run_all.sh --split test --run-id test-final --confirm-frozen --reason "G6"
#   ./scripts/run_all.sh --split dev --run-id dev-smoke --smoke
#
# Order: preflight → hyu → memory (not implemented yet: skipped) → generation (backbones) → external (if present).
# The runner's guard refuses a test run without --confirm-frozen, with a dirty git tree, or with labels that do not
# match FROZEN.sha256, and appends the test run to Report/results/TEST_RUNS.md.
set -euo pipefail
cd "$(dirname "$0")/.."

SPLIT="" RUN_ID="" EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --split) SPLIT="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --reason) EXTRA+=(--reason "$2"); shift 2 ;;
    --confirm-frozen|--resume|--smoke) EXTRA+=("$1"); shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ "$SPLIT" = dev ] || [ "$SPLIT" = test ] || { echo "--split dev|test is required" >&2; exit 2; }
[ -n "$RUN_ID" ] || { echo "--run-id is required" >&2; exit 2; }

echo "==> preflight"
docker info >/dev/null 2>&1 || { echo "Docker is not running" >&2; exit 1; }
curl -sf http://127.0.0.1:11434/api/version >/dev/null || { echo "Ollama is not reachable (ollama serve)" >&2; exit 1; }
python -m evaluation.runner --suite hyu --split "$SPLIT" --run-id "$RUN_ID" --dry-run

echo "==> hyu"
python -m evaluation.runner --suite hyu --split "$SPLIT" --run-id "$RUN_ID" ${EXTRA[@]+"${EXTRA[@]}"}

echo "==> memory: skipped (M1/M2 are 'if time', PLAYBOOK A29)"

if [ "$SPLIT" = dev ]; then  # the backbone comparison uses BEIR + fixture cases, never the HYU test split
  echo "==> generation"
  python -m evaluation.runner --suite generation --run-id "$RUN_ID" --resume $( [[ " ${EXTRA[*]-} " == *" --smoke "* ]] && echo --smoke )
fi

echo "==> external: skipped (ConditionalQA is 'if time', PLAYBOOK A29)"
echo "Done: Report/results/$RUN_ID/summary.md"
