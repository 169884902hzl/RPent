# 4335 node01 停写的只读接入诊断

node01 与 node02 使用相同 SSH 参数执行 `/bin/hostname`，认证细节已脱敏。node01 TCP连接、SSH banner、KEX、SERVICE_ACCEPT成功，但在offer public key后15秒超时，未完成认证，也未发送命令。node02 0.868秒完成认证/执行，返回node02。

因此不能由这次SSH超时推断GPU driver故障；阻塞发生在认证阶段，可能是服务端authorized_keys/home访问或PAM。只读证据不足以最终区分它们。node01两片动作记录同秒停写提供了共同基础设施问题的线索，但不能证明同一根因。

未取消作业、未reset GPU、未修改SSH/PAM/NFS服务、未读取凭据/key material。详细JSON和脱敏日志保留，已交root处理；两局不当作模型物理失败。
