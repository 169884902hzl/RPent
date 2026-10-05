# Codex3：摩卡壶双视角查询与缺测重试修复

已接入默认关闭的 `moka_query_ladder_v1`，两视角使用同一公开RGB-D查询梯度 `.5/.35/.25`。非空SAM回复但没有有限深度、被同帧平底锅掩码排掉、或既有低分几何规则拒绝时，继续下一个同义词。复用既有10点/15%剩余mask/02–98分位/低分extent规则，未改抓取或放置真值门槛。主/腕融合与中性ID关联沿现实现。

集成回归发现并修复placement路径的真实缺陷：目标外的锅会先被目标关联过滤，导致同帧锅mask丢失。现在在该过滤之前留存实际测得的锅mask供moka排除；不会将目标外锅关联为已放置物体。所有query计数严格按RPC开始次数，每视角原图/world-array SHA、query、原mask/排除后mask、点数、bounds、拒因、RPC错误存独立artifact。记录mask开关打开时另存逐mask文件与SHA；不增加131文本字段，不访问私有谓词或sim坐标。

源码SHA：runtime `f362b8023a1836d92a14f74f0b6004cc099a83c12ad909bdca3032f835af9279`；helper `a6ac68e2f76b2b9c0f041c7c4f0043a6caaf8e4fb3d314c5e6c2c87a450e5201`；harness `ed761a0d0c05a27f92ec0a2c3fc0b199034954fd7e8afc9c976d269dc7ab9654`。入口 `MeasuredScene.refresh` 与 `harness_v5_eval.py --moka-query-ladder-v1`。测试9项包括RPC错误已落盘、second-view-only仍保留原ID、两视角placement排除与131文本逐字节一致。

实际CPU命令 `python3 -m pytest -q tests/unit_tests/robots/libero/test_v5_moka_queries.py tests/unit_tests/robots/libero/test_v5_moka_scene_ladder.py tests/unit_tests/robots/libero/test_v5_runtime.py tests/unit_tests/robots/libero/test_v5_perception_geometry.py`：168通过；compile与diff检查通过。尚未声称真实SAM召回/技能资格改善，待3680保存图真实查询结果后再用独立源码做原版物理smoke。3670、3678–3683的已有源码和作业全不改；本项无新Slurm作业，0训练行，未冻结。
