# Codex3 pan527 独立CPU支撑可观测性核对

Owned `robots/libero/v5_pan_surface.py`、`tests/unit_tests/robots/libero/test_v5_pan_surface.py`、`scripts/audit_v5_pan527_support_feasibility.py` 和pan527报告。没有动runtime/verification/旧快照，保留其他代理改动，root负责push及共享COORD。

已实际CPU运行report2，SHA `8c9e75a1470d301f7c83aba04706b7bd46dddb7a5e8d38baef37403198619401`；manifest SHA `7095262cdd14a597b57218f9c0daf393593c96c8718b50fef9057323e99369b1`；helper SHA `2d4d6c7d53a82f9ed686f88f87fceb098bd7e5752c329f2e723b4e08ea439fe8`。五项focused测试通过，所有输入逐SHA一致。内侧低平面P95径向约6.57–7.26cm、rim约10.13–10.27cm，相机均在低面上方；不能以低面补一个不可见锅底。helper只提供事实/显式圆面积假设，support_footprint=null。

place525三例不能假设去柄能过：圆与bbox面积不同，18cm目标最佳居中rim覆盖约90–94%，但s4/s12实际中位中心代理约59–60%/85–86%。s8当前target盒扩27cm未经原云核身份，跨90%的假设不能用来放行。3662同局target sample0/6原云已取回；终态rim假设20–31%覆盖、真实低带点仅3–12%在target盒内，仍偏位。target5/7缺测；6/7 object云重复。报告不授资格、不改90%、不改旧判断。

详细数字、同局/跨局边界和后续post-release取证字段见 `results/harness_v5/pan527_observed_support_feasibility_CPU_20261005/REPORT.md`。
