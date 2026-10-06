# 抽屉公开深度窗口缺陷（CPU，未冻结）

4254 t0/init10 的公开父实体 AABB 包含已打开抽屉，正面最大y约-0.063m；RGB-D固定柜框平面约-0.218m。旧固定框的depth窗口只围绕最大front extent±2.5cm，完全错过固定frame。动作后关闭面也在旧moving窗口edge-3cm之外。

只把深度搜索改为已测parent AABB范围，原拟合点数、plane法向、frame宽高、current-part±5mm绑定与融合/稳定规则不变，可从同两次公开capture恢复before/after fixed frame与moving face。原before/after未知判定不覆盖，私有关节/谓词没有参与这次推断。原front_axis未序列化，本次用公开moving-plane normal与部件相对parent位置推断方向，不能声称逐字复用了运行时axis；轴约[.0017,.999999]。

运行时新增drawer_bounds_depth_v5默认off，仅在current-part binding存在时生效，下一步还需扩大公开记录复算和原版物理验证；不授新确认/冻结。33项相关CPU检查通过。
