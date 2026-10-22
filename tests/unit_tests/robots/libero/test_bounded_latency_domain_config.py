"""Mixed latency cohorts must select config paths before the suite import."""
import hashlib
import importlib.util
import os
from pathlib import Path

import pytest


def launcher():
    path=Path(__file__).resolve().parents[4]/'coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py'
    spec=importlib.util.spec_from_file_location('latency_domain_config',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('domain,expected',[('original','standard'),('d2','pro')])
def test_config_path_follows_episode_domain_not_parent_process(tmp_path,monkeypatch,domain,expected):
    plan={'libero_config_by_domain':{}}
    for name in ('original','d2'):
        path=tmp_path/name/'config.yaml';path.parent.mkdir();path.write_text(name+'_suite_root\n')
        plan['libero_config_by_domain'][name]={'path':str(path),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    monkeypatch.setenv('LIBERO_CONFIG_PATH',str(tmp_path/'wrong_inherited_config'))
    monkeypatch.setenv('LIBERO_TYPE','wrong_inherited_type')
    launcher().configure_libero_domain({'domain':domain},plan)
    assert os.environ['LIBERO_TYPE']==expected
    assert os.environ['LIBERO_CONFIG_PATH']==str(tmp_path/domain)


def test_changed_domain_config_is_rejected_before_simulator_import(tmp_path,monkeypatch):
    path=tmp_path/'config.yaml';path.write_text('changed\n')
    monkeypatch.setenv('LIBERO_TYPE','standard')
    with pytest.raises(ValueError,match='configuration changed'):
        launcher().configure_libero_domain({'domain':'d2'},
            {'libero_config_by_domain':{'d2':{'path':str(path),'sha256':'0'*64}}})
