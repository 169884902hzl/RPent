1. 完整oracle CPU条件规划已完成三状态串行/spawn4配对；全部保存前缀、完整标签、请求和选择一致。并未测得整回合加速。
2. 杯子函数级profile及12份完整JSON已交共享COORDINATION，C1可以直接核原字节。初始接触计划与实时感知不在这份CPU实验中。
3. 当前request生产捕获路径已完成五状态串行/worker4配对，候选与诊断全部原字节一致；大候选请求耗时降低，小于64项保留串行。源码1378906e已推送。
4. 原版固定源仍109/136完成/220登记，27失败/84未完成。9杯失败中8局第一杯已完成；未用动作回执代替任务谓词。
5. C3继续同源真实startup和逐状态诊断；新源startup10090已提交，D2正式40未提交，VLA四种交还条件没有物理证据。无训练。

## 完整oracle决策的CPU配对

源码7ffe2118，保存请求来自固定原版状态。计时包含进程开销，排除初始request/接触计划、实时感知与仿真。

| 状态 | 串行秒 | spawn4秒 | 请求/完整contexts/labels/选择 |
| --- | ---: | ---: | --- |
| 碗9248_0 | 35.255 | 23.331 | 一致 |
| 杯9544_124 | 60.415 | 33.248 | 一致 |
| 微波炉9611_120 | 14.939 | 8.112 | 一致 |

证据：`reports/runtime_spawn_oracle_CPU_20261019.json`。`reports/runtime_spawn_profile_CPU_20261019.json`单独记录杯状态含profiler的72.206→37.069秒；不得把它替代上表的基准计时。

## 函数级profile与可采取的改动

同杯状态串行累计时间如下，函数存在嵌套，不能相加。

| 函数 | 调用数 | 累计秒 |
| --- | ---: | ---: |
| SmoothMotion.prepare | 270 | 60.053 |
| PublicRouteScreen.__call__ | 270 | 44.043 |
| PublicRouteScreen._geometry_at | 5431 | 25.988 |
| PublicPoseScreen.check | 2636 | 11.261 |
| PublicPrefixPrediction._screen | 270 | 10.605 |
| separate_target_points | 11 | 7.580 |

后果计算可按候选并行；spawn4已减少完整oracle选择时间，子进程不访问仿真。主进程profile有34.115秒等待三批候选，不能拿主进程的低IK时间当计算已消失。完整top15、调用数、主机和解释器身份保留在profile JSON。精确world分离缓存已经存在，变更像素/载荷/夹爪后不能复用旧结果。

早先真实9006_24感知profile也仍保留：首次refresh6.752秒，其中9次SAM RPC4.930秒；下一次refresh1.506秒，其中3次RPC1.410秒。原件`reports/visual_profile_startup_pair_20261018.json`。它是特定保存任务的真实感知证据，不代表当前全部场景的35–40秒成本已经解决；新源真实startup/整局时间还未出现。

## 初始候选后果的独立CPU探针

相同已完成接触计划的公开adapter，77/107/64个原候选。只枚举候选后果，不重新拟合接触计划，不生成整份实时请求。

| 状态 | 串行秒 | spawn4秒 | 候选和诊断字节 |
| --- | ---: | ---: | --- |
| 碗9248_0 | 12.068 | 8.336 | 一致 |
| 杯9544_124 | 17.174 | 9.644 | 一致 |
| 微波炉9611_120 | 6.858 | 4.924 | 一致 |

证据：`reports/initial_candidates_spawn_CPU_20261019.json`。新开关还需验证捕获当前screen图和公开控制历史后的完整开销；探针结果不能冒充完整request加速。

共享交付收据：`reports/coord_cpu_profile_stove_append_20261019.json`。同目录`runtime_spawn_profile_CPU_20261019/`的12份JSON共473748字节；源端pstats单列保存，未复制为Git二进制。

## 当前request生产捕获路径的五状态复测

源码1378906e，包含公开screen图和控制历史捕获、spawn及合并开销；接触计划已经完成，仍不含重新感知或接触拟合。相比前版c82，小于64个候选保留串行，避免29项持物请求从约0.7秒退步到约3.3秒。

| 状态 | 候选数 | 串行秒 | worker4开关秒 | 候选与诊断字节 |
| --- | ---: | ---: | ---: | --- |
| 碗9248_0 | 77 | 10.673 | 7.142 | 一致 |
| 杯9544_124 | 107 | 16.692 | 8.485 | 一致 |
| 微波炉9611_120 | 64 | 7.101 | 4.650 | 一致 |
| 持第二杯9248_47 | 29 | 0.758 | 0.756 | 一致，实际走串行 |
| 持第二杯9248_113 | 29 | 0.714 | 0.726 | 一致，实际走串行 |

原件：`reports/request_dispatch_pair_CPU_20261019.json`与同名目录中的10份完整JSON。实际CPU主机master；不是node02整局或模型服务延迟。137变更的6项CPU测试通过，c82其余52项定向测试通过；见对应cpu_request_dispatch_tests和cpu_request_planning_tests收据。未运行全仓CI。

串行/worker4两份清单都保持原220个case和预算，CPU preflight均退出0。准备脚本原先误读不存在的manifest.config；已改为核SHA、读取base_config绝对路径、写新配置并更新引用。没有改变场景、标签或公开schema。worker4同源同launcher启动10090_0排在9967后，未跳过真实物理预检。准备原件：`reports/chunk_v3_request_w1_20261019_preparation.json`和`reports/chunk_v3_request_w4_20261019_preparation.json`。

## D2静态切分覆盖

固定40个开发场景的既有任务规则均可切分，未覆盖0；共94个子任务（pick44、on22、in22、open2、close2、turn_on2）。原件：`reports/hybrid_d2_rule_coverage_CPU_20261019.json`。这是静态规则覆盖，不代表公开绑定、call_vla候选、物理可行性、任务成功或模型正确率。9928直接VLA startup还需实际产生请求，后续四触发、3次采样与独立整局复验都欠物理证据。
