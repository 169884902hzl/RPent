# Codex3：3630 JSON计量修复后开发smoke预回执

接受12:20交接；已核对3630全部五片，均因numpy snapshot JSON失败退出，原产物保留。修复只把数组完整转list、scalar转item，不删证据，未知类型/非有限数仍报错。30 focused tests通过。原smoke额外证据：part0/1没有可证明动作，part2抽屉setup方向/已满足判据需定位，part3私有放置成功而公共判false，part4锅公共判抓起但持续夹持真值false。都不宣称技能达标。

独立源码 `/public/home/sunyihan/rpent_libero_eval/source_v5_skill511_json_repaired_20261005`，commit `ab33e3fe7bf5a1daaf7e8f22ab96147dc6abb75d`，archive SHA `a6f590c16bc884c5237bb331d2f7bc66ac7af45d847550e74e1199f88fe98c05`。包括JSON修复ecb5849及私有无名geom接触修复，不改旧source。新smoke保持20原请求/原arm/原预算，开发允许修复复跑，非确认或模型成绩。三个manifest逐字节同506，SHA4b41dd0ce72b7694a20d0e1c95f299ac1caab77ae5f798ae0e3893cc11c65c37 / 37d3eac254090f553b9854846b922b359e3f83118626e3c0d18fcb2561c672c1 / 4ec7550ae488c9a77d3cf52694a8ad4ce49a8624478fc14db3b583e145163b02。

先push本回执并写远端COORD，再提交 `sbatch --parsable scripts/run_v5_skill511_json_repaired_smoke.sbatch`。array0–4%8，1GPU/片，不设依赖或节点绑定，Slurm用空卡启动。输出 `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill511_json_repaired_smoke_20261005/smoke_job<jobid>/part0–4`。实际入口source目录中repo.venv/bin/python -u -m scripts.probe_v5_skill501_original；jobid返回立即登记。未冻结、未提交训练，无异议。
