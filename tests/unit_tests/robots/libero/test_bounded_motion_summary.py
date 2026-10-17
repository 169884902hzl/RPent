"""Controller-independent errors from the recorded public motion stream."""
import pytest

from scripts.summarize_bounded_probes import common_path_errors


def test_path_error_uses_segments_and_the_same_prescribed_corner():
    record = {'waypoints': [{'xyz_m': [1., 0., 0.]}, {'xyz_m': [1., 1., 0.]}],
        'trace': [
            {'before': {'eef_xyz_m': [0., 0., 0.]}, 'after': {'eef_xyz_m': [.5, .1, 0.]}},
            {'after': {'eef_xyz_m': [.8, .7, 0.]}},
            {'after': {'eef_xyz_m': [1., .95, 0.]}},
        ]}
    result = common_path_errors(record)
    assert result['max_path_deviation_m'] == pytest.approx(.2)
    assert result['rms_path_deviation_m'] == pytest.approx((.05/4)**.5)
    assert result['final_endpoint_error_m'] == pytest.approx(.05)


def test_path_error_handles_a_repeated_waypoint_without_claiming_an_empty_trace():
    record = {'waypoints': [{'xyz_m': [0., 0., 0.]}, {'xyz_m': [1., 0., 0.]}],
        'trace': [{'before': {'eef_xyz_m': [0., 0., 0.]}, 'after': {'eef_xyz_m': [.4, 0., 0.]}}]}
    assert common_path_errors(record)['max_path_deviation_m'] == 0.
    assert common_path_errors(record)['final_endpoint_error_m'] == pytest.approx(.6)
    assert common_path_errors({'trace': []}) == {}
