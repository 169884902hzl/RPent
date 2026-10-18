"""Shared skill contract prevents private/free-form action payloads."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA = json.loads((Path(__file__).resolve().parents[4] / 'rpent/skill_package/schema.json').read_text())


def test_schema_is_valid():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


def decision():
    return {'schema_version': 'bounded-skills/3', 'kind': 'decision',
            'observation_id': 'obs1', 'revision': 0, 'candidate_ids': ['c1']}


def test_decision_only_selects_existing_ids_shape():
    jsonschema.validate(decision(), SCHEMA)


@pytest.mark.parametrize('field,value', [('xyz', [1, 2, 3]), ('force', 5), ('prompt', 'do anything'),
                                          ('sim_truth', True), ('goal_predicate', 'On')])
def test_decision_cannot_inject_action_or_private_truth(field, value):
    row = decision()
    row[field] = value
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(row, SCHEMA)


def test_decision_bound_and_unique_ids():
    for ids in [[], ['c1'] * 2, [str(i) for i in range(5)]]:
        row = copy.deepcopy(decision())
        row['candidate_ids'] = ids
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(row, SCHEMA)
