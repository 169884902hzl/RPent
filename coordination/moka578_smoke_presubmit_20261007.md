# Codex3 摩卡壶转移原句＋公共放置验证开发冒烟预回执

用户已授权摩卡壶按原版完整子任务句单独作为转移技能。先在已访问选择池t19/init0–9测新公共放置验证，不计独立确认、不入训练。SOURCE571固定5da67d19及41afc849…；原句put the moka pot on the stove，SOURCE571 execute_subtask完整块，不以私有On真值停止；严格放置验证照常测量。注册10，所有失败/null保留。

8片真实/tmp CPU预检全部0，10状态原bytes核对、runner真实入口加载通过。manifest `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/moka_original_public_placement_visited10.json` SHA `259690ca59d4c021d9f1716761686b30a8b2648e58727b8c526f0151d7275294`；launcher SHA `c9f9333f551874d82999e5b30883fcffbb920c6011452ac2c17ad041d2fa033d`；准备commitf7519a4，完整handoff及producer SHA同目录。

当前4346占4卡、4349占剩4卡，等待技能资源，优先级nice1000高于interim nice10000，不取消或绕过运行中的作业。数组限流按当前空闲池规模4，无节点/依赖绑定。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/smoke10/job<id>/part0..7/probe`。实际号由sbatch回填。

```bash
sbatch --parsable --array=0-7%4 --export=ALL,MOKA_TRANSFER_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_drawer571_20261006,MOKA_TRANSFER_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007/preparation/moka_original_public_placement_visited10.json,MOKA_TRANSFER_MANIFEST_SHA=259690ca59d4c021d9f1716761686b30a8b2648e58727b8c526f0151d7275294 /public/home/sunyihan/rpent_libero_eval/scripts/run_v5_moka_transfer_public_smoke10_20261007.sbatch
```

其余五类保守汇总485/500=97.0%，Wilson95%95.11%–98.17%；验证器一致489/500=97.8%，Wilson96.10%–98.77%。两unknown保留，pan100请求含99unique＋1预登记repeat；这是不同来源确认的描述汇总，尚非新统一SOURCE确认。摩卡壶拆分确认60/100继续单列披露。旧转移95/100只证明On，不证明新放置验证一致率。
