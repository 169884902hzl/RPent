# 新增76摩卡布局：CPU预检与永久训练隔离交接

已完成：先登记规则，再固定50步CPU落定，再用同基底/同50步无扰动对照审计。新增76个raw SHA及几何指纹均唯一，与原24及task19全部官方几何指纹零重复。

注册总数100，CPU有效98，CPU无效2；有效数不足100，不能宣称确认数量或技能资格达标。580124在CPU落定阶段爆飞，580174的其他物体相对未扰动基底偏离6.04mm。原提案/落定/审计保留，不替换、不调参数、不重跑；两条永久排除训练。

新增global index24–99，seed580124–580199，基底task19 seed=index%50，原24幅度网格[index%24]。不改目标、指令、家具；提案只改moka freejoint XY/yaw。布局共用原任务/已用基底，不主张IID。

100态永久排除清单schema=libero_confirmation_exclusions/1。全部rule/base/raw SHA/fingerprint/落定XY仅保存在远端私有元数据；本Git交接只存path/hash。训练seed680100–689999，生成后必须与每一确认态落定world XY距离≥5cm，不能用rawhash差替代几何隔离。

运行时SOURCE582r2、320个完整5动作块预算、公开双帧placement stop均不变。新launcher只调整76声明身份、明确排除2个CPU无效布局及形式记账。正式运行合法completed/no-execution保留unknown分母；启动/基础设施/执行报错非零。实际580104记录与6种异常变体，7/7通过；全部8shard同launcher CPU前检覆盖76状态，通过。

主代理负责GPU预约与提交。先显式exclude580124/580174，指定first=moka_layout_580125，用同launcher真实首局产生>0 physical controls；新contract通过后，再显式exclude该已完成首局，放行剩73有效布局。源目录、manifest、launcher、排除文件及CPU检查SHA均见manifest.json/handoff.json。当前root已接手首局提交，本代理未提交GPU、不改COORDINATION。

prep_r1为被记账修复取代的未投GPU开发包，保留；唯一续跑入口为preparation_r2。不能复用原24或r1的startup contract。旧4502的完成回合保留，不修改不可变launcher或重复物理回合。
