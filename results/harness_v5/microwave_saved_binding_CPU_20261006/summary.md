# 原版微波炉实体/绑定/把手测量诊断

只读取已pin的4128旧source544选择批和4178 source549原30冒烟批；微波炉分别400和10个注册案例。所有原始label、失败、预算和组别保留，0新物理执行、0训练行、不授确认资格。

| 作业/分层 | 注册 | first VLA执行 | first私有端点真 | 未执行根因 |
|---|---:|---:|---:|---|
| 4128 close/current |100|43|42|setup绑定50＋first绑定7|
| 4128 close/VLA |100|43|43|setup绑定50＋first绑定7|
| 4128 open/current |100|0|0|setup绑定7＋first绑定93|
| 4128 open/VLA |100|0|0|setup绑定7＋first绑定93|
| 4178 close/测量把手 |5|0|0|current_fixture_handle_not_measured5|
| 4178 open/测量把手 |5|0|0|current_fixture_handle_not_measured3＋wrist_fixture_handle_not_measured1＋实例绑定歧义1|

4128的314个未执行全部是公共实体缺失或歧义。86个已执行均动作前private false，85个动作后true，但86个公共回执全null；其实际块控制含short，不能授资格。典型t33/s0 close仅有两个mug实体、无microwave；t33/s4 open仅缓存的invisible microwave，没有部件。不能拿544旧结果断言现行运行时仍如此。

4178已经启用microwave_instance_geometry_v4、microwave_recall_geometry_v3、appliance_support_crop_v5、microwave_door_cloud_v6、door_point_recall_v7、door_plane_consensus_v1、fixture_part_visibility_v2、fixture_endpoint_geometry_v3。10例都能在公共记录找到microwave；9例进入first记录、1例只有接近servo，实际first VLA接触0。close5例agentview/wrist的handle SAM instances全0。open的3例有handle instance却无法得到当前唯一parent door或同capture cloud provenance；另1例初始agentview姿态有效，接近后腕部再测失败。1例s1 post-setup公共scene有两个visible microwave（e109、e98），造成唯一实例绑定失败；缓存door e103为part_of=e109、invisible。

完整逐例实体的name/part_of/visible/source_step/xyz/lower/upper/geometry/src、公共binding错误、handle各视角accepted_instances/reason、private端点标签及原ledger路径/行号/SHA在诊断JSON里；大motion trajectory保留在原hash ledger，不伪造缺失。

固定place v9（8fe6b18）源码中这些微波炉/门面开关默认false，place专项manifest也没有显式开启；dual_view_fusion_v1显式true。该配置只是放置专项，不代表整个现行harness。现有第三法已完成parent召回，剩余优先级是公共handle测量/door同capture朝向链，不能靠打开place v9现有开关就宣称修好。

建议原版smoke：沿同批10个已登记状态，固定全套微波炉开关，分别核对(a)源实体唯一绑定；(b)handle queries检测与door面云同capture provenance；(c)agentview有效接近后腕部refine是否因遮挡丢掉measurement。只依据RGB-D同capture云和测得部件几何修适配/测量链；不使用sim关节控制动作、不放宽公共可测要求。本次未修改shared runtime。

SHA与版本：
- `4128_4178_diagnosis.json` SHA `fe4d004bdd9dfaa1d9450b29673b506cadeb60659713ea62bf438e240b1990ca`
- `scripts/analyze_v5_original_microwave_saved.py` SHA `3afb606d912612a11fee0eeed2397e47013364d18dc322ddf636c03a2e7d71c6`
- job4128 report SHA `cdb013ac1d9e70236db1836b1a39f9b12c453b5e9448cc45c85dda3c0f76c668`；source `2b4b5da`
- job4178 report SHA `6bb8dddbf4aacd6df9f10b4633582cece4bb000667d325a2e2aca7ed875cf365`；source `8b45399594355c79c2abe6c76a8badab010b8de4`
