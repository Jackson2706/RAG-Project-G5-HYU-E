"""Create and verify the frozen dev/test label split."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

FROZEN_FILES = ("dev.jsonl", "test.jsonl")


def split(cases: list[dict], dev_size: int, seed: int = 13) -> tuple[list[dict], list[dict]]:
    if not 0 <= dev_size <= len(cases):
        raise ValueError(f"dev_size must be between 0 and {len(cases)}")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("case_id values must be unique")
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for case in sorted(cases, key=lambda item: item["case_id"]):
        strata[(case["slice"], case["gold_profile"]["campus"])].append(case)

    quotas = {key: len(values) * dev_size / len(cases) for key, values in strata.items()} if cases else {}
    allocations = {key: int(quota) for key, quota in quotas.items()}
    remaining = dev_size - sum(allocations.values())
    order = sorted(strata, key=lambda key: (-(quotas[key] - allocations[key]), key))
    for key in order[:remaining]:
        allocations[key] += 1

    rng = random.Random(seed)
    dev, test = [], []
    for key in sorted(strata):
        values = strata[key]
        rng.shuffle(values)
        dev.extend(values[: allocations[key]])
        test.extend(values[allocations[key] :])
    return sorted(dev, key=lambda item: item["case_id"]), sorted(test, key=lambda item: item["case_id"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_jsonl(path: Path, cases: list[dict], split_name: str) -> None:
    text = "".join(json.dumps({**case, "split": split_name}, ensure_ascii=False, sort_keys=True) + "\n" for case in cases)
    path.write_text(text, encoding="utf-8")


def freeze(labels_path: str | Path, out_dir: str | Path, dev_size: int, seed: int = 13) -> dict[str, int]:
    labels_path, out_dir = Path(labels_path), Path(out_dir)
    targets = [out_dir / name for name in (*FROZEN_FILES, "FROZEN.sha256")]
    if any(path.exists() for path in targets):
        raise FileExistsError(f"refusing to re-freeze labels in {out_dir}")
    with labels_path.open(encoding="utf-8") as handle:
        cases = [json.loads(line) for line in handle if line.strip()]
    for case in cases:
        if not isinstance(case.get("adjudicated_by"), str) or not case["adjudicated_by"].startswith("human:"):
            raise ValueError(f"{case.get('case_id', '<unknown>')} is not human-adjudicated")

    dev, test = split(cases, dev_size, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "dev.jsonl", dev, "dev")
    _write_jsonl(out_dir / "test.jsonl", test, "test")
    hashes = {name: _sha256(out_dir / name) for name in FROZEN_FILES}
    (out_dir / "FROZEN.sha256").write_text(
        "".join(f"{hashes[name]}  {name}\n" for name in FROZEN_FILES), encoding="utf-8"
    )
    (out_dir / "test.jsonl").chmod(0o444)
    return {"dev": len(dev), "test": len(test), "seed": seed}


def verify(out_dir: str | Path) -> bool:
    out_dir = Path(out_dir)
    checksum_path = out_dir / "FROZEN.sha256"
    if not checksum_path.is_file():
        return False
    expected: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2:
            return False
        digest, name = parts
        if name not in FROZEN_FILES or len(digest) != 64:
            return False
        expected[name] = digest
    return set(expected) == set(FROZEN_FILES) and all(
        (out_dir / name).is_file() and _sha256(out_dir / name) == digest for name, digest in expected.items()
    )


def verify_frozen(out_dir: str | Path) -> bool:
    return verify(out_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dev-size", type=int, required=True)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args(argv)
    print(json.dumps(freeze(args.labels, args.out, args.dev_size, args.seed), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
