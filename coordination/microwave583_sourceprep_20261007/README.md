# microwave583 新包与CPU预检

两份单局计划均已用同一不可变source、同一launcher通过CPU预检：2/2，exit0；各核对
1个原版state hash、29个输入引用，launcher另逐项核对639份源码和archive。未提交GPU，
真实物理preflight由root接续。旧581的638份显式源码与archive前后哈希均未改变。
既有diag3、4463与其他尝试记录未修改。

source目录：`/public/home/sunyihan/rpent_libero_eval/source_v5_microwave583_20261007`。
来源是source581的显式`source_plan.json`文件清单，不扫artifacts；只覆盖capture与
door_temporal两份代码（`db8d49c`）和launcher（`7b33862`），另加入提交`151cf6b`的
准备脚本。identity的commit是准备配方commit，明确记`identity_kind`、base_commit、
每项overlay commit与逐文件SHA，不声称所有文件来自一个完整git checkout。

archive SHA256：`df630169cc5a8113d89790e8c48e0379e2626d29e18e27ded70ca64dcc2d86c7`。
source_identity：`results/harness_v5/microwave583_source_CPU_20261007/r1/source_identity.json`
（均相对远端RPent根目录），SHA为`decc2174b439405aea8718581582ca2b4ab9130cf54e1a9e9b6ada47bc7b69d1`。

- capture8：原已访问task33/init0的open用例，8块、capture-only，SHA
  `1df559ce429bf005d71d174173390f5c2cee0e0610517b29803e4efdaba2d4cd`。
  原版setup与状态不改；已开不会计首次开门成功。先拿这局真实输出检查baseline，再放后续。
- close_stop40：同一已访问原版task33/init0的close用例，无setup，40块、公开stop开启，SHA
  `1a5c92bf90bdb32c85932646dde96319cee5ebd9a71fd8a417800d9d6ca49c4d`。
  是方法选择开发，不是资格；若后续扩大160块，须另存计划并保留本次结果。

完整manifest、env与逐字submission命令在`handoff.json`；两个`*_submit.sh`只是给root的
单局命令，本代理未执行。所有文件引用绝对路径+SHA，无节点或依赖绑定。
CPU结果远端`r1/cpu_preflight.json`，SHA
`d57e7d4b72daab538b4c940fb6c178bc89d69ff49c94a4c63c78c7736b755b23`，stdout/stderr分别保留。

真实输出需报告：动作前重采pair数；每个pair的interval_controls（应为6）及被拒原因；
每帧固定/活动平面角度、残差、mask独立性和来源相机；endpoint=true/false/null、
stop是否接纳及下一块请求。比较公开纯函数重算与原记录；私有joint/predicate仅作
独立标签，不能救回缺测，也不能让运行时停止。baseline3对仍缺测保持unmeasured。
任何首次失败与已开状态分层保留。本包没有训练行、确认状态或资格结果。
