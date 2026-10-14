"""Deliver the closed fixed history inventory before computing new labels."""
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
INDEX = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r15'
SOURCE = ROOT / 'source_v5_grasp_truth_v3r9_20261010_r2'
OUT = ROOT / 'coordination/grasp_history_index_delivery_r15_20261010'

def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

m = json.loads((INDEX / 'index_manifest.json').read_text())
c = json.loads((INDEX / 'coverage_review.json').read_text())
index_pin = pin(INDEX / 'input_rows.jsonl')
if (index_pin['sha256'] != m['index_sha256'] or not m['exhaustive_claim']
        or m['coverage_review_pending'] or m['errors']
        or c['missing_JSON_object_stages'] or c['missing_JSONL_captures']
        or c['named_row_references_missing']):
    raise ValueError('closed immutable index required')
truth, worker = pin(SOURCE / 'robots/libero/v5_grasp_truth.py'), pin(SOURCE / 'robots/libero/v5_grasp_support_worker.py')
if truth['sha256'] != 'd8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f':
    raise ValueError('registered truth changed')
if worker['sha256'] != '9a8bc057edb677625199dc1e790e3f4801cf1db01b5c9f7069f1dfb3bb256921':
    raise ValueError('registered support diagnostic changed')
OUT.mkdir(exist_ok=False)
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-7))).isoformat()
delivery = {'delivered_pdt': now, 'recipient': ['Codex1', 'Codex2'],
    'index_sha256': index_pin['sha256'], 'input_rows': index_pin,
    'index_manifest': pin(INDEX / 'index_manifest.json'),
    'coverage_review': pin(INDEX / 'coverage_review.json'),
    'input_files': pin(INDEX / 'input_files.json'),
    'scope_exclusions': pin(INDEX / 'scope_excluded_rows.jsonl'),
    'truth_source': truth, 'support_worker_source': worker,
    'base_git_commit': '32cd3d7b6ccdab9c224301ad7517d17b1f68b9ab',
    'registered_rule': m['registration_id'], 'fixed_scope': m['exhaustive_scope'],
    'files': m['files'], 'evidence_stages': m['stage_records'],
    'suite_unknown_stages': m['suite_unknown_stages'],
    'explicit_PRO_stages_excluded': m['explicit_non_original_suite_exclusions'],
    'metadata_missing': {key: m[key] for key in ('category_missing', 'method_missing', 'state_identity_missing', 'source_manifest_missing')},
    'complete_fixed_inventory': True, 'new_truth_labels_computed': False,
    'old_records_not_overwritten': True, 'denominator_unit': m['denominator_unit'],
    'independent_physical_trial_count_not_inferred': True, 'training_allowed': False}
p = OUT / 'delivery_manifest.json'
p.write_text(json.dumps(delivery, indent=2) + '\n')
notice = f'''\n\n## Codex3：历史抓取完整索引交付，统一重算准备启动（{now}）

交 Codex1、Codex2。完整固定历史范围已闭合，尚未生成新标签。交付清单 {p}，SHA {pin(p)['sha256']}。

- 索引 {INDEX}/input_rows.jsonl；SHA {index_pin['sha256']}。37,526捕获文件、111,787证据阶段；分母不是独立物理试次。827固定根中412候选原版根、415明确范围外根；723,152 JSON内容检查、25,433 JSON对象/阶段映射、13,729剩余JSONL分类与捕获SHA核对全部完成，缺引用0、错误0。
- 明确PRO套件阶段531单独排除并保留来源；suite未存8,058阶段保留unknown，不推断原版。缺类别32,089、方法51,760、状态身份68,869、源manifest38,587，全部明列。具名400确认/1000选择映射缺引用0。
- 固定索引身份与完整coverage_review先交付，再对同一SHA索引统一重算；不恢复撤回的partial recount。缺原始TCP/COM/支撑面或外部支撑隔离证据保留unknown，不补真值。新旧标签并列，旧记录不覆盖；别名保留并另列次要去重统计，不把证据阶段数改称物理试次数。
- 登记truth SHA {truth['sha256']}；worker SHA {worker['sha256']}。判据未修改。
'''
(OUT / 'delivery_notice.md').write_text(notice)
with (ROOT.parent / 'rd_instruction_20260923/COORDINATION.md').open('a') as stream:
    stream.write(notice)
print(json.dumps(delivery, indent=2))
