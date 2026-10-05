# Codex3 pan526 公共测量锅体/柄诊断交接

Owned CPU脚本 `scripts/analyze_v5_pan526_public_body.py` 与显式报告已实际运行，未提交Slurm、未改runtime/旧快照/原结果。父代理负责push和共享COORDINATION。

报告 `results/harness_v5/grasp526_pan_measured_body_CPU_20261005/report1/report.json`，SHA `154d35a682df84e167bb77580444eb552bfc191f5da837a6e8203152c616902b`；manifest SHA `1397791428bfd068ad6e4ac218603f4d35156976dcd0540b7a51aafd28f44746`。5条公开点云与camera metadata均逐SHA通过。原版3662单局的初始主视角/双视角和抬起帧拟合半径约10.0–10.3cm、圆弧291–346°；锅体/柄可分。腕部半圆遮挡、终态同一云重复且拟合漂移，不能将现有false重判true。

建议后续原版正负物理分支取真正两个post-release新帧的锅体/柄及target raw mask/depth/cloud/相机transform，并保存全部公共子条件与独立私有谓词。用实测圆锅体支撑脚印需保留原90%覆盖、release/height/stability，缺测unknown。现在未创建生产helper、未授资格，细节见REPORT.md。
