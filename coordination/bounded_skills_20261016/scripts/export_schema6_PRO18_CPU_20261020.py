"""Rebuild the exact saved PRO evaluation packets without simulation or GPU."""
import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    from robots.libero.bounded_offline_labels import (
        annotate_prefix, load_annotation_state, rebuild_schema6_captured_request, request_digest)

    args.output.mkdir(exist_ok=False)
    opener = gzip.open if args.input.suffix == '.gz' else open
    with opener(args.input, 'rt') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    records = []
    with (args.output / 'public_packets.jsonl').open('x') as public_stream, \
            (args.output / 'private_empty_prefix_labels.jsonl').open('x') as private_stream:
        for row in rows:
            started = time.perf_counter()
            record = {'record_id': row['record_id'], 'physics_steps': 0,
                      'gpu_used': False, 'training_authorized': False, 'evaluation_only': True}
            try:
                provided = row['public_request']
                request = provided
                group = Path(row['source_group'])
                path = group / 'private_annotation.pkl'
                sha = hashlib.sha256(path.read_bytes()).hexdigest()
                state = load_annotation_state(path, sha)
                matched_choices = None
                if state['request_sha256'] != request_digest(provided):
                    # Preserve the supplied packet's digest. A source request
                    # is usable only if the captured annotation actually pins it.
                    for choices in sorted(group.glob('*/choices.jsonl')):
                        with choices.open() as stream:
                            for index, line in enumerate(stream):
                                candidate_request = json.loads(line).get('request')
                                if candidate_request and request_digest(candidate_request) == state['request_sha256']:
                                    request = candidate_request
                                    matched_choices = {'path': str(choices), 'line_zero_based': index}
                                    break
                        if matched_choices:
                            break
                    if matched_choices is None:
                        # The consumer normalized old headers. Restore a
                        # header only when the captured digest proves the
                        # entire original request, including all candidates.
                        for version in (3, 4, 5, 6):
                            candidate_request = dict(provided, schema_version=f'bounded-skills/{version}')
                            if request_digest(candidate_request) == state['request_sha256']:
                                request = candidate_request
                                matched_choices = {'recovered_header': candidate_request['schema_version'],
                                    'proof': 'complete_request_digest_matches_captured_annotation'}
                                break
                    if matched_choices is None:
                        raise ValueError('no source request matches annotation digest; supplied packet was not changed')
                rebuilt, current, flags = rebuild_schema6_captured_request(state, request)
                label = annotate_prefix(rebuilt, current, [])
                packet = dict(record, public_request=current,
                    provided_public_request_sha256=request_digest(provided),
                    old_public_request_sha256=request_digest(request),
                    provided_request_matches_source=provided == request,
                    differing_top_level_fields=[key for key in sorted(set(provided) | set(request))
                        if provided.get(key) != request.get(key)],
                    old_to_new_candidate_ids=flags['old_to_new_candidate_ids'],
                    default_old_candidate_id_by_new_id=flags['default_old_candidate_id_by_new_id'],
                    prefix_compatible=flags['prefix_compatible'],
                    unknown_reasons=flags['unknown_reasons'], migration_flags=flags,
                    source_link={'dataset': str(args.input), 'source_group': str(group),
                        'annotation': {'path': str(path), 'sha256': sha},
                        'matched_choices': matched_choices})
                public_stream.write(json.dumps(packet, allow_nan=False) + '\n')
                public_stream.flush()
                private_stream.write(json.dumps({'record_id': row['record_id'], 'label': label}, allow_nan=False) + '\n')
                private_stream.flush()
                record.update(status='exported', provided_request_matches_source=provided == request,
                    differing_top_level_fields=packet['differing_top_level_fields'],
                    old_candidates=len(request['candidates']), new_candidates=len(current['candidates']),
                    old_moves=sum(c['skill'] == 'move_to' for c in request['candidates']),
                    new_moves=sum(c['skill'] == 'move_to' for c in current['candidates']),
                    label_status=label['status'], acceptable_count=len(label['rule_acceptable']))
            except Exception as exc:
                record.update(status='unresolved', error=f'{type(exc).__name__}: {exc}')
            record['cpu_wall_s'] = time.perf_counter() - started
            records.append(record)
            print(json.dumps(record), flush=True)
    summary = {'input': str(args.input), 'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
        'source': str(args.source), 'evaluation_only': True, 'training_authorized': False,
        'registered': len(rows), 'exported': sum(r['status'] == 'exported' for r in records), 'records': records}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if summary['exported'] == summary['registered'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
