"""Background array encoding with read/checkpoint barriers for LIBERO runs."""
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import os
from pathlib import Path
import weakref
import zipfile

import imageio.v2 as imageio
import numpy as np

from rpent.session import EnvState

_writers = weakref.WeakKeyDictionary()
_read_caches = weakref.WeakKeyDictionary()


def _write_array(destination, array, compression):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name('.'+destination.stem+'.async.tmp'+destination.suffix)
    try:
        if destination.suffix == '.png':
            imageio.imwrite(temporary,array.astype(np.uint8),
                **({'compress_level':compression} if compression is not None else {}))
        elif compression is None:
            np.savez_compressed(temporary,array=array)
        else:
            with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,
                    compresslevel=compression) as archive:
                with archive.open('array.npy','w',force_zip64=True) as member:
                    np.lib.format.write_array(member,array)
        os.replace(temporary,destination)
    finally:
        temporary.unlink(missing_ok=True)


class AsyncEnvState(EnvState):
    """Keep live writers outside checkpoint state and serialize owned copies."""

    @classmethod
    def enable(cls, state):
        if not isinstance(state,cls):
            state.__class__ = cls
        return state

    def save(self,name,value,*,step=-1,**options):
        cache = _read_caches.get(self,{})
        cache.pop((self._output_dir,name,self._resolve_read_step(step)),None)
        if Path(name).suffix not in {'.png','.npz'}:
            return super().save(name,value,step=step,**options)
        step = self._resolve_read_step(step)
        destination = self._artifact_file(name,step)
        writer,pending = _writers.setdefault(self,(None,{}))
        if writer is None:
            writer = ThreadPoolExecutor(max_workers=1,thread_name_prefix='libero-artifacts')
            _writers[self] = writer,pending
        key = name,step
        self.flush(key)
        if len(pending) >= 8:
            self.flush(next(iter(pending)))
        # Never let an environment overwrite an array still being encoded.
        pending[key] = writer.submit(_write_array,destination,np.array(value,copy=True),
            self._lossless_compression_level)
        if step is None:
            self._run_artifacts.add(name)
        else:
            self._record_for(step).artifacts.add(name)
        if not self._step_open:
            self._write_manifest()
        return name

    def flush(self,key=None):
        resource = _writers.get(self)
        if resource is None:
            return
        _,pending = resource
        for item in list(pending) if key is None else [key]:
            future = pending.pop(item,None)
            if future is not None:
                future.result()  # Encoding failures remain nonzero startup/runtime errors.

    def load(self,name,*,step=-1):
        resolved = self._resolve_read_step(step)
        self.flush((name,resolved))
        if not name.endswith(('_world_high.npz','_high.png')):
            return super().load(name,step=step)
        key = self._output_dir,name,resolved
        cache = _read_caches.setdefault(self,OrderedDict())
        if key not in cache:
            cache[key] = super().load(name,step=step)
            while len(cache)>8:
                cache.popitem(last=False)
        cache.move_to_end(key)
        # EnvState.load historically returns a fresh writable array. Local
        # mask/self-filter edits must never alter another reader's pixels.
        return cache[key].copy()

    def load_bytes(self,name,*,step=-1):
        self.flush((name,self._resolve_read_step(step)))
        return super().load_bytes(name,step=step)

    def artifact_path(self,name,*,step=-1):
        self.flush((name,self._resolve_read_step(step)))
        return super().artifact_path(name,step=step)

    def exists(self,name,*,step=-1):
        self.flush((name,self._resolve_read_step(step)))
        return super().exists(name,step=step)

    def close(self):
        self.flush()
        _read_caches.pop(self,None)
        resource = _writers.pop(self,None)
        if resource is not None:
            resource[0].shutdown(wait=True)
