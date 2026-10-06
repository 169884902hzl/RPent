# fixture542：ac3fe58 全分片 CPU 预检与耗时估算

只读现有显式manifest/具名时间报告，未改runtime、状态、恢复或manifest；未执行物理回合、未提交作业。等待主代理实际提交后提供作业号，再接手只读监控。

## 预检结果

新源码目录：`/public/home/sunyihan/rpent_libero_eval/source_v5_runtime542_20261006`，登记commit `ac3fe58`。probe SHA与本地`git show ac3fe58`字节一致：`c9077711da8f5d69841f8774f50fabbfe5ea1b2d7088273aba85785919ee10f9`。helper SHA `0dbd2334ae6cf849329cdb8dcd3d4c63be762d2754985a58c1b1fb20d4140dcd`。

从 `/tmp` 用 snapshot 中真实 launcher、`SKILL535_PREFLIGHT_ONLY=1` 检查，全部30片通过：smoke30 6片，其余各8片。四个manifest SHA保持原样。每片argv/env/cwd/stdout/stderr另存，不覆盖旧报告。

|批次|片数|每片cases|每片引用文件|
|---|---:|---:|---:|
|第三法 smoke30|6|5|87|
|fixtures1200|8|150|2426|
|place400|8|50|826|
|第三法 selection600|8|75|1227|

远端报告：`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill540_articulate_place_selection/launcher_preflight_ac3fe58_20261006/report.json`。SHA `c3c8a6d02f346fca4e36891b9975f44a6f2b52a335c21e293ad964332d6aae5a`；本地同相对路径已镜像。0物理调用、0训练行、0作业提交。

## 每片耗时规划代理

时间输入只读job3637的具名报告 `results/harness_v5/skill512_fixture_labels_CPU_20261005/report.json`，SHA `a0bee3771db56d571ae0d95248a91fb875975689a96a4216ec6200bda4260983`。12条中3条第一次动作未执行（binding缺失），估算排除它们，避免用早退时间低估物理流程。剩9条实际执行的开合记录：平均63.16秒、中位66.70秒、P90/最大84.60秒，预算同为160个动作块；其中含真实setup开合的耗时。

|批次|每片规划平均值|逐次P90累加值|
|---|---:|---:|
|第三法 smoke30|约5.3分钟|约7.1分钟|
|fixtures1200|约162分钟（2.7小时）|约212分钟（3.5小时）|
|place400|约53分钟|约71分钟|
|第三法 selection600|约79分钟|约106分钟|

fixtures1200按类型均值估算，缺实际执行drawer_open时间的类型用全部执行均值；第三法和放置仅使用全体旧开合时间代理，因为没有匹配新配置的物理计时。新把手精修、融合/验证的额外耗时以及新服务冷启动分布未测，不能把代理当source542的实测交期。逐次P90之和只是规划值，不是整片P90置信区间。收到新作业首批实际逐次记录后按类型/condition更新，保留旧估算。

详细逐片类型/condition计数和计算保存在同目录`runtime_estimate.json`，SHA `70d8d2a44fb6fb5d370c2338608c2eeb922258c9f287f9ce6ec9d77837e57e49`。

## GPU共享结论

现有launcher申请`gpu:1`。每个probe分片只启动一套SAM3和π0.5服务，按case顺序执行，各类型/condition共用该分片的一张GPU。`ProcessDaemon`复制当前环境，两个服务继承Slurm给定的CUDA_VISIBLE_DEVICES，probe没有传`--cuda-device`去突破分配。发生基础设施故障时先停服务，再创建下一generation。

不同manifest也可以在同一个`gpu:1` allocation里顺序调用probe、分别给独立输出目录；上一调用finally停止两个服务后，下一调用再启动，始终只用一张GPU。现有两个独立`gpu:1` Slurm作业会各占一张卡，调度器不会自动把它们塞到同一卡；跨manifest同时运行尚未实现/实测，而且当前probe每次自建两GPU服务，没有外部endpoint CLI，因此不声称并发共卡可用。不改已有launcher/作业，不预设2–3进程/卡吞吐。
