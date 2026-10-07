# 灶台三 train 态 off320 时序模型开发归档

三态全部为注册 train state；val3/4 未读取。公开 RGB-D / 本体感知特征先编码，再打开私有关节标签。固定 300 epoch、seed577、MLP32、AdamW；没有阈值搜索、val早停或运行时停止准入。

960 块末端样本：114 正、840 负、6 unknown；unknown 不作负样本。训练内 954 条：TP113 / FP3 / FN1 / TN837，AUROC 0.999875、精确率 0.974138、召回率 0.991228。按原始 train state 留一：TP75 / FP90 / FN39 / TN750，AUROC 0.861325、精确率 0.454545、召回率 0.657895，Brier 0.109984。留一泛化明显不足，独立确认资格 pending，stop=false。

所有帧相关，不把954帧当独立物理试次。报告中的 Wilson 为描述性帧级区间，不能替代按独立状态的确认门槛。

输入 / 数据 / 模型逐文件身份见 manifest.json 与 copied_files.json。源码 commit 2528b3590d9dfaf3acce22fa6e2c32244d2fe5d2。模型 SHA256：98008807eb41dc27e6c8e883d93c05778ae1def7b1b5a1dc7839828f18821c10。

三个物理回合均曾达到关火端点后又退回，最终全部未关火。这份开发模型尚不能作为终点停止器。保留全部数据与失败。
