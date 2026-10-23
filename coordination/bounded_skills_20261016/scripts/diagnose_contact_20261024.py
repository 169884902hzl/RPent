"""Capture the exact public screen rejected by the adaptive contact prototype."""
import argparse, importlib.util, json, pickle, sys
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int,default=5)
 a=p.parse_args();sys.path.insert(0,str(a.source));a.output.mkdir(parents=True,exist_ok=True)
 spec=importlib.util.spec_from_file_location('feedback_capture',a.source/'coordination/bounded_skills_20261016/scripts/run_success_feedback_20261024.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
 hooks=runner.module(a.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py','capture_hooks');hooks.bootstrap_source('original',evaluation='hybrid_repair');hooks.install_d2_restore_compatibility()
 from robots.libero import bounded_adaptive_contact as contact
 from robots.libero.bounded_motion import SmoothMotion,measured_robot
 class RecordingMotion(SmoothMotion):
  def run(self,waypoints,**kwargs):
   robot=measured_robot(self.p)
   i=len(list(a.output.glob('public_screen_*.pkl')))
   (a.output/f'public_screen_{i:03d}.pkl').write_bytes(pickle.dumps({'screen':self.screen,'robot':robot,'waypoints':waypoints,'config':self.config},protocol=5))
   result=super().run(waypoints,**kwargs)
   (a.output/f'screen_result_{i:03d}.json').write_text(json.dumps(result,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x),indent=2))
   return result
 contact.SmoothMotion=RecordingMotion
 plan=json.loads(a.manifest.read_bytes());row=plan['jobs'][a.index];row['repeats']=1
 plan['jobs']=[row]
 a.worker=0
 runner.worker(a,plan)

if __name__=='__main__':main()
