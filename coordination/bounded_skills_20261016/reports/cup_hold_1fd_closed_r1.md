# 杯子交还：同一状态三旧种子的开发回归

1fd 的三试次全部闭合，公开与私有结果为 success/True、success/True、failure/False。
修前 e4 为 TP0/TN1/FP0/FN2；修后 TP2/TN1/FP0/FN0。
两个真实持物随后均成功执行 carry_to 和 release；整局放置未独立评判，仍为 unknown。
同一原版状态的三个旧策略种子，不作类别可靠性或三个独立新状态。
旧记录保留，确认批不改判，未训练模型。

| 策略种子 | 修前公开/私有 | 修后公开/私有 | 后续成功回执 |
|---|---|---|---|
| 28271000 | failure / True | success / True | carry_to 123步、release 15步 |
| 28272000 | failure / True | success / True | carry_to 32步、release 15步 |
| 28273000 | failure / False | failure / False | 保留恢复动作 |

证据来自 π0.5 已执行动作块的 RGB-D 共动，不增加探测控制，也不删静态障碍点。前两例手位移49.293/60.404mm，相对位移误差1.077/4.167mm。力、预算、4mm碰撞间隙、3cm抬升和15mm共动判据均未变。

运行时记录的完整初态SHA、请求、全部推理输入、预测、控制轨迹3/3相等；独立快照摘要重算仍由Codex1核验。私有成功2/3，Wilson95%区间20.8%–93.9%；一致3/3，区间43.9%–100%，仅描述这个状态的种子样本。

CPU面板693通过；固定10首物理面板11021、同launcher启动11022、正式回归11023均COMPLETED0:0。固定10只验证物理请求，不是10整局成功率。
源码：`1fd0e18070eccf2d6126a2dbdf1e168b4f945208`。快照归档SHA：`45abb240252254bf6021c00953f6b188567d7c8043245ed9283a90841aa50721`。
[机器可读交付](cup_hold_1fd_closed_r1.json)保留逐试次引用、SHA和区间。远端完整原件：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/schema6_20261020/cpu/cup_hold_1fd_closed_r1/`。

动作块传感器复制耗时不是全部检测耗时；旧fallback计时不含最后RGB-D，不能据此宣称达到检测速度目标。盒子FP仍未修复。B2扩展目录继续关闭。
