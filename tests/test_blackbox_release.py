import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('blackbox_release',Path(__file__).resolve().parents[1]/'scripts/blackbox-release.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class ReleaseTests(unittest.TestCase):
    def test_merged_candidate_includes_manual_profiles(self):
        with patch.object(r,'compose',return_value='{"services":{"blackbox":{"profiles":["manual-blackbox"]}}}') as compose:
            model=r.merged_candidate(['fixed-stack'])
        self.assertIn('blackbox',model['services'])
        self.assertEqual(compose.call_args.args,(['fixed-stack'],'--profile','manual-blackbox','--profile','manual-grafana','config','--format','json'))

    def test_release_manifest_matches_repository_assets(self):
        import hashlib
        root=Path(__file__).resolve().parents[1]
        for line in (root/'scripts/blackbox-release.sha256').read_text().splitlines():
            digest,path=line.split()
            self.assertEqual(hashlib.sha256((root/path).read_bytes()).hexdigest(),digest,path)

    def snapshot(self,migrated=True):
        at=time.time();out={k:[] for k in ('probe','status','times','durations')}
        for check,job,url in [('proxy','portal-health','http://10.20.10.62:8080/proxy-health'),('app','portal-health','http://10.20.10.62:8080/health'),('database','portal-db-health','http://10.20.10.62:8081/internal/check/employee')]:
            labels={'check':check,'job':job,'instance':url}
            for key,value in [('probe',1),('status',200),('times',at),('durations',0.1)]:out[key].append({'metric':dict(labels),'value':[at,str(value)]})
        out['up']=[] if migrated else [{'metric':{'job':'blackbox-exporter','instance':'blackbox:9115'},'value':[at,'1']}]
        for key in r.METRICS:out[key]=[{'metric':{},'value':[at,str(at)]}]
        base='http://otel-collector:8889/api/v0/component/prometheus.exporter.blackbox.portal_check/metrics' if migrated else 'http://blackbox:9115/probe'
        out['targets']=[{'labels':dict(x['metric']),'health':'up','scrapeUrl':base+'?module=http_2xx'} for x in out['probe']]
        labels=json.loads(json.dumps([list(k) for k in sorted(r.index(out['probe']))]))
        return out,labels,at-1

    def test_migrated_candidate_rejects_legacy_scrape_and_rollback_requires_it(self):
        migrated, labels, after = self.snapshot(migrated=True)
        self.assertTrue(r.samples_ok(migrated, labels, after, True))
        migrated['up'] = [{'metric': {'job': 'blackbox-exporter', 'instance': 'blackbox:9115'}, 'value': [time.time(), '1']}]
        self.assertFalse(r.samples_ok(migrated, labels, after, True))
        original, labels, after = self.snapshot(migrated=False)
        original['up'] = []
        self.assertFalse(r.samples_ok(original, labels, after, False))

    def test_saved_json_manifest_labels_work_for_apply_and_rollback(self):
        for migrated in (False,True):
            data,labels,after=self.snapshot(migrated)
            self.assertTrue(r.samples_ok(data,json.loads(json.dumps(labels)),after,migrated))

    def test_stale_future_or_pre_switch_samples_fail(self):
        for value in (time.time()-90,time.time()+20,time.time()-5):
            d,l,a=self.snapshot();d['times'][0]['value'][1]=str(value)
            self.assertFalse(r.samples_ok(d,l,a,True))

    def test_nonfinite_duration_is_rejected(self):
        d,l,a=self.snapshot();d['durations'][0]['value'][1]='NaN'
        self.assertFalse(r.samples_ok(d,l,a,True))

    def test_missing_or_stale_otlp_prevents_success(self):
        for missing in (True,False):
            d,l,a=self.snapshot();d[r.METRICS[0]]=[] if missing else [{'metric':{},'value':[0,str(time.time()-90)]}]
            self.assertFalse(r.samples_ok(d,l,a,True))

    def test_unchanged_probe_endpoint_does_not_pass_migration(self):
        d,l,a=self.snapshot(False);self.assertFalse(r.samples_ok(d,l,a,True))
        d,l,a=self.snapshot();d['targets'][0]['scrapeUrl']=d['targets'][0]['scrapeUrl'].replace('otel-collector:8889','other:8889')
        self.assertFalse(r.samples_ok(d,l,a,True))

    def test_label_drift_duplicate_or_failed_probe_is_rejected(self):
        d,l,a=self.snapshot();d['probe'][0]['metric']['check']='other'
        self.assertFalse(r.samples_ok(d,l,a,True))
        d,l,a=self.snapshot();d['probe'].append(d['probe'][0])
        with self.assertRaises(ValueError):r.samples_ok(d,l,a,True)
        d,l,a=self.snapshot();d['probe'][0]['value'][1]='0'
        self.assertFalse(r.samples_ok(d,l,a,True))

    def test_command_diagnostics_do_not_print_secret_stderr(self):
        import subprocess
        with patch.object(r.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','SECRET')):
            with self.assertRaises(RuntimeError) as error:r.call(['docker','compose','config'])
        self.assertNotIn('SECRET',str(error.exception))

    def test_candidate_keeps_production_receiver_and_mount_path(self):
        root=Path(__file__).resolve().parents[1]
        original={r.FILES[3]:b'services:\n  blackbox:\n    image: test\n'}
        result=r.candidates(root,original)
        self.assertIn(b'./monitoring/alloy-otel.alloy:',result[r.FILES[0]])
        self.assertNotIn(b'./monitoring/alloy-otel-blackbox.alloy:',result[r.FILES[0]])
        self.assertIn(b'profiles: [manual-blackbox]',result[r.FILES[3]])
        self.assertEqual(result[r.FILES[1]].count(b'http://prometheus:9090/api/v1/write'),1)

    def test_existing_profile_or_changed_stack_is_rejected(self):
        root=Path(__file__).resolve().parents[1]
        with self.assertRaises(RuntimeError):r.candidates(root,{r.FILES[3]:b'services:\n  blackbox:\n    profiles: [manual]\n'})
        paths=[str(r.ROOT/p) for p in r.STACK]
        self.assertEqual(r.require_stack(paths),paths)
        with self.assertRaises(RuntimeError):r.require_stack(paths[::-1])

    def test_file_write_preserves_bind_inode(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config';path.write_text('old');inode=path.stat().st_ino
            with patch.object(r,'ROOT',Path(folder)):r.write_contents({'config':b'new'})
            self.assertEqual(path.read_bytes(),b'new');self.assertEqual(path.stat().st_ino,inode)

    def test_peer_drift_stops_before_configuration_restore(self):
        manifest={'peers':{'management-web':{'id':'old','image':'same','restarts':0}},'unchanged':{}}
        with patch.object(r,'inspect',return_value={'Id':'new','Image':'same','State':{'Running':True},'RestartCount':0}):
            with self.assertRaises(RuntimeError):r.baseline_ok(manifest)

class RestoreTests(unittest.TestCase):
    def backup(self,folder):
        root=Path(folder)/'server';backup=Path(folder)/'backup';root.mkdir();backup.mkdir()
        data={p:('original '+p).encode() for p in r.FILES}
        for path,value in data.items():
            for base,content in [(backup,value),(root,b'candidate')]:
                p=base/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
        manifest={'original_hashes':{p:r.sha(v) for p,v in data.items()},
                  'blackbox_restart':{'Name':'unless-stopped'},'stack':['fixed-stack']}
        return root,backup,data,manifest

    def test_restore_preserves_inode_and_only_recreates_alloy(self):
        with tempfile.TemporaryDirectory() as folder:
            root,backup,data,manifest=self.backup(folder)
            inode=(root/r.FILES[0]).stat().st_ino
            with patch.object(r,'ROOT',root),patch.object(r,'BACKUP',backup),patch.object(r,'baseline_ok'),patch.object(r,'call') as call,patch.object(r,'compose') as compose,patch.object(r,'wait_healthy') as wait,patch.object(r,'timer_stop'):
                r.restore(manifest)
            self.assertEqual((root/r.FILES[0]).stat().st_ino,inode)
            for path,value in data.items():self.assertEqual((root/path).read_bytes(),value)
            self.assertEqual(compose.call_args_list[-1].args[-1],'otel-collector')
            self.assertIn('--no-deps',compose.call_args_list[-1].args)
            self.assertFalse(wait.call_args.args[-1])
            self.assertTrue(any('--signal=HUP' in c.args[0] for c in call.call_args_list))

    def test_corrupt_backup_is_rejected_before_live_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root,backup,data,manifest=self.backup(folder)
            (backup/r.FILES[0]).write_text('corrupt')
            with patch.object(r,'ROOT',root),patch.object(r,'BACKUP',backup),patch.object(r,'baseline_ok'),patch.object(r,'write_contents') as write:
                with self.assertRaises(RuntimeError):r.restore(manifest)
                write.assert_not_called()

    def test_completed_release_watchdog_does_not_rollback(self):
        import os,sys
        cwd=os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);backup=root/'backup';backup.mkdir();(backup/'applied.ok').write_text('ok')
            try:
                with patch.object(r,'ROOT',root),patch.object(r,'BACKUP',backup),patch.object(r,'call',return_value='ip-10-20-20-10'),patch.object(r.os,'geteuid',return_value=0),patch.object(sys,'argv',['script','rollback','--confirmation','ROLLBACK_BLACKBOX','--watchdog']),patch.object(r,'restore') as restore:
                    r.main();restore.assert_not_called()
            finally:os.chdir(cwd)

if __name__=='__main__':unittest.main()

