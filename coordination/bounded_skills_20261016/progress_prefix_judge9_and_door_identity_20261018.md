# 10/18：前缀标注核对与门身份诊断

1. 10:05 的五项问题均已有实现和证据：函数级 profile、碗 init2 双臂修复、CPU 任意前缀接口、候选顺序无语义、最近三条详细回执。
2. 新源码 8966ce8 / 私有 judge9 的真实捕获再次核对：四个 oracle 位置的 legal、acceptable、selected 零差异；另一个非 oracle nudge 前缀可标注。
3. Codex2 可以补有匹配私有测量上下文的 unknown；缺上下文的历史 26 个请求、59 个 unknown 仍不支持，不能换状态补标签。
4. 微波炉门身份仍未修好：保留腕部历史未恢复测量；跨视角跟踪虽恢复三个平面，但叠图确认是固定控制面板，不能作为门或终点证据。
5. Codex3 继续物理复测与类别上限；Codex2 使用匹配源版本的离线接口。未训练、未冻结，确认状态永久排除训练。

## 规划和感知分别耗在哪里

原始证据：`reports/profile_saved9024_120_CPU_20261018.json`，包含每个 pstats 的路径、SHA、全局和项目内前十五函数。代表性源 ff00387，实际请求 46.782 秒。下面是项目内前十五项；累计时间相互嵌套，不能相加。

| 请求函数 | 调用数 | 累计秒 |
| --- | ---: | ---: |
| MeasuredSkillAdapter.request | 1 | 46.782 |
| bounded_timing.timed | 1175 | 43.590 |
| _surface_contact_plan | 3 | 18.913 |
| _cloud_and_ik | 48 | 17.987 |
| request.add | 58 | 15.693 |
| _candidate | 58 | 15.691 |
| SmoothMotion.prepare | 54 | 14.917 |
| grasp_geometry | 1 | 14.563 |
| PublicRouteScreen.__call__ | 54 | 12.737 |
| measure_fixture_handle_pose | 2 | 11.223 |
| PublicPoseScreen.check | 900 | 6.711 |
| measure_fixture_endpoint | 4 | 5.648 |
| _contact_pixels | 6 | 5.331 |
| _instance_pixels | 8 | 5.331 |
| remove_visual_robot | 5 | 5.003 |

一次完整 refresh 为 5.821–7.481 秒。初次 refresh 内 11 次 RPC 共 5.356 秒；其中 refresh_fixture_parts 累计 3.013 秒，_measure_microwave_door 累计 2.943 秒，adjacent_panel_prompt 0.629 秒。其余十五项见原始报告。客户端 profile 把服务端分割计算和传输等待放在一起，不能据此拆出 SAM kernel 时间。

同一个真实启动的互斥墙钟分桶：规划后果 67.198 秒、请求包装 3.193 秒、分割 27.617 秒、实体测量 20.892 秒、深度 0.259 秒、捕获传输 3.626 秒、oracle 3.911 秒、仿真步进和渲染 4.831 秒。它包含初始请求、前缀后果预测和多次回执刷新，所以不能把 35–40 秒理解成一次 refresh。

能缓存的是同一次捕获的原始像素、去机器人后的点云、目标扣除结果和相同位姿的精确 mesh 检查。相关优化已有同状态请求字节及几何数组一致性证据，见 `progress_0750_followup_20261018.md`。不能跨捕获直接复用障碍物。

逐候选进程并行尚不能保持原数值：候选共享数值 IK 的 last_solution、暖启动以及计划缓存。把候选分别送进独立进程会改变续解路径。双视角的纯几何转换和拟合可以在固定输入后并行、按原顺序组装；尚无实测速比，未启用。chunk 内仅测回执目标也未启用，因为它会漏掉移动障碍。结论是先复用同捕获几何，不能把候选当成现成的独立任务并行。

## 碗 init2、候选顺序和详细历史

碗失败是 SAM 遗漏持物下沿、把其深度像素当成静态障碍，新旧规则共同受影响。使用原有 3 mm 连通深度补全，没有降低碰撞间隙。同命令 9022_2：两臂原生成功，各 260 仿真步；新规则 3 次决策 / 356.706 秒，旧规则 5 次 / 435.904 秒。逐臂证据见 `reports/chunk_v3_connected_payload_20261018_paired_latest.json`。

`SKILL_PACKAGE_SPEC.md` 已写明候选目录顺序不表示排名或语义；决策 ID 的序列才是执行顺序。源端详细回执保留最近三条，不按目标筛历史。这两项本轮无变更。

## 最新离线前缀核对

接口为 `robots.libero.bounded_offline_labels.annotate_prefix(state, request, prefix)`；CLI 为 `python -m scripts.label_bounded_prefix`。`legal` 严格调用公开 `legal_after`，`rule_acceptable` 用 oracle 的条件预测状态。它不执行仿真、RPC、渲染或控制。acceptable 是规则标签，不能解释为实际分叉成功率。

真实启动 9471_120、源码 8966ce8 / judge9、捕获文件 81,393,458 字节：

| 前缀位置 | CPU 秒 | legal 数 | acceptable 数 | 与在线差异 |
| --- | ---: | ---: | ---: | ---: |
| oracle 0 | 1.426 | 29 | 5 | 0 |
| oracle 1 | 8.807 | 28 | 1 | 0 |
| oracle 2 | 12.234 | 27 | 1 | 0 |
| oracle 3 | 14.348 | 26 | 1 | 0 |
| 另一合法 nudge | 9.608 | 28 | 5 | 非 oracle 前缀，无在线对照 |

原始输出：`reports/offline_prefix_9471_120_CPU_20261018.json`。最后一行是构造的替代前缀，不宣称它是模型实际输出。旧源码八个上下文、26 个位置的核对与新 judge9 分开保存。缺少测量上下文的历史 unknown 保持 unsupported；私有上下文不进入模型请求。

## 微波炉：跟踪成功不代表门身份正确

完整物理复测 9470_140 仍失败：14 次决策、849 步、923.705 秒，最终无公开选项。绑定 e98 没丢；打开夹爪后没有新的接触计划。原失败 9248_7 完整保留。

`replay_door_history9470_CPU_20261018.py` 用独立腕部掩码在后续真实 RGB-D 上重放原跟踪器，六对全部缺少足够双向视觉对应。没有部署简单的历史保留改动。

`replay_door_crossview9470_CPU_20261018.py` 先把同一时刻的腕部掩码点匹配到主视角，再在主视角追踪。step14→16/17/19 可拟合 1803/1802/1802 个像素，均有 18 个刚体对应；但保存的主视角和腕部叠图显示掩码位于固定控制面板。它揭示上游 SAM 门身份错误，不能进入门验证器，不能证明开合终点。

输出：`reports/microwave9470_140_history_retain_CPU_20261018.json`、`reports/microwave9470_140_crossview_CPU_20261018.json`。后者记录各张叠图的远端绝对路径和 SHA。未修改跟踪阈值、未引入虚构门平面、未部署跨视角跟踪修复。

当前基座预测修复的完整物理复测为 9473_120；启动 9471_120 的实际控制证据只证明启动成功。类别上限批 9248 和真实盒子 9472 仍按各自不可变源码与登记状态运行，不并入同一源版本结果。资源监控继续使用唯一控制器，node02 / nice500；Codex2 排 GPU 作业时降回至多三卡。
