"""The evaluation contrasts change one factor and preserve actual inputs."""
from types import SimpleNamespace

from scripts.probe_bounded_option_ceiling import PromptOverride, factor_budget


def test_prompt_contrast_changes_wire_and_predict_identically_without_mutating_image():
    seen=[]
    client=SimpleNamespace(encode_obs=lambda obs:dict(obs),
        predict=lambda obs,options=None:seen.append((obs,options)))
    image=object();obs={'task_descriptions':'original','image':image,'state':[1,2]}
    wrapper=PromptOverride(client,'A1 wording')
    encoded=wrapper.encode_obs(obs)
    wrapper.predict(obs,{'sampling_seed':123})
    assert encoded==seen[0][0]
    assert encoded['task_descriptions']=='A1 wording' and encoded['image'] is image
    assert obs['task_descriptions']=='original' and seen[0][1]=={'sampling_seed':123}


def test_primitive_contrast_shares_budget_arm_and_prompt_contrast_keeps_original_budget():
    baseline={'blocks':104,'no_progress_blocks':5,'max_controls':520,
        'controls_per_check':None,'minimum_progress_m':.005}
    params={'max_chunks':30}
    assert factor_budget('baseline',baseline,params)==factor_budget('a1_prompt_only',baseline,params)
    a=factor_budget('a1_budget_only',baseline,params)
    b=factor_budget('a1_primitive',baseline,params)
    assert a==b and a.blocks==30 and a.no_progress_blocks is None
    assert baseline['no_progress_blocks']==5 and baseline['max_controls']==520
