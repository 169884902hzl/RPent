# 摩卡公开 stove 绑定 CPU 诊断 r1

三个登记确认布局的旧结果均保留：580104（4502 part3）、580152（4531 part2）、580159（4531 part1）在目标执行前 `original_transfer_public_stove_binding_missing_or_ambiguous`，目标 controls=0，私有目标完成=null。没有物理重跑、没有新 GPU 作业，不修改 SOURCE582r2。

报告 `public_binding_diagnosis_r1.json` SHA256 `234e526715e93cac8f668efa69a9d5410e2203b13419dedc6e320b41efcbd695`。只沿三个显式 episodes 路径、各自 choices 的保存 SHA、七个 fixture RGB-D 点云引用读证据；七个文件 SHA 全通过。点云的中位中心及 2%/98% 边界与原记录逐项复算，误差均为 0。没有使用私有几何、目标谓词或接触标签来选择目标。

三者不是漏 SAM，也不是类别归一化不一致：所有参与绑定的实体名称都是 stove，当前可见、source_step=0、来源 agentview；原 stove operating-area 距离与原 nested `same_measured_bbox` 去重函数均复算一致，输出仍 ambiguous。

| 布局 | 原 eligible IDs | 根因 |
|---|---|---|
|580104|e14、e93|近处薄 stove 与远处宽 cloud 同为 stove；远 cloud 中心 x=-1.456m，bbox 延伸至 x=-0.640m，bbox→EEF XY 距离 0.434013m，仍通过 ≤1m gate。|
|580152|e11、e47|同一视角的嵌套分割点云未合并；较小 cloud 的 30696 个点中 30693 个与较大 cloud 精确相同（99.9902%）。|
|580159|e35、e48|同 580104，远 cloud 中心 x=-1.456m，bbox→EEF XY 距离 0.424932m，仍通过 ≤1m gate。|

580152 两个近处实体的 XY bbox IoU=0.981010、最大 bbox 边差仅 0.005371m，但薄体的 3D bbox IoU=0.734086，低于原门槛 0.8；中位中心差 0.025741m 也高于 scene 原 2cm 去重线。因此同一测得表面的嵌套实例幸存，并不是双视角冲突。远处 e107 已被 >1m gate 拒绝。

原 stove SAM mask 未持久化（这些 perception evidence 无 `sam_mask_files`），planner media 也是 null。上述 99.9902% 是精确 RGB-D 点的覆盖比例，不能冒充 SAM mask IoU；也不能仅据远中心把它的语义判为已核实误检。两局宽 bbox 的尾部进入 operating-area 是已支持的绑定层缺陷，具体远处物体语义仍未核验。

登记源码：`/public/home/sunyihan/rpent_libero_eval/source_v5_placement582_r2_20261008`。
runtime SHA256 `17b7ce4ffc1d0a02278eb3308b6f7c76425c19241fbf74aeffcbf76dfefab7bb`；原版 transfer probe SHA256 `5cc5def4fa8d666ecd73815da7987772add2a9151f1deb530a0937affffba7d7`。报告保存三条 episodes 的完整远端路径、行号和 SHA，以及 choices/cloud refs。

下一步在新开发源码内修：按同类别、同 capture 的实际点云/掩码覆盖去重，保留原 ID 和测量；对宽 bbox 使用实际点支持和公开测量中心核验 operating area。先复算保存公开输入，证明新路径，不重试这三个确认布局。随后只用原版选择池准备独立单局包；旧确认标准、记录与永久训练排除不改变。
