"""Private oracle prerequisite/deferred-close order for storage insertions."""
import copy


def ordered_status(status):
    result = copy.deepcopy(status)
    pairs = list(zip(result['goals'], result['satisfied']))
    close = {goal[1]: (index, satisfied) for index, (goal, satisfied) in enumerate(pairs)
        if len(goal) == 2 and goal[0] == 'close'}
    prereq, deferred, ordinary = [], [], []
    destinations = {goal[2] for goal, satisfied in pairs if len(goal) == 3 and goal[0] == 'in' and not satisfied}
    for index, (goal, satisfied) in enumerate(pairs):
        if len(goal) == 2 and goal[0] == 'close' and goal[1] in destinations:
            deferred.append((goal, satisfied))
        else:
            ordinary.append((goal, satisfied))
        if len(goal) == 3 and goal[0] == 'in' and not satisfied and goal[2] in close:
            # Native open and close thresholds leave a partially open band.
            # Not-closed does not establish an accessible insertion region.
            if status.get('storage_open', {}).get(goal[2]) is not True:
                prereq.append((['open', goal[2]], False))
    ordered = prereq+ordinary+deferred
    result['goals'] = [goal for goal, _ in ordered]
    result['satisfied'] = [satisfied for _, satisfied in ordered]
    return result
