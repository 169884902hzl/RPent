"""Compile a plain source reference before original-scene skill diagnostics."""


def source_reference(symbol, geometry, axes, public_names, *, minimum_gap=.04):
    """Describe the registered source without emitting coordinates or IDs."""
    name = public_names[symbol]
    peers = [other for other, kind in public_names.items() if kind == name and other in geometry]
    if len(peers) == 1:
        return f'the {name}'
    for word, axis, sign in [('left', axes[0], -1), ('right', axes[0], 1),
                             ('front', axes[1], 1), ('back', axes[1], -1)]:
        ranked = sorted(peers, key=lambda other: sign*sum(geometry[other][i]*axis[i] for i in range(3)),
                        reverse=True)
        gap = abs(sum((geometry[ranked[0]][i]-geometry[ranked[1]][i])*axis[i] for i in range(3)))
        if ranked[0] == symbol and gap > minimum_gap:
            return f'the {name} at the {word}'
    ranked = sorted(peers, key=lambda other: sum(geometry[other][i]*axes[0][i] for i in range(3)))
    if len(ranked) % 2 and ranked[len(ranked)//2] == symbol:
        midpoint = len(ranked)//2
        if all(abs(sum((geometry[symbol][i]-geometry[other][i])*axes[0][i] for i in range(3))) > minimum_gap
               for other in (ranked[midpoint-1], ranked[midpoint+1])):
            return f'the middle {name}'
    return None
