# Codex3：预测载荷自碰撞的像素身份修复

源码已推送 harness-v5：9a1de6849fbd4084821ca0c44b7bcd4edc7d92f6。快照 /public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v2_pixelidentity_20261018_9a1de68；归档 SHA256 cab0f32a61614ea2540f8a6a740acaa6cc5d40373c692026b8fdd504ee55a51f。规格 SHA256 96511e014a34d323035310e0a4457eedd867a628d7de26fc136a0a66d4e03920，请 Codex1 核对。schema 仍为 bounded-skills/2，SHA256 2af1ac62f759f540c5d96a0f1c6328982f414c0c2b560e80ea98a430a2ef601c。没有新增模型字段。

对 8300_0 首次 move_to → descend → close 预测前缀做了保存输入的 CPU 重放。lift 被排除的实际原因是 measured_payload_collision，不是 IK。旧预测先分别对场景/物体采样，再扣实例；相同表面保留的像素代表不一定一致，留下虚假的静止自体障碍。新实现保留自体过滤后的原始场景像素与实例像素，一次扣除全部移动/附着实例后才采样。仍只允许 1 微米数值身份匹配，附近非实例点及 4 mm 碰撞间隙不变。

同一保存 RGB-D 的新旧重放：旧碰撞点 [-0.02981248,0.23530205,0.94000518] 消除；仍有另一个未被实例掩码覆盖的边界点 [-0.05563947,0.15488490,0.93093240] 阻挡预测载荷。因此这不是“完整 lift 路线已通过”的证据，也没有把多出的 425 仿真步全部归因于像素问题。两视角截图和逐阶段报告在 reports/prefix8300_*CPU_20261018.*，无新观测、SAM 或物理控制。

同时修正私有 oracle 的恢复选择：预测 lift 路线不清楚、但尚无实际失败 lift 时，优先从当前接触位姿刷新感知；不在同一个 chunk 中 close 后立即 open。实际 lift 已失败时仍允许打开后重新接近。此改动不把抓取当成功，不跳过碰撞筛选，不向公开状态添加真值。

CPU 共 255 passed：相关适配器/载荷/运动/碰撞 242 项（98.74 秒），chunk 13 项（12.55 秒），包括自体残点消失、5 mm 处真实邻物仍触发碰撞，以及未知 grasp 先测量/实际失败才释放。致命 Ruff 和 diff 检查通过；既存 pytest timeout 警告保留。收据 reports/chunk_v2_pixelidentity_cpu_validation_20261018.json。

220 个原版状态、绝对路径和永久排除预检通过，manifest SHA256 cb15680cf3fa2ca0bdb2cc9ed34ec80ce73a828a68f141dbb1c42dde9912edfd。新同 launcher 启动是 8597_24，目前排队，尚无物理结果。原 8596_24 及 8300 的 218 个普通 pending 重复分片由此快照接替；取消前均未运行。8300_0 的完整旧配对和仍运行的 8300_1、8262_160 全部保留。取消清单及 held 身份不变的证据见 reports/chunk_v2_pixelidentity_pending_replacement_20261018.json。新正式配对数组仍须等同快照启动真正发出物理请求且正常结束后提交。

资源仍仅 node02/nice500，本项目当时 2 GPU，RF 2 GPU；Codex2 无 GPU 运行/排队时才允许借第 4 卡。没有修改 RF/C5/C6 或历史 held，无训练。原版 oracle 上限 → 两个对照 → K1/K4 → 分叉顺序不变，旧物理结果不覆盖。
