# control580 r3：保留开火后的接触，开发配对采集

r2 原版 task7/init0–2 的关火块末端为 0/480；它在开火后新增了
release、retreat 及 12 个张夹保持控制。r3 仅删除这段物理操作，开火
160 块、关火 160 块、原始状态、提示词、后置标签和动作后恢复保持一致。
关火前仍保存当前只读双视角测量，允许遮挡，缺测不改为通过。

源码提交：`740f24d0d3cf3f11030458e6495f26aa80170f23`。
入口：`scripts/prepare_v5_temporal_control_capture_20261007.py`，新增
`--preserve-pre-off-contact` 开关；默认继续使用 r2 操作。未修改 runtime。

7 项 CPU 回归通过：r3 在 on 到第一次 off 调用之间无物理控制；
170 次公开采样、24 个保持控制、动作后 release/retreat 各一次；
r2 仍为 172/36/各两次。末块采样异常和 parent 空返回均保存非零失败。
模拟测试只证明控制流，不算物理成绩。

远端包：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r3/`。

| 文件 | SHA256 |
| --- | --- |
| capture_manifest.json | 3c7fd3936187f99c47ad5fd760cc6233e3e1ca68c808e0f1c5f3495887cf28ef |
| capture_control_sequence.py | 71e9151f86c223565143ad840dfbdd0fc475f6d59262b897634534e3202614e6 |
| run_capture.sbatch | 8e42a2dd434d52dd6376f4c171da7e9f83f57f22ed37756abac237a8a0e1046f |
| same_launcher_CPU_receipt.json | 7b05512f61e9a8ddc1fefe074723d212f796831d4effc99df5ebad56fd3392e0 |

同 launcher CPU 预检 3/3 exit0，各核对原始状态和 23 个源码引用。
旧 r2 manifest 及其 23 个 pin 前后相同。解释器为
`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`；导入与本地服务
配置均继承已实跑的 stove555/source 和 r2 launcher，无节点绑定。

首次物理入口，交给主代理登记后提交：

```bash
sbatch --array=0-0%1 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/temporal_control580_capture_CPU_20261007/r3/run_capture.sbatch
```

同 snapshot、同 launcher 实际产生首个物理请求后，其余状态使用
`--array=1-2%2`。输出为
`results/harness_v5/temporal_control580_original_r3_20261008/probe_jobJOBID/partINDEX`。
CPU 回执不代替该物理检查。本子代理未提交 GPU。

仅重采既有 verifier-train seed0–2，不用 validation seed3–4；不是确认批。
已登记确认重叠为0，但完整 registry 仍 incomplete。不开启公开 stop，
不调阈值，私有标签不控制采样、动作或 ROI。物理结果待逐块配对。
