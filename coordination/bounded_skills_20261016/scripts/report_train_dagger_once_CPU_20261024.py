"""Describe the strictly closed original-train candidate collection."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def read_rows(path):
    with path.open() as stream:
        for line in stream:
            yield json.loads(line)


def checked(reference):
    path = Path(reference['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == reference['sha256'], path
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--closure', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.closure / 'manifest.json').read_bytes())
    assert not manifest['incomplete']
    assert manifest['registered_queries'] == manifest['closed_queries'] == 1963
    assert manifest['closed_packets'] == 62 and manifest['pending_queries'] == 0
    assert manifest['source_split'] == 'train' and not manifest['training_executed']
    assert not any(manifest[key] for key in ('PRO', 'D2', 'confirmation'))

    counts = Counter()
    sources = Counter()
    outcomes = list(read_rows(checked(manifest['query_outcomes'])))
    for outcome in outcomes:
        counts[(outcome['category'], 'closed')] += 1
        if outcome['status'] == 'unknown':
            counts[(outcome['category'], 'context_unknown')] += 1
    for row in read_rows(checked(manifest['data'])):
        category = row['case']['category']
        sources[row['binding']['source_revision']] += 1
        counts[(category, 'positions')] += 1
        counts[(category, 'truth_unknown')] += len(row['unknown_trials'])
        for branch in row['branches']:
            for trial in branch['trials']:
                assert isinstance(trial['success'], bool)
                assert trial['state_binding_verified']
                counts[(category, 'known')] += 1
                counts[(category, branch['method_family'])] += 1
                counts[(category, 'success' if trial['success'] else 'failure')] += 1
                counts[(category, branch['method_family'] + ('_success' if trial['success'] else '_failure'))] += 1
    checked(manifest['replacements'])
    assert sum(value for (cat, kind), value in counts.items() if kind == 'known') == manifest['bound_trials']
    assert sum(value for (cat, kind), value in counts.items() if kind == 'truth_unknown') == manifest['unknown_trials']

    categories = sorted({category for category, _ in counts})
    keys = ('closed', 'positions', 'known', 'success', 'failure', 'context_unknown', 'truth_unknown',
            'self', 'self_success', 'vla', 'vla_success')
    details = {
        'categories': {category: {key: counts[(category, key)] for key in keys} for category in categories},
        'bound_positions_by_execution_source': dict(sources),
        'closure_manifest_sha256': hashlib.sha256((args.closure / 'manifest.json').read_bytes()).hexdigest(),
    }
    (args.closure / 'collection_details.json').write_text(json.dumps(details, indent=2) + '\n')
    lines = [
        '# 原版训练切分候选采集', '',
        f"登记 1963 条查询全部闭合，62 个包；实际到达上下文 {manifest['positions']} 个，"
        f"已知结果 {manifest['bound_trials']} 条，真值 unknown {manifest['unknown_trials']} 条。",
        f"另有 {manifest['unreached_or_unavailable_contexts']} 条未到达前缀或候选不可用，保留为上下文 unknown，不作技能失败标签。", '',
        '| 类别 | 查询闭合 | 已知结果 | 成功 | 失败 | 上下文 unknown | 真值 unknown | 自有成功/次数 | π 成功/次数 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for category in categories:
        values = [counts[(category, key)] for key in ('closed', 'known', 'success', 'failure', 'context_unknown', 'truth_unknown')]
        values += [f"{counts[(category, 'self_success')]}/{counts[(category, 'self')]}",
                   f"{counts[(category, 'vla_success')]}/{counts[(category, 'vla')]}"]
        lines.append('| ' + category + ' | ' + ' | '.join(map(str, values)) + ' |')
    lines += [
        '', '每个可到达候选只测一次；表中成功率受查询选择和上下文组成影响，不用于比较方法优劣，也不冒充三次采样的可接受率。',
        f"合计自有技能 {sum(counts[(category, 'self_success')] for category in categories)}/{sum(counts[(category, 'self')] for category in categories)}、π {sum(counts[(category, 'vla_success')] for category in categories)}/{sum(counts[(category, 'vla')] for category in categories)}；类别与上下文并非平衡随机比较。",
        '旧清单 2871 条中的 908 条已过时求助候选未进入本次合法采集，不补写失败标签。',
        '公开前缀实际执行后，在新到达上下文重新登记请求、快照和绑定。replacements.jsonl 显式列出旧→新映射；消费者确认后替换上下文，不把新结果回填到旧绑定。',
        '缺失私有支撑计量的 43 条只补留存积分状态上的隔离夹爪介入，不重跑策略或持物窗口；旧包保留，聚合只取显式替换包一次。',
        '空跟踪表面修复只跳过空范围恢复，保留当前公开像素和场景碰撞检查。每条绑定保留其实际执行源码版本，未把旧记录改写成新源码。',
        '仅原版 train；PRO、D2、确认集均未采入。没有训练模型。', '',
        '数据：positions.jsonl；逐查询状态：query_outcomes.jsonl；替换：replacements.jsonl；哈希和包清单：manifest.json。',
    ]
    (args.closure / 'RESULTS.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(details))


if __name__ == '__main__':
    main()
