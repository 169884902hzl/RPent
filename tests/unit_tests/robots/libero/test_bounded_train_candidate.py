"""Train collection keeps exact action bindings and excludes protected scopes."""
import copy
import pytest
from scripts.evaluate_bounded_training_candidate import frozen_choice_request
from tests.unit_tests.robots.libero.test_bounded_saved_candidate import frozen_case


def train_case():
    query,saved=frozen_case()
    query.update(split='train',training_admission=True,evaluation_only=False,
        scope_kind='registered_original_train_dagger',PRO=False,D2=False,confirmation=False)
    return query,saved


def test_registered_training_action_keeps_its_parameters_and_frozen_binding():
    query,saved=train_case();before=copy.deepcopy(saved)
    request,candidate=frozen_choice_request(query,saved)
    assert request==before['request'] and candidate['parameters']==query['candidate']['parameters']
    candidate['parameters']['mode']='on'
    assert saved==before


@pytest.mark.parametrize('field,value',[('split','holdout'),('PRO',True),('D2',True),
    ('confirmation',True),('training_admission',False),('scope_kind','unregistered')])
def test_protected_or_unregistered_input_is_not_admitted(field,value):
    query,saved=train_case();query[field]=value
    with pytest.raises(ValueError,match='original training-split'):
        frozen_choice_request(query,saved)


def test_unexecuted_original_prefix_cannot_be_attached_to_a_new_measurement():
    query,saved=train_case();query['prefix']=['not-yet-executed']
    with pytest.raises(ValueError,match='empty prefixes'):
        frozen_choice_request(query,saved)
