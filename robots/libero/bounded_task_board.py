"""Task-level development counts and promotion rules, separate from data filtering."""
import json
from pathlib import Path


PROTOCOL = {'decisions': 40, 'sim_steps': 10000, 'wall_s': 7200,
    'vla_blocks': 104, 'vla_controls': 520, 'cross_episode_memory': False,
    'reset_world_after_failure': False}


def next_level(level, success):
    if level not in (5, 10, 20):
        raise ValueError('development levels are 5, 10 and 20')
    threshold = {5: 4, 10: 9, 20: 19}[level]
    return (None if level == 20 else level*2) if success >= threshold else level


def classify(level, oracle, model):
    threshold = {5: 4, 10: 9, 20: 19}[level]
    if oracle is not None and oracle < threshold:
        return '修复中', '技能/感知/执行'
    if oracle is None or model is None:
        return '待测', None
    if model < threshold:
        return '修复中', '模型选择（Codex2）'
    return ('已毕业' if level == 20 else '已升级'), None


def write_board(output, tasks, results):
    """Retain every attempted outcome; program/infrastructure issues stay explicit."""
    output = Path(output);output.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in tasks:
        row = {**task, 'level': task.get('level', 5), 'oracle_success': 0,
            'oracle_n': 0, 'model_success': 0, 'model_n': 0,
            'pi_success': 0, 'pi_n': 0, 'infrastructure_pending': 0}
        sources = set()
        for result in results:
            if result['panel_task_id'] != task['panel_task_id']:
                continue
            sources.add(result['source_commit'])
            if result['status'] != 'physical_result':
                row['infrastructure_pending'] += 1;continue
            method = result['line']
            row[method+'_n'] += 1
            row[method+'_success'] += bool(result['success'])
        level=row['level']
        oracle = row['oracle_success'] if row['oracle_n'] == level else None
        model = row['model_success'] if row['model_n'] == level else None
        row['status'],row['owner_reason'] = classify(level,oracle,model)
        row['source_shas'] = sorted(sources)
        row['task_key'] = row['panel_task_id']
        row['layout_seed'] = task.get('layout_seeds', [])
        row['seeds'] = task.get('seeds', [])
        row['oracle_A_successes'] = oracle
        row['model_A_successes'] = model
        row['n'] = level
        row['line_n'] = {'oracle': row['oracle_n'], 'model': row['model_n'], 'pi': row['pi_n']}
        row['results_path'] = str(output)
        # This is a measurement board, not a measured-label admission packet.
        row['training_admission'] = False
        row['source_split'] = 'train' if row['panel'] == 'development' else 'evaluation_only'
        row['next_level'] = next_level(level,min(oracle,model)) if oracle is not None and model is not None else level
        rows.append(row)
    data=output/'task_board.jsonl'
    data.write_text(''.join(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n' for row in rows))
    lines=['# 分级任务看板','', '协议：40次决策 / 10000控制 / 7200秒；π104块/520控制；失败不重置世界。', '',
        '| 面板 | 任务 | 类别 | 级别 | oracle+A | 模型+A | π+A | 状态 | 归因 | 最近源码 |',
        '|---|---|---|---:|---:|---:|---:|---|---|---|']
    for row in rows:
        count=lambda method:f"{row[method+'_success']}/{row[method+'_n']}"
        lines.append(f"| {row['panel']} | {row['panel_task_id']} | {row['category']} | {row['level']} | {count('oracle')} | {count('model')} | {count('pi')} | {row['status']} | {row['owner_reason'] or ''} | {','.join(s[:8] for s in row['source_shas'])} |")
    (output/'TASK_BOARD.md').write_text('\n'.join(lines)+'\n')
    return rows


def update_from_results(root):
    """Refresh the shared task board after each independently closed world."""
    import fcntl
    root=Path(root)
    with (root/'task_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        tasks=json.loads((root/'preparation/tasks.json').read_text())
        results=[]
        for pointer in (root/'results').glob('*/closed_*.json'):
            reference=json.loads(pointer.read_text())
            value=json.loads(Path(reference['path']).read_text())
            results.extend(value['results'])
        rows=write_board(root,tasks,results)
        fcntl.flock(lock,fcntl.LOCK_UN)
    return rows
