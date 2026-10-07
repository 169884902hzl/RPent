# 腕部微波炉观察方案（CPU，只读）

腕部未贡献不只是SAM词或缺fixed anchor。4463原版task33/init0、source_step20的
腕图朝下看杯子，微波炉固定前壳仅在左上边缘；主视角则完整看到固定前壳与开门。
用保存的1024px公开相机metadata与主视角的两份独立测量云重投影，固定参照云只有
15.89%在腕部FOV内（中位u=-109.7，越界），门云74.93%在FOV。公开固定ROI在腕部
RGB-D能找到5033点，但z跨度不足现有vertical_face的4cm支持要求，不能直接用跨视角
anchor把该云变成合格平面。输入8文件逐项SHA已核对，analysis.py可按显式清单复算。

现有代码位置：v5_runtime.py::measure_fixture_endpoint先分割两个视角；固定query没
测到时交v5_fixture_parts.py::measured_microwave_frame，它要求可见独立门面/固定patch。
v5_verification.py::vertical_face对z跨度<0.04m返回None。这个例子wrist的固定SAM18帧
均零实例；门前4帧有实例，但fixed patch未建立，后14帧无实例。不要放宽平面支持
或用私有关节救缺测。SAM point接口是[row,col]，server转换[col,row]；本例没有证据
表明是点序错。

最小新开发移动：接触前保留实际当前姿态，先EEF上抬5cm，再向公开两个平面中心的
方向平移，先试当前位姿(+8,+10)cm（由观测计算，非任务配方）。此step20实际EEF为
(-0.18893,0.00349,1.17746)m，示例终点(-0.10893,0.10349,1.22746)m；代码实现应从
当前测量实时计算，不写死此例坐标。保存每段真实EEF终点与move返回；未达或接触
就保留缺测换观察点。纯相机同姿态平移几何预测这一步能让两云FOV均100%，但是
没有模拟新遮挡、臂姿可达或证明新视角深度有效，需真实单局。

在新位置采两个当前RGB-D视角。先要求腕部测得fixed patch>=4cm垂直支持及独立门
面，复核两个mask低重叠、实际robot clearance和机器人遮挡，间隔6个真实中性hold
再采第二帧。若仍缺fixed或door，回执仍unmeasured；不要直接将agentview拟合当成
wrist贡献。只读capture不改变任务目标。若确需cross-view anchor，必须在新的腕部
云中重新测出fixed plane，并保留相机来源，不能复制主视角plane写wrist标签。

观察移动改变控制轨迹，后续应加独立opt-in开发开关；本次只给方案，没有修改runtime
或提交GPU。先在已访问原版task33/init0作1局公开测量开发，预计实现与窄回归0.5–1h，
1GPU物理检查30–60min（SAM/撤臂主导）。合格后再与不移动的583作同状态方法选择。
private truth仅作after独立标签，不能选择观察点或停止；旧583/581/4463记录保持不变。
