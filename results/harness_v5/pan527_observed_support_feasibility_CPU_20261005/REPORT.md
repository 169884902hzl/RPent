# pan527：可见低面不等于锅底支撑带

CPU 分析已运行，公开输入逐 SHA 通过。独立 `v5_pan_surface.py` 只输出点云分层与明确假设的圆/矩形交面积，没有接入 runtime，没有改变旧标签或90%覆盖阈值。五项数学/不可见支撑回归测试通过。

公开测量显示：初始主视角、腕部、抬起和终态的低平面，95%低带点的径向范围约6.57–7.26cm；随后曲面向约10.13–10.27cm锅沿上升3–4cm。相机位于拟合低面上方0.38–0.71m。这说明看到了内侧低面/侧壁，不能建立外部锅底接触面身份。少量低点延伸至柄或背景，还不能用最低z补一个完整底面。

初始缓存rim和终态低面有不同的测量对象。若底面不可见，把内侧低面半径填成一个外部支撑圆，会新增未经观测的几何。helper 因此始终保留 `support_footprint=null`，不把内侧低面、rim、已遮挡区域或圆拟合当成接触真值。

| place525原版例 | 缓存stove尺寸cm | 缓存圆rim在最佳居中时的覆盖假设 | 按可见中位中心的覆盖假设 |
|---|---:|---:|---:|
| s4 |18.10×18.09|90.36–91.72%|59.36–59.82%|
| s8 |18.35×18.49|92.23–93.52%|83.67–84.49%|
| s12 |18.36×18.48|92.19–93.48%|85.37–86.20%|

这些是水平圆rim的数学假设，半径来自另外一局原版s0；三例未保存足够原云，且实体中位中心会受遮挡影响，因此不是三例的支撑重判。18cm目标与20cm圆的尺寸并非绝对不能达到90%，圆与其包围盒面积不同；实际偏心位置则仍可能不足。s8当前stove bbox突然变为26.73×18.60cm，假设覆盖89.96–90.38%跨门槛；没有该局target原云的身份证据，不能挑较大的当前盒来放行。

同局3662/s0的两份显式target raw云（sample0/6）已取回并核SHA：stove主可见平面z约0.9257/0.9258m，主平面观测y上边缘两帧约0.2988m，当前02–98% bbox却缩到y0.2846m。终态锅偏出该观测区域：缓存rim移到终态各圆拟合中心的覆盖仅25.74–31.20%（缓存target）、20.60–25.75%（current stove）、18.28–23.27%（current top）。终态13,578个实际低带点分别只有12.13%、5.76%、3.45%落在上述box；这是观测点密度比例，不能当支撑面积比例。这里去柄也不能解决偏位。

sample6/7锅云逐字节相同，不能作为两份稳定证据；target只存sample0和6，5/7没有当前target原云，不拿6替7。本分析没有借私有位置或物体尺寸拟合。

helper方案：保持显式输入的点云、拟合面、测量圆和相机位姿；输出径向高度分层、真实低带点范围/数量、相机相对面的距离，以及圆/box假设的交面积。contact身份与完整support footprint仍unknown。后续可接纳的证据应包括：真正两个post-release新帧的obj/target mask/depth/cloud及时间/相机变换；物体外侧下缘或底部的可见证据与target支撑平面；预抓缓存与当前姿态的实测配准/残差；所有release/height/stability条件及独立私有谓词诊断。只有rim/内侧floor，或不可见底部需要补全时，不产生true。

实际命令：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 scripts/audit_v5_pan527_support_feasibility.py --manifest results/harness_v5/pan527_observed_support_feasibility_CPU_20261005/preparation/manifest.json --output results/harness_v5/pan527_observed_support_feasibility_CPU_20261005/report2
python3 -m pytest -q tests/unit_tests/robots/libero/test_v5_pan_surface.py
```

manifest SHA `7095262cdd14a597b57218f9c0daf393593c96c8718b50fef9057323e99369b1`；helper SHA `2d4d6c7d53a82f9ed686f88f87fceb098bd7e5752c329f2e723b4e08ea439fe8`；report2 SHA `8c9e75a1470d301f7c83aba04706b7bd46dddb7a5e8d38baef37403198619401`。report1与对应源脚本副本保持；报告中的matched scene来源、点云、choices/states SHA均显式登记。原始NPZ与原始choices/states不入git，输入路径/SHA在manifest。
