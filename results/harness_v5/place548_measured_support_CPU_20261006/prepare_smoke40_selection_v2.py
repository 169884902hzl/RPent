"""Deterministic paired development smoke; selection is independent of results."""

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
DIRECTORY = ROOT / "results/harness_v5/place548_measured_support_CPU_20261006"
PARENT = ROOT / "results/harness_v5/skill540_articulate_place_selection/preparation/place.json"
PARENT_SHA = "23e97aeda7ae28c44ba15c74c10d4c80e92f12fd8de49e17b17c37fdb00abe93"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert sha(PARENT) == PARENT_SHA
    plan = copy.deepcopy(json.loads(PARENT.read_text()))
    counts = Counter()
    cases = []
    for case in plan["cases"]:
        group = (case["type"], case["episode"]["task"], case["condition"])
        if counts[group] < 5:
            case["parent_registered_name"] = case["name"]
            case["name"] = "place548_" + case["name"]
            cases.append(case)
            counts[group] += 1
    assert len(cases) == 40 and set(counts.values()) == {5}
    assert {case["episode"]["task"] for case in cases} == {2, 24, 10, 25}
    plan["cases"] = cases
    plan["version"] = "place548-paired-unified-v6-development-smoke/2"
    plan["cohort"] = "selection"
    plan["purpose"] = "development smoke after measured drawer contact and unique measured cabinet support fixes; no training or qualification"
    plan["selection"] = "first five already preregistered states in each original manifest task x relation x arm, without consulting outcomes; includes top/bottom drawer and both cabinet-top contexts"
    plan["parent_manifest"] = {"path": str(PARENT), "sha256": PARENT_SHA}
    plan["prior_development_smoke_manifest"] = {"path": str(DIRECTORY / "place_smoke40.json"), "sha256": "f23ceede646ad3742481221532705aa859cb353f3f8910e6b7868f5bfac47b1e"}
    plan["cohort_consumer_contract"] = "launcher selection cohort; reused states remain development-only, not disjoint confirmation"
    plan["selection_group_counts"] = {"/".join(map(str, key)): value for key, value in counts.items()}
    plan["confirmation"] = "development reuse of selection states; cannot grant qualification; preserve all failures"
    plan["qualification_authorized"] = False
    plan["new_training_rows"] = 0
    plan["new_physical_trials"] = 0
    plan["planned_physical_trials"] = 40
    plan["planned_unique_states"] = 20
    plan["metrics"]["first_attempt_denominator"] = "all 10 preregistered states per operation and arm, with setup failures reported separately"
    plan["preregistered_requests_by_type_arm"] = dict(Counter(f"{c['type']}/{c['condition']}" for c in cases))
    for condition in plan["conditions"].values():
        condition["overrides"].update({f"strict_place_v{i}": False for i in range(1, 6)})
        condition["overrides"].update(strict_place_v6=True, fixture_in_contact_v1=True,
                                     target_cache_v1=True)
    plan["common_placement_verifier"] = "strict_place/6-dev"
    plan["common_in_contact_policy"] = "fixture_in_contact_v1; selected measured drawer face/shell routes to contact, measured cavity retains geometry"
    plan["measurement_flags"] = "both arms retain identical parent pinned measurement/front/support/identity flags and explicit dual_view_fusion_v1 + fusion_depth_trim_v2"
    plan["access_reservations"]["inputs"].append({**plan["parent_manifest"], "role": "parent_selection_manifest"})
    plan["producer"] = {"path": str(DIRECTORY / Path(__file__).name), "sha256": sha(Path(__file__))}
    output = DIRECTORY / "place_smoke40_selection_v2.json"
    output.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"manifest": str(output), "sha256": sha(output), "cases": len(cases),
                      "unique_states": len({c['state_sha256'] for c in cases}), "groups": plan["selection_group_counts"]}))


if __name__ == "__main__":
    main()
