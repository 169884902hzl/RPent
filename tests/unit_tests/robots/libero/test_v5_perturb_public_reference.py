from scripts.v5_perturb_public_reference import source_reference


def test_layout_reference_tracks_swapped_objects_and_contains_no_coordinates():
    names = {'a': 'bowl', 'b': 'bowl', 'c': 'bowl'}
    geometry = {'a': [-.2, 0, .9], 'b': [0, 0, .9], 'c': [.2, 0, .9]}
    axes = ((1, 0, 0), (0, 1, 0))
    assert source_reference('a', geometry, axes, names) == 'the bowl at the left'
    geometry['a'], geometry['c'] = geometry['c'], geometry['a']
    assert source_reference('a', geometry, axes, names) == 'the bowl at the right'
    assert source_reference('b', geometry, axes, names) == 'the middle bowl'


def test_unclear_reference_is_rejected_before_policy_execution():
    names = {'a': 'bowl', 'b': 'bowl'}
    geometry = {'a': [0, 0, .9], 'b': [.01, .01, .9]}
    assert source_reference('a', geometry, ((1, 0, 0), (0, 1, 0)), names) is None
    assert source_reference('a', geometry, ((1, 0, 0), (0, 1, 0)), {'a': 'bowl', 'b': 'cup'}) == 'the bowl'
