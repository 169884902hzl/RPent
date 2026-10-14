"""Recount delivered immutable stage evidence under the locked v3 rule."""
import argparse
from collections import Counter, defaultdict
import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

from coordination.load_indexed_grasp_evidence_20261010 import load_indexed_row, load_indexed_reference

parser = argparse.ArgumentParser()
parser.add_argument('--index', type=Path, required=True)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--delivery', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
manifest = json.loads((args.index/'index_manifest.json').read_text())
data = (args.index/'input_rows.jsonl').read_bytes()
sha = hashlib.sha256(data).hexdigest()
delivered = json.loads(args.delivery.read_text())
if sha != manifest['index_sha256'] or sha != delivered['index_sha256']:
    raise ValueError('index identity differs from delivered input index')
coverage_complete = bool(manifest.get('exhaustive_claim') and not manifest.get('coverage_review_pending'))
if not coverage_complete:
    raise ValueError('complete historical coverage must be delivered before recount')
truth_path = args.source/'robots/libero/v5_grasp_truth.py'
truth_sha = hashlib.sha256(truth_path.read_bytes()).hexdigest()
if truth_sha != 'd8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f':
    raise ValueError('use the delivered registered v3r9 truth source')
sys.path.insert(0, str(args.source))
from robots.libero.v5_grasp_truth import grasp_trace_summary_v3, sustained_grasp_v3


def select_stage(row, key):
    if key == 'row':
        return row
    if key == 'first_attempt':
        return row.get(key) or {}
    name, position = key.split('/')
    return row[name][int(position)]


cache, records = {}, []
for line in data.splitlines():
    index = json.loads(line)
    row = load_indexed_row(index, cache)
    stage = select_stage(row, index['stage_key'])
    phase = stage.get('private_grasp_phase') or {}
    hold = stage.get('private_setup_hold') or row.get('sustained_hold') or {}
    samples = phase.get('samples') or hold.get('samples') or stage.get('contact_samples') or []
    direct_window = index.get('evidence_schema') in ('direct_saved_hold_window', 'direct_saved_trace_window')
    if direct_window:
        samples = stage.get('samples') or []
    if not isinstance(samples, list) or any(not isinstance(s, dict) for s in samples):
        samples = []
    reference = phase.get('reference') or hold.get('reference') or stage.get('initial_private_reference') or row.get('support_reference')
    if direct_window:
        reference = stage.get('reference') or load_indexed_reference(index, cache)
    reasons, score, end_score = [], None, None
    if not isinstance(reference, dict):
        reference = None
    if not reference:
        reasons.append('original_reference_not_saved')
    if not samples:
        reasons.append('physical_sample_sequence_not_saved')
    if samples:
        try:
            times = [float(s['sim_time']) for s in samples]
            if not all(math.isfinite(t) for t in times):
                raise ValueError('nonfinite sample time')
        except (KeyError, TypeError, ValueError, OverflowError):
            reasons.append('physical_sample_times_missing_or_invalid')
            samples = []
    if samples and reference:
        try:
            if phase or index.get('evidence_schema') == 'direct_saved_trace_window':
                result = grasp_trace_summary_v3(reference, samples)
                score, end_score = result['true_sustained_grasp_during_skill'], result['true_sustained_grasp_at_end']
                if score is None:
                    reasons.append('no_proven_sustained_window_with_required_saved_evidence')
            else:
                result = sustained_grasp_v3(samples, reference)
                score = end_score = result['success']
            if score is None:
                check = sustained_grasp_v3(samples[-11:], reference)
                reasons.extend(c['unknown_reason'] for c in check['checks'] if c.get('unknown_reason'))
                if not check['continuous_20hz']:
                    reasons.append('registered_11frame_0p5second_continuous_window_not_saved')
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
            score = end_score = None
            reasons.append('saved_v3_evidence_invalid:' + type(exc).__name__)
    receipt = stage.get('receipt') or (row.get('first_receipt') if index['stage_key'] == 'row' else {}) or {}
    public = receipt.get('grasp_verified')
    records.append({**index, 'registered_v3': score, 'registered_v3_end': end_score,
                    'unknown_reasons': sorted(set(reasons)) if score is None else [],
                    'old_exclusive_v2': (stage.get('private_hold_truth_v2') or phase.get('all_supports_v2') or {}).get('success',
                        (phase.get('all_supports_v2') or {}).get('true_sustained_grasp_during_skill')),
                    'historical_v3_label_not_substituted': (stage.get('private_hold_truth_v3') or {}).get('success'),
                    'public_verifier': public if type(public) is bool else None,
                    'new_replay': False, 'old_values_not_overwritten': True})


def summarize(rows):
    known = [r for r in rows if type(r['registered_v3']) is bool]
    paired = [r for r in known if type(r['public_verifier']) is bool]
    confusion = {key: sum(r['registered_v3'] is t and r['public_verifier'] is p for r in paired)
                 for key, t, p in [('tp', True, True), ('tn', False, False), ('fp', False, True), ('fn', True, False)]}
    return {'evidence_stage_count': len(rows),
            'old_labels': dict(Counter(str(r['old_label']) for r in rows)),
            'registered_v3': dict(Counter(str(r['registered_v3']) for r in rows)),
            'confusion': confusion, 'known_truth_evidence_stages': len(known),
            'public_null_on_known_truth': len(known)-len(paired),
            'unknown_reasons': dict(Counter(x for r in rows for x in r['unknown_reasons']))}


groups = defaultdict(list)
for row in records:
    episode = row.get('episode') or {}
    stratum = row.get('stratum') or 'original_or_unspecified_saved_metadata'
    groups[(str(row['category']), str(row['method']), stratum)].append(row)
deduplicated = [r for r in records if not r.get('exact_evidence_alias_of')
               and not r.get('container_alias_of') and not r.get('saved_physical_evidence_alias_of')]
report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'registration_id': 'grasp_truth_v3_1153_20261009', 'input_index_sha256': sha,
    'truth_source_sha256': truth_sha, 'source': str(truth_path),
    'summary_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'coverage_exhaustive': coverage_complete, 'coverage_review_pending': not coverage_complete,
    'input_index_delivery': str(args.delivery), 'new_replay': False, 'control_visibility': False,
    'denominator_unit': 'evidence_stage_not_independent_trial; duplicate ledger aliases retained',
    'total': summarize(records),
    'deduplicated_evidence_secondary': summarize(deduplicated),
    'independent_physical_trial_count_not_inferred': True,
    'exact_alias_records': sum(bool(r.get('exact_evidence_alias_of')) for r in records),
    'container_alias_records': sum(bool(r.get('container_alias_of')) for r in records),
    'groups': [
        {'category': c, 'method': m, 'stratum': s, **summarize(rows)}
        for (c, m, s), rows in sorted(groups.items())]}
args.output.mkdir(exist_ok=False, parents=True)
(args.output/'rows.jsonl').write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in records))
(args.output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: v for k, v in report.items() if k != 'groups'}, indent=2))
