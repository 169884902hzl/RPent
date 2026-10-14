"""Read pinned raw JSON or JSONL evidence without inventing line numbers."""

import hashlib
import json
from pathlib import Path


def canonical_object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def resolve_json_pointer(value, pointer):
    """Resolve recorded JSON object locations, including nested raw windows."""
    if not pointer:
        return value
    if not pointer.startswith('/'):
        raise ValueError('JSON document pointer must start with a slash')
    for encoded in pointer[1:].split('/'):
        key = encoded.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not key.isdigit():
                raise ValueError('JSON array pointer requires an index')
            value = value[int(key)]
        elif isinstance(value, dict):
            value = value[key]
        else:
            raise ValueError('JSON pointer descends through a scalar')
    return value


def load_indexed_row(index, cache):
    path = index['captured_path']
    if cache.get('path') != path:
        data = Path(path).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != index['input_sha256']:
            raise ValueError('captured historical evidence changed')
        cache.clear()
        cache.update(path=path, sha256=actual, data=data)
    if cache['sha256'] != index['input_sha256']:
        raise ValueError('inconsistent input SHA in evidence index')
    if index.get('source_format', 'jsonl') == 'json':
        if index.get('line') is not None:
            raise ValueError('pretty JSON evidence must use a document pointer, not a line')
        if 'document' not in cache:
            cache['document'] = json.loads(cache['data'])
        value = cache['document']
        pointer = index.get('json_pointer', '')
        value = resolve_json_pointer(value, pointer)
        if canonical_object_sha(value) != index['raw_object_sha256']:
            raise ValueError('captured JSON object differs from index')
    elif index.get('source_format', 'jsonl') == 'jsonl':
        if 'lines' not in cache:
            cache['lines'] = cache['data'].splitlines()
        raw = cache['lines'][index['line'] - 1]
        if hashlib.sha256(raw).hexdigest() != index['raw_row_sha256']:
            raise ValueError('captured JSONL row differs from index')
        value = json.loads(raw)
    else:
        raise ValueError('unsupported indexed evidence format')
    if not isinstance(value, dict):
        raise ValueError('raw grasp evidence must be an object')
    return value


def load_indexed_reference(index, cache):
    """Read a sibling reference from the same pinned JSON document."""
    pointer = index.get('reference_json_pointer')
    if pointer is None:
        return None
    if index.get('source_format') != 'json' or not index.get('reference_object_sha256'):
        raise ValueError('indexed sibling reference must have its own object SHA')
    return load_indexed_row({**index, 'json_pointer': pointer,
                            'raw_object_sha256': index['reference_object_sha256']}, cache)
