# 4533 当前抽屉 fragment 重复柜体：公开证据与窄修复

原版 LIBERO-90 task25/init2，原 4311 的第三个绑定失败，同 setup、160 block、deterministic reset。4533 实际86.62秒，setup抓取16个完整5步块/80 controls；状态 `first_attempt_public_binding_missing`，基础设施故障false，place未执行。原记录保留，不作为新place物理成绩，不改原4311结果。

显式公开索引：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_dev_20261008/case0/job4533/place_trace_place_on_libero_90_t25_s2_r0_place_vla_subtask160/attempt0/place_trace_index.jsonl`，SHA `4a058ea3a185b696ad7b77cd75b569a211e2a9f9e3169d11f318a3c45b693e27`。10公开frame；119个mask/cloud/RGB-D/metadata文件逐项SHA核对。没有carry段，因为未进入place。

公开报告：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/diagnosis4533/report.json`，SHA `65908634fda94b22864e19c921a9dd7993e2fecf0722b61bf37c423347d07846`。脚本仅读index所列文件，不扫描目录，不读取物体sim坐标/私有goal。

step5：e107 cabinet fragment与独立drawer e47同时为当前测量。两份actual agentview SAM masks的IoU=0.99075252，cabinet覆盖0.99740021、drawer覆盖0.99331772；3D lower/upper边界最大差0.00061035m。mask SHA分别 `c7b1ecdb3ec3e2f6bfcc9f9943eafd4229f20cd3eb60ec464dbfa7aa5db8d3fc`、`444718267e950161c343a184aa3473ef16738a632eebac61d4bc6b7a58b3ab4b`；完整路径在report的duplicate_pair.mask_refs。

旧helper只处理stale cabinet fragments，保留当前的e107以及派生假top e40，与真实当前parent e12/top e104一起形成歧义。窄修：`allow_drawer_fragment_alias=True`时，当前fragment也需通过原有独立current drawer同volume、唯一current较高cabinet关联才删除；排除自己作为parent，拒绝不匹配体积、stale drawer或多个可能parent，保留真正未解的第二柜体。默认False调用保持原行为。没有新几何、没有ID重定向、没有放宽place阈值。

已保存公开frame CPU复现：修前target bind=None；修后删除e107及派生e110/e40/e86，原版专家绑定唯一现有measured top e104。见 `diagnosis4533/binding_reproduction.json`；它只测试绑定，不表示物理完成。38个相关CPU tests通过，未再加宽测试。

下一步只对同case0运行r2源码/同launcher物理单局，真实place执行后才由root决定其余7单局。默认runtime仍未启用此开发清理，旧快照不修改。
