"""Own C2 kernel caches per measured capture, outside serialized input state."""
from collections import OrderedDict
import hashlib
import weakref

import numpy as np

from robots.libero.bounded_kernels.route import CaptureFields,ConservativeGeometry

_captures = OrderedDict()


def capture_fields(points,key=None):
    if key is None:
        key = hashlib.sha256(np.ascontiguousarray(points).tobytes()).hexdigest()
    if key not in _captures:
        fields = CaptureFields(voxel_m=.008,max_voxels=2_000_000)
        fields.prepare_capture([points],lazy=True)
        _captures[key] = fields
        while len(_captures)>2:
            _captures.popitem(last=False)
    _captures.move_to_end(key)
    return _captures[key]


def can_accelerate(screen):
    """Keep warm unladen routes on the source until a payload built the EDT."""
    if screen.initial_margin or screen.initial_target_margin or screen.initial_payload_margin:
        # The source owns changing initial-contact semantics. Keep its exact
        # checks until the accelerator supports the same surface minimum rule.
        return False
    if len(screen.payload):
        return True
    fields = _captures.get(screen.capture_key)
    return fields is not None and hasattr(fields,'universal_field')


def geometry_kernel(screen):
    kernel = getattr(screen,'_geometry_kernel',None)
    if kernel is None:
        points = screen.capture_points if screen.capture_points is not None else np.concatenate((screen.points,screen.target))
        kernel = ConservativeGeometry(screen,capture_fields=capture_fields(points,screen.capture_key))
        # Derived acceleration objects must neither retain old captures nor
        # enter trusted CPU input/checkpoint pickle state.
        reference = weakref.ref(screen)
        kernel.screen = weakref.proxy(screen)
        kernel.exact = lambda pose:reference()._geometry_exact(pose)
        screen._geometry_kernel = kernel
    return kernel
