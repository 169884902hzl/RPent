# Exact seeded payload graph reduction

The saved public bowl-holding state in job9001_2/index2 has 164741 eligible raw pixels, 164706 seed pixels and 46629149 exact radius edges. The original helper materializes all edges even though only 35 pixels have unknown membership. All seed vertices can be contracted to a virtual source because the result is the union of components touching any seed. The new helper constructs unknown-to-unknown edges and links unknown pixels touching a seed to that source. It preserves the original full edge count with an exact KD-tree self-pair count; no threshold, seed, depth point, static-scene veto or membership rule changes.

CPU: 90 affected tests passed, plus 120 literal old/new comparisons including empty/all-seeded, duplicated pixels, exact-gap edges and stationary veto. On the saved public state, two alternating old/new comparisons preserved both the complete output mask and evidence dictionary exactly. Original4.3605/4.3384s, optimized2.0344/2.0420s (about53% lower for this helper). This is a CPU geometry result, not full-episode throughput or physical success. The 19 blocked candidates and the omitted boundary point remain blocked; this performance change does not repair that perception failure.

Artifacts: `reports/payload_seed_saved_exact_CPU_20261018.json`, `reports/payload_seed_synthetic_exact_CPU_20261018.json`, `reports/payload_seed_integrated_CPU_tests_20261018.log.gz`. The saved replay has no new SAM query or control action; full sensor membership and its limitations are retained in the report.

Canonical contract/schema hashes remain identical to 79d1d59 (public-request-legal/2, bounded-skills/3). No training or confirmation admission.
