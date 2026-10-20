"""Conservative observed-point clearance with one EDT per immutable capture.

Unknown/outside-grid queries return -inf and require the exact source check.
The field certifies distance from the observed point set only, not unseen
space. Occupied-voxel and query rounding errors are both subtracted.
"""
from dataclasses import dataclass
import time

import numpy as np
from scipy.ndimage import distance_transform_edt


@dataclass(frozen=True)
class SphereCover:
    centers: np.ndarray
    radii: np.ndarray
    names: tuple
    approximation_error_m: float = 0.


class VoxelDistanceField:
    def __init__(self, points, *, voxel_m=.004, padding_m=.25, max_voxels=16000000):
        started=time.perf_counter()
        points=np.asarray(points,dtype=np.float64).reshape(-1,3)
        if not np.isfinite(points).all() or voxel_m<=0 or padding_m<0 or max_voxels<8:
            raise ValueError('finite points and positive voxel/budget required')
        self.points_count=len(points)
        self.voxel_m=float(voxel_m)
        self.values=None
        if len(points):
            lo,hi=points.min(0)-padding_m,points.max(0)+padding_m
            while True:
                self.origin=np.floor(lo/self.voxel_m)*self.voxel_m
                shape=np.floor((hi-self.origin)/self.voxel_m).astype(np.int64)+2
                if int(np.prod(shape,dtype=np.int64))<=max_voxels:break
                self.voxel_m*=1.25
            cells=np.floor((points-self.origin)/self.voxel_m).astype(np.int64)
            free=np.ones(tuple(shape),dtype=bool)
            free[tuple(cells.T)]=False
            # EDT values refer to voxel centers. The measured point and query
            # can each deviate by sqrt(3)*pitch/2 from those centers.
            distance=distance_transform_edt(free,sampling=self.voxel_m)
            self.values=np.nextafter(distance.astype(np.float32),np.float32(-np.inf))
            self.shape=np.asarray(shape)
        else:
            self.origin=np.zeros(3);self.shape=np.zeros(3,dtype=int)
        self.voxel_error_m=float(np.sqrt(3)*self.voxel_m)
        self.build_s=time.perf_counter()-started

    def distance_lower(self, points):
        points=np.asarray(points,dtype=np.float64)
        shape=points.shape[:-1]
        points=points.reshape(-1,3)
        result=np.full(len(points),-np.inf)
        if self.values is None:return result.reshape(shape)
        finite=np.isfinite(points).all(1)
        indices=np.zeros((len(points),3),dtype=np.int64)
        indices[finite]=np.floor((points[finite]-self.origin)/self.voxel_m).astype(np.int64)
        valid=finite&(indices>=0).all(1)&(indices<self.shape).all(1)
        result[valid]=self.values[tuple(indices[valid].T)].astype(np.float64)-self.voxel_error_m
        return result.reshape(shape)

    def covers(self, points):
        points=np.asarray(points,float).reshape(-1,3)
        if not len(points):return True
        if self.values is None or not np.isfinite(points).all():return False
        indices=np.floor((points-self.origin)/self.voxel_m).astype(np.int64)
        valid=(indices>=0).all(1)&(indices<self.shape).all(1)
        if not valid.all():return False
        # A source point in an occupied voxel is covered by the same
        # sqrt(3)/2 voxel uncertainty, even with a different representative.
        return bool((self.values[tuple(indices.T)]<=0.).all())

    @property
    def identity(self):
        return {'observed_points':self.points_count,'voxel_m':self.voxel_m,
                'voxel_error_m':self.voxel_error_m,'shape':self.shape.tolist(),
                'bytes':self.values.nbytes if self.values is not None else 0,
                'build_s':self.build_s,'unobserved_space_certified':False}


def cover_boxes(boxes, *, opening=.08, cell_m=.04):
    """Cover entire source AABBs; therefore also every enclosed convex mesh.

    One circumsphere per AABB partition. A clearance-expanded source box is
    contained in these spheres after an extra sqrt(3)*clearance inflation.
    Finger-opening shifts are applied in the box frame before rotation.
    """
    if cell_m<=0:raise ValueError('positive cover cell required')
    centers=[];radii=[];names=[]
    for box in boxes:
        lower=np.asarray(box['lower'],float);upper=np.asarray(box['upper'],float)
        if (upper<lower).any():raise ValueError('invalid box bounds')
        shift=np.asarray(box.get('slide_per_half_opening',[0.,0.,0.]))*opening/2
        n=np.maximum(1,np.ceil((upper-lower)/cell_m).astype(int))
        width=(upper-lower)/n
        ids=np.stack(np.meshgrid(*[np.arange(i) for i in n],indexing='ij'),-1).reshape(-1,3)
        centers.extend(lower+shift+(ids+.5)*width)
        radii.extend([float(np.linalg.norm(width)/2)]*len(ids))
        names.extend([box['name']]*len(ids))
    return SphereCover(np.asarray(centers).reshape(-1,3),np.asarray(radii),tuple(names))


def cover_points(points, *, cell_m=.02):
    """Each measured payload point lies in its cell's circumsphere."""
    points=np.asarray(points,float).reshape(-1,3)
    if not len(points):return SphereCover(np.empty((0,3)),np.empty(0),())
    cells=np.unique(np.floor(points/cell_m).astype(np.int64),axis=0)
    return SphereCover((cells+.5)*cell_m,np.full(len(cells),np.sqrt(3)*cell_m/2),
                       tuple('payload' for _ in cells))


def sphere_clearance(field, translations, rotations, cover, *, clearance_m=.004,
                     approximation_error_m=0., batch_poses=256):
    """Evaluate all poses/spheres in vectorized batches; no accept on unknown."""
    translations=np.asarray(translations,float).reshape(-1,3)
    rotations=np.asarray(rotations,float).reshape(-1,3,3)
    if len(translations)!=len(rotations):raise ValueError('pose count mismatch')
    result=np.full(len(translations),np.inf)
    if not len(cover.centers):return np.zeros(len(result),bool),np.full(len(result),-np.inf)
    for start in range(0,len(result),batch_poses):
        stop=start+batch_poses
        centers=np.einsum('bij,sj->bsi',rotations[start:stop],cover.centers)+translations[start:stop,None,:]
        result[start:stop]=(field.distance_lower(centers)-cover.radii[None,:]).min(1)
    threshold=clearance_m+approximation_error_m+cover.approximation_error_m
    return result>threshold,result
