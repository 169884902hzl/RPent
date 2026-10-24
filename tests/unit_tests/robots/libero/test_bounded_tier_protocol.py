"""Tiered panels keep task identities and the final-seed exclusion explicit."""
from robots.libero.bounded_task_board import classify, next_level, write_board


def test_task_promotion_is_not_episode_filtering(tmp_path):
    assert next_level(5,4)==10 and next_level(10,9)==20 and next_level(20,19) is None
    assert classify(5,3,5)==('修复中','技能/感知/执行')
    assert classify(5,4,3)==('修复中','模型选择（Codex2）')
    task={'panel':'development','panel_task_id':'bowl','category':'bowl'}
    result=[{'panel_task_id':'bowl','line':method,'success':index<4,'status':'physical_result','source_commit':'frozen'}
        for method in ['oracle','model'] for index in range(5)]
    row=write_board(tmp_path,[task],result)[0]
    assert row['oracle_n']==5 and row['oracle_success']==4 and row['status']=='已升级'
    assert len((tmp_path/'task_board.jsonl').read_text().splitlines())==1
    assert row['task_key']=='bowl' and row['oracle_A_successes']==4
    assert row['n']==5 and row['line_n']['model']==5 and row['training_admission'] is False


def test_pro_development_does_not_admit_final_seeds(monkeypatch):
    import pytest
    import robots.libero.bounded_hybrid_diagnostic as h
    monkeypatch.setattr(h,'_pro_session',lambda episode,budget:episode)
    for seed in range(40,45):
        assert h.pro_development_session({'suite':'libero_goal_swap','task':0,'seed':seed})['seed']==seed
    for seed in range(5):
        with pytest.raises(ValueError):
            h.pro_development_session({'suite':'libero_goal_swap','task':0,'seed':seed})
    with pytest.raises(ValueError):
        h.validate_d2_episode({'suite':'libero_goal_swap','task':0,'seed':41})
