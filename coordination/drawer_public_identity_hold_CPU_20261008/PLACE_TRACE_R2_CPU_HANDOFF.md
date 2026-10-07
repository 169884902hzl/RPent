# place4311 r2 修复后同 launcher 原版单局已就绪

源码快照 `/public/home/sunyihan/rpent_libero_eval/source_v5_place4311_public_trace_r2_20261008`；commit `0eff8550d2c9cb73f778423d5945c1562c62898d`。

Archive `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/source_code.tar`，SHA `419403734586b6fb2261d7018efc5284c9da2f2887b0dafdb711d23b6ac32505`；沿r1显式462-file list，原skill runtime/controller及launcher保持同版，仅新alias helper会影响本单局。无既有快照覆盖。

case0 manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/case0_vla_subtask160_t25_s2.json`；SHA `f24e99b558d2c343a52e3a58e22bff0ccce3e4a977fcffd779471db194d10b9d`。

同launcher实际CPU preflight从 `/tmp` 运行exit0，source/files/archive/producer/manifest及1个官方state SHA均通过：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/case0_actual_launcher_preflight.json`，SHA `62e8711dfd6edf2682dda18f1bdc911d9848c92dfe7c9c32389b2d1dd7944d6f`。Launcher SHA `87a93437021427560babc47ceaf4da2b307265ec64fd2ad27240533523c8b847`；真实解释器 `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。

公开证据根因及修前None/修后e104的绑定CPU复现见 `PLACE4533_ROOT_CAUSE.md`，38相关tests pass。默认开关仍False；只在此开发trace清理独立drawer公开证明的current fragment。行为/测量可能变化，不声称历史精确重放；旧4311/4533记录和分数不改。

由root预回执并提交，1GPU、无node/依赖；CPU包本身没有提交新GPU。实际命令：

```bash
env PLACE_TRACE_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_place4311_public_trace_r2_20261008 \
 PLACE_TRACE_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/case0_vla_subtask160_t25_s2.json \
 PLACE_TRACE_MANIFEST_SHA=f24e99b558d2c343a52e3a58e22bff0ccce3e4a977fcffd779471db194d10b9d \
 PLACE_TRACE_BASE=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case0_r2 \
 sbatch --parsable /public/home/sunyihan/rpent_libero_eval/source_v5_place4311_public_trace_r2_20261008/coordination/drawer_public_identity_hold_CPU_20261008/run_place_trace.sbatch
```

8单局manifest index `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/registered/manifest_index.json`，SHA `2b923c5ac314b6296ec4a73360105edb291e392ab4165ace3108dfc2717e3a43`。其余7单局尚未投；等case0真实place物理请求及启动无故障后继续。8请求/6 distinct原版状态全部永久训练排除。
