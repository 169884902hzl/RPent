# Codex3 pan526 公共测量锅体/柄诊断交接

Owned CPU脚本 `scripts/analyze_v5_pan526_public_body.py` 与显式报告已实际运行，未提交Slurm、未改runtime/旧快照/原结果。父代理负责push和共享COORDINATION。

报告 `results/harness_v5/grasp526_pan_measured_body_CPU_20261005/report1/report.json`，SHA `154d35a682df84e167bb77580444eb552bfc191f5da837a6e8203152c616902b`；manifest SHA `1397791428bfd068ad6e4ac218603f4d35156976dcd0540b7a51aafd28f44746`。5条公开点云与camera metadata均逐SHA通过。原版3662单局的初始主视角/双视角和抬起帧拟合半径约10.0–10.3cm、圆弧291–346°；锅体/柄可分。腕部半圆遮挡、终态同一云重复且拟合漂移，不能将现有false重判true。

建议后续原版正负物理分支取真正两个post-release新帧的锅体/柄及target raw mask/depth/cloud/相机transform，并保存全部公共子条件与独立私有谓词。用实测圆锅体支撑脚印需保留原90%覆盖、release/height/stability，缺测unknown。现在未创建生产helper、未授资格，细节见REPORT.md。

远端镜像已完成：独立源 `source_pan526_public_body_CPU_20261005/scripts/analyze_v5_pan526_public_body.py`，报告路径与本地relative路径一致、SHA不变，10个输入SHA一致。远端专用 `preparation/remote_replay_manifest.json` SHA `daab94b4cb2bf1f4c193a764f048c8307dd3e5397ab2f3715b205ecb84a87bb2` 只映射input local_path并记录原manifest SHA。旧CPU快照最终保持不变。

3670 report3 已CPU运行：106/400闭合、choices SHA106一致，SHA `f4a013a4cf119f5d356351b87c7b668340099ad1475645f4c4586bcd5ac5530e`。pan centre68局：期间抓65、最终仍夹0、最终目标61；handle38局：期间抓27、最终仍夹2、最终目标24。place TP0/TN21/FP0/FN85/unknown0；moka没有闭合。所有stop=chunk_budget，已达成的最终物理目标不因此判失败。8份prefix已逐SHA取回，report1/2保留；非独立首次抓取确认、非资格。
