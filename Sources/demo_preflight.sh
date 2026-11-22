#!/bin/zsh
# Demo preflight (deck v6): checks every service the live demo needs, then warms each demo method with one dev
# question (dev T14-132) and prints PASS/FAIL per check with the warm-up seconds. It starts and stops nothing;
# each warm-up is an ordinary chat request (its trace is stored like any other). Run from anywhere:  Sources/demo_preflight.sh   (exit 1 if any check fails)
API=${API:-http://127.0.0.1:8000/api}
INDEX=${HYU_INDEX_ID:-hyu_20261110_97dc1269_r5}
METHODS=(B0_BASIC_DENSE_RAG R16_PROMPTED_CONDITIONAL AP_RRRL)  # the three compare-mode columns
QUESTION="Which insurance rules apply to me?"
PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
fail=0
report() { if [ "$1" = 0 ]; then echo "PASS  $2"; else echo "FAIL  $2"; fail=1; fi; }

echo "HYU Compass demo preflight  $(TZ=Asia/Seoul date '+%F %T KST')  commit $(git -C "${0:A:h}" rev-parse --short HEAD 2>/dev/null)"
docker ps --format '{{.Names}}' 2>/dev/null | grep -qi mongo;  report $? "Docker: MongoDB container running"
docker ps --format '{{.Names}}' 2>/dev/null | grep -qi qdrant; report $? "Docker: Qdrant container running"
health=$(curl -s -m 10 "$API/health")
echo "$health" | python3 -c 'import json,sys; h=json.load(sys.stdin); sys.exit(0 if h["mongodb"]["ok"] and h["qdrant"]["ok"] else 1)' 2>/dev/null
report $? "Backend up and reaches MongoDB + Qdrant ($API/health)"
curl -s -m 5 http://127.0.0.1:11434/api/tags | python3 -c 'import json,sys; sys.exit(0 if "qwen3.5:4b" in [m["name"] for m in json.load(sys.stdin)["models"]] else 1)' 2>/dev/null
report $? "Ollama running with qwen3.5:4b"
curl -s -m 10 "$API/indexes" | python3 -c "import json,sys; sys.exit(0 if '$INDEX' in [i['index_id'] for i in json.load(sys.stdin)['indexes']] else 1)" 2>/dev/null
report $? "Index $INDEX present"
[ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:5173)" = 200 ]; report $? "Frontend up (http://127.0.0.1:5173)"

presets=$(curl -s -m 10 "$API/pipeline/presets")
for m in $METHODS; do
  out=$(echo "$presets" | python3 -c "
import json, sys, time, urllib.request
p = next(p for p in json.load(sys.stdin)['presets'] if p['id'] == '$m')
assert p['enabled'], p['errors']
body = json.dumps({'question': '$QUESTION', 'stages': p['config'], 'index_id': '$INDEX'}).encode()
start = time.time()
req = urllib.request.Request('$API/chat', body, {'Content-Type': 'application/json'})
trace = json.load(urllib.request.urlopen(req, timeout=300))
assert trace['status'] == 'completed', trace.get('error')
print(f\"{p['name']}: {trace.get('action') or trace['outcome']}, {time.time() - start:.1f} s\")
" 2>&1)
  report $? "Warm-up $m: ${out##*$'\n'}"
done
[ $fail = 0 ] && echo "ALL PASS" || echo "SOME CHECKS FAILED"
exit $fail
