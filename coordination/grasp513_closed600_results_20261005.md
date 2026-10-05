# Codex3：完整抓取600次统计与公共灶台测量模块

3616四片全完成，3619瓶/碗全完成，600/600 choices SHA一致、真值已知、execution_error0。锅四探索臂各100：name160 83（Wilson74.45–89.11%）/一致100%；handle160 65（55.25–73.64%）/98%；name320 84（75.58–89.90%）/99%；handle320 66（56.28–74.53%）/99%。各pan臂50唯一状态各reset两次，Wilson使用名义试次数、有相关性；不能授确认。handle两臂各16次未测到把手，前置拒绝保留分母。

3619瓶96/100（Wilson90.2–98.4%），一致97%，FP2/4真阴性、FN1/96真阳性；碗98/100（93.0–99.4%），一致97%，FP1/2、FN2/98。各100唯一tuple和state SHA，无重复。六类尚不完整、pan尚不达标；保持NO-GO。报告 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp_complete3616_3619_CPU_20261005/report/report.json` SHA37d95fd22d585774ad9895a48c45723ac264b3186e658d373159373db9de13e0，源码commit9c8dfaf。

公共灶台模块commit151551f，18 focused tests通过；原版10组turn_on真实RGB-D selection smoke前0/10、后10/10，未有关闭/失败独立确认。模块SHA5e7b9be7edca82700fe5503a302ee67ba08d27110d85a3e6baa4f7f841937482；完整smoke报告SHA1017deeb4fe02acb7539c17b3bc18dc97912dba885132688b3f162743d90d4b4，目录skill504_regression_memory_CPU_20261005/stove_module_smoke/。on凭可见红线圈支持；off需原已测on anchors真实可见且红消失，缺测/遮挡为unmeasured；不读仿真关节控制。还不能宣称95%一致率。
