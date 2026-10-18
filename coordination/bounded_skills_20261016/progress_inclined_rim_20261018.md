# 10/18：盘沿接触生成与杯子物理复测

1. 杯子 init1 同状态复测成功：10决策/失败 → 6决策/成功；新墙钟820.128秒。它是实际完整回合，非启动判定。
2. 薄表面接触保留测得的局部倾斜，源码2997335已提交推送；261项相关CPU回归通过。
3. 两个保存盘子状态的完整碰撞/IK CPU检查通过，固定向下法向变为局部拟合法向；还没有物理推成功结论。
4. 220状态CPU预检已通过；同快照同launcher启动9497_8在node02运行，完整两状态验证仍按启动证据门控。
5. Codex3继续物理验证；Codex1核对SHA，Codex2按匹配源使用上下文。公共协议不变、未冻结、未训练。

## 实际杯子配对

| 同一官方状态 | 源码 | 原生成功 | 决策 | 仿真步 | 墙钟秒 |
| --- | --- | --- | ---: | ---: | ---: |
| cup_transfer_libero_10_t4_s1 / 9248_14 | ec89f74 | false | 10 | 722 | 702.797 |
| 同状态 / 9475_61 | eee8434 | true | 6 | 1174 | 820.128 |

状态SHA b55dd89278457f3c00d7b4d871dc8d64e84534e5a119dd35a53e5a152c831d6a。原任务包含两个杯子的放置。旧轨迹放好第一个后，另一个仍可见但无接触拟合，只扫描直到无公开选项；新轨迹对其测量边界执行非接触接近，随后恢复接触拟合并完成。恢复不是伪造抓取宽度或关闭碰撞检查。墙钟比旧失败回合更长，仿真步也更多；不能将成功前后的墙钟直接解释为吞吐改善。完整逐局结果：reports/cup9475_61_physical_20261018.jsonl。微波炉9475_120/140尚未结束，不能将杯子结果扩成该批全部通过。

## 新代码与CPU证据

源码commit：29973353fd587acdd3172caaad4e452a465f3168，分支harness-v5，普通推送user-fork，无合并/强推。

快照：/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_inclined_rim_20261018_2997335。

archive SHA256：eaa9ff4b35ced712df6d3f2c56fea4076a540fb06cd44ee78bb1eccaf50c02e4。

入口：scripts.probe_bounded_feasibility:episode；解释器：/public/home/sunyihan/rpent_libero_eval/.venv/bin/python。

公共schema仍bounded-skills/3，SHA256 df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa。public-request-legal/2与私有judge10未变。源端参数、夹持力、速度限制、4mm碰撞间隙、仿真预算均未改。

`_surface_contact_plan` 在薄水平表面的每个测量盘沿邻域（半径15mm，至少8点）拟合局部法向，用已有的协方差稳定性比例判断。法向朝向测量支撑面的上半空间，倾斜候选先经同一手部闭合、整条路线扫掠和IK检查；广义平面方案继续保留。所有合适形状共用该流程，不读目标或私有坐标，不按类别写接触规则，不把表面接触声称为对夹抓取。

| 保存状态 | 原法向 | 新选中法向 | CPU秒 |
| --- | --- | --- | ---: |
| 9248_8 / init0 | [0,0,1] | [-0.4362,0.0213,0.8996] | 2.038 |
| 9248_19 / init1 | [0,0,1] | [0.0733,0.4263,0.9016] | 3.196 |

这张表只证明测量/几何路线覆盖，不证明接触效果或任务进展方向正确。CPU回放的contact reference取自捕获的resolved screen.target，而不是不存在的实时SAM缓存；后者缺失曾使第一次诊断脚本退出，已修脚本并完成重跑，没有以假测量替代路线筛选。

测试：`.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_bounded_skills.py tests/unit_tests/robots/libero/test_bounded_payload.py tests/unit_tests/robots/libero/test_bounded_offline_labels.py -q`，261 passed，133.58秒。仅有既存pytest timeout插件配置警告。两个改动代码/测试文件的Ruff问题数与原HEAD相同（5和2），新增0；新辅助脚本Ruff通过。测试原始日志gz、命令及文件SHA见reports/inclined_rim_cpu_validation_20261018.json。未开PR，不将单环境结果称为完整CI矩阵通过。

预检：reports/chunk_v3_inclined_rim_20261018_preparation.json，原220状态身份、任务规则、预算未变，CPU预检exit0。几何回放：reports/plate_inclined_rim_replay_CPU_20261018.json。旧的两盘子物理记录继续保留，18个未启动状态不计作失败。

## 资源和剩余工作

9497_8是同一新快照与launcher的真实启动检查。原9475杯子已结束，Codex2无GPU排队/运行、只余3个本组任务时，移除了9497普通待排的整批依赖，利用第四张空卡；不是release held作业。逐次命令和队列证据另存reports/inclined_rim9497_available_slot_20261018.json。node02/nice500不变。

10:05五项问答及新judge10实际前缀零差异证据分别在progress_prefix_judge9_and_door_identity_20261018.md、progress_judge10_and_plate_20261018.md。新源码的盘子物理结果、微波炉、真实盒子和每类20局上限继续进行；未进入训练或冻结。确认状态永久排除训练。
