# place560 / job4262 完成回执

40/40 已保留，8 片全部 COMPLETED 0:0；这是原版任务选择批，不授冻结或训练资格。

| 方法 | strict setup 真 | 已执行 | 真准备且动作前未完成 | 首次新增完成 | Wilson 95% | TP / FP / FN / TN / null |
|---|---:|---:|---:|---:|---|---|
| place_in/current160 | 3/10 | 6 | 3 | 1 | 6.1–79.2% | 3 / 0 / 1 / 2 / 0 |
| place_on/current160 | 7/10 | 7 | 6 | 4 | 30.0–90.3% | 2 / 0 / 3 / 2 / 0 |
| place_in/vla_subtask160 | 5/10 | 6 | 5 | 5 | 56.6–100.0% | 1 / 0 / 1 / 0 / 4 |
| place_on/vla_subtask160 | 6/10 | 8 | 6 | 4 | 30.0–90.3% | 3 / 0 / 1 / 3 / 1 |

总体真准备+动作前未完成+已执行为 14/20（70.0%，Wilson 48.1–85.5%）。27 次真实执行中新增完成17、已有完成保留2、端点未完成8；未执行13：准备抓取无公共验证7、第一动作公共绑定缺失3、所选实例非唯一3。strict setup v2 真21/40、假19/40，legacy真25，legacy真但v2假4。

验证器 TP9、FP0、FN6、TN7、null5。测得精确率9/9（Wilson 70.1–100%）、可测召回9/15（60.0%，Wilson35.7–80.2%）；真值一致且将null算未证实为16/27（59.3%）。这些分母不足以判行业门槛。

FN: footprint5、真实放置后空手闭夹1。缺测5：VLA in4、on1；两帧全部 invisible，且分别复用了source_step5或4。不能将遮挡缺测改为失败或成功。

基础设施失败0；setup VLA14480/14480、first VLA11565/11565 controls，短块0；first non-VLA1204 controls。

SOURCE560只在VLA arm开启v7，current字典/40案例/setup/预算不变。但未记录remeasure触发bool和之前缺测，故不逐行推断v7因果；π0.5轨迹也未锁定RNG。原4219与4262判定全部保留。

manifest SHA `327dd7044215829e46168d81f8bbb8743505a22ceab07493f76d4c1955217679`
report SHA `4f8d112f2f193ac9447136a5edcb65de5b832431ce651e39e71e5fef9d8f6536`
audit SHA `9e1a06c98a7794d6a528cf14d288829fb93d4937ea26686675887dcdc301684f`

源码：`/public/home/sunyihan/rpent_libero_eval/source_v5_place560_20261006`；commit `37f4a979096ed5da630166953127c0e880973862`。逐行证据和显式ledger路径/SHA见audit，未扫artifact目录。
