"""Episode progress derived solely from published measurements and receipts."""
from __future__ import annotations

import math

VERSION = 'public-measured-progress/1'


class PublicProgress:
    def __init__(self, limit=None):
        self.limit = limit
        self.stagnant = 0
        self.positions = {}
        self.relations = set()
        self.held = None
        self.last_revision = None
        self.last_reasons = []
        self.seen_receipts = set()

    def update(self, request):
        if self.last_revision == request['revision']:
            return self.stagnant
        first = self.last_revision is None
        reasons = []
        for anchor in request['anchors']:
            key, position = anchor['id'], anchor['xyz_m']
            if anchor.get('cached'):
                continue
            old = self.positions.get(key)
            if old is None or math.dist(position, old) >= .01:
                self.positions[key] = list(position)
                if old is not None:
                    reasons.append('measured_anchor_displacement:' + key)
        relations = {(r['source_id'], r['relation'], r['target_id'])
            for r in request.get('relations', []) if r['relation'] in {'on', 'in'}}
        if relations - self.relations:
            reasons.append('new_measured_relation')
        self.relations |= relations
        held = request['robot']['held_anchor_id']
        if held != self.held:
            reasons.append('measured_holding_change')
        self.held = held
        for receipt in request.get('receipts', []):
            token = (receipt['observation_id'], receipt['candidate_id'])
            if token in self.seen_receipts:
                continue
            self.seen_receipts.add(token)
            for check in receipt.get('expectation_checks', []):
                if check['condition']['metric'] == 'contact_progress_m' and check['passed'] is True:
                    reasons.append('measured_contact_progress')
        self.stagnant = 0 if first or reasons else self.stagnant + 1
        self.last_revision = request['revision']
        self.last_reasons = reasons
        return self.stagnant

    @property
    def exhausted(self):
        return self.limit is not None and self.stagnant >= self.limit
