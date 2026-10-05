# Codex3 pan527 独立CPU支撑可观测性核对

Owned `robots/libero/v5_pan_surface.py`、`tests/unit_tests/robots/libero/test_v5_pan_surface.py`、`scripts/audit_v5_pan527_support_feasibility.py` 和pan527报告。没有动runtime/verification/旧快照，保留其他代理改动，root负责push及共享COORD。

已实际CPU运行report2，SHA `8c9e75a1470d301f7c83aba04706b7bd46dddb7a5e8d38baef37403198619401`；manifest SHA `7095262cdd14a597b57218f9c0daf393593c96c8718b50fef9057323e99369b1`；helper SHA `2d4d6c7d53a82f9ed686f88f87fceb098bd7e5752c329f2e723b4e08ea439fe8`。五项focused测试通过，所有输入逐SHA一致。内侧低平面P95径向约6.57–7.26cm、rim约10.13–10.27cm，相机均在低面上方；不能以低面补一个不可见锅底。helper只提供事实/显式圆面积假设，support_footprint=null。

place525三例不能假设去柄能过：圆与bbox面积不同，18cm目标最佳居中rim覆盖约90–94%，但s4/s12实际中位中心代理约59–60%/85–86%。s8当前target盒扩27cm未经原云核身份，跨90%的假设不能用来放行。3662同局target sample0/6原云已取回；终态rim假设20–31%覆盖、真实低带点仅3–12%在target盒内，仍偏位。target5/7缺测；6/7 object云重复。报告不授资格、不改90%、不改旧判断。

详细数字、同局/跨局边界和后续post-release取证字段见 `results/harness_v5/pan527_observed_support_feasibility_CPU_20261005/REPORT.md`。

远端同步已实际完成：独立源 `/public/home/sunyihan/rpent_libero_eval/source_pan527_support_feasibility_CPU_20261005`，18个explicit文件、无glob。tar SHA `e770daeb6d81a96feb7c38821be1bc64e1106c302fbdc55768e5000d466c10a2`；canonical报告relative路径与本地一致、SHA不变。`preparation/remote_replay_manifest.json` SHA `e2a09b8f6e0f271527322f76f9a84abf5cb6ef30e72d7d86d8f35e0c5f68d36d`，映射显式本地输入为已验证远端路径，不动原manifest。生产robots目录与旧strict6未改。

3670 report5新增Wilson与rep0首访问统计，162/400闭合、choices SHA162一致，报告 SHA `90e7f227b6fa699242277699ab1ffdcc99c5da70dc7d1f4620c5f60666febc60`。nominal含重复只描述；rep0每臂独立scene首访问、未知单列、无资格判断。pan centre名义期间抓96/100（CI90.16–98.43）、最终目标91/100（83.77–95.19）；rep0抓47/50（83.78–97.94）、目标44/50（76.20–94.38）。handle名义抓38/58（52.67–76.44）、目标33/58（44.12–68.82）；rep0抓31/49（49.27–75.33）、目标27/49（41.32–68.15）。moka centre4/100闭合，rep0四局独立：期间抓2/4、目标2/4，两者CI15.00–85.00；公共place TP1/TN1/unknown2。moka handle未闭合，不填失败。私有label未知0，place公共unknown单列。report4的122旧case所有既有字段未变，8份prefix逐SHA且startsWith旧prefix、源SHA相同、label_changes=0。新CPU源码 `source_skill528_prefix_Wilson_CPU_20261005/scripts/audit_v5_skill524_prefix.py`，无新Slurm作业。
