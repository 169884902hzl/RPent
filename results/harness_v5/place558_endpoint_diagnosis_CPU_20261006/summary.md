# 4219 放置端点与公共验证器独立诊断

只读40个已保存选择回合；31个已执行首次动作的冻结 strict_place/6 CPU复算与原判定31/31一致。没有物理重放、改判或准入。

7个on物理端点失败：4个来自准备抓持v2真值为false；真准备后的失败只有3个（current t10 init0/3、vla t25 init1）。两个current真准备失败的servo均到达既定waypoint，最终碗却测在桌面；当前公共记录无法定位掉落发生在哪一段，不能归成servo未达。vla真准备失败执行了800controls，最终碗低于目标柜顶且xy偏离。

9次公共FN的互斥原因：AABB footprint门5（on3/in2）、缓存drawer壳z范围不符2、完整VLA结束后空手夹爪关闭2。5个null均为被遮挡物体的同一步缓存两帧；4个私有真、1个私有假。

| case | 原私有端点 | 原公共判定 | 证据类别 |
|---|---|---|---|
| place548_place_on_libero_90_t10_s2_r0_place_current160 | True | False | FN:measured_AABB_footprint_below_required_overlap |
| place548_place_on_libero_90_t25_s1_r0_place_current160 | False | False | physical_failure:setup_not_true_sustained_hold |
| place548_place_in_libero_90_t2_s0_r0_place_vla_subtask160 | True | None | null:two_frame_object_occluded_cached_same_step |
| place548_place_in_libero_90_t2_s4_r0_place_vla_subtask160 | True | None | null:two_frame_object_occluded_cached_same_step |
| place548_place_in_libero_90_t24_s3_r0_place_vla_subtask160 | True | False | FN:centre_outside_cached_drawer_shell_z_range |
| place548_place_on_libero_90_t25_s1_r0_place_vla_subtask160 | False | False | physical_failure:true_hold_VLA800_endpoint_bowl_below_target_no_support |
| place548_place_on_libero_90_t10_s3_r0_place_current160 | False | False | physical_failure:servo_waypoints_reached_bowl_returned_to_table_carry_loss_not_resolved |
| place548_place_on_libero_90_t25_s2_r0_place_current160 | True | False | FN:measured_AABB_footprint_below_required_overlap |
| place548_place_in_libero_90_t24_s0_r0_place_vla_subtask160 | True | None | null:two_frame_object_occluded_cached_same_step |
| place548_place_in_libero_90_t24_s4_r0_place_vla_subtask160 | True | False | FN:centre_outside_cached_drawer_shell_z_range |
| place548_place_in_libero_90_t24_s1_r0_place_current160 | True | False | FN:measured_AABB_footprint_below_required_overlap |
| place548_place_on_libero_90_t10_s0_r0_place_current160 | False | False | physical_failure:servo_waypoints_reached_bowl_returned_to_table_carry_loss_not_resolved |
| place548_place_in_libero_90_t24_s1_r0_place_vla_subtask160 | True | None | null:two_frame_object_occluded_cached_same_step |
| place548_place_on_libero_90_t10_s4_r0_place_vla_subtask160 | True | False | FN:endpoint_empty_gripper_closed_release_history_not_checked |
| place548_place_on_libero_90_t25_s3_r0_place_vla_subtask160 | False | None | null:two_frame_object_occluded_cached_same_step; physical_failure:setup_not_true_sustained_hold |
| place548_place_on_libero_90_t25_s4_r0_place_current160 | True | False | FN:measured_AABB_footprint_below_required_overlap |
| place548_place_in_libero_90_t2_s3_r0_place_vla_subtask160 | True | False | FN:measured_AABB_footprint_below_required_overlap |
| place548_place_on_libero_90_t10_s1_r0_place_vla_subtask160 | True | False | FN:endpoint_empty_gripper_closed_release_history_not_checked |
| place548_place_on_libero_90_t25_s0_r0_place_vla_subtask160 | False | False | physical_failure:setup_not_true_sustained_hold |
| place548_place_on_libero_90_t25_s4_r0_place_vla_subtask160 | False | False | physical_failure:setup_not_true_sustained_hold |

两例空手关闭FN的EEF距目标碗55–58cm，碗实测稳定在柜顶；末端开度只有1.44/2.70cm，held元数据仍未清。问题是缺释放/持物历史，不建议把开度阈值直接放宽。

三个on footprint FN overlap约0.690–0.780，两个in约0.796–0.799；中心、稳定、开夹、撤离均通过。on的下沿与柜顶差约0.6–0.9cm。应检查放置中心与可见表面AABB的支持几何，不能凭私有成功直接降低阈值。两个in z拒绝均用source_step=0的drawer可见壳界，未证明内腔体积；完整逐例范围与薄片测量保存在diagnosis.json。

execute_subtask (SOURCE553 v5_runtime.py:3005)没有写placement_unknown_reason，普通place (:2826)会写；因此五个null的原日志缺具体缺测原因。这里新增独立诊断解释，不覆盖原回执。

源码SHA与原report/raw路径逐项写入manifest；runtime和已完成作业未动。根因能被记录直接证明的部分与下一轮开发假设分开。
