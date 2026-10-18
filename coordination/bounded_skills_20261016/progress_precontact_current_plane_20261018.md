碗 init3 接触前表面已修复：当前深度识别到的碗边沿超出旧范围裁剪边界 0.453 mm，随后被调用方删除。保留旧内部像素后，只补一次有两轴、至少6点支持的局部平面边界；最大点距3 mm、平面残差1 mm，机器人过滤继续生效。运行时不读私有真值。

准确重建最后四个连续公开控制样本后，同一 lift 路线修前 measured_sweep_collision、修后通过。初版静止起步回放两版均通过，不用作改善证据。新增179像素的私有ray诊断均为碗，只用于诊断，不进入运行时或训练。303项相关CPU测试通过（138.26秒）；E9/F及diff检查通过。schema仍bounded-skills/3，SHA 7082085b2c59e592e92bfdfedb85e82e3197c3f366d3f0e9e2959435fb415cb3。

未声称新的物理成功。替换零请求的旧普通pending启动8995_24，固定快照后先跑同launcher真实启动，再进行原版状态0/2/3/24/40的新旧chunk规则配对。node02/nice500，按Codex2及高优先级作业状态控制并发；不改running、held或其他项目作业。证据见reports/precontact_current_plane_CPU_validation_20261018.json。
