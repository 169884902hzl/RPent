# Codex3 pan562 已提交4271

预回执9a41338先推送/写COORDINATION。10原版已访问开发状态、8片各1GPU/限流8，无节点/依赖绑定，4246确认overlap0。SOURCE562 e6f69a80，archive bd65b1ed75867ce582fe49309d7cc46aed796a8221174d5bdb004bfcbd6e5cf7；manifest SHA6800976d91fab44c3195bed378e83370aa1ae0ffa6f27615a537e91af75b9e63。输出 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/pan562_runtime_direct_same10_selection/job4271/part0..7/probe。仅运行时路径冒烟，不授冻结或新确认。

实际命令：

```bash
env PAN562_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_pan562_20261006 PAN562_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/pan562_runtime_smoke10_CPU_20261006/preparation/pan562_runtime_direct_same10_selection.json PAN562_MANIFEST_SHA=6800976d91fab44c3195bed378e83370aa1ae0ffa6f27615a537e91af75b9e63 sbatch --parsable --array=0-7%8 /public/home/sunyihan/rpent_libero_eval/scripts/run_v5_pan562_runtime_smoke10.sbatch
```
