# LIBERO-MAX：只读运行时接入审计

结论：可以复用 MAX 的配对编排，但当前 v5 不能直接挂上 MAX wrapper 后当作完整评测。首先要修正传感器 observation 合同、明确相机标定条件，并保留逐控制步动作前缀。未提交 MAX GPU 作业；本报告没有打开 benchmark case manifests、PRO BDDL、测试 payload 或训练数据。

## 版本与范围

- 公开仓库：https://github.com/liberomax/LIBERO-MAX
- 只读 checkout：`external_readonly/libero_max_audit_20261007`
- upstream commit：`a1e3cef258b3e00487db5282aef4e36010aaf401`
- 当前 RPent 相关 runtime 最后一次源码提交：`85052d594cf87e0db2e355b405034d758fdcf684`。最终以 `source_evidence.json` 的逐文件 SHA 为准，因为共享仓库还有其他代理提交。
- 远端真实安装源码：`/public/home/sunyihan/rpent_libero_eval/.venv/lib/python3.10/site-packages/`。三份文件已原样复制进 `evidence/installed5880/`；不创建环境，不导入 MuJoCo，不运行仿真。

## 关键接入差异

| 项 | 已核实事实及代码位置 | 影响与需要的改动 |
| --- | --- | --- |
| 运动动作不可按观察及时重规划 | `robots/libero/tools.py:333–397` 的 `move_to` 最多80 controls；target 固定，仅检查外部取消与原生终止。`v5_runtime.py:2041–2088` 可串联8个分段和1个最终 move，理论上至多720 controls。 | 存在通用 cancel checkpoint，但没有 MAX 事件/公共测量变化触发的重感知、更新 target 或路径重规划。保留 native cadence 后记录真正反应延迟；不把整个 move 称为1个不可中止动作，也不声称已有在线避障。 |
| VLA action commitment | `tools.py:151–208` 用单次 RPC 跑 action chunk；真实 `rlinf/libero_env.py:720–741` 在 chunk 内循环全部 actions。`v5_runtime.py:1728–1828` 的 public stop 在 chunk 返回后检查，当前π0.5配置为5 controls/chunk；接触技能还可连跑数百块。 | MAX hook 应在 worker 的每个control后更新事件/observation，不仅在技能结束后。决策层动作承诺和VLA内部新图像查询分别记账。事件后不得静默提前中止已登记的 native chunk。 |
| 官方 X-VLA 也有固定动作块 | MAX `run_xvla_persistent_shard.py:119–150,280–331`：query interval默认30；一次物化30个动作，deque耗尽才再query。MAX事件可能在块中触发，但queue没有clear。 | 最多29个剩余controls才发生下一次查询；这是其native inference配置，不是框架缺陷。我们的adapter应报告自己的cadence和事件后第一query，不擅自把它改成逐步重规划。 |
| **高分辨率重渲染会绕过噪声/亮度响应** | MAX `libero_backend.py:99–136` 仅变换 `*_image` observation；`set_lighting:418–441` 还加0.75/1.25 observation亮度补偿。RPent `tools.py:1164–1217` 额外调用 `render_camera`；远端 `rlinf/venv.py:132–153` 直接 `sim.render`；v5 `refresh:263–284` 使用这些high图。 | **直接接入会绕过sensor noise、occlusion以及illumination的observation brightness部分。** 物理光照和RGBA theme仍能影响重渲染；不能笼统说全部视觉扰动被绕过。PRO `pro_runtime.py:255–279` 的像素变换也只作用返回observation。需要统一observer，RGB/SAM/media均经过同一个受扰路径，避免重复apply。 |
| **相机外参来自实时sim真值** | RPC `env_server.py:267–277`→远端 `libero_env.py:664–672`→`venv.py:198–227`→`robosuite/camera_utils.py:54–56`，每次读取 `sim.data.cam_xpos/cam_xmat`；intrinsics在`camera_utils.py:32–35`读实时fovy。`tools.py:973–985`用它反投影，highres每次重新取meta。MAX `libero_backend.py:195–255` 会改cam位置、四元数、fovy。 | camera_shift后会自动得到新真值标定，不能称为仅从图像恢复相机姿态。登记两个独立configuration：live simulator calibration、initial frozen calibration；每种各跑自身Base/Dynamic配对。移动腕部相机需区分公开机器人FK更新与私有相机位姿读取；本审计只证实当前是后者。 |
| 旧缓存和关系轴不适合在线移物 | `v5_runtime.py:236–246` 关系轴只从初帧相机meta算一次；`refresh:263–284`只重分割被请求类别；`621–629`漏检留cached perception；`2655–2657,2674–2676`抓取前缓存其余目标；`3118–3136`优先用target cache；只有`3020–3022` articulate有局部invalidation。 | 没有MAX事件通用invalidation。目标/容器被挪动会继续沿用旧measurement；新distractors也不一定被枚举。需要仅由公共新帧/测量变化更新缓存，不把私有event payload、目标位置或对象身份给planner；event可用于编排日志，不能替planner绑定。 |
| 避障 | MAX `libero_backend.py:336–379` 把障碍置于eef-target路径。v5的分段servo只做平面分段和测量safeheight，未见occupied-volume规划。 | 目前不是碰撞感知避障器。先保留事实并记录执行失败/恢复；若新增公共几何避障，属于独立行为版本，不能悄悄替换冻结组。 |
| red/SAM鲁棒性 | 公共色比本来不是完整开合验证器。已有4335原版选择状态CPU审计：red_fraction=0诊断precision仅27.48%，不能授权stop；MAX theme/light/noise会直接改变颜色与mask。 | 将颜色规则视为待验证特征，不能给动态成功背书。缺两视角/测量证据输出unknown；时序模型仍不准入stop。测试前后按同一公开observer记录mask/几何缺测，不用sim关节修补runtime。 |

## 官方协议和工作量

`docs/BENCHMARK_SPEC.md` 明确：Lite 800 **pairs**＝1600 rollouts（560 Plus、240 PRO）；Max 8000 pairs＝16000 rollouts（5600 Plus、2400 PRO），8种事件各100/1000 pairs。不是800/8000单局。任务controls上限Spatial220、Object280、Goal300、Long520，warmup10另记。

`docs/RUNTIME_INTEGRATION.md` 要求Plus与PRO使用不同进程和配置：Plus源码`4976dc30028e805ff8094b55501d532c48fec182`，PRO源码`2b910b5b5f53016bef9907632f6f840f1ce2229c`，HF资产单独安装。当前真实venv有standard LIBERO及liberopro，没有liberoplus；不得用现有PRO包冒充官方的两种pinned source。公开README的包版本0.1.0与spec benchmark3.0.0不是同一种版本号，均需记录。

没有读取case分布，因此只能给control预算范围：Lite 352k–832k scored controls加16k warmup；Max 3.52m–8.32m加160k warmup。实际时长尚未测量，不能拿π0.5原版40局的墙钟估MAX完成时间。

配对必须同初始rawstate、policy seed以及**精确的执行动作前缀**，不是仅同seed。Base成功但Dynamic失败、两者均失败、trigger未到、event后无query都保留完整分母。基础设施/trace integrity错误修复后补齐，不能和有效物理失败混淆。案例元数据和私有事件实体/位置/触发真值只进隔离编排与后置评分。

## 下一步独立adapter工作包

1. source/environment launcher：Plus/PRO独立进程、pinned资产与渲染QA，显式case文件，不glob artifacts。
2. observation adapter：一个canonical observation/受扰RGB路径，SAM/media/RGB-D全部使用；若增加1024尺寸observer，明示区别于官方X-VLA360配置，不隐式绕过transform。
3. calibration adapter：live和initial-frozen两种配置独立运行；保存逐帧K/E版本与来源。initial-frozen不是把腕相机冻结在空间中，移动腕部需设计公开FK与固定camera-to-TCP合同。
4. action runner：逐control触发，保留native chunk/技能commitment；共享Base前缀、每次query记录prompt与实际actions；超suite控制预算不得继续。
5. perception/cache：当前公共measurement刷新、公开变化失效缓存、来源/时间与unknown；不能从MAX payload绑定实体或清零某个指定对象的cache。
6. aggregation：初态/前缀一致性、渲染QA、事件/query时刻、全部分母、Base/Dynamic配对与CI；不要把未受扰图像当通过。

只读审计本身不改变现有runtime。父代理随后授权的隔离抽样adapter：先登记seed/算法，再从公开元数据取8 events各20pairs（160pairs），没有成绩条件；GPU最多2卡且技能优先，由父代理统一登记提交。

## sampler并行监控

现有 temporal577 物理采样作业4349，输出`articulate577_stove_multiframe_original_20261007/probe_job4349/part0..4`。第一次live检查四片RUNNING且preflight passed=true，第五片等待JobArrayTaskLimit；没有启动traceback。该作业是原版选择状态的新开发采样，不是确认批或MAX评测。
