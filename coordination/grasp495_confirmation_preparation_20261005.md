# Codex3：剩余两类独立确认入口已完成（未采样）

新增prepare_v5_grasp495_remaining_confirmation.py，复用grasp492/487的固定discovery与pool身份。接受显式recipe JSON、recipe SHA、探索报告SHA，报告只核字节身份、不看分数自动选赢家。每类100预留原版LIBERO90官方init10–39，生成前复核tuple/raw state SHA与3550零重合、类内唯一及BDDL/init/单state SHA；失败不换状态。

当前没有正式pan/moka确认manifest，没有消费确认状态、没有新物理试次或Slurm。待3616/3620完整探索结果后先固定配方，再生成一次对应确认manifest。规则仍六类完整独立确认总体95%、每类90%、验证一致率95%，不拿探索结果补门槛。扩展原版90分布、跨类共享场景将披露，资格探针不入训练。

入口 --parent --pool --group {frypan,moka_pot} --recipe --recipe-sha256 --output。35 focused tests通过；脚本SHA85cb5ca0f8367c4828acfeca8f64e28f489b9bf4c31ed7f3fd62070ae4e0f761。不改probe、现有训练/评测格式或运行中的作业。
