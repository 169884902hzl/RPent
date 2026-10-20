"""Resolve progress targets from instruction text and public anchor geometry."""
from __future__ import annotations

import re
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_public_transfer_reference import _reference, transfer_reference


def instruction_goal_metrics(request, *, view_axes=((1, 0, 0), (0, -1, 0)), normals=None):
    """Return public goal distances, never private task predicates or poses.

    Ambiguous noun phrases remain unmeasured. An unrelated relation or an
    anchor merely moving does not establish task progress.
    """
    entities = []
    for anchor in request['anchors']:
        xyz, size = np.asarray(anchor['xyz_m']), np.asarray(anchor.get('size_m', [0., 0., 0.]))
        entities.append(SimpleNamespace(id=anchor['id'], name=anchor.get('label', ''),
            xyz=xyz, lower=xyz-size/2, upper=xyz+size/2, visible=True,
            geometry='cached_perception' if anchor.get('cached') else 'measured'))
    by_id = {e.id: e for e in entities}
    text = request.get('instruction', '').lower().strip()
    metrics = []
    transfer_text = re.split(r'\s+and\s+(?=turn\s|open\s|close\s)', text, maxsplit=1)[0]
    reference = transfer_reference(entities, transfer_text, view_axes)
    source, target = (by_id.get(reference.get(key)) for key in ('source', 'target'))
    if source is not None and target is not None:
        delta = np.maximum(np.maximum(target.lower[:2]-source.xyz[:2],
            source.xyz[:2]-target.upper[:2]), 0.)
        prefix = f'{source.id}:{reference["mode"]}:{target.id}'
        metrics.append({'key':'target_xy:'+prefix, 'value':float(np.linalg.norm(delta)), 'resolution':.005})
        # Lowering is progress only over the target footprint; lifting or
        # lowering at the source must not repeatedly reset stagnation.
        if np.linalg.norm(delta) <= .01:
            metrics.append({'key':'target_z:'+prefix,
                'value':float(abs(source.lower[2]-(target.upper[2] if reference['mode']=='on' else target.lower[2]))),
                'resolution':.005})
        satisfied = any(r['source_id']==source.id and r['target_id']==target.id
            and r['relation']==reference['mode'] for r in request.get('relations', []))
        metrics.append({'key':'relation:'+prefix, 'value':0. if satisfied else 1., 'resolution':.5})
    if normals is None:
        normals = {}
    for match in re.finditer(r'\b(open|close)\s+(?:the\s+)?(.+?)(?=\s+and\s+|$)', text):
        part = re.search(r'\b(top|middle|bottom)\s+(drawer|door)\b', match[2])
        parts = [e for e in entities if part and {part[1],part[2]} <= set(e.name.split())]
        entity = parts[0] if len(parts) == 1 else _reference(match[2], entities, view_axes)
        if entity is None:
            continue
        if entity.id not in normals:
            # A measured part's thin planar dimension supplies its outward
            # direction relative to the fixed enclosing body. Keep this
            # initial reference when a later partial mask changes its bounds.
            parents = [e for e in entities if e.id != entity.id and e.name in {'cabinet','microwave'}]
            if len(parents) == 1 and any(word in entity.name for word in ('drawer','door')):
                axis = int(np.argmin((entity.upper-entity.lower)[:2]))
                normal = np.zeros(3)
                normal[axis] = np.sign(entity.xyz[axis]-parents[0].xyz[axis])
                normals[entity.id] = normal.tolist()
            else:
                normals[entity.id] = view_axes[1]
        normal = np.asarray(normals[entity.id])
        length = np.linalg.norm(normal)
        if length <= 1e-9:
            continue
        extent = float(np.dot(entity.xyz, normal/length))
        metrics.append({'key':match[1]+'_extent:'+entity.id,
            'value':extent*(-1 if match[1]=='open' else 1), 'resolution':.005,
            'anchor_id':entity.id,'direction':(normal/length*(1 if match[1]=='open' else -1)).tolist()})
    return metrics
