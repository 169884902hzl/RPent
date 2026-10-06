"""Freeze a twenty-cell original off-skill development design, not qualification."""

import hashlib
import json
from pathlib import Path


def main():
    root=Path('/home/agilex/cobot_magic/rpent_libero_eval')
    remote=Path('/public/home/sunyihan/rpent_libero_eval')
    packet=Path(__file__).resolve().parent
    source_manifest=root/'results/harness_v5/stove555_fixed_prefix_CPU_20261006/stove_control_sampling10.json'
    data=source_manifest.read_bytes()
    if hashlib.sha256(data).hexdigest()!='50fef3327c6d264d19a911ea5f3bd86807c683dab9bbbf25d4e9042874d83597':
        raise ValueError('original state/source manifest changed')
    old=json.loads(data)
    methods=[
        {'id':'literal_off','off_prompt':'turn off the stove','public_contact_refinement':False},
        {'id':'paraphrase_off','off_prompt':'switch off the stove','public_contact_refinement':False},
        {'id':'complete_knob_off','off_prompt':'turn the stove knob all the way to the off position','public_contact_refinement':False},
        {'id':'measured_complete_knob_off','off_prompt':'turn the stove knob all the way to the off position','public_contact_refinement':True},
    ]
    for method in methods:
        method['off_prompt_sha256']=hashlib.sha256(method['off_prompt'].encode()).hexdigest()
        method['prompt_origin']='Developer authored generic instruction, no PRO/user/sealed text; literal inherited from original on/off diagnostic'
    cells=[]
    for case in old['cases'][:5]:
        for method in methods:
            cells.append({'name':case['name']+'__'+method['id'],'original_case':case,'method':method['id'],
                          'on_prompt':'turn on the stove','off_prompt':method['off_prompt'],
                          'public_contact_refinement':method['public_contact_refinement'],
                          'preserve_on_setup_failure_and_continue_fixed_off':True})
    plan={'version':'original-stove-off-physical-development/1-plan',
          'scope':'Twenty paired developer selection cells, five original Goal7 init0-4 times four conditions. Not independent confirmation or 100-cell qualification',
          'original_sampling_manifest':{'path':str(remote/source_manifest.relative_to(root)),
                                        'sha256':hashlib.sha256(data).hexdigest()},
          'original_case_count':5,'paired_cells':20,'methods':methods,'cells':cells,
          'source_root':str(remote/'source_v5_stove555_20261006'),'source_sha256':old['required_source_sha256'],
          'base_config':old['base_config'],'budget':old['budget'],'full_chunk_diagnostic_scope':True,
          'phase_order':['on','off'],'fixed_on_chunks':160,'fixed_off_chunks':160,'actions_per_chunk':5,
          'native_original_goal_is_on':'Preserve original native success labels; ignore them only inside the already bounded off diagnostic scope',
          'public_refinement':{'inputs':'Current original RGB-D, measured shell and control geometry; dual main/wrist views, no private qpos or object coordinates',
                               'source_preference':'Current accepted original SAM control geometry; otherwise explicitly report missing and keep the fixed literal VLA contact test',
                               'approach':'Stage above current measured contact patch with existing 0.15m standoff; wrist refinement from a new capture; no contact-servo endpoint inferred from private qpos',
                               'missing_or_ambiguous':'Preserve a public refinement_unmeasured receipt; execute the same fixed complete_knob_off prompt for all160 chunks, with no private fallback',
                               'comparison':'complete_knob_off vs measured_complete_knob_off isolates added public refinement; other prompt arms compare wording at unchanged budget'},
          'private_scoring':{'collection':'Read original oracle.skill501_truth for on and off once before each fixed phase and after every completed five-action chunk, writing separate labels_chunk.jsonl only',
                             'stored_fields':['cell','phase','chunk_index','actual_controls','joint_names','joint_qpos','turn_on_satisfied','turn_off_satisfied','sim_time'],
                             'controller_access':False,'affects_actions':False,'affects_stop':False,'affects_binding':False,
                             'capture_final_before_and_after_recovery':True,
                             'diagnostics':'Joint vs chunk reveals first movement, stall/reversal, and whether recovery changes the endpoint; no direct endpoint threshold is fitted'},
          'public_trace':{'stored_fields':['cell','phase','prompt','chunks','executed_actions','eef_position','gripper_opening','measured_contact_ref','measured_approach_residual','raw_native_success','external_truncation'],
                          'no_private_joint_field':True},
          'analysis':['Paired true_off completion per original init and method','On setup stratum reported after collection; all cells retained',
                      'Joint private scoring trajectories and reversal/stall categories','Public measured-contact coverage and approach residual',
                      'Actual160x5 controls or exact execution/infrastructure failure, never counted as model score'],
          'implementation':{'GPU_submission_ready':False,'status':'Explicit development design; chunk-private-score writer and immutable launcher still to be implemented by owner',
                            'owned_server_extension':'StoveProbeFacade.chunk_step: append private q/predicate score after inherited completed chunk, discard score from returned public observation',
                            'owned_driver_extension':'Original run_phases: select fixed off prompt from manifest; optionally call existing stage_fixture_handle before fixed VLA contact',
                            'shared_runtime_functions_to_modify':[],'shared_verifier_functions_to_modify':[]},
          'no_PRO_read':True,'no_simulator_started':True,'no_GPU_submitted':True,'no_new_training_rows':True,
          'endpoint_state':'unmeasured','qualification_authorized':False,'node_binding':None,
          'planned_output_root':str(remote/'results/harness_v5/stove564_off20_original_20261006')}
    (packet/'off20_development_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({'cells':20,'paired_original_states':5,'GPU_submission_ready':False,
                      'manifest_sha256':hashlib.sha256((packet/'off20_development_plan.json').read_bytes()).hexdigest()}))


if __name__=='__main__':main()
