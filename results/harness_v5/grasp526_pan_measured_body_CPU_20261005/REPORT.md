# 原版平底锅公开点云：锅体与把手的支撑脚印证据

已在 CPU 上运行拟合；只按显式 manifest 读取一局原版任务的公开 SAM RGB-D 点云。没有读仿真物体尺寸、PRO 文件或改变 90% 覆盖阈值，也没有替换运行时判定。

源回合为 3662 `pan_handle_full_libero_10_t2_s0_r0_centre_full_subtask160_sync520`。manifest 的 5 条点云和相机 metadata 均逐 SHA 核对通过。平面 RANSAC 使用 2mm 实测残差，2/3/4/6mm 栅格轮廓上的圆拟合是离线几何假设；形态闭运算和孔洞填充不是额外观测。

| 测量 | 拟合半径跨栅格 | 实测圆弧支持 | 判断 |
|---|---:|---:|---|
| 初始主视角 | 10.131–10.223cm | 343–346° | 锅体圆轮廓稳定，柄延伸可分离 |
| 初始双视角联合 | 10.165–10.265cm | 338–343° | 与主视角一致 |
| 抬起后主视角 | 10.007–10.115cm | 291–336° | 与初始锅体尺寸一致；倾斜由拟合平面处理 |
| 初始腕部 | 8.996–9.938cm | 167–228° | 遮挡半圆，不能独立授尺寸 |
| 终态主视角 | 8.975–10.071cm | 243–351° | 跨栅格漂移约1.1cm；sample6/7同一云重复 |

初始主视角、抬起帧中的圆锅体和细柄可见，支持进一步测试“实测锅体支撑脚印”，而不把柄计入矩形支撑面积。但现有终态不是物理成功的双帧支撑样本，重复点云不能算两份稳定证据；不能据此声称验证器精确率或将现有 false 改 true。

下一份原版正/负物理分支 smoke 应逐字段保存：

- 放手后间隔至少0.3s的两个实际新帧；每帧时间、机器人开度/撤离测量、主视角和腕部相机内外参。
- 每个视角的 current 锅体/柄 SAM mask、原始深度与测量世界点云；目标支撑面 mask 与原始点云；缺测明确为 unknown。
- 实测拟合半径/中心/法向、点云与轮廓残差、可见圆弧、跨视角和跨帧一致性、锅体/柄分离证据；不把不可见轮廓当测量。
- 公共判定的每个子条件，包括原90%支撑覆盖、高度、稳定、release、retreat；另存独立私有目标谓词用于诊断，私有标签不控制执行或公共 receipt。

生产验证器若采用实测锅体支撑脚印，必须保留原90%覆盖与release/height/stability条件，并在原版正负分支上独立测精确率/召回率。遮挡或不一致时保持 unknown。本报告不授资格、不冻结、不新增训练行。

实际命令：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 scripts/analyze_v5_pan526_public_body.py --manifest results/harness_v5/grasp526_pan_measured_body_CPU_20261005/preparation/manifest.json --output results/harness_v5/grasp526_pan_measured_body_CPU_20261005/report1
```

manifest SHA256 `1397791428bfd068ad6e4ac218603f4d35156976dcd0540b7a51aafd28f44746`；报告 SHA256 `154d35a682df84e167bb77580444eb552bfc191f5da837a6e8203152c616902b`；脚本 SHA256 `91e9685063ed7a3809c79ca650b9b67ae3cc5ec3e8e4742da7309492d08b6abd`。原始 NPZ 不入 git，manifest 保留远端显式路径/SHA。拟合图位于 `report1/measured_body_circle_hypotheses.png`。
