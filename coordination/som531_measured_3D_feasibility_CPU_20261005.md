# Codex3 child：完整测量3D几何的有限 SoM 可行性，未通过门槛

按root续接，仅使用SoM529固定的50张（主/腕各25）及3662已有显式同帧公开点云。没有重采样、GPU、私有物体坐标、2D mask贴框、剪柄或改共享renderer。所有50例已实际完成exit0，所有有限测量点100%保留，原始完整SAM参考未修改。

方法固定于结果之前：全部公开点拟合PCA 3D OBB，局部min/max每侧仅加已有2mm测量roundoff余量；对46张pan复用已有`analyze_v5_pan526_public_body.py`的`measured_plane`/`circle_fit`固定3mm网格，把观测分成圆锅体假设和**全部剩余几何（含柄）**两组。圈外点不删。4张Moka保持单OBB。先固定3D几何，再加载原2D mask评分；同一原实体中性ID保留。

| 完整几何投影 | mask IoU≥0.5 | 比例 | 原mask覆盖最小值 |
| --- | ---: | ---: | ---: |
| 单个3D OBB投影的轴矩形 | 3/50 | 6% | 100% |
| 单个3D OBB投影体轮廓 | 11/50 | 22% | 100% |
| 锅体/柄两个完整OBB的轴框并集 | 6/50 | 12% | 100% |
| 两个完整OBB投影体轮廓并集 | 27/50 | 54% | 100% |

四法都没有达到既定90%门槛。最好的一法主13/25、腕14/25；原SoM529的39/50=78%报告原样保留。这些是有限CPU几何可行性数字，**不是runtime/model退步成绩或新renderer准入结论**。

完整3D箱体投影仍包含大量当前无可见支持的空间。圆体/柄拆分可减小长柄连带膨胀，但完整每组箱体仍会填入遮挡区、体积角落。全部原点保留也保留了测量深度尾部：例如主step54的完整OBB三轴长约40.7×22.6×15.6cm，腕step29约33.6×18.8×28.1cm，投影面积比当前仅有可见深度支持的框明显大。这里不把深度尾点擅自认定为错误、也不删它们来取得通过。仅凭现有测量边界无法证明隐藏或被遮挡区域的实体轮廓。

SoM530的单轴矩形数学上限仍适用：必须完整覆盖原始mask时，最小轴矩形就是其bbox，IoU上限=`mask_area/bbox_area`；11张低分上限仅22.3–46.9%。本次另外实测有向3D体投影和完整多部件，依旧未达到数字门槛，因此**当前这几种测量箱体实现都不能直接替换共有训练/运行renderer**。没有放宽标准、改mask或新增部件状态字段。

若之后继续，最可能需要区分“完整体积边界”与“当前可见测量支持”，并在同一公开3D几何上保留锅体和柄的非矩形投影；需要新的明确实现与验证，不能直接按当前SAM 2D轮廓贴框。此有限任务到此交付，未追加新的方法/GPU或修改公共代码。parent继续技能链与共享实现协同。

实际CPU命令：

```bash
cd /public/home/sunyihan/rpent_libero_eval
.venv/bin/python scripts/audit_v6_som531_measured_obb.py --report /public/home/sunyihan/rpent_libero_eval/results/harness_v5/som529_current_renderer_CPU_20261005/report1/report.json --report-sha256 d32dbed72cf2091306381d50f4c7705a10482b3762c4d5972e9d7437127b185f --geometry-helper /public/home/sunyihan/rpent_libero_eval/results/harness_v5/som531_measured_3D_feasibility_CPU_20261005/preparation/pan526_public_geometry_snapshot.py --geometry-helper-sha256 91e9685063ed7a3809c79ca650b9b67ae3cc5ec3e8e4742da7309492d08b6abd --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/som531_measured_3D_feasibility_CPU_20261005/report1
```

helper只是现有公开拟合脚本的逐SHA输入快照，没有修改兄弟owner的代码。产物：

- `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/som531_measured_3D_feasibility_CPU_20261005/report1/report.json`，SHA `6a6678da92e451bd706fb5163d7cf2f105073982e4b9925fa3e41c97e7652b58`。
- 同目录`cases.jsonl`包含每例点云SHA、完整OBB、原ID、组件拟合与四种评分；其SHA由report显式登记。本机已复制这两份实际产物。

没有相机独立capture sim_time的限制、50相关原版帧的类别/初态覆盖限制都保留。当前source runtime与训练数据均未改；3678/3680实际产物审计继续等队列/产物变化，不反复报相同Pending。
