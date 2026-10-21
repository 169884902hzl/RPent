"""Goal-directed episode progress from public measurements only."""
from __future__ import annotations

import math
import json

VERSION = 'public-measured-progress/2-goal-directed'
# Exact captured camera axes/handle normals, original220 CPU replay r5,
# 2026-10-21: only the allowed stove s8 success is cut. N=33 keeps all.
# Neither calibration used PRO/D2 or confirmation-state outcomes.
DEFAULT_STAGNANT_DECISIONS = 11


class PublicProgress:
    """Track best goal distances and repeated action groups, never any motion."""
    def __init__(self, limit=None):
        self.limit = limit
        self.stagnant = 0
        self.last_revision = None
        self.last_reasons = []
        self.best = {}
        self.action_groups = []
        self.loop_detected = False
        self.goal_contact = {}
        self.seen_motion_receipts = set()
        self.skip_planning_rejection = False

    def record_actions(self, candidates, receipts, *, goal_directions=None):
        self.skip_planning_rejection = bool(receipts) and all(
            r.get('steps_used') == 0 and r.get('phase') == 'planning_unreachable' for r in receipts)
        executed = {r['candidate_id'] for r in receipts if r.get('steps_used', 0) > 0}
        group = [(c['skill'], c['parameters']) for c in candidates if c['id'] in executed]
        if group:
            self.action_groups.append(json.dumps(group, sort_keys=True, separators=(',', ':')))
        if not hasattr(self, 'goal_contact'):
            self.goal_contact, self.seen_motion_receipts = {}, set()
        by_id = {c['id']:c for c in candidates}
        for receipt in receipts:
            token = (receipt.get('observation_id'),receipt['candidate_id'])
            if token in self.seen_motion_receipts:
                continue
            self.seen_motion_receipts.add(token)
            candidate = by_id[receipt['candidate_id']]
            params = candidate['parameters']
            if candidate['skill'] not in {'nudge','guarded_move'} or params.get('axis') not in 'xyz':
                continue
            checks = [c for c in receipt.get('expectation_checks', [])
                if c['condition']['metric']=='contact_progress_m' and c.get('measured') is not None]
            for check in checks:
                anchor = check['condition'].get('anchor_id')
                direction = (goal_directions or {}).get(anchor)
                if direction is None:
                    continue
                step = params.get('distance_m',params.get('direction',0.))
                projection = direction['xyz'.index(params['axis'])]*math.copysign(1.,step)
                key = 'goal_contact:'+anchor
                self.best.setdefault(key,0.)
                self.goal_contact[key] = self.goal_contact.get(key,0.)+projection*check['measured']

    def update(self, request, metrics=None):
        """Consume lower-is-better public goal metrics with explicit resolution."""
        if self.last_revision == request['revision']:
            return self.stagnant
        if getattr(self, 'skip_planning_rejection', False):
            self.last_revision = request['revision']
            self.skip_planning_rejection = False
            self.last_reasons = ['internal_planning_rejection_not_task_attempt']
            return self.stagnant
        first = self.last_revision is None
        if not hasattr(self, 'best'):  # Trusted historical CPU snapshots.
            self.best, self.action_groups, self.loop_detected = {}, [], False
        reasons = []
        directional = [{'key':key,'value':-value,'resolution':.005}
            for key,value in getattr(self,'goal_contact',{}).items()]
        for metric in [*(metrics or ()),*directional]:
            key, value, resolution = metric['key'], metric['value'], metric['resolution']
            if not math.isfinite(value) or resolution <= 0:
                continue
            previous = self.best.get(key)
            if previous is None:
                self.best[key] = value
            elif previous-value >= resolution:
                self.best[key] = value
                reasons.append('closer_to_goal:'+key)
        if first or reasons:
            self.stagnant = 0
            self.action_groups.clear()
            self.loop_detected = False
        else:
            self.stagnant += 1
            history = self.action_groups
            # Missing target measurements cannot prove a stationary target.
            self.loop_detected = bool(metrics) and any(history[-2*n:-n] == history[-n:]
                for n in range(1, min(8, len(history)//2)+1))
        self.last_revision = request['revision']
        self.last_reasons = reasons
        return self.stagnant

    @property
    def exhausted(self):
        return self.loop_detected or (self.limit is not None and self.stagnant >= self.limit)
