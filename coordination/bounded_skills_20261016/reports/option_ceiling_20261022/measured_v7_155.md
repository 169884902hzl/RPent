155 状态、1630 次登记尝试全部闭合：旧方法 1165 次为 460→461，改善 1、退步 0；所有完整初态和首个所选候选 ID 均一致。新增公开锚点调用单列为 160/465，Wilson 95% 30.2%–38.8%。

执行树 `efa57340221c82cb359d72514c7062edb34de599`。155 状态由原版 train 90 + 自生成扰动 65 构成；无 PRO、D2、确认集。旧 1165 的构成为原版 self×2 + initial_pose×3，以及扰动 self×2 + 三种 VLA 各×3；新增方法每状态×3。新请求按 schema7 重新测量，未把旧 schema6 标签改标题后转用。

局部/登记判据、分支端点原生完成和公开停止原因分别保留。160/465 是登记分支结果，100/465 是这些分支端点已原生完成整任务；很多分支仅执行取物，所以 100/465 不应视作完整回合成功率。各方法目标判据也不完全相同，不跨行作同口径排名。区间按重复试次描述，不能当作独立布局的泛化区间。

| 登记域 | 状态 | 旧方法：基线→本轮 | 新调用登记结果 | Wilson 95% | 新调用端点原生完成 | Wilson 95% |
|---|---:|---:|---:|---:|---:|---:|
| 原版90 | 90 | 203/450→203/450 | 118/270 | 37.9–49.7% | 79/270 | 24.2–34.9% |
| 自扰动65 | 65 | 257/715→258/715 | 42/195 | 16.3–27.8% | 21/195 | 7.2–15.9% |

| 类别 | 旧方法：基线→本轮 | 新调用登记结果 | Wilson 95% | 新调用端点原生完成 | Wilson 95% |
|---|---:|---:|---:|---:|---:|
| bowl_transfer | 93/215→93/215 | 32/75 | 32.1–53.9% | 21/75 | 19.1–39.0% |
| box_transfer | 16/116→17/116 | 15/48 | 19.9–45.3% | 0/48 | 0.0–7.4% |
| container | 55/116→55/116 | 19/48 | 27.0–53.7% | 0/48 | 0.0–7.4% |
| cup_transfer | 58/149→58/149 | 30/57 | 39.9–65.0% | 15/57 | 16.6–39.0% |
| drawer_close | 58/160→58/160 | 28/60 | 34.6–59.1% | 28/60 | 34.6–59.1% |
| drawer_open | 58/127→58/127 | 6/51 | 5.5–23.4% | 6/51 | 5.5–23.4% |
| microwave_close | 56/94→56/94 | 9/42 | 11.7–35.9% | 9/42 | 11.7–35.9% |
| microwave_open | 47/94→47/94 | 8/42 | 10.0–33.3% | 8/42 | 10.0–33.3% |
| plate_push | 19/94→19/94 | 13/42 | 19.1–46.0% | 13/42 | 19.1–46.0% |

唯一正翻转为 `box_transfer_libero_object_t0_s10_B2_d001_layout11020603_prefix000`，旧 initial_pose 臂、种子 34103000；完整初态相同、首个候选 ID 相同，原记录 2157 步/False，本轮 1895 步/True，两边原生整局均 False，停止原因均 preparation_not_reached。该变化发生在旧臂，不把它当作新增方法的效果。原始回执与登记真值分别保留。

| 新方法：停止原因 | 登记成功 | 登记失败 | 端点原生完成 |
|---|---:|---:|---:|
| block_budget | 0 | 24 | 0 |
| completion_lost_during_handoff | 9 | 39 | 0 |
| handoff_hold_not_settled | 0 | 7 | 0 |
| left_target_region | 0 | 5 | 0 |
| measured_success_after_handoff | 54 | 7 | 0 |
| native_stop | 0 | 3 | 3 |
| native_success | 97 | 0 | 97 |
| no_progress_blocks | 0 | 66 | 0 |
| preparation_not_reached | 0 | 150 | 0 |
| requested_vla_variant_unavailable | 0 | 4 | 0 |

公开结束观测与私有计量使用各自的窗口；仅凭停止原因和真值不一致，不能断言发生真实滑落或验证器误判。公开宣告成功但登记失败的记录、公开未保持完成但登记成功的记录都保留，未调阈值。

150 条 preparation_not_reached 的内层原因：手部扫掠筛查拒绝 111、手臂扫掠筛查拒绝 3、数值 IK 未找到解 26、跟踪误差 7、终点未到达 3。数值搜索失败不是不可达证明，碰撞筛查拒绝也不是已验证物理碰撞；没有据此放宽碰撞检查。

465 次新增尝试中，144 次没有进入 π 推理。逐条实际调用参数、推理次数、内层接近回执和原件 SHA 见 [CPU 明细](measured_v7_155_audit_trials.jsonl)。

| 状态 | 旧方法：基线→本轮 | 新登记结果 | 新端点原生完成 |
|---|---:|---:|---:|
| bowl_transfer_libero_spatial_t0_s0_B2_d000 | 4/5→4/5 | 2/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s10_B2_d002 | 2/5→2/5 | 3/3 | 3/3 |
| bowl_transfer_libero_spatial_t0_s10_B2_d002_layout11020600_prefix000 | 6/11→6/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s10_B2_d002_layout11020600_prefix001 | 6/11→6/11 | 2/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s10_B2_d002_layout11020600_prefix002 | 7/11→7/11 | 1/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s10_B2_d002_layout11020600_prefix003 | 8/11→8/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s10_B2_d002_layout11020600_prefix004 | 9/11→9/11 | 3/3 | 3/3 |
| bowl_transfer_libero_spatial_t0_s11_B2_d000 | 4/5→4/5 | 2/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s12_B2_d000 | 3/5→3/5 | 3/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s13_B2_d002 | 5/5→5/5 | 3/3 | 3/3 |
| bowl_transfer_libero_spatial_t0_s13_B2_d002_layout11020601_prefix000 | 0/11→0/11 | 1/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s13_B2_d002_layout11020601_prefix001 | 7/11→7/11 | 1/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s13_B2_d002_layout11020601_prefix002 | 5/11→5/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s13_B2_d002_layout11020601_prefix003 | 2/11→2/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s13_B2_d002_layout11020601_prefix004 | 8/11→8/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s14_B2_d000 | 0/5→0/5 | 0/3 | 3/3 |
| bowl_transfer_libero_spatial_t0_s15_B2_d002 | 5/5→5/5 | 3/3 | 3/3 |
| bowl_transfer_libero_spatial_t0_s15_B2_d002_layout11020618_prefix000 | 0/11→0/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s15_B2_d002_layout11020618_prefix001 | 0/11→0/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s15_B2_d002_layout11020618_prefix002 | 0/11→0/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s15_B2_d002_layout11020618_prefix003 | 0/11→0/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s15_B2_d002_layout11020618_prefix004 | 0/11→0/11 | 0/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s16_B2_d002 | 5/5→5/5 | 3/3 | 3/3 |
| bowl_transfer_libero_spatial_t0_s1_B2_d000 | 4/5→4/5 | 2/3 | 0/3 |
| bowl_transfer_libero_spatial_t0_s2_B2_d002 | 3/5→3/5 | 3/3 | 3/3 |
| box_transfer_libero_object_t0_s10_B2_d001 | 0/5→0/5 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s10_B2_d001_layout11020603_prefix000 | 0/11→1/11 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s10_B2_d001_layout11020603_prefix001 | 0/11→0/11 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s11_B2_d001 | 0/5→0/5 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s11_B2_d001_layout11020619_prefix000 | 0/11→0/11 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s11_B2_d001_layout11020619_prefix001 | 0/11→0/11 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s12_B2_d001 | 0/5→0/5 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s13_B2_d001 | 0/5→0/5 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s14_B2_d000 | 2/5→2/5 | 3/3 | 0/3 |
| box_transfer_libero_object_t0_s15_B2_d000 | 2/5→2/5 | 3/3 | 0/3 |
| box_transfer_libero_object_t0_s16_B2_d000 | 2/5→2/5 | 3/3 | 0/3 |
| box_transfer_libero_object_t0_s19_B2_d000 | 5/5→5/5 | 3/3 | 0/3 |
| box_transfer_libero_object_t0_s1_B2_d001 | 2/5→2/5 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s1_B2_d001_layout11020602_prefix000 | 0/11→0/11 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s1_B2_d001_layout11020602_prefix001 | 0/11→0/11 | 0/3 | 0/3 |
| box_transfer_libero_object_t0_s3_B2_d000 | 3/5→3/5 | 3/3 | 0/3 |
| container_libero_object_t2_s0_B2_d001 | 0/5→0/5 | 0/3 | 0/3 |
| container_libero_object_t2_s0_B2_d001_layout11020606_prefix000 | 0/11→0/11 | 2/3 | 0/3 |
| container_libero_object_t2_s0_B2_d001_layout11020606_prefix001 | 5/11→5/11 | 0/3 | 0/3 |
| container_libero_object_t2_s0_B2_d001_layout11020606_prefix002 | 3/11→3/11 | 0/3 | 0/3 |
| container_libero_object_t2_s10_B2_d001 | 0/5→0/5 | 0/3 | 0/3 |
| container_libero_object_t2_s11_B2_d001 | 2/5→2/5 | 0/3 | 0/3 |
| container_libero_object_t2_s12_B2_d001 | 0/5→0/5 | 0/3 | 0/3 |
| container_libero_object_t2_s13_B2_d000 | 5/5→5/5 | 3/3 | 0/3 |
| container_libero_object_t2_s14_B2_d000 | 3/5→3/5 | 3/3 | 0/3 |
| container_libero_object_t2_s15_B2_d000 | 3/5→3/5 | 3/3 | 0/3 |
| container_libero_object_t2_s16_B2_d000 | 5/5→5/5 | 0/3 | 0/3 |
| container_libero_object_t2_s17_B2_d000 | 5/5→5/5 | 0/3 | 0/3 |
| container_libero_object_t2_s1_B2_d001 | 0/5→0/5 | 0/3 | 0/3 |
| container_libero_object_t2_s1_B2_d001_layout11020607_prefix000 | 11/11→11/11 | 2/3 | 0/3 |
| container_libero_object_t2_s1_B2_d001_layout11020607_prefix001 | 6/11→6/11 | 3/3 | 0/3 |
| container_libero_object_t2_s1_B2_d001_layout11020607_prefix002 | 7/11→7/11 | 3/3 | 0/3 |
| cup_transfer_libero_10_t4_s10_B2_d005 | 5/5→5/5 | 3/3 | 3/3 |
| cup_transfer_libero_10_t4_s10_B2_d005_layout11020604_prefix000 | 0/11→0/11 | 0/3 | 0/3 |
| cup_transfer_libero_10_t4_s10_B2_d005_layout11020604_prefix001 | 0/11→0/11 | 0/3 | 0/3 |
| cup_transfer_libero_10_t4_s10_B2_d005_layout11020604_prefix002 | 0/11→0/11 | 0/3 | 0/3 |
| cup_transfer_libero_10_t4_s10_B2_d005_layout11020604_prefix003 | 0/11→0/11 | 0/3 | 0/3 |
| cup_transfer_libero_10_t4_s11_B2_d000 | 2/5→2/5 | 1/3 | 0/3 |
| cup_transfer_libero_10_t4_s12_B2_d005 | 2/5→2/5 | 3/3 | 3/3 |
| cup_transfer_libero_10_t4_s12_B2_d005_layout11020605_prefix000 | 3/11→3/11 | 1/3 | 0/3 |
| cup_transfer_libero_10_t4_s12_B2_d005_layout11020605_prefix001 | 5/11→5/11 | 1/3 | 0/3 |
| cup_transfer_libero_10_t4_s12_B2_d005_layout11020605_prefix002 | 5/11→5/11 | 3/3 | 0/3 |
| cup_transfer_libero_10_t4_s12_B2_d005_layout11020605_prefix003 | 3/11→3/11 | 1/3 | 0/3 |
| cup_transfer_libero_10_t4_s12_B2_d005_layout11020605_prefix004 | 5/11→5/11 | 0/3 | 0/3 |
| cup_transfer_libero_10_t4_s13_B2_d005 | 5/5→5/5 | 3/3 | 3/3 |
| cup_transfer_libero_10_t4_s15_B2_d000 | 2/5→2/5 | 2/3 | 0/3 |
| cup_transfer_libero_10_t4_s16_B2_d010 | 5/5→5/5 | 3/3 | 3/3 |
| cup_transfer_libero_10_t4_s17_B2_d000 | 4/5→4/5 | 1/3 | 0/3 |
| cup_transfer_libero_10_t4_s18_B2_d005 | 5/5→5/5 | 3/3 | 3/3 |
| cup_transfer_libero_10_t4_s19_B2_d000 | 4/5→4/5 | 3/3 | 0/3 |
| cup_transfer_libero_10_t4_s1_B2_d000 | 3/5→3/5 | 2/3 | 0/3 |
| drawer_close_libero_90_t0_s10_B2_d018 | 0/5→0/5 | 0/3 | 0/3 |
| drawer_close_libero_90_t0_s10_B2_d018_layout11020611_prefix000 | 1/11→1/11 | 3/3 | 3/3 |
| drawer_close_libero_90_t0_s10_B2_d018_layout11020611_prefix001 | 3/11→3/11 | 2/3 | 2/3 |
| drawer_close_libero_90_t0_s10_B2_d018_layout11020611_prefix002 | 6/11→6/11 | 0/3 | 0/3 |
| drawer_close_libero_90_t0_s10_B2_d018_layout11020611_prefix003 | 2/11→2/11 | 3/3 | 3/3 |
| drawer_close_libero_90_t0_s10_B2_d018_layout11020611_prefix004 | 5/11→5/11 | 1/3 | 1/3 |
| drawer_close_libero_90_t0_s11_B2_d015 | 0/5→0/5 | 0/3 | 0/3 |
| drawer_close_libero_90_t0_s12_B2_d018 | 0/5→0/5 | 0/3 | 0/3 |
| drawer_close_libero_90_t0_s13_B2_d016 | 0/5→0/5 | 0/3 | 0/3 |
| drawer_close_libero_90_t0_s15_B2_d000 | 3/5→3/5 | 3/3 | 3/3 |
| drawer_close_libero_90_t0_s16_B2_d000 | 3/5→3/5 | 3/3 | 3/3 |
| drawer_close_libero_90_t0_s17_B2_d000 | 3/5→3/5 | 2/3 | 2/3 |
| drawer_close_libero_90_t0_s18_B2_d000 | 3/5→3/5 | 3/3 | 3/3 |
| drawer_close_libero_90_t0_s19_B2_d000 | 3/5→3/5 | 2/3 | 2/3 |
| drawer_close_libero_90_t0_s1_B2_d018 | 0/5→0/5 | 0/3 | 0/3 |
| drawer_close_libero_90_t0_s1_B2_d018_layout11020610_prefix000 | 8/11→8/11 | 3/3 | 3/3 |
| drawer_close_libero_90_t0_s1_B2_d018_layout11020610_prefix001 | 6/11→6/11 | 1/3 | 1/3 |
| drawer_close_libero_90_t0_s1_B2_d018_layout11020610_prefix002 | 3/11→3/11 | 2/3 | 2/3 |
| drawer_close_libero_90_t0_s1_B2_d018_layout11020610_prefix003 | 5/11→5/11 | 0/3 | 0/3 |
| drawer_close_libero_90_t0_s1_B2_d018_layout11020610_prefix004 | 4/11→4/11 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s0_B2_d006 | 0/5→0/5 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s0_B2_d006_layout11020608_prefix000 | 11/11→11/11 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s0_B2_d006_layout11020608_prefix001 | 5/11→5/11 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s0_B2_d006_layout11020608_prefix002 | 5/11→5/11 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s0_B2_d006_layout11020608_prefix003 | 5/11→5/11 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s0_B2_d006_layout11020608_prefix004 | 2/11→2/11 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s10_B2_d006 | 0/5→0/5 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s10_B2_d006_layout11020609_prefix000 | 9/11→9/11 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s10_B2_d006_layout11020609_prefix001 | 4/11→4/11 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s11_B2_d007 | 0/5→0/5 | 2/3 | 2/3 |
| drawer_open_libero_goal_t0_s12_B2_d006 | 0/5→0/5 | 3/3 | 3/3 |
| drawer_open_libero_goal_t0_s13_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s14_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s15_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s19_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| drawer_open_libero_goal_t0_s1_B2_d014 | 3/5→3/5 | 1/3 | 1/3 |
| drawer_open_libero_goal_t0_s3_B2_d000 | 2/5→2/5 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s0_B2_d013 | 0/5→0/5 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s10_B2_d003 | 2/5→2/5 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s10_B2_d003_layout11020614_prefix000 | 8/11→8/11 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s10_B2_d003_layout11020614_prefix001 | 8/11→8/11 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s11_B2_d004 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s11_B2_d004_layout11020615_prefix000 | 8/11→8/11 | 2/3 | 2/3 |
| microwave_close_libero_90_t33_s11_B2_d004_layout11020615_prefix001 | 9/11→9/11 | 1/3 | 1/3 |
| microwave_close_libero_90_t33_s12_B2_d003 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s13_B2_d001 | 0/5→0/5 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s14_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s15_B2_d000 | 3/5→3/5 | 3/3 | 3/3 |
| microwave_close_libero_90_t33_s16_B2_d000 | 3/5→3/5 | 3/3 | 3/3 |
| microwave_close_libero_90_t33_s17_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_close_libero_90_t33_s18_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s0_B2_d009 | 0/5→0/5 | 2/3 | 2/3 |
| microwave_open_libero_90_t35_s0_B2_d009_layout11020612_prefix000 | 9/11→9/11 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s0_B2_d009_layout11020612_prefix001 | 4/11→4/11 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s10_B2_d003 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s11_B2_d009 | 0/5→0/5 | 3/3 | 3/3 |
| microwave_open_libero_90_t35_s12_B2_d009 | 0/5→0/5 | 3/3 | 3/3 |
| microwave_open_libero_90_t35_s14_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s15_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s18_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s19_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s1_B2_d009 | 0/5→0/5 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s1_B2_d009_layout11020613_prefix000 | 9/11→9/11 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s1_B2_d009_layout11020613_prefix001 | 7/11→7/11 | 0/3 | 0/3 |
| microwave_open_libero_90_t35_s2_B2_d000 | 3/5→3/5 | 0/3 | 0/3 |
| plate_push_libero_goal_t5_s0_B2_d065 | 3/5→3/5 | 0/3 | 0/3 |
| plate_push_libero_goal_t5_s10_B2_d002 | 3/5→3/5 | 2/3 | 2/3 |
| plate_push_libero_goal_t5_s10_B2_d002_layout11020616_prefix000 | 0/11→0/11 | 0/3 | 0/3 |
| plate_push_libero_goal_t5_s10_B2_d002_layout11020616_prefix001 | 0/11→0/11 | 0/3 | 0/3 |
| plate_push_libero_goal_t5_s12_B2_d089 | 3/5→3/5 | 0/3 | 0/3 |
| plate_push_libero_goal_t5_s13_B2_d089 | 0/5→0/5 | 0/3 | 0/3 |
| plate_push_libero_goal_t5_s14_B2_d000 | 3/5→3/5 | 3/3 | 3/3 |
| plate_push_libero_goal_t5_s14_B2_d000_layout11020617_prefix000 | 0/11→0/11 | 0/3 | 0/3 |
| plate_push_libero_goal_t5_s14_B2_d000_layout11020617_prefix001 | 0/11→0/11 | 0/3 | 0/3 |
| plate_push_libero_goal_t5_s15_B2_d000 | 2/5→2/5 | 2/3 | 2/3 |
| plate_push_libero_goal_t5_s16_B2_d000 | 1/5→1/5 | 1/3 | 1/3 |
| plate_push_libero_goal_t5_s17_B2_d000 | 2/5→2/5 | 3/3 | 3/3 |
| plate_push_libero_goal_t5_s18_B2_d000 | 1/5→1/5 | 2/3 | 2/3 |
| plate_push_libero_goal_t5_s1_B2_d088 | 1/5→1/5 | 0/3 | 0/3 |

原件：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022/measured_anchor_efa57340/CPU_155/` 及 `CPU_155_audit_r1/`。

[执行登记](measured_v7_155_registration.json) · [汇总](measured_v7_155_summary.json) · [1165 条配对](measured_v7_155_pairs.jsonl) · [465 条新增](measured_v7_155_added.jsonl) · [逐状态](measured_v7_155_states.jsonl) · [内层原因和口径](measured_v7_155_audit_manifest.json)。

重分片仅改变未启动状态的分发。第一波 112 个状态完整保存，其余 43 个通过真实 summary 的 SHA 链接回原登记位置；最后 4 个有独立转发证明。无已完成回合重跑、删分或覆盖。见 [第一波证明](measured_v7_first_wave_drain_complete.json)、[43 状态链接](measured_v7_155_link_complete.json)、[尾部4状态](measured_v7_tail4_link_complete.json)。

随后新 D2 使用 `2db200134ea6689e36a66e8aee6f45daa8270b4e`：公开执行代码与 efa 逐 blob 相同，私有目标进展续接口径另行登记。D2 原生完整回放必须独立完成，新增选项、额外采样和私有续接修复的效果不混为单一因果结论。
