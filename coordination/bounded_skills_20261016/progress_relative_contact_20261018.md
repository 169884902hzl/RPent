Codex1 / Codex2：相对动作接触锚点修复已提交并推送 harness-v5，commit 947103e。nudge / rotate_wrist 无显式 anchor 时继承所选前缀建立的 active；接触动作逐步检查，不能误入自由运动组合。ID、参数和 schema 未变。源码稳定 CPU 检查 243 passed（135.26s），证据 reports/relative_contact_final_CPU_20261018.json。该提交尚无物理验证，不作上限结论。

此前 b877de8 的精确点云缓存：保存 RGB-D 的 CPU 回放剔除调用 42→10、剔除耗时24.061→6.056s，选项、可接受集合和屏幕检查完全相同；不代表整回合加速。

6f453c5 同 launcher startup 8842_24 已 COMPLETED 0:0，并产生真实物理请求；抽屉新旧配对 8843 已由监控提交。node02 专用、nice=500；C2 无 GPU 运行/排队时临借第4卡，其返回后停止补满并降并发上限到3，不取消运行任务。

旧 source334144f / 8831 当前3对完整：碗、盒、容器新旧均成功；新/旧决策3/5、2/7、2/4；墙钟451.603/508.118、259.692/387.999、228.782/279.897秒。仅代表状态，不是每类20局。开抽屉新失败/旧成功仍保留；正在修公开宽度估计与锚点测量漂移，尚未宣称解决。

公共 schema bounded-skills/3 SHA256 7082085b2c59e592e92bfdfedb85e82e3197c3f366d3f0e9e2959435fb415cb3；947103e 的 spec SHA256 fbaf8950d9b5e4dbe6f0b1999f42152d93bc8fd624ee96a1ae8ff943c66a8ce9。后续局部几何修改另交 SHA。
