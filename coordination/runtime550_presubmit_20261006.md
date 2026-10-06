# Codex3 runtime550 完整冒烟预回执

已接受用户 10/06 00:52 PDT 的全部队列、开发故障直接修复、独立确认/最终失败保留、不绑定节点、显式 manifest 读取、不重复旧作业。当前只提交第 2 项完整 harness 冒烟：原版 10 + 开发 10，v5@750。20 个身份沿用开发 job4103；旧记录保留，非确认/最终回合。

源码 `/public/home/sunyihan/rpent_libero_eval/source_v5_runtime550_20261006`，commit `0538169f4a2f355b429cdeb80848b10fac7bcace`，archive SHA `11b8dce9eba8925fcc816ef87a442682bbaa70d0775ba50e9acb13a44f70671b`。manifest SHA `8e66366f67ac7953c20935f2a8ff3aec2424f3c2636c68282af1c08911ad9d50`。实际 launcher 同入口、从 `/tmp` 执行的 8/8 分片 CPU 预检通过，report SHA `c592fb864d968c02803fc4c7145db46bdc7fd7dd544b4ae8cf3e6d4e5fc12b4a`；未初始化 GPU、未做物理动作。

启用融合、指令查询/腕部召回、当前家具测量、统一严格放置 v6、公共 in 接触路径/目标缓存、测量回执、恢复与 vla_subtask。100 决策 / 80 chunks / 10000 物理步 / 3072 token 不变。观察位姿专项开关仍只在第三法技能 probe 中使用。这是当前合并配置的开发检查，不是单项消融。

预定 job 由 Slurm 在回执推送后分配，立即补登记。无依赖、无节点绑定，每片 1 GPU，8 片上限；当前 4128 占满 8 卡，新作业由 Slurm 在卡释放后调度，不中止运行回合。实际命令与路径详见同名 JSON。输出沿 launcher 的 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/runtime536_smoke20_20261006/job<JOB>/part0..7/{original,development}`。

无异议。技能门槛仍未全通过，未冻结、未开训、未大规模采集；SOURCE549 专项 probe 的配置缺口和旧选择批验证问题独立保留。完成后逐局报融合/相机分布、no_effect/屏蔽动作、最大重复、vla_subtask 可用/选用/结果、测量变化回执及物理结果。
