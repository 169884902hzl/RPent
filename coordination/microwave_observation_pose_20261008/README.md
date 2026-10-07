# 微波炉公开观察位姿：opt-in 开发对照

实现提交 `07d0f85cb41bbef805d8e6e0cf092feff1bb8759`，开关
`microwave_observation_pose_v1` 默认 false。本次原版 task33/init0 的
capture8 计划启用它，仅比较当前双视角测量；不作技能资格或训练。

每次观察先撤离，保存当前独立固定框架与门平面的测量。从两平面中心
算中点，先抬升再向中点平移最多15cm。第一次测得的观察高度缓存，
baseline 重试不累计抬高。每段记录 target、真实 EEF 起终点、距离和
move 返回；第一段实际未达时不继续平移。不存在或不独立的平面不触发
移动。私有关节、完成谓词、物体坐标和任务目标不参与此过程。

移动后重新采两帧公开 RGB-D，保持6个真实中性控制。规划帧仅作路径
证据，不计为移动后的验证帧；新视角仍缺测时保留 null，不复制主视角
拟合成腕部贡献。`vertical_face` 的4cm支持、两面独立性、遮挡、稳定性
及端点阈值不变，88c4388 的分部件机器人查询保留。

窄测试 `test_v5_microwave_capture.py` 与
`test_v5_microwave_door_temporal.py` 共 **59/59通过**，覆盖真实EEF
判定、先抬后移、源帧陈旧/缺平面/重叠/同测量拒绝、缺测重新采集、
私有标签不改变路径、默认off与重试不累计升高。CPU测试不算物理结果。

本次**保留原有每块撤离与采样节奏**；接触被撤臂破坏的假设由另一项
close40 对照处理，不与观察移动同时混改。

新 source：
`/public/home/sunyihan/rpent_libero_eval/source_v5_microwave_observation_pose_20261008`。

冻结来源为4493的source584显式639文件清单；新增prep后640文件。
capture 与 prep 为提交的确切内容；runtime 在584的原字节上只加两行
flag，prepare会检查严格等于这两行补丁，没有带入live runtime其它改动。
这是显式混合谱系，不能说所有源码来自一个完整checkout。旧584的639
文件和archive均前后核验不变，launcher内容也保持一致。

远端包：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_observation_pose_CPU_20261008/r1/`。

| 文件 | SHA256 |
| --- | --- |
| source_identity.json | 2b58c9461a82df9eee218d4560a9e5bbc9285873f5213baf14b9bbec63c9457b |
| capture8.json | f0d3c358d93035b552a5c7bcc205d8772fc1b366e026d3bd3e16680eeb10aab3 |
| same_launcher_CPU_receipt.json | 29f1c2d46ff3bb2f01df08c13e6d65a0e188fc127c21e5f5edd258679107ba8d |
| source archive | b3c26dfdb899e9d6ae0fbaa56914c0b571c1e1fd78614e68b66d33f3c1c69478 |
| launcher | 8cba334fa65b15d906b8c5cda055c5599804602d127131fd7e33c0935ad0d2bf |

同launcher的实际CPU预检exit0，核对29个显式输入、1个raw-state。
整理回执时误把多行JSON最后一行当完整JSON，已从原stdout整体解析
恢复；原stdout/stderr保留，没有重复launcher。完整物理提交参数在
同目录CPU receipt的`submission_command`，本地副本为handoff.json。

物理输出计划：
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_observation_pose_original_20261008/capture8`。
主代理登记后启动这1局，检查实际请求、起终点、腕部plane贡献及缺测。
本子代理未提交GPU、未修改COORDINATION。4493已访问的原版状态保留
为方法选择；先前已经开门的现象不能计作开门技能成功。
