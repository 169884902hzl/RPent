import json

import numpy as np
import pytest

from rpent.utils.serialization import json_numpy_default


@pytest.mark.parametrize("flag", [True, False])
def test_physical_measurement_record_keeps_numpy_boolean_and_numbers(flag):
    # The moka trace and probe ledger include nested measurement/RPC evidence.
    record = {"receipt": {"place_verified": np.bool_(flag),
                          "opening": np.float64(.081)},
              "measurement": {"visible": np.bool_(True), "xyz": np.array([.1, .2, .3])},
              "server_chunk_execution": {"executed_controls": np.int64(1600)}}
    saved = json.loads(json.dumps(record, default=json_numpy_default))
    assert saved["receipt"]["place_verified"] is flag
    assert saved["measurement"] == {"visible": True, "xyz": [.1, .2, .3]}
    assert saved["server_chunk_execution"]["executed_controls"] == 1600
    assert saved["receipt"]["opening"] == .081


def test_unsupported_objects_are_not_relabelled_or_stringified():
    with pytest.raises(TypeError, match="not JSON serializable"):
        json.dumps({"measurement": object()}, default=json_numpy_default)
