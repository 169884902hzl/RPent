# Codex3：reset 姿态＋选中物体短提示词提交前回执

已读取用户 10/05 01:45、03:10 的抓取要求、当前 COORDINATION，以及
3550_0–5 的完整正式产物；接管 3550/3554/3565/3591，不修改或重复提交。
接受总体真成功 >=95%、每类 >=90%、每类至少100次首次抓取、Wilson95%CI、
运行时验证器一致率 >=95% 和两个方向的误判分别报告。真值仅用于诊断标签。
五种方法不能用 alias/预算/同族参数变化充数，不降低标准。

3550_6/_7 盒类仍运行，未将未闭合前缀当作正式100次结果。
早期闭合前缀出现非目标物体双指接触及 body-origin 上升3cm的代理证据；
该代理不等同于完整持续夹持真值，不改旧标签，不归为 decider 选错对象。
假设：完整多对象任务条款会干扰 π0.5 对指定首抓对象的执行。
本轮保持 reset 姿态、测量类别的词汇、160动作块、public pick stop、
单帧验证器相同，只对实验组移除原任务中的其他对象/放置目标条款。
两组为原 full/control 与 selected-only；默认runtime、renderer131均未改变。

GPU预约：3550完整结束后3565/3591最多两张；本轮等待3591释放一张后执行，
与可能仍在运行的3565合计最多两张。1GPU/8CPU/90GB/1h/nice1000，无节点绑定。
提交前回执先推送并append远端COORD，随后执行一次：
`sbatch --parsable --dependency=afterany:3591 runtime_launchers/run_v5_grasp476_start_selected.sbatch`。
作业号尚未分配，提交后立即回报；输出目录
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp476_start_selected_20261005/smoke_job<assigned_job_id>/`。

源码快照
`/public/home/sunyihan/rpent_libero_eval/source_v5_grasp476_start_selected_20261005/`，
commit `be5a51f`；archive SHA256
`9353de6baf8ff1514526b8d3b92e50f68d72738f062060b1fce1897c94d3978d`。
入口 `scripts/probe_v5_grasp449_20261005.py::probe_contact_prompt`；Python
`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`。
准备目录 `results/harness_v5/grasp476_start_selected_20261005/preparation/`；
smoke12 SHA256 `d935332b08a161e295faed88339a6a3f6fb73fec5fd45250f0c0437220efe219`；
full1200 SHA256 `19caef0d0a592e4086db1d3aef4e5e6869d0b909b2002c05938130a98b4e5417`，仅准备、未提交。
launcher SHA256 `0a9b528852e7cc582f7d09fea47f1c0e68058e0b47cdac851f34de7f68d8b1bd`。
45项绑定/视觉验证/私有真值/感知几何测试通过，launcher语法和远端入口import通过。
12次物理smoke尚未执行；smoke不授予资格，不算完成的新物理方法。

无异议。六类正式资格、在线成功率预测核验、A3/A4新旧复测、严格放置完整
物理复验、行为冻结仍未完成。本轮原版诊断init0–49不入训练；不读PRO、
人工/密封测试文本或Jev输出作为训练输入。若以后采纳新回执语义，先通知
Codex1/2重渲染；不能后验拼各类赢家宣称单一配方已达标。
