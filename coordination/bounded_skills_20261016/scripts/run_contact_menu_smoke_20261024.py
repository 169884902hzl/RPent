"""Exercise a measured contact through its exact public v9 selection/receipt."""
import argparse
import importlib.util
from pathlib import Path
import sys


def execute_selected_contact(probe, facade, adapter, policy, spec, source, target):
    from robots.libero.bounded_success_loop import enable
    from robots.libero.bounded_oracle import NoPublicOption
    from rpent.skill_package.feedback import TaskAlreadySucceeded
    adapter.adaptive_contact_skills=True
    enable(adapter,facade)
    adapter.allow_vla=False
    setup=[]
    for _ in range(8):
        try:request=adapter.request(k=1)
        except TaskAlreadySucceeded:
            return {'success':True,'stop_reason':'native_success','setup':setup}
        try:decision=policy.choose(request)
        except NoPublicOption:
            return {'success':False,'stop_reason':'no_public_contact_option','setup':setup}
        choice=next(c for c in request['candidates'] if c['id']==decision['candidate_ids'][0])
        receipts=adapter.execute(request,decision)
        if choice['skill'] in {'open_close_articulated','push_to'}:
            detail=adapter.details[-1]['execution']
            return {**detail,'setup':setup,'skill':choice['skill'],'parameters':choice['parameters'],
                'selected_request':request,'selected_decision':decision,'selected_receipts':receipts,
                'exact_public_menu_execution':True}
        setup.extend(receipts)
        if any(r['outcome']!='success' for r in receipts):
            return {'success':False,'stop_reason':'contact_setup_failed','setup':setup}
    return {'success':False,'stop_reason':'contact_setup_decision_budget','setup':setup}


def main():
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--source',type=Path,required=True)
    args,_=parser.parse_known_args();source=args.source.resolve();sys.path.insert(0,str(source))
    entry=source/'coordination/bounded_skills_20261016/scripts/run_success_feedback_20261024.py'
    spec=importlib.util.spec_from_file_location('contact_menu_smoke_runner',entry)
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    runner.execute_new_contact=execute_selected_contact
    # Child workers must load this same override, preserving process isolation.
    runner.__file__=str(Path(__file__).resolve())
    runner.main()


if __name__=='__main__':main()
