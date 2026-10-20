"""Full-route regressions: clear endpoints do not establish a clear route."""
import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.v5_grasp_route import sweep_route, separate_target_points, approach_route


class PoseScreen:
    def __init__(self, forbidden=None):
        self.forbidden = forbidden

    def check(self, xyz, quat):
        valid = self.forbidden is None or not self.forbidden(xyz)
        return {'solution_found': valid, 'source': 'test_public_proprioception'}


def geometry():
    return {'boxes': [{'name': 'hand', 'lower': [-.01]*3, 'upper': [.01]*3}]}


def route():
    return [{'phase': 'route_contact', 'xyz': [.2,0,1],
             'body_quat_xyzw': Rotation.identity().as_quat().tolist()}]


def test_thin_obstacle_between_clear_endpoints_rejects_swept_route():
    valid, result = sweep_route([0,0,1],[0,0,0,1],route(),np.array([[.1,0,1]]),
                               np.empty((0,3)),geometry(),pose_screen=PoseScreen())
    assert valid is False
    assert result['reason']=='approach_sweep_collision'
    assert 0 < result['segments'][0]['collision']['fraction'] < 1


def test_blocked_route_is_rejected_before_running_ik():
    class NoIK:
        def check(self, xyz, quat):
            raise AssertionError('a blocked route does not need IK')

    valid, result = sweep_route([0,0,1],[0,0,0,1],route(),np.array([[.19,0,1]]),
                               np.empty((0,3)),geometry(),pose_screen=NoIK())
    assert not valid
    assert result['reason'] == 'approach_sweep_collision'


def test_intermediate_ik_failure_rejects_reachable_endpoints():
    valid, result = sweep_route([0,0,1],[0,0,0,1],route(),np.empty((0,3)),
                               np.empty((0,3)),geometry(),
                               pose_screen=PoseScreen(lambda xyz:.07<xyz[0]<.13))
    assert valid is False
    assert result['reason']=='approach_route_ik_not_found'


def test_execution_uses_only_screened_waypoints_and_includes_contact_endpoint():
    valid, result = sweep_route([0,0,1],[0,0,0,1],route(),np.empty((0,3)),
                               np.empty((0,3)),geometry(),pose_screen=PoseScreen())
    assert valid is True
    assert result['execution_waypoints'][-1]['xyz']==[.2,0,1]
    assert result['execution_waypoints'][-1]['contact_endpoint'] is True
    assert len(result['execution_waypoints'])==len(result['segments'][0]['ik_checks'])


def test_neighbour_within_old_carving_radius_is_kept_as_obstacle():
    target = np.array([[0., 0., 1.]])
    scene = np.array([[0., 0., 1.], [0., 0., 1.005]])
    _, obstacles = separate_target_points(target, scene)
    assert np.allclose(obstacles, [[0., 0., 1.005]])


def test_scene_voxel_cannot_merge_target_pixel_and_adjacent_obstacle():
    target = np.array([[.0001, 0., 1.]])
    scene = np.array([[.0001, 0., 1.], [.002, 0., 1.]])
    _, obstacles = separate_target_points(target, scene)
    assert np.allclose(obstacles, [[.002, 0., 1.]])


def test_surface_opposition_cache_keeps_new_pose_routes_and_all_results(monkeypatch):
    import robots.libero.v5_geometric_grasp as geometric
    from robots.libero.v5_grasp_route import sample_unified_grasps
    grid=np.linspace(-.02,.02,17)
    cloud=np.array([[x,y,z+.9] for x in grid for y in grid for z in grid
        if abs(x)==.02 or abs(y)==.02 or abs(z)==.02])
    hand={'boxes':[{'name':name,'lower':[-.003,-.01,.01],'upper':[.003,.01,.03]}
                   for name in ('left_pad','right_pad')]}
    arguments=(cloud,np.empty((0,3)),'box',[0.,0.,1.2],[0.,0.,0.,1.],hand,None,1.2)
    cache={}
    sample_unified_grasps(*arguments,candidate_only=True,opposition_cache=cache)
    assert cache
    moved=(*arguments[:3],[.1,.05,1.1],*arguments[4:])
    expected=sample_unified_grasps(*moved,candidate_only=True)
    monkeypatch.setattr(geometric,'_opposition',lambda *_: (_ for _ in ()).throw(AssertionError('surface recomputed')))
    actual=sample_unified_grasps(*moved,candidate_only=True,opposition_cache=cache)
    assert actual==expected
    assert any('route' in row for row in actual[1])


def test_side_route_can_rotate_at_lower_pregrasp_without_assuming_high_wrist_reachable():
    start_quat = [1.,0.,0.,0.]
    side_quat = Rotation.from_euler('y', np.pi/2).as_quat().tolist()
    path = approach_route([0,0,1.2], start_quat, [.2,0,.95], side_quat,
                          'side_1', [.05,0,.95], 1.2, orient_at_pregrasp=True)
    assert path[1]['body_quat_xyzw'] == start_quat
    assert path[2]['body_quat_xyzw'] == start_quat
    assert path[3]['phase'] == 'route_orient_at_pregrasp'
    assert path[3]['xyz'] == path[2]['xyz']
    assert path[3]['body_quat_xyzw'] == side_quat
    assert path[-1]['phase'] == 'route_contact'
    valid, evidence = sweep_route([0,0,1.2], start_quat, path, np.empty((0,3)),
        np.empty((0,3)),geometry(),pose_screen=PoseScreen())
    assert valid is True
    assert any('route_orient_at_pregrasp' in w['phase'] for w in evidence['execution_waypoints'])


def test_distal_pad_placement_retains_observed_flanks_and_clears_low_support():
    from robots.libero.v5_geometric_grasp import collision_counts
    from robots.libero.v5_grasp_route import sample_unified_grasps

    # Two measured vertical faces of a thin object above a support plane.
    cloud = np.array([[x, y, z] for x in (-.02, .02)
        for y in np.linspace(-.015, .015, 31) for z in np.linspace(.005, .018, 15)]
        + [[x, y, z] for y in (-.015, .015)
        for x in np.linspace(-.02, .02, 41) for z in np.linspace(.005, .018, 15)])
    pads = [{'name': name+'_pad', 'lower': [-.004, -.008, -.0116],
        'upper': [.004, .008, .0044], 'slide_per_half_opening': [sign, 0., 0.]}
        for name, sign in (('leftfinger', -1.), ('rightfinger', 1.))]
    fingers = [{'name': name, 'lower': [-.004, -.008, -.0445],
        'upper': [.004, .008, .00925], 'slide_per_half_opening': [sign, 0., 0.]}
        for name, sign in (('leftfinger', -1.), ('rightfinger', 1.))]
    hand = {'boxes': [*pads, *fingers]}
    _, rows = sample_unified_grasps(cloud, np.empty((0, 3)), 'box',
        [0., 0., .3], [1., 0., 0., 0.], hand, None, .3, candidate_only=True)
    catalog = {row['id']: row for row in rows if not row['rejected']}
    table = np.array([[x, y, 0.] for x in np.linspace(-.08, .08, 81)
        for y in np.linspace(-.08, .08, 81)])
    recovered, edge_recovered = [], []
    for cid, row in catalog.items():
        if not cid.endswith('_top_distal_pad'):
            continue
        centred = catalog[cid.removesuffix('_distal_pad')]
        site = Rotation.from_quat(row['body_quat_xyzw']).as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
        patch_centre = np.mean(row['measured_contact_patch_centres_xyz'], axis=0)
        np.testing.assert_allclose(np.asarray(row['xyz'])+site@row['pad_contact_local_xyz_m'], patch_centre)
        assert row['route'][-1]['xyz'] == row['xyz']
        assert row['route'][-2]['xyz'] == row['approach_xyz']
        assert row['measured_contact_patch_centres_xyz'] == centred['measured_contact_patch_centres_xyz']
        before = collision_counts(table, centred['xyz'], site, hand, .08, clearance_m=.004)
        after = collision_counts(table, row['xyz'], site, hand, .08, clearance_m=.004)
        if any(before.values()) and not any(after.values()):
            recovered.append(cid)
        edge = catalog[cid+'_edge_cell']
        np.testing.assert_allclose(np.asarray(edge['xyz'])+site@edge['pad_contact_local_xyz_m'], patch_centre)
        # A slightly higher measured support can block the old distal
        # placement while the additional pad-face cell remains clear.
        old_blocked, edge_blocked = False, False
        for opening in np.linspace(.08, 0., 9):
            old_counts = collision_counts(table+[0., 0., .001], row['xyz'], site,
                hand, opening, clearance_m=.004)
            new_counts = collision_counts(table+[0., 0., .001], edge['xyz'], site,
                hand, opening, clearance_m=.004)
            old_blocked |= any(old_counts.values())
            edge_blocked |= any(new_counts.values())
        if old_blocked and not edge_blocked:
            edge_recovered.append(cid)
    assert recovered, 'a supported distal contact must survive without deleting support pixels'
    assert edge_recovered, 'the new pad-face cell must clear support that blocks the former sample'


def test_side_band_sampling_recovers_measured_flanks_missing_from_primary_seeds(monkeypatch):
    from robots.libero.v5_grasp_route import sample_unified_grasps

    # The original centroid/top seeds need not hit a narrow side feature.
    # Its two observed faces remain subject to the original normal test.
    cloud = np.array([[x, y, z] for x in (-.02, .02)
        for y in np.linspace(-.018, .018, 37) for z in np.linspace(.9, .96, 61)])
    monkeypatch.setattr('robots.libero.v5_grasp_geometry.measured_grasp_regions', lambda *args:
        ({'points': cloud, 'seeds': [np.array([.2, 0., .93])],
          'closing_axis_xy': np.array([1., 0.]), 'top_z': .96}, {}))
    pads = [{'name': name + '_pad', 'lower': [-.004, -.008, -.0116],
        'upper': [.004, .008, .0044], 'slide_per_half_opening': [sign, 0., 0.]}
        for name, sign in (('leftfinger', -1.), ('rightfinger', 1.))]
    _, rows = sample_unified_grasps(cloud, np.empty((0, 3)), 'unseen object',
        [0., 0., 1.2], [1., 0., 0., 0.], {'boxes': pads}, None, 1.2, candidate_only=True)
    assert all(row['rejected'] for row in rows if row['id'].startswith('s0_'))
    recovered = [row for row in rows if not row['rejected']]
    assert recovered
    assert all(min(row['normal_quality']) >= .65 for row in recovered)
    assert all(row['width_m'] + .008 < .08 for row in recovered)
    assert all(row['route_status'] == 'not_screened' for row in recovered)


def test_successful_primary_sampling_does_not_expand_catalogue(monkeypatch):
    from robots.libero.v5_grasp_route import sample_unified_grasps

    cloud = np.array([[x, y, z] for x in (-.02, .02)
        for y in np.linspace(-.018, .018, 37) for z in np.linspace(.9, .96, 61)])
    def unexpected(*args):
        raise AssertionError('primary observed flanks already suffice')
    monkeypatch.setattr('robots.libero.v5_grasp_geometry.measured_band_seeds', unexpected)
    pads = [{'name': name + '_pad', 'lower': [-.004, -.008, -.0116],
        'upper': [.004, .008, .0044], 'slide_per_half_opening': [sign, 0., 0.]}
        for name, sign in (('leftfinger', -1.), ('rightfinger', 1.))]
    _, rows = sample_unified_grasps(cloud, np.empty((0, 3)), 'unseen object',
        [0., 0., 1.2], [1., 0., 0., 0.], {'boxes': pads}, None, 1.2, candidate_only=True)
    assert any(not row['rejected'] for row in rows)
