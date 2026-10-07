# 固定 train14/val6 公共端点模型：关闭失败，未准入

CPU 拟合完成。固定注册脚本 commit `47e32c5`，SHA256 `79044529b5ca96bf9f98b18579cbb8a9c4c390f133d0c0b6cbcc4b07eecf3683`。训练函数直接复用 `scripts.train_v5_temporal_control_trainonly_20261008.fit`；公共编码和 runtime `infer` 与 v9 快照相同。

固定参数：open/close 各一个 MLP32（满足所请求模式，避免把相反端点混成同一判断）；AdamW lr=0.001、weight_decay=0.03、seed577、完整300 epoch、`baseline_relative_v1` 特征、仅 train mean/std、std<0.02→1。无早停、无模型选优、无阈值选择。拟合阶段只打开单独 `train.npz`；两模型 SHA 写入报告后才执行一次 val 推断。0.5 和0.95 两阈值在拟合前已固定，两份汇总共用同一次概率；都未授 runtime stop。

14 train /6 validation 原始状态 SHA，配对的4319/4327同一状态始终同组。训练232行，176可用、56 unknown；验证74行，50可用、24 unknown。准备阶段拆分已编码的组合文件（所以明确记录 `preparation_opened_existing_encoded_val=true`），梯度、归一化和参数选择未读取 val。两者没有状态重叠，但6状态的相关帧不是独立确认批。

| 模式/固定阈值 | val行数 | TP | FP | FN | TN | 精确率 | 召回率 | AUROC | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| open /0.5 |21|12|1|0|8|92.31%|100%|1.000|0.0467|
| open /0.95 |21|12|0|0|9|100%|100%|1.000|0.0467|
| close /0.5 |29|11|10|2|6|52.38%|84.62%|0.846|0.4073|
| close /0.95 |29|11|10|2|6|52.38%|84.62%|0.846|0.4073|

open在固定0.95下21/21，描述性帧Wilson95%为84.54–100%，不能授95%物理资格。close在两个固定阈值下同样失败，10个FP全部是 LIBERO-90 t22/s30 同一原始状态；2个FN分别在t22/s30和另一个状态。训练两个模式均100%拟合，close的val预测过度自信（21个p≥0.9的平均p=0.9957，真实率52.38%），说明当前整个柜体粗网格不足以可靠泛化端点/面身份。全部概率和错误保留；不据val结果改超参/阈值重训这批。

公共runtime `infer` 与CPU Torch概率最大误差：open `7.22e−8`、close `1.50e−7`。模型仅含 mean/scale/网络权重/encoder身份/所支持模式，无私有关节值或目标；每次infer默认`stop_admitted=false`。端点真值只在隔离 labels 和离线评价。没有模型进入harness，v9 close继续unmeasured。

远端统一目录 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_public_fixed_train14_val6_CPU_20261008/`：

- `preparation/fit_manifest.json` SHA256 `aba70e2b73b510b571fbe42080ea6314386a6b0302349c0b02be3db3870502df`；其中逐文件/source SHA与固定recipe。
- `final300/training_report.json` SHA256 `5a5dd22997c42db51c1f897652bec1e761dbb95fbdccdae333091e7bd435e807`。
- `final300/drawer_open_mlp32.npz` SHA256 `c4d8abb2c5ac2225364608035dd4f2298f42b033f08121f15f7ed454270e7708`。
- `final300/drawer_close_mlp32.npz` SHA256 `2820a89c82e3101bac36ba21571a4d1064ec97dd668a5b10b8f95f44810036c0`。
- `final300/train_predictions.jsonl`、`open_curve.json`、`close_curve.json`；300条train loss，val loss均null。
- `validation_once/validation_report.json` SHA256 `4473a13dfbcecedcc71fff79e0612ee3fd54f4e1f90071fe465ededea0be6e5c`；`validation_predictions.jsonl`保留74条概率、标签及unknown，报告含每原始状态class confusion及帧Wilson。
- `identity_tracking_protocol.json` SHA256 `6adb7ee81eff75c1c0e8f554e9f22774ebbff2c5f107d832d8ce56e93ce2178f`；下一步方案来自公开面对应，不用private q控制。

实际CPU命令（都exit0，无GPU）：

```bash
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer_endpoint_hold_v9_20261008 \
 /public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_public_fixed_train14_val6_CPU_20261008/fit_fixed_public_verifier.py fit \
 --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_public_fixed_train14_val6_CPU_20261008/preparation/fit_manifest.json \
 --manifest-sha aba70e2b73b510b571fbe42080ea6314386a6b0302349c0b02be3db3870502df \
 --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_public_fixed_train14_val6_CPU_20261008/final300

PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer_endpoint_hold_v9_20261008 \
 /public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_public_fixed_train14_val6_CPU_20261008/fit_fixed_public_verifier.py evaluate \
 --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_public_fixed_train14_val6_CPU_20261008/preparation/fit_manifest.json \
 --manifest-sha aba70e2b73b510b571fbe42080ea6314386a6b0302349c0b02be3db3870502df \
 --training-report /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_public_fixed_train14_val6_CPU_20261008/final300/training_report.json \
 --training-report-sha 5a5dd22997c42db51c1f897652bec1e761dbb95fbdccdae333091e7bd435e807 \
 --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer_public_fixed_train14_val6_CPU_20261008/validation_once
```

下一步已准备而未执行：在已访问原版t23/s20、t22/s30、t0/s20记录每块公开双视角点云/图像，保存初始选中面外观与3D点；按实测抽屉方向的刚性平移对应跟踪，检查匹配覆盖、固定柜体静止、时序链及双视角一致。只有ID相同、当前检测框换了面或单帧几何flush不能准入。白色板面缺纹理时保持unmeasured，探索把手/边缘对应或选中部件专用公开时序encoder；这批val已用于后续开发定位，不再称新确认。所有新threshold仅训练状态定，再用新的独立状态确认，不降低原门槛。
