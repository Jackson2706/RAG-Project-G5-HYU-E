"""Compare-mode check over the API (same sequential /api/chat calls the UI makes): A0, B0, R16 on a demo case; G1 with/without a demo case."""
import json, sys, time, urllib.request, urllib.error
API = "http://127.0.0.1:8000/api"
INDEX = "hyu_20261110_97dc1269_r5"
out_path = sys.argv[1]
presets = {p["id"]: p for p in json.load(urllib.request.urlopen(f"{API}/pipeline/presets"))["presets"]}
case = next(c for c in json.load(urllib.request.urlopen(f"{API}/demo/cases"))["cases"] if c["case_id"] == "T14-134")

def chat(pid, demo):
    body = {"question": case["question"], "stages": presets[pid]["stages"], "index_id": INDEX, "history": case["history"]}
    if demo:
        body["demo_case_id"] = case["case_id"]
    req = urllib.request.Request(f"{API}/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=300)); code = 200
    except urllib.error.HTTPError as e:
        r = {"detail": e.read().decode()[:300]}; code = e.code
    stages = [s["stage_id"] for s in r.get("stages", []) if s.get("status") == "completed"] if code == 200 else []
    return {"preset": pid, "demo_case": demo, "http": code, "seconds": round(time.time() - t, 1), "action": r.get("action"),
            "outcome": r.get("outcome"), "answer": (r.get("answer") or r.get("detail") or "")[:400],
            "cited": [s.get("title") for s in r.get("sources", []) if s.get("cited")], "trace_stages": stages}

rows = [chat(p, True) for p in ("A0_AAES", "B0_BASIC_DENSE_RAG", "R16_PROMPTED_CONDITIONAL")]
rows += [chat("G1_ORACLE_CONTEXT", False), chat("G1_ORACLE_CONTEXT", True)]
json.dump({"case": case["case_id"], "question": case["question"], "index": INDEX, "runs": rows}, open(out_path, "w"), indent=2)
for r in rows: print(r["preset"], r["demo_case"], r["http"], r["seconds"], r["action"], r["outcome"], r["cited"][:2], "|", r["answer"][:120].replace("\n", " "))
