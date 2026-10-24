"""Crop uncertainty must not multiply one measured instance into new IDs."""
from types import SimpleNamespace
import numpy as np
from robots.libero.v5_runtime import MeasuredScene
from robots.libero.bounded_instance_crops import reclassify_duplicate_instances
from tests.unit_tests.robots.libero.test_v5_moka_scene_ladder import PublicState,encoded_item


def test_uncertain_crop_classes_keep_two_separate_measured_ids_across_refreshes(tmp_path):
    class State(PublicState):
        def load(self,name):
            if name.endswith('_high.png'):return np.zeros((20,20,3),np.uint8)
            return super().load(name)
    state=State(tmp_path)
    first=np.zeros((20,20),bool);first[6:10,:8]=True
    second=np.zeros((20,20),bool);second[10:14,12:]=True
    class RPC:
        def call(self,method,*,kwargs,timeout_s):
            assert method=='sam3.segment_all'
            if kwargs['min_score']==0.:return {'instances':[]}
            return {'instances':[encoded_item(first),encoded_item(second)]}
    scene=MeasuredScene(SimpleNamespace(_state=state),RPC(),31)
    scene.refresh(['bowl']);ids=set(scene.entities)
    assert len(ids)==2
    positions={e.id:e.xyz for e in scene.entities.values()}
    for _ in range(5):
        reclassify_duplicate_instances(scene,state)
        assert {e.name for e in scene.entities.values()}=={'unclassified object'}
        assert set(scene.entities)==ids
        state.latest_step+=1;scene.refresh(['bowl'])
        assert set(scene.entities)==ids
        assert {e.id:e.xyz for e in scene.entities.values()}==positions
    assert len(set(positions.values()))==2
