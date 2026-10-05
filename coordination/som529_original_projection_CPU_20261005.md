# Codex3 child：原版双视角 SoM CPU 核对，门槛未通过

只读复用3662显式manifest、四个闭合ledger、states声明和522已核的RGB-D/camera/mask引用。没有artifact发现、私有物体坐标、模拟动作、GPU作业或新训练行。owner仅本次新audit脚本/报告；共享renderer/runtime均未修改。

当前renderer `robots/libero/v6_som.py` 版本 `measured-set-of-mark/5`，SHA `4c1b5b0136a8b8503b2537981ca6fde40db6fe611ba7658f7ce9c34f19a87605`。远端live缺此模块，首次入口ImportError，改为从显式`source_v5_grasp520_synced_measurements_20261005`读取；该文件与本机current逐SHA相同，pixel marks函数SHA `e57f251d310dbd67ff020f5425fa328b8daf34e17eadcf1c8f0762d588cabc72`。不是换了投影实现，也不是模型失败。

257采样共514个视角槽位中，当前同帧可见测量205份：主158（pan119、Moka39），腕47（pan46、Moka1）；其余309槽没有当前目标测量。按图像SHA去重后主151/腕46；固定seed360各抽25图，共50图，未用私有接触/完成标签选样。

| 范围 | mask IoU≥0.5 | 比例 | bbox IoU≥0.5 |
| --- | ---: | ---: | ---: |
| 主视角 | 21/25 | 84% | 25/25 |
| 腕部 | 18/25 | 72% | 25/25 |
| pan | 35/46 | 76.1% | 46/46 |
| Moka | 4/4 | 100% | 4/4 |
| 合计 | 39/50 | **78%，未过90%** | 50/50 |

外接框IoU不得替代mask IoU。50张来自四个相关轨迹、两类物体、原版同一初态，不能充当广泛LIBERO类型准入或独立抓取确认。参考mask是精确重建已登记同帧目标点云的记录实例，不是按最高IoU重新选SAM实例。运行时`visible_component_filter_v1=false`，没有切掉真实部件。

全部11张低mask IoU已保存为独立诊断，原报告保留。4主/7腕，全为pan：

- 最终框覆盖原mask的96.4–98.5%；框面积为mask自身外接框的84.8–93.1%，外接框IoU0.848–0.931。主要不是漏框。
- 原mask占它自身外接矩形面积仅22.3–46.9%，11/11都<50%。蒙太奇显示圆锅体+长柄及夹爪遮挡后呈非矩形，腕部部分锅体又被前景遮挡。这是最终低mask IoU的主要原因；不能只靠把单个矩形贴得更紧凑数。
- 测量世界系AABB原投影面积为SAM外接框的1.00–1.84倍，确有轴对齐体积经透视投影后的额外膨胀，但当前depth-supported矩形已大幅消减。
- 7张腕部的AABB角点部分截出FOV，只有4张原mask实际碰图像边。4张主视角未出FOV仍低IoU，不能把11张全归为FOV。
- metadata写256×256、high RGB/world/mask为1024×1024是原版明确登记的分辨率口径；共享projector对K缩放×4。当前公开world点回投像素的p99最大0.723px，旋转矩阵正交/行列式正常，未发现此次尺寸或transform处理错误。这只验证存储公开几何的内部一致性，不是独立相机标定真值。
- 诊断脚本初版错误要求metadata尺寸等于high尺寸，已按共享代码的K缩放修复并复跑；保留未完成的`low_iou1`，实际成功诊断是`low_iou2`。这不是放宽IoU门槛。

未测量槽的FOV分析仅投影公共pregrasp缓存，明确标为**cached FOV hypothesis，不是当前定位或visible证据**。当前腕部测量47份中40份的AABB部分截出FOV；309个缺测槽不进入好框分母。

建议供root与Codex2协同，未实现：

1. 用既有公开同帧点云拟合测量3D有向边界，再投影；这能减轻世界系AABB膨胀，但单矩形仍保留锅体+柄的空白，不承诺仅此能过90%。仅有lower/upper六个数不足以唯一恢复方向，需复用已有公开测量点云，不能借仿真朝向。
2. 对测量可辨认的锅体/柄做明确3D几何分解，两个部分都保留，带同一中性实体ID并注明测量支持与歧义。使用同一相机投影、同一训练/运行代码，对原始完整实体mask评分，不裁掉柄或夹爪遮挡后的真实可见部分。实现前与Codex2确认媒体字段及联合框评分口径，不能以换成bbox IoU宣称通过。
3. 遮挡让测量无法区分部件时保持unknown/缺测，必要时注册公开视角扫描验证；不靠当前SAM的2D轮廓直接贴紧框，不用阈值/选样/裁mask解决失败。

实际命令（CPU）分别为：

```bash
cd /public/home/sunyihan/rpent_libero_eval
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_grasp520_synced_measurements_20261005 .venv/bin/python scripts/audit_v6_som529_original_frames.py --audit-report /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp522_synced_smoke_CPU_20261005/report2/report.json --audit-report-sha256 70c01d53713840d66acd50a119b8cbdf1464d06d956e10cebe81af2fea722fb3 --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/som529_current_renderer_CPU_20261005/report1
.venv/bin/python scripts/audit_v6_som530_low_iou.py --report /public/home/sunyihan/rpent_libero_eval/results/harness_v5/som529_current_renderer_CPU_20261005/report1/report.json --report-sha256 d32dbed72cf2091306381d50f4c7705a10482b3762c4d5972e9d7437127b185f --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/som529_current_renderer_CPU_20261005/low_iou2
```

两次实际运行exit0；首次语法编译通过，未新增GPU作业。产物与SHA：

- `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/som529_current_renderer_CPU_20261005/report1/report.json`：`d32dbed72cf2091306381d50f4c7705a10482b3762c4d5972e9d7437127b185f`。
- 同目录`checks.jsonl`：`0b24150c88c53b846ec505aace3596a05f09817c394507302f799e795c8f1571`；`inventory.jsonl`：`a1bc1c1984cb76b3a6a4326f2f28e433a2e109d04ef48cbd5ccbb40a276d7ac6`。
- `low_iou2/report.json`：`0ea3c07b7e2f4e2e096dd24b0afed7a5e3beb6ba6937ed58ac454a75cca4969f`；`low_iou2/low_iou_montage.png`：`141aa953d3826611f2500a1814a6b5cd99a7812c68ea9f97e3cce5b24c0428d4`。

本机同名结果目录已有三份JSON/JSONL、低IoU报告和蒙太奇的精确副本。3678/3680的完成产物审计责任保留；不反复报告相同Pending，无重提或调度修改。
