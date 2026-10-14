"""Publish the closed confirmation together with the existing selection evidence."""
import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path


def pin(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def interval(value):
    lo, hi = value['wilson95']
    return f'{lo:.1%}–{hi:.1%}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--confirmation', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--contact-diagnosis', type=Path, required=True)
    parser.add_argument('--exclusions', type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.confirmation / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if not manifest['complete_fiveclass_batch']:
        raise ValueError('five registered object classes are not closed')
    selection_path = args.selection / 'manifest.json'
    selection = json.loads(selection_path.read_text())
    diagnosis_path = args.contact_diagnosis / 'manifest.json'
    diagnosis = json.loads(diagnosis_path.read_text())
    exclusions_path = args.exclusions / 'manifest.json'
    exclusions = json.loads(exclusions_path.read_text())
    excluded = {json.loads(line)['state_sha256'] for line in
                Path(exclusions['records']['path']).read_text().splitlines()}
    rows_path = args.confirmation / 'rows.jsonl'
    if pin(rows_path) != manifest['records']:
        raise ValueError('confirmation rows changed after scoring')
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    if not exclusions['permanent_training_exclusion'] or excluded != {r['state_sha256'] for r in rows}:
        raise ValueError('permanent exclusion index differs from scored confirmation states')
    names = {'bottle': '瓶', 'bowl': '碗', 'box': '盒', 'cup': '杯', 'frypan': '平底锅'}
    methods = {}
    source_paths = {}
    for reference in manifest['plans']:
        plan = json.loads(Path(reference['plan']['path']).read_text())
        category = plan['cases'][0]['type'].removeprefix('grasp_')
        methods[category] = plan['source_commit'].removeprefix('source_v5_')
        source_paths[category] = plan['source_path']
    public = manifest['overall_public_verifier']
    physical = manifest['overall_success']
    threshold = manifest['internal_thresholds_passed']
    lines = [
        '# 独立扰动布局抓取确认', '',
        f'五类全部闭合：{physical["n"]}个注册状态，v3成功{physical["k"]}/{physical["n"]}'
        f'（Wilson 95% {interval(physical)}）；公开验证一致'
        f'{public["agreement_all_registered"]["k"]}/{physical["n"]}。内部门槛通过：{threshold}。', '',
        '内部门槛：总体≥95%、单类≥90%、验证器一致≥95%。只以本确认批判定。'
        'unknown、绑定失败和公开缺测保留注册分母；物理失败未重跑或替换；所有确认布局和种子永久排除训练。'
        '仿真v3真值只用于私有测量，运行时控制和验证只读公开RGB-D、本体状态及静态机器人几何。', '',
        '|类别|锁定完整方法|v3成功|Wilson 95%|公开一致|FP / FN|已知真值公开缺测 / 真值unknown|内部门槛|',
        '|---|---|---:|---|---:|---:|---:|---|']
    for category, group in manifest['groups'].items():
        p, metric = group['public_verifier'], group['success']
        lines.append(f'|{names[category]}|{methods[category]}|{metric["k"]}/{metric["n"]}|'
            f'{interval(metric)}|{p["agreement_all_registered"]["k"]}/{metric["n"]}|'
            f'{p["fp"]} / {p["fn"]}|{p["public_null_on_known_truth"]} / {p["truth_unknown"]}|'
            f'{group["internal_class_thresholds_passed"]}|')
    lines += ['', 'FP指未抓住却判通过，FN指真抓住却判失败。两个方向分别报告；'
        '已知真值下的FP/FN率及分母在manifest.json中。公开一致的Wilson区间也在该文件中。', '',
        '## 基础设施与失败分母', '',
        '|类别|经历基础设施故障的唯一状态 / 注册数|故障试次|恢复状态|未恢复状态|中位每状态墙钟秒|',
        '|---|---:|---:|---:|---:|---:|']
    for category, group in manifest['groups'].items():
        infra = group['infrastructure']
        metric = infra['unique_registered_cases']
        lines.append(f'|{names[category]}|{metric["k"]}/{metric["n"]}|{infra["fault_attempt_n"]}|'
            f'{len(infra["recovered_cases"])}|{len(infra["unresolved_cases"])}|{group["median_wall_s"]:.1f}|')
    lines += ['', '故障率按完整注册池跨分片取唯一状态并集计算，不能使用原runner的分片局部分子。'
        '碗两条补测只补原本从未执行抓取的启动故障状态，原fault/FAILED记录保留。'
        '独立reset诊断证实环境恢复；启动延迟的底层原因仍未定位，不能称已修复。', '',
        '各类运行时失败原因计数（成功回执的null不列作失败）：']
    for category, group in manifest['groups'].items():
        failures = {k: v for k, v in group['failure_reasons'].items() if k != 'null'}
        lines.append(f'- {names[category]}：`{json.dumps(failures, ensure_ascii=False)}`')
        selected = [row for row in rows if row['group'] == category]
        no_named_reason = sum(row['registered_v3'] is False and not row['failure_reason']
                              for row in selected)
        unknown_reasons = group['private_truth_unknown_reasons']
        lines.append(f'  私有v3失败但回执未命名原因{no_named_reason}次；'
            f'私有unknown原因：`{json.dumps(unknown_reasons, ensure_ascii=False)}`。'
            '这些缺口不以公开验证标签填补。')
        lines.append('  v3失败的逐判据状态计数（可重叠）：`'
            + json.dumps(group['private_failed_v3_predicate_case_counts'], ensure_ascii=False)
            + '`；接触阶段分类：`'
            + json.dumps(group['private_contact_failure_classes'], ensure_ascii=False) + '`。')
    phases = Counter()
    for group in diagnosis['groups'].values():
        phases.update(group['classes'])
    lines += ['', '## 已完成的选择和根因证据', '',
        f'选择批已闭合{len(selection["groups"])}个完整配置，'
        f'{sum(g["registered_n"] for g in selection["groups"].values())}次注册试验。'
        '同方法内每类100次；不同方法共享选择状态，不作为独立总体。', '',
        '1. 单纯伺服容差修复的500次配对：下降失败31→31。解析下降使用独立move_pose路径；'
        '31次下降失败中29次接触停滞，19次涉及柜体接触。',
        '2. 13条盒超宽均为chocolate pudding，精修边界主要落在公开柜体区域。'
        '深度清理、身份排除和具体包装语义查询都做了同池比较；最后语义查询53→58，改善5、退步0。'
        '历史SAM mask缺失，不能断言具体像素污染来源。',
        '3. 杯身份守护77→86，改善9、退步0；超过10cm的规划偏移16→0。'
        '确认锁定的是执行器和验证器整体排序选出的servo_only配置，不能用身份守护成绩替代。',
        '4. 锅连接把手使缺测17→4、成功58→70。加入公开随动验证后成功65，公开一致59；'
        '直接父方法配对改善2、退步7，退步包括下降未到位5、把手缺测1、闭合后夹持失败1。',
        '5. 多yaw与侧向几何采样、两指对夹检查、静态Panda STL凸包碰撞窄阶段均已实测。'
        'STL窄阶段相对直接父方法：瓶+6、碗+1、杯+9且均无退步；'
        '它们仍弱于部分类别解析式。无来源或许可不明确的学习权重未使用。', '',
        f'旧失败状态的专门接触诊断子集共{sum(g["n"] for g in diagnosis["groups"].values())}次：'
        f'`{json.dumps(dict(phases), ensure_ascii=False)}`。这是失败选择子集，不能外推为总体比例。'
        '未对夹先修几何和接触深度；闭合后滑落优先检查抓取面与闭合保持；'
        '抬升后丢接触再比较抬升速度。保持原执行器力限制，不以增大力补偿定位错误。', '',
        '## 源码和交付', '',
        f'锁定v3 SHA：`{manifest["locked_v3_sha256"]}`。'
        'manifest.json含计划、源码身份、逐文件SHA、原始ledger路径与SHA；rows.jsonl逐次记录结果。'
        '计划中的source_commit是源码快照标识，远端不是完整Git checkout，不能当作Git commit SHA。', '']
    lines.append(f'永久排除索引：`{exclusions["records"]["path"]}`；'
        '逐状态包含种子、状态SHA、布局文件SHA和登记计划。既有确认池其他状态的排除规则继续有效。')
    for category in names:
        lines.append(f'- {names[category]}源码快照：`{source_paths[category]}`。')
    lines += ['', '当前未冻结、未准入训练。'
        + ('本批未达到内部门槛；已有多种不同方法的物理结果，保留失败并交用户和Codex1决策，不降低标准。'
           if not threshold else '本批通过抓取内部门槛，其他技能和集成验证需独立判定。'), '']
    report = args.confirmation / 'REPORT.md'
    report.write_text('\n'.join(lines))
    receipt = args.confirmation / 'receipt.md'
    receipt_lines = [
        '### Codex3：扰动布局抓取独立确认正式交付', '',
        f'五类500个注册状态全部闭合；锁定v3成功{physical["k"]}/{physical["n"]}'
        f'（{physical["rate"]:.1%}，Wilson 95% {interval(physical)}），'
        f'公开验证一致{public["agreement_all_registered"]["k"]}/500。'
        f'内部门槛通过：{threshold}；当前未冻结、未准入训练。', '',
        '|类别|v3成功/注册数|公开一致|FP/FN/公开缺测/真值unknown|',
        '|---|---:|---:|---:|']
    for category, group in manifest['groups'].items():
        v = group['public_verifier']
        receipt_lines.append(f'|{names[category]}|{group["success"]["k"]}/100|'
            f'{v["agreement_all_registered"]["k"]}/100|{v["fp"]}/{v["fn"]}/'
            f'{v["public_null_on_known_truth"]}/{v["truth_unknown"]}|')
    receipt_lines += ['',
        '所有物理失败保留，确认失败未重跑或替换。只补了两条从未执行抓取的碗启动故障状态，'
        '原状态/方法/真值不变；补测一成功一失败。跨分片基础设施故障：碗8/100，10次故障试次，'
        '均恢复；其他四类0。底层启动延迟未定位。原99/100提前汇总保留；'
        '监控已修复为startup/formal均在sacct可见并结束才闭合，新结果核对100/100。', '',
        '69个完整选择配置、6900次注册试验已完成。多种方法仍未达内部门槛，'
        '不降低标准，不拼接历史最佳执行器和验证器成绩。各方法配对、失败分类、缺失证据见报告。', '',
        f'完整报告：{report.resolve()}',
        f'逐次记录、源码SHA与输入SHA：{manifest_path.resolve()}，{rows_path.resolve()}。',
        f'永久训练排除索引：{exclusions["records"]["path"]}。',
        f'锁定v3 SHA：{manifest["locked_v3_sha256"]}。'
        'source_commit是源码快照标识，远端不是完整Git checkout。']
    receipt.write_text('\n'.join(receipt_lines) + '\n')
    evidence = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'confirmation': pin(manifest_path), 'selection': pin(selection_path),
        'contact_diagnosis': pin(diagnosis_path), 'report': pin(report), 'producer': pin(Path(__file__)),
        'permanent_training_exclusions': pin(exclusions_path),
        'receipt': pin(receipt),
        'training_allowed': False, 'physical_retries_performed_by_report': False}
    (args.confirmation / 'delivery_manifest.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps({'report': str(report), 'internal_thresholds_passed': threshold}))


if __name__ == '__main__':
    main()
