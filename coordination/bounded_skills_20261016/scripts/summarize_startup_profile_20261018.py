"""Compare saved startup request profiles without rerunning simulation."""
import argparse
import hashlib
import json
import pstats
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(root):
    rows = []
    requests = []
    for job in ("8857_24", "8860_24"):
        directory = root / "results/bounded_skills/feasibility_20261017" / ("job" + job)
        case = directory / "box_transfer_libero_object_t0_s4_oracle_k4"
        choices = case / "choices.jsonl"
        episodes = directory / "episodes.jsonl"
        profile = case / "request_profile.pstats"
        records = [json.loads(line) for line in choices.read_text().splitlines()]
        assert len(records) == 1
        request = records[0]["request"]
        requests.append(request)
        episode, = [json.loads(line) for line in episodes.read_text().splitlines()]
        assert episode["status"] == "startup_physical" and episode["pi05_calls"] == 0
        assert episode["sim_steps"] > 0
        stats = pstats.Stats(str(profile))
        functions = [
            dict(file=key[0], line=key[1], function=key[2], primitive_calls=value[0],
                 calls=value[1], self_s=value[2], inclusive_s=value[3])
            for key, value in sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)
        ]
        rows.append(dict(job=job, source_commit=episode.get("source_commit"),
            inputs=[dict(path=str(path), sha256=digest(path)) for path in (choices, episodes, profile)],
            request_sha256=hashlib.sha256(json.dumps(request, sort_keys=True,
                separators=(",", ":")).encode()).hexdigest(),
            candidate_count=len(request["candidates"]), profile_total_self_s=stats.total_tt,
            top_inclusive_functions=functions[:30],
            scope="one first request in a startup check; not a full episode"))
    assert requests[0] == requests[1], "Public startup requests differ"
    assert rows[0]["request_sha256"] == rows[1]["request_sha256"]
    return dict(rows=rows, public_requests_exactly_equal=True,
        request_profile_self_s_delta=rows[1]["profile_total_self_s"]-rows[0]["profile_total_self_s"],
        script_sha256=digest(Path(__file__)), training=False, confirmation=False,
        limitations=["One startup request per source does not establish stable speedup.",
            "Inclusive function times overlap and must not be summed.",
            "No collision, inverse-kinematics or perception criterion is changed."])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/public/home/sunyihan/rpent_libero_eval"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.root)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("public_requests_exactly_equal", "request_profile_self_s_delta")}))
