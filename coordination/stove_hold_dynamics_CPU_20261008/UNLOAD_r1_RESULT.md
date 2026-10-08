# 灶台接触卸载开发结果

同一已访问原版 `libero_goal/task7/init2`，每个分支先精确重放 900 个已保存公开控制；180 个末端/夹爪检查点逐值一致。7 个固定后缀在执行前登记，每个后缀 20 个控制，再执行 40 个开夹爪零位移控制。私有 `turnoff`/关节值只作被动标签，不选择动作或停点。

| 固定后缀 | 卸载后 off | 再过 2 秒 off | 最后 1 秒始终 off |
| --- | --- | --- | --- |
| 只松手 | false | false | false |
| 松手同时向上 | true | true | true |
| 松手同时向后 | true | true | true |
| 松手同时斜向撤离 | true | true | true |
| 先松手再向上 | true | true | true |
| 先松手再向后 | true | true | true |
| 先闭夹上移再松手 | true | false | false |

这是单个开发状态的固定前缀物理对照，不是独立确认、成功率估计或验证器资格。它支持撤离时同时解除手指接触，不能把瞬时关火锁存为稳定成功。未修改原始失败记录、门槛、判据或确认排除表。

结果 `/public/home/sunyihan/rpent_libero_eval/coordination/stove_hold_dynamics_CPU_20261008/unload_r1/manifest.json`，SHA256 `05b226eeb7fcb70b39432c0de4ab957e9ff7ed6028255f3b767994a8e866e64f`；同目录 `registered_plan.json`、逐次 public controls 和 private labels 的 SHA 均在 manifest 内。

新增开发开关 `--stove-contact-unload-v1`，默认关闭。`articulate` / `vla_subtask` 的灶台接触后同时开夹并上移，再测量稳定状态，跳过旧独立 release/retreat；不自行宣称 endpoint 通过。12 个定向单元测试通过，检查两条实际分支、默认不变、原生终止停止控制与缺测不变。运行时的新物理验证仍待执行，不能用上面的 CPU 对照替代。
