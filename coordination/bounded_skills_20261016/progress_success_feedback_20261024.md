# Success feedback and aggressive retries — active round

User 10/23 14:00 PDT replaces13:50. Implement/measure only, no training.
Do not end while owned GPU work is queued/running. node02 only,nice500,max3GPU;
C2+C3<=80CPU/600GB. Do not modify p3,c5,c6,rf,RVRT or historicalheld jobs.
Resource poll every15min whenwaiting; running logs may be checked to fix errors.

## Implemented and pushed

- db8be033: independent A task_success / B subgoal_status switches, schema8,
  public-request-legal/6; false task_success forbidsfinish, nohuman forbidsask_help.
  A true exits BEFORE perception/planning. B omitted bydefault. Explicit private
  truth may now be model-visible; no coordinates and no scoring change.
- Aggressive policy records40decisions/10000environmentsteps,recovery_budget=null;
  public stagnation no longer removes retryable actions, failurehistoryretained.
- 2b5653c2: bounded permissive measured_anchor preparation (max200steps,2cm vector
  clip,.1rad rotationclip,existing endpointtol,no sweep/trackingerrorveto);
  public RGB-D adaptive contact implementation and same-state experiment runner.
- Nativequery fix pendingcommit: RLinf env_call defaults to inner LIBERO env,
  so call `_check_success`,not wrapper `check_success`. CPUreproductionpassed.
- Contactdiagnostic binding improvement: only resolve duplicated fixtureparent
  when exactlyone has an observed childpart. Real N2 microwave had2 parent
  detections but just1 observed door. No privatecoordinates or taskcase rule.
- Localtests36feedback/schema/staged passed;12feedback/control/40failureloop
  passed,then7focused nativequery/contacttests passed. Frozenexecutionimports and
  all138episode/12N2/40skillmanifest shapes passed CPU.

## Exact execution source and jobs

Executionbase df589b7d (previous qualifiedf6 + emptytrackedcontactfix), not local
HEAD executor (which contains unrelated selectedgrasp changes). Qualifiedtree
`3605901c7425d27df9fa04d1ca7345aeeb388663`:
`/public/home/sunyihan/rpent_libero_eval/source_feedback8_3605901c_20261024`.
Basearchive58b98480 sourcehadwrongnativeAPI;retained,neveruseitsfailedphysical
attempts as task failures. Newtree differs in nativequery/unique publichandle
binding and runner only. Registration `/tmp/rd_feedback8_r1_registration.json`
local;remoteROOT samebasename.

SchemaSHA 5ab07c9ce77fef3f339cbb29fc6d45fd5f7060f1bcf193f044e229448a8928b4.
ContractSHA b6917b52a9cbe317adebec3d3140e2db509a838a898bb0db330952a8d2eba99b.
Both notified toC2/C1 via sharedCOORDINATION+owneralerts:
C3_FEEDBACK8_AGGRESSIVE_20261024.json and C3_FEEDBACK8_SOURCE_QUEUE_20261024.json.
Need followup nativeAPI/currenttree notice; fields/hashes unchanged.

RemoteRUN `/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/success_feedback_20261024`.
Preparation `*_r1.json`, `*_r1.sbatch`;output `N2_r1`, `pi_A_r1`, `skills_r1`,
`oracle_A_r1`,`oracle_AB_r1`.

-11955 N2:12registeredstates x screened/permissive x3repeats.
-11956 pi_A:40D2+original6, samefullstates/seeds/configasold18/40.
-11957 skills:40originaltrainstates (drawerclose,microwaveopen/close,platepush),3each.
-11958 oracle_A afterok11955; prior measuredpath preference+privaterule selection,
  live legal candidates and permissivepreparation enabled.
-11959 oracle_AB afterok11958. A/B oracle itself hasprivatepredicate truth in both;
  exposingB is not extraoracleknowledge. This is executablediagnosticoracle, NOT
  exhaustive mathematicalbound. Disclose whenreporting.

At mostN2/pi/skills3active;afterN2 replacedbyoracleA;AB replacesA. node02p3 had3
activejobs at21:25UTC leaving1GPU;protectedjob11923_2 naturallyended. Nochanges
made toprotectedjobs. Original11950failed dueAPI;11951andpending11952/3/4onlyour
jobs canceled. Rawoutputs retained. r1 startsfreshdirs,doesnotmixfailedattempts.

## Remaining

1. Monitor r1 startup/errors,fixsupportedbugs andresumewithnewimmutabletree.
2. Close N2 metrics >1um/>1mm,new/deepercontacts,nontargetdisplacement,endpointerror.
   Privatecontacts sampled only forreport;notcontrollerinput. Bindingmissing is
   unknown,notfalsecollisionorphysicalfailure.
3. Complete3arms40D2+6original,percase results/decisions/wall andWilson,pairedwith
   oldpure18/oracle24/A1M28 usingold rawtableSHA.
4. Newcontactskillspubliccontroller writtenbutNOTYET menu-enabled:measurefirst,
   then integrate finite menu/schema andnotifyC2,doCPUtests. At leastone must
   physicallyexecute ontrainstates;setup failuresmustbesplitout.
5. Optional63defaultcandidatequeries x3 ifremainingresource;listnotyetlocated.
6. NewCPUreport script report_success_feedback_CPU_20261024.py needs suffixr1
   handling andN2/skillsaggregation. Noformalmetricsyet.
7. Commitperfile,pushuser-fork harness-v5,noadd-A. Preserveguided-SAMcachehunk in
   bounded_skills andall unrelateddirty. Localnativefix/runnerhelper/tests/
   report/progresschanges notyetcommitted asofthisnote.
