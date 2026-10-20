# M7 原版220 schema6：bcc22412 版本闭合

2966 个父请求全部闭合，24 片退出码均为 0；0 错误、0 RPC、0 仿真步。
5488 个前缀位置，4923 个有效；保留源 status 后可用 4439，旧 2414，增加 2025。
可用位置包括 train 3248、init_holdout 798、task_holdout 393，不将留出集计入训练。
本版固定 bcc22412；当前 oracle 恢复修复后另采新版，旧原件不覆盖。
VLA 选项均 unknown，无物理成功标签；PRO、D2、确认状态未采。

| 类别 | 旧可用 | 新有效 | 源身份可用 | 差值 |
|---|---:|---:|---:|---:|
| bowl_transfer | 31 | 195 | 195 | +164 |
| box_transfer | 28 | 213 | 172 | +144 |
| container | 21 | 168 | 162 | +141 |
| cup_transfer | 81 | 488 | 396 | +315 |
| drawer_close | 319 | 470 | 466 | +147 |
| drawer_open | 116 | 232 | 221 | +105 |
| microwave_close | 123 | 280 | 218 | +95 |
| microwave_open | 157 | 516 | 343 | +186 |
| plate_push | 1462 | 1892 | 1873 | +411 |
| stove_off | 66 | 347 | 299 | +233 |
| stove_on | 10 | 122 | 94 | +84 |

源码：`bcc224124b3cc9ac5b85a4823035876359c8028d`。
逐位置：`/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/schema6_20261020/cpu/M7_bcc22412_closed_r1/positions.jsonl.gz`。
逐位置 SHA256：`8fb0b7694e205e3590e9ce3aa4abcd90247494f96dc0fe9912b028a5bf4bdcf0`。
聚合 manifest 与逐片输入哈希：同目录 `manifest.json`。
父索引 SHA256：`787fa248f126b73b141703f53e62ab948f6743ab5217416afe7a57999f7b8e26`。
模型侧接入仍须重算新请求跨 split 别名。新 B2 目录尚未获三端同步 ACK，保持关闭；新增候选遇到旧标签一律 unknown。
