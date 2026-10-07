# 当前公开 stove 身份修复 r2

开发源码 commit `da2fd07`。开关 `--stove-public-identity-v1` / `stove_public_identity_v1` 默认关闭；没有修改登记确认 SOURCE582r2、旧阈值、旧结果或确认布局。42 项相关 CPU 测试通过（新接线、原 transfer 绑定、旧 drawer 清理与 fixture 身份），pytest 仅有本地缺 timeout 插件的原有配置 warning。

实际默认运行时数据已核查：`MeasuredScene.refresh()` 的局部 `instance_masks` 只包含本次 capture 中匹配或新增的实体 ID；`measurement_clouds_by_view[id][camera]` 在同次刷新保存 `xyz_world`、`src=perception`、`source_step`，默认已可用，不依赖持久化诊断文件。新清理在家具派生与状态、候选、专家绑定之前执行。没有追加 capture 或 controls，没有新增状态文本字段。

同类别、同 capture、同视角的 stove 测量在 XY 区域互相覆盖 ≥0.8 且较小实际点云或实际 SAM mask 覆盖 ≥0.98 时，删除重复实例和其派生子实体；代表实例按可用点数排序，保留原实体对象、ID 和全部测量数值。缺原始点云、跨视角、不在本次 capture 或真正分离的测量不合并。只处理 stove，不把柜体/抽屉或微波炉的部件规则扩进来。

原版 transfer probe 在新开关开启时调用 scene owner 的当前点云检查：沿用原 operating-area 的 1m 半径，但同时要求公开中位测量中心在范围内，以及该视角 ≥90% 的实际分割点落在该范围内。没有当作逆运动学可达性或目标谓词；两个真实近处 stove 仍 ambiguous。缺 current raw points 时为 unmeasured，不回退到 bbox 尾部。远处实体可留在场景中，只有本 transfer 的 operating-area eligibility 被拒绝。

保存公开输入的运行时 owner 复算报告：
`coordination/moka_binding_public_CPU_20261008/public_identity_runtime_reproduction_r2.json`。
SHA256 `9100d23386dfc940098622dbb63e617b717318d5616947f5ae8b7183596912ab`。
三局原 ambiguous 均变唯一：580104→e14、580152→e11、580159→e48。580152 原嵌套 e47 与其派生 e95 被去除，其他已有测量不变；远处实际点支持分别为 2.083678%、0.098196%、2.033354%，近处均为 100%。

这只是已访问确认布局的 CPU 公开测量复算，不是确认失败的物理重跑，也不授予技能资格。下一次物理执行必须从原版选择池登记一个独立开发 case，由父代理预约、预回执和提交；不在三个失败确认布局上重试。单局需用同一不可变源码、同一 launcher 的 CPU/GPU 两条分支，记录原版 state SHA、源文件 SHA、实际目标 controls、公开绑定和物理标签。

render 入口仍为 `robots/libero/v5_state.py`，其状态格式不在此改动范围。scene 入口为 `MeasuredScene.canonicalize_stove_measurements()` / `MeasuredScene.stove_operating_area()`；新行为必须显式登记，不能把此次修复隐式混入旧确认结论或训练生成器。
