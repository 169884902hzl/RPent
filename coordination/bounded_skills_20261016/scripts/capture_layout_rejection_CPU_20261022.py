"""Capture a failed constructor's authored geometry without changing its rules."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--registration', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    import robots.libero.env_server
    from scripts import generate_bounded_train_layouts as generator
    registration = json.loads(args.registration.read_bytes())
    plan = json.loads(Path(registration['parent']['path']).read_bytes())
    job = registration['jobs'][args.index]

    def capture(**kwargs):
        witness = kwargs.pop('witness_check')
        closure = dict(zip(witness.__code__.co_freevars,
            [cell.cell_contents for cell in witness.__closure__]))
        base = closure['base']
        sim = base.sim
        kwargs['workspace_collision_geoms'] = [
            {'name': sim.model.geom_id2name(i), 'body': sim.model.body_id2name(
                int(sim.model.geom_bodyid[i])), 'type': int(sim.model.geom_type[i]),
             'position': sim.data.geom_xpos[i].tolist(),
             'rotation': sim.data.geom_xmat[i].tolist(),
             'half_size': sim.model.geom_size[i].tolist()}
            for i in range(sim.model.ngeom)
            if sim.model.geom_contype[i] or sim.model.geom_conaffinity[i]]
        kwargs['witness_at_original_geometry'] = witness(kwargs['objects'])
        on_support = [{**item, 'xyz_m': [*item['xyz_m'][:2],
            kwargs['support']['upper_m'][2]+item['size_m'][2]/2]}
            if item['movable'] else item for item in kwargs['objects']]
        kwargs['witness_at_proposed_support_height'] = witness(on_support)
        kwargs['limits'] = vars(kwargs['limits'])
        kwargs['scope'] = 'private authoring geometry; no policy call or state admission'
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            json.dump(kwargs, stream, indent=2)
        raise SystemExit(0)

    generator.generate_layout = capture
    generator.generate_case(plan, job['case_index'], job['seed'],
        args.output.parent/'not_a_generated_state', registration['registry'],
        registration['original_geometry'], native_witness=job.get('native_witness'))


if __name__ == '__main__':
    main()
