# 4235 三方法 × 同5状态抽屉选择批

15/15记录已齐，5片COMPLETED 0:0，最后结束 2026-10-06 15:10:30 UTC。原版 LIBERO-90 t6，init10–14，同5个raw状态配对；没有重跑确认批或改判。

| 方法 | 私有端点新完成 | Wilson95 | 公共true / false / null | VLA controls |
|---|---:|---:|---:|---:|
| native_original160 | 5/5 | 56.55–100.00% | 0 / 4 / 1 | 4000/4000 |
| stage_original160 | 2/5 | 11.76–76.93% | 0 / 3 / 2 | 4000/4000 |
| stage_reordered160 | 0/5 | 0.00–43.45% | 0 / 5 / 0 | 4000/4000 |

原句为 `open the bottom drawer of the cabinet`；旧重排句为 `open the cabinet bottom drawer`。相同原句加脚本stage后5→2（3个a-only、0个b-only）；相同stage把原句重排后2→0（2个a-only、0个b-only）。这5例支持接近与语序都影响接触结果；不能推广成达到行业门槛。

全部private-before=false。每例160完整chunks、800controls，三方法共12000/12000 VLA controls；短块0、无native或external截断、无private joint/predicate控制。非VLA接近/恢复计数另列在审计，不算VLA步数。

公共验证器没有一次true：7个私有真端点中4次false、3次null（moving_face_or_static_frame_not_measured）；其余8次为TN。测量分母下recall0/4，全已知真值分母下一致率8/15；null保留。不得把私有成功覆盖公共回执。

| init | native joint/公共延伸 | stage原句 joint/公共延伸 | stage重排 joint/公共延伸 |
|---|---|---|---|
| 10 | -0.159873 m / 0.63 cm (False) | 0.001603 m / 0.24 cm (False) | 0.001656 m / 0.2 cm (False) |
| 11 | -0.159915 m / 0.63 cm (False) | -0.159887 m / None cm (None) | 0.000000 m / 0.13 cm (False) |
| 12 | -0.159977 m / 0.61 cm (False) | 0.001652 m / 0.02 cm (False) | 0.000000 m / 0.03 cm (False) |
| 13 | -0.159884 m / None cm (None) | -0.013735 m / 1.39 cm (False) | 0.000000 m / 0.01 cm (False) |
| 14 | -0.159890 m / 0.73 cm (False) | -0.159998 m / None cm (None) | 0.001649 m / 0.02 cm (False) |

native的4次公共false均将约16cm私有关节位移测成小于1cm的moving-face延伸；整体实体回执与独立几何端点证据均保存。疑似打开后moving-face关联到了原静态柜面，仍需在独立源码开发中定位，不调整当前结果阈值。

源码 `/public/home/sunyihan/rpent_libero_eval/source_v5_pan556_20261006`，commit `d8b1d980603e6e0e8f7e14f9541c01f7686c7673`。source和manifest未改；原report SHA256 `f3392d5a78e9dcf7623e8601c33ff4ce37908aa4a545a62afbbf29490a838fd0`。
