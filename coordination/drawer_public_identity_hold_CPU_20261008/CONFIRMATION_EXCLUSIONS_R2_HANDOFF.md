# official confirmation registry r2：对齐真实消费者 schema，继续拒绝准入

修正r1的producer字段缺口：真实 `check_registered_training_original_state()` 严格读取 `schema`，而r1只有 `version`。r2同时明确schema/version=`libero_official_confirmation_exclusions/1`；不为旧产物增加fallback，不覆盖r1。665个永久确认状态身份、831个注册请求和六份source不变；两个旧skill535登记冲突的650个状态仍为独立临时training hold，permanent=false。

远端不可变目录：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/confirmation_registry_r2/`。

- `official_confirmation_exclusions.json`：SHA `49273ed0e83a0183393f8771c77131ecf01c4478227878950c637443db035cdf`。
- `ambiguous_training_hold_identities.json`：SHA `31dc149e325ab3917990ea930181decdb6020dd4879380770813ed5af620910e`；同样补明确schema，禁止future collection，待Codex1仅按协议元数据澄清。
- 495/497补证固定引用r1旁挂的 `grasp495_497_registration_provenance.json` SHA `8e44862ff451c7d0fb67dcdca64c034c1840f4f33d5095d0f7741a26d30a7968`：497命令仅已登记first4 manifest；后续535两类正式plan与同pool各100tuple完全对应，无新增身份。没有打开成绩或ledger，没有整池扩大排除。

`coverage_complete=false`保留：六份注册之外的全历史覆盖尚未建立，skill535确认/选择登记冲突未澄清。r2不能让一个未命中665身份的状态自动准入训练。真实消费者CPU执行已验证：已确认身份抛ValueError；已观察的distinct原版t25/init2返回training_allowed=false/registration_coverage_complete=false。见本目录 `confirmation_registry_r2/actual_consumer_smoke.json`；消费者代码SHA `27070e63b2f88e068fc0779b1382be7dcae8356e9563fa30554fe183d8d90b6c`。该检查未投GPU、未改消费实现。

消费者接线由root负责 `v5_confirmation_exclusions.py`、`v5_collection.py`、`v5_batch_eval.py`和相应测试。本子任务只提供producer/不可变数据和文档，不改这些文件。

layout另用schema `libero_confirmation_exclusions/1`：确认布局永久排除；后续训练layout_seed=680100–689999，落定moka XY距每条已确认布局至少0.050m，几何仅用于私有generation/audit metadata。此规则在r2记为独立合同说明，未把layout union100的base官方tuple误列为确认。本项目尚无正式layout采集generator接线，不能宣称已完成。

运行命令：

```bash
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
 /public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/prepare_known_confirmation_exclusions.py \
 --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_public_trace_CPU_20261008/preparation_r2/confirmation_registry_r2
```
