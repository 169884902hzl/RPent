# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""An endpoint migration preserves all policy/environment inputs."""
import copy
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def launcher():
    root=Path(__file__).resolve().parents[4]
    path=root/'coordination/bounded_skills_20261016/scripts/run_ladder_selector_shard_20261025.py'
    spec=importlib.util.spec_from_file_location('selector_launch',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_sidecar_binding_preserves_source_budget_initials_and_weights(launcher):
    plan={'model_service':{'adapter_sha256':'abc','service_job':12318,'endpoint':'http://node02:18065/v1/bounded-choice',
        'presentation':'compact','decode_mode':'cached'},'source_commit':'frozen','jobs':[{'state_sha256':'initial'}],
        'budget':{'decisions':40,'sim_steps':10000,'wall_s':7200},'vla_budget':{'blocks':104,'max_controls':520}}
    before=copy.deepcopy(plan)
    updated=launcher.with_endpoint(plan,'http://127.0.0.1:12345/v1/bounded-choice',{'status':'ok','adapter_sha256':'abc'})
    assert plan==before
    assert {k:v for k,v in updated.items() if k not in {'model_service','model_line'}}=={k:v for k,v in plan.items() if k!='model_service'}
    assert updated['model_service']['adapter_sha256']==plan['model_service']['adapter_sha256']
    assert updated['model_service']['endpoint'].startswith('http://127.0.0.1:')
    assert updated['model_service']['reference_service_job']==12318


def test_sidecar_rejects_wrong_adapter_before_running_any_world(launcher):
    plan={'model_service':{'adapter_sha256':'registered'}}
    with pytest.raises(ValueError,match='adapter'):
        launcher.with_endpoint(plan,'http://127.0.0.1:12345/v1/bounded-choice',{'status':'ok','adapter_sha256':'other'})
