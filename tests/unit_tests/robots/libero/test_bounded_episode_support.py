"""A pi-first continuation must not redefine the original support as midair."""
from types import SimpleNamespace
from scripts.probe_bounded_hybrid_d2 import grasp_trial_reference

def test_original_support_is_reused_without_replacing_current_grip_pose():
    current={'original_support_plane_z_m':None,'original_support_plane_evidence':{'support_geom_ids':[]},
        'support_proxy_source':'midair_unknown','relative_com_tcp':[.01,0.,0.],'tcp_xyz':[0.,0.,1.2]}
    origin={'original_support_plane_z_m':.9,'original_support_plane_evidence':{'support_geom_ids':[17]},
        'support_proxy_source':'episode_initial_contacts','relative_com_tcp':[.5,.5,.5]}
    facade=SimpleNamespace(grasp_reference=lambda _:dict(current),_episode_initial_grasp_supports={'bowl':origin})
    result=grasp_trial_reference(facade,'bowl')
    assert result['original_support_plane_z_m']==.9
    assert result['original_support_plane_evidence']=={'support_geom_ids':[17]}
    assert result['relative_com_tcp']==current['relative_com_tcp'] and result['tcp_xyz']==current['tcp_xyz']
    assert current['original_support_plane_z_m'] is None
    assert result['original_support_plane_evidence'] is not origin['original_support_plane_evidence']

def test_normal_episode_reference_is_unchanged_without_a_registered_origin():
    current={'original_support_plane_z_m':.9,'relative_com_tcp':[0.,0.,0.]}
    assert grasp_trial_reference(SimpleNamespace(grasp_reference=lambda _:current),'bowl')==current
