# Function profiles and exact startup comparison

Source snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_visual_profile_20261018_85107ca`; code commit `85107ca7edd711f78c829c1ef794c4f71103119b`.

Same original state (box, task0/init4), same launcher: jobs 9000_24 / 9006_24. Both produced 175 physical ticks; the latter is a startup probe, not a task-success score. Canonical serialized public request bytes and oracle decision bytes are exactly equal. No candidate, consequence or selected ID changed.

| Metric | Before | After |
| --- | ---: | ---: |
| Request bytes | 30709 | 30709 |
| First request planning profile, s | 28.176859 | 26.121778 |

One physical startup pair; no claim of full episode throughput improvement. CPU exact geometry: 8/8 saved-view pairs, 20 relevant CPU tests passed.

Profiles below are measured, inclusive cumulative values overlap. Perception refresh can recursively invoke the wrist refresh: its child profiles must not be added to the parent. HTTP includes local segmentation service/transport wait, not GPU kernel time.

## Planning request

| Function | Calls | Self s | Cumulative s |
| --- | ---: | ---: | ---: |
| bounded_skills.py:1496 request | 1 | 0.000741 | 26.123525 |
| bounded_timing.py:46 timed | 1322 | 0.007582 | 23.813251 |
| bounded_skills.py:935 grasp_geometry | 2 | 0.064351 | 16.603559 |
| bounded_skills.py:253 _cloud_and_ik | 48 | 0.007888 | 13.218029 |
| bounded_motion.py:124 prepare | 59 | 0.004167 | 11.810370 |
| bounded_skills.py:1604 add | 56 | 0.000149 | 9.436292 |
| bounded_skills.py:1376 _candidate | 56 | 0.001471 | 9.433885 |
| bounded_screen.py:103 __call__ | 59 | 0.276750 | 8.962572 |
| bounded_screen.py:165 _geometry_at | 1909 | 2.204633 | 6.649689 |
| ~:0 <method 'reduce' of 'numpy.ufunc' objects> | 153314 | 6.326693 | 6.326693 |
| bounded_skills.py:369 _contact_pixels | 6 | 0.000061 | 4.496671 |
| bounded_skills.py:689 _instance_pixels | 6 | 0.160460 | 4.496390 |
| ~:0 <method 'all' of 'numpy.ndarray' objects> | 51895 | 0.021397 | 3.763510 |
| _methods.py:61 _all | 55893 | 0.017548 | 3.750428 |
| v5_geometric_grasp.py:152 collision_counts | 3756 | 1.452172 | 3.121998 |

## Actual initial perception refresh

| Function | Calls | Self s | Cumulative s |
| --- | ---: | ---: | ---: |
| v5_runtime.py:279 refresh | 1 | 0.009284 | 6.751638 |
| bounded_timing.py:46 timed | 9 | 0.000099 | 4.930071 |
| http_rpc.py:99 call | 9 | 0.000276 | 4.929685 |
| request.py:500 open | 9 | 0.000110 | 4.906555 |
| request.py:529 _open | 9 | 0.000028 | 4.906112 |
| request.py:489 _call_chain | 18 | 0.000028 | 4.906084 |
| request.py:1376 http_open | 9 | 0.000028 | 4.906037 |
| request.py:1307 do_open | 9 | 0.000129 | 4.906009 |
| client.py:1331 getresponse | 9 | 0.000077 | 4.901781 |
| client.py:311 begin | 9 | 0.000147 | 4.901454 |
| client.py:278 _read_status | 9 | 0.000213 | 4.899472 |
| ~:0 <method 'readline' of '_io.BufferedReader' objects> | 45 | 0.000116 | 4.899254 |
| socket.py:703 readinto | 18 | 0.000088 | 4.899233 |
| ~:0 <method 'recv_into' of '_socket.socket' objects> | 18 | 4.899119 | 4.899119 |
| probe_bounded_feasibility.py:35 refresh | 1 | 0.000021 | 1.508639 |

Planning process parallelism is deferred: `PublicPoseScreen.last_solution`/route warm starts and mutable plans/caches make candidate order observable. The validated optimization only adds a conservative AABB broad phase before the identical local box and hull tests. New legality labels use `public-request-legal/1`; legacy physical runs are development evidence and must not be ingested as current labels.

Previously queued stale snapshots: 132 ordinary pending, zero-request shards cancelled (8870:112, 8987:20). Running/held/protected jobs untouched. Corrected focused pair array9001 continues; bowl init0 is success in both arms (new 3 decisions / old5, both265 steps), init2 still has payload-boundary obstruction and is retained for diagnosis. No freeze, training or confirmation admission.
