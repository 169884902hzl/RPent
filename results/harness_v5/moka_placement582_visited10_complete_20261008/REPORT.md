# placement582 r2 摩卡壶十个访问状态开发结果

4470 单局真实预检与 4477 剩余九局均完成，同源码、同 launcher，init0 的预检回合保留且未在正式分片重跑。10/10 官方成功、10/10 私有末态 done、10/10 公开严格放置通过并在端点停止。公共 stop=true 而私有末态=false 为 0；曾成功后退回为 0。

这是访问过的选择状态开发验证，不是独立确认批，不能判 100 状态门槛。10/10 的 Wilson 95% CI 为 [0.722, 1.000]。

| init | VLA 块 | 实际接触 controls | 额外稳定 hold controls | 私有末态 | 公开停止 |
| --- | ---: | ---: | ---: | --- | --- |
| 0 | 35 | 175 | 138 | True | placement_endpoint_verified |
| 1 | 30 | 150 | 108 | True | placement_endpoint_verified |
| 2 | 28 | 140 | 102 | True | placement_endpoint_verified |
| 3 | 36 | 180 | 138 | True | placement_endpoint_verified |
| 4 | 30 | 150 | 114 | True | placement_endpoint_verified |
| 5 | 32 | 160 | 126 | True | placement_endpoint_verified |
| 6 | 34 | 170 | 138 | True | placement_endpoint_verified |
| 7 | 31 | 155 | 120 | True | placement_endpoint_verified |
| 8 | 30 | 150 | 114 | True | placement_endpoint_verified |
| 9 | 32 | 160 | 114 | True | placement_endpoint_verified |

实际接触轨迹合计 318 块 / 1590 controls，与私有服务执行计数一致。另执行 1212 个零动作稳定 hold controls；它们不包含在接触计数中。每局中位墙钟 146.66 秒。停止检查使用新鲜的公开物体测量、真实夹爪开度、本体感知末端位置、固定公开目标测量和实际 6-control 稳定间隔；没有用私有 done 或关节值驱动停止。

同十个原始 state SHA 与旧混合 SOURCE571/r5/r6 开发包逐局配对：私有末态由 3/10 到 10/10，7 局改善、0 局退步。旧包 6 局曾成功后退回，新包 0；多个代码改动和重复开发状态共同存在，这个对照不是单项因果检验，也不是确认结果。

原始 ledger、contact trace、35 至 28 等全部 public-stop 记录、最终公开两帧、私有末态以及源码 SHA 均在 report.json。外层被选动作的字符串仍为 grasp，但 owned adapter 实际调用的是完整 vla_subtask，实际 receipt/motion trace 已分别披露。所有输入仅从显式 manifest / ledger 定位；未扫描 artifacts。
