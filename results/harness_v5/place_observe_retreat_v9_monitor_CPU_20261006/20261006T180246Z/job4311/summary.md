# 4311 原40放置选择批完整结果

8片均 COMPLETED 0:0，40/40 注册案例全保留，20 个唯一原始状态；不是独立确认批，不授冻结资格。源码为 8fe6b188bac4d233f4c4d632a38d6dc5f724f583。manifest SHA `76f4f8db4c6e3581af275bbe4823a9918193188fa6d8549e6872921fdd04900d`。

两组共用 category-C setup 与独立公共抓取验证器：真实持续持物40/40、公共TP40/FP0/FN0/TN0。真实放置执行37；新增完成35/40（87.5%，Wilson95% 73.9–94.5），条件分母35/37（94.6%，82.3–98.5）。三例 selected_instance_not_uniquely_measured 保留。执行失败2，均 current/on 的 bowl 测得端点低于支撑面。

| 分层 | 注册 | 执行 | 新增完成 | TP/FP/FN/TN/null |
|---|---:|---:|---:|---|
| place_in/current160 | 10 | 9 | 9 | 9/0/0/0/0 |
| place_on/current160 | 10 | 10 | 8 | 4/0/4/2/0 |
| place_in/vla_subtask160 | 10 | 9 | 9 | 3/0/1/0/5 |
| place_on/vla_subtask160 | 10 | 9 | 9 | 6/0/2/0/1 |

公共放置：TP22/FP0/FN7/TN2/null6；测得精确率22/22=100%（Wilson95% 85.1–100），测得召回22/29=75.9%（57.9–87.8）。包含null的已证实一致率24/37=64.9%（48.8–78.2）。7个漏判的实际测量 footprint 为 .61–.89，未达原strict6门槛（on .90、in .85）；阈值保持，原判定不修改。6个null全部private true。

v9真实观察退避触发7，记录动作617个控制步（含收敛检查637 steps），到达5，fresh两帧1；另2次80步后仍距目标 .2845/.2389m，保留可恢复null。5次成功退避中4次仍缺新鲜可见物体。仍有6个null，不能说v9已解决缺测。v8实际release触发3、60控制步，fresh两帧3、公共false→true3；没有release前即时private标签，不能宣称因果物理改善。

完整动作块：first动作逐块trace 3006块、请求/实际15030/15030步、short0；C setup仅有primitive chunks_used摘要606块/3030步，没有逐块motion trace。每例 摘要＋first trace 与 server 请求/实际总计完全相等，无native-stop截块、外部截断或私有判定控制；报告显式保留这个记录覆盖限制，不补造逐块证据。

与4279逐例原样并列在审计 records.prior4279_saved_labels；原始state SHA相同、setup和VLA联合方法变化、策略RNG未配对，所以不把跨轮改善归因纯v9。旧4279 setup真19/40、执行22、新增完成16、已有完成5；本轮setup真40/40、执行37、新增35、已有0。

下一步：处理公共实例唯一绑定3、退避后仍看不到物体的6个null以及7个footprint漏判；独立100个原版新状态确认另行登记，不能筛持物或公共可绑定成功。本分析0新物理试验、0训练行。

产物和SHA：
- `report.json` SHA `a5bcfc9e25d4a6dfa9117b6411f17ae168e62938309047f4e574f49919c1c201`
- `strict_setup_observe_retreat_and_verifier_audit.json` SHA `a2f505924b5c7c3126908b037d9c367e4af781b883f7b5ad1cf2dd52e4e2de2f`
- `scripts/analyze_v5_observe_retreat_selection.py` SHA `ba4b3e969a6a6f48282998284ba9aa2bd95e6047fabde0e4a339003ad61e22e2`
