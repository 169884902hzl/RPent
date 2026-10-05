# Codex3 skill505：统一测量回执候选版，尚未冻结

按12:20交接接入运行时：双视角融合默认开启（只有登记的去融合消融可显式关闭）；完整vla_subtask与拆分技能并列，公共类别句式、无BDDL输入，不在抓后停止。新动作回执含夹爪前后、持物前后、公共实体位移/缺测、家具部件变化；没有测得变化记no_effect，缺失验证记unmeasured，release以实测开度验证。每次感知单独记录fusion_version/source_cameras到measurement_history.jsonl。

防循环：release只在夹爪闭合或held时出候选；同动作两次no_effect/明确验证失败后移除，直到场景有测量变化；原execution_error三步冷却保留。卡片解析后的动作也接受相同过滤，不通过card_next绕过。候选总数24不变；恢复/receipt字段本轮有变化，旧训练行不能直接作新格式数据，必须冻结后重采。新入口flags：--measured-action-receipts-v1、--measurement-progress-blocking-v1、--vla-subtask-v1，默认true，各有显式no开关供既定对照。动作身份使用中性ID。

当前是开发候选，未授抓取/开合/place确认或190/200资格，未冻结。已有3616/3619/3620固定源码与配方不改变。将用独立source与原版技能smoke检查实际公共测量、token长度与私有诊断隔离，通过后放大探索，最终确认仍用独立场景。精确renderer交付在统一冻结时给Codex1/2；当前渲染入口harness_v5_eval.run_episode调用robots.libero.v5_state.serialize，不可标成冻结版。

CPU已运行178项相关tests通过；新增完整macro无grasp stop的回归另测。真实物理融合、技能成功率、验证误判、回合最大重复次数仍待新作业证据。不将CPU通过称为物理成功。
