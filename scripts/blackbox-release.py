#!/usr/bin/env python3
"""Explicit, locked Blackbox migration. Never runs on import or CI by default."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path('/opt/schutz-monitoring')
BACKUP = ROOT / '.release-backups/blackbox-alloy-20261026-retry1'
UNIT = 'schutz-blackbox-rollback-20261026-retry1'
PREFIX = 'schutz-monitoring-'
FILES = ['compose.otel-only.yaml', 'monitoring/alloy-otel.alloy',
         'monitoring/prometheus.ec2.yaml', 'compose.blackbox-only.yaml']
EXPECTED = dict(zip(FILES, [
    '138d6c6dc4f53166e356aad5ada2e872bd19b98d',
    '977051ff1a85129809ca2987339303f871fcb98c',
    'cb133079d2d7e98fe6bb0faeaaa37fa5a176fb78',
    'da05cbd56dacaf8ab3928fd5823d8fd4a2ded698',
]))
STACK = ['compose.otel-only.yaml', 'compose.prometheus-only.yaml',
         'compose.management-ec2.yaml',
         'updates/incident-drafts/compose.incident-drafts.yaml',
         'compose.loki-only.yaml', 'compose.blackbox-only.yaml',
         'compose.grafana-only.yaml', 'compose.ecr.yaml',
         'compose.management-https.yaml']
PEERS = ['management-web', 'management-worker', 'management-db', 'prometheus']
METRICS = ['portal_http_requests', 'portal_http_duration_bucket',
           'portal_http_duration_sum', 'portal_http_duration_count',
           'portal_db_duration_bucket', 'portal_db_duration_sum',
           'portal_db_duration_count']

def call(args, timeout=30, input=None):
    r = subprocess.run(args, input=input, text=True, capture_output=True,
                       timeout=timeout)
    if r.returncode:
        # Do not print Compose environment or arbitrary provider responses.
        raise RuntimeError('명령 실패: ' + ' '.join(args[:3]))
    return r.stdout

def inspect(service):
    return json.loads(call(['docker', 'inspect', PREFIX + service + '-1']))[0]

def git_hash(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def require_stack(paths):
    expected = [str(ROOT / p) for p in STACK]
    if paths != expected:
        raise RuntimeError('활성 Compose 순서가 승인 기준과 다릅니다.')
    return paths

def compose(paths, *args):
    cmd = ['docker', 'compose', '-p', 'schutz-monitoring']
    for path in paths:
        cmd += ['-f', path]
    return call(cmd + list(args), timeout=60)

def merged_candidate(paths):
    # Include opt-in services when inspecting the complete model.
    return json.loads(compose(paths, '--profile', 'manual-blackbox',
                              '--profile', 'manual-grafana',
                              'config', '--format', 'json'))

def candidates(asset_root, originals):
    contents = {
        FILES[0]: (asset_root / 'monitoring/compose.alloy-otel-blackbox.yaml').read_bytes(),
        FILES[1]: (asset_root / 'monitoring/alloy-otel-blackbox.alloy').read_bytes(),
        FILES[2]: (asset_root / 'monitoring/prometheus.alloy-blackbox.yaml').read_bytes(),
    }
    old = b'./monitoring/alloy-otel-blackbox.alloy:'
    if contents[FILES[0]].count(old) != 1:
        raise RuntimeError('후보 Alloy 마운트 경로 확인 필요')
    contents[FILES[0]] = contents[FILES[0]].replace(old, b'./monitoring/alloy-otel.alloy:')
    text = originals[FILES[3]].decode()
    if text.count('  blackbox:\n') != 1 or re.search(r'^    profiles:', text, re.M):
        raise RuntimeError('기존 Blackbox 프로필 기준 확인 필요')
    contents[FILES[3]] = text.replace(
        '  blackbox:\n', '  blackbox:\n    profiles: [manual-blackbox]\n', 1
    ).encode()
    # Production pipeline must never point to an isolated test receiver.
    if contents[FILES[1]].count(b'http://prometheus:9090/api/v1/write') != 1:
        raise RuntimeError('운영 OTLP 전송 주소 확인 필요')
    return contents

def write_contents(contents):
    # Preserve bind-mounted inodes; never replace the original files by rename.
    for relative, data in contents.items():
        with (ROOT / relative).open('wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

def baseline_ok(manifest):
    for service, expected in manifest['peers'].items():
        item = inspect(service)
        if (item['Id'] != expected['id'] or item['Image'] != expected['image']
                or not item['State']['Running']
                or item['RestartCount'] != expected['restarts']):
            raise RuntimeError('유지 대상 변경 또는 비정상: ' + service)
        if service == 'management-db' and item['State'].get('Health', {}).get('Status') != 'healthy':
            raise RuntimeError('관리 DB 건강 확인 필요')
    for path, digest in manifest['unchanged'].items():
        p = Path(path)
        actual = sha(p.read_bytes()) if p.is_file() else None
        if actual != digest:
            raise RuntimeError('보존 대상 설정 변경: ' + str(p))

def sample():
    code = '''import json,httpx
from management.config import WorkerSettings
s=WorkerSettings()
expressions=%s
with httpx.Client(timeout=4,trust_env=False) as c:
 out={}
 for key,expr in expressions.items():
  r=c.get(s.prometheus_url.rstrip('/')+'/api/v1/query',params={'query':expr})
  r.raise_for_status();d=r.json();assert d.get('status')=='success'
  out[key]=d['data']['result']
 r=c.get(s.prometheus_url.rstrip('/')+'/api/v1/targets');r.raise_for_status()
 out['targets']=r.json()['data']['activeTargets']
 print(json.dumps(out))
''' % repr({
        'probe': 'probe_success{job=~"portal-health|portal-db-health"}',
        'status': 'probe_http_status_code{job=~"portal-health|portal-db-health"}',
        'durations': 'probe_duration_seconds{job=~"portal-health|portal-db-health"}',
        'times': 'timestamp(probe_success{job=~"portal-health|portal-db-health"})',
        'up': 'up{job="blackbox-exporter"}',
        **{m: 'max(timestamp(' + m + '{job="portal-otel"}))' for m in METRICS},
    })
    return json.loads(call(['docker', 'exec', '-i', PREFIX + 'management-worker-1',
                            'python', '-'], timeout=30, input=code))

def index(rows):
    out = {}
    for row in rows:
        key = tuple(sorted((k, v) for k, v in row['metric'].items() if k != '__name__'))
        if key in out:
            raise ValueError('중복 라벨')
        out[key] = float(row['value'][1])
    return out

def samples_ok(data, expected_labels, after, migrated):
    current = time.time()
    probes, statuses, times, durations = (index(data[k]) for k in ('probe', 'status', 'times', 'durations'))
    labels = json.loads(json.dumps([list(x) for x in sorted(probes)]))
    if labels != expected_labels or len(probes) != 3:
        return False
    if statuses.keys() != probes.keys() or times.keys() != probes.keys() or durations.keys() != probes.keys():
        return False
    if not all(probes[k] == 1 and statuses[k] == 200
               and math.isfinite(durations[k]) and 0 <= durations[k] < 8
               and after <= times[k] <= current + 5 and current - times[k] <= 60
               for k in probes):
        return False
    targets = [t for t in data['targets'] if t['labels'].get('job')
               in {'portal-health', 'portal-db-health'}]
    suffix = '/api/v0/component/prometheus.exporter.blackbox.portal_check/metrics' if migrated else '/probe'
    from urllib.parse import urlsplit
    if len(targets) != 3 or not all(t['health'] == 'up'
            and urlsplit(t['scrapeUrl']).path == suffix
            and urlsplit(t['scrapeUrl']).netloc == ('otel-collector:8889' if migrated else 'blackbox:9115')
            for t in targets):
        return False
    up = data['up']
    # The legacy exporter scrape is required before migration only.
    # After migration the duplicate blackbox-exporter job is intentionally absent.
    if migrated:
        if up:
            return False
    elif not (len(up) == 1 and up[0]['metric'].get('instance') == 'blackbox:9115'
              and float(up[0]['value'][1]) == 1):
        return False
    for name in METRICS:
        rows = data[name]
        if len(rows) != 1:
            return False
        at = float(rows[0]['value'][1])
        if not after <= at <= current + 5 or current - at > 60:
            return False
    return True

def web_health():
    code = '''import http.client,ssl,socket
from pathlib import Path
from urllib.parse import urlsplit
from portal.config import Settings
args=Path('/proc/1/cmdline').read_bytes().decode().split('\\0')
def option(k,default=None):return args[args.index(k)+1] if k in args else default
port=int(option('--port','8000'));cert=option('--ssl-certfile')
if cert:
 ctx=ssl.create_default_context(cafile=cert)
 raw=socket.create_connection(('127.0.0.1',port),timeout=5)
 sock=ctx.wrap_socket(raw,server_hostname=urlsplit(Settings().allowed_origin).hostname)
 sock.sendall(b'GET /health HTTP/1.1\\r\\nHost: localhost\\r\\nConnection: close\\r\\n\\r\\n')
 response=http.client.HTTPResponse(sock);response.begin();assert response.status==200
 response.close();sock.close()
else:
 conn=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
 conn.request('GET','/health');assert conn.getresponse().status==200;conn.close()
'''
    call(['docker', 'exec', '-i', PREFIX + 'management-web-1', 'python', '-'], input=code)

def wait_healthy(manifest, after, migrated):
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        baseline_ok(manifest)
        try:
            alloy = inspect('otel-collector')
            old = manifest['alloy']
            volumes = {m['Destination']:m['Source'] for m in alloy['Mounts']
                       if m['Destination'] == '/var/lib/alloy/data'}
            if (alloy['State']['Running'] and alloy['Image'] == old['image']
                    and alloy['RestartCount'] == 0 and volumes == old['volumes']
                    and samples_ok(sample(), manifest['probe_labels'], after, migrated)):
                web_health()
                from datetime import datetime, timezone
                since = datetime.fromtimestamp(after, timezone.utc).isoformat()
                logs = subprocess.run(['docker', 'logs', '--since', since,
                    PREFIX + 'management-worker-1'], capture_output=True, text=True, timeout=15)
                text = logs.stdout + logs.stderr
                if (logs.returncode == 0 and 'probe collection complete' in text
                        and 'login event collection complete' in text
                        and 'unavailable' not in text):
                    return
        except (subprocess.TimeoutExpired, RuntimeError, ValueError, KeyError):
            pass
        time.sleep(3)
    raise RuntimeError('신규 표본·OTLP·Worker·Web 검증 시간 초과')

def timer_stop():
    r=subprocess.run(['systemctl','stop',UNIT+'.timer'],capture_output=True,text=True,timeout=15)
    if r.returncode:
        state=call(['systemctl','show',UNIT+'.timer','--property=LoadState','--value']).strip()
        if state!='not-found':raise RuntimeError('자동 원복 타이머 중지 확인 필요')

def restore(manifest):
    baseline_ok(manifest)
    old = {p:(BACKUP / p).read_bytes() for p in FILES}
    for p, data in old.items():
        if sha(data) != manifest['original_hashes'][p]:
            raise RuntimeError('복구 파일 해시 불일치')
    write_contents(old)
    policy = manifest['blackbox_restart']
    restart = policy['Name']
    if restart == 'on-failure' and policy.get('MaximumRetryCount'):
        restart += ':' + str(policy['MaximumRetryCount'])
    call(['docker', 'update', '--restart=' + restart, PREFIX + 'blackbox-1'])
    call(['docker', 'start', PREFIX + 'blackbox-1'])
    compose(manifest['stack'], 'config', '-q')
    compose(manifest['stack'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never', 'otel-collector')
    at = time.time()
    call(['docker', 'kill', '--signal=HUP', PREFIX + 'prometheus-1'])
    wait_healthy(manifest, at, False)
    timer_stop()
    print('BLACKBOX_ROLLBACK_HEALTHY', flush=True)

def apply(asset_root):
    if BACKUP.exists():
        raise RuntimeError('고정 백업 경로가 이미 있습니다. 재실행하지 마세요.')
    for binary in ('systemd-run', 'systemctl', 'timeout'):
        if not shutil.which(binary):
            raise RuntimeError('자동 원복 도구 없음: ' + binary)
    if call(['systemctl', 'is-active', 'timers.target']).strip() != 'active':
        raise RuntimeError('타이머 기능 확인 필요')
    call(['docker', 'image', 'inspect', 'grafana/alloy:v1.9.1'])
    call(['docker', 'image', 'inspect', 'prom/prometheus:v3.4.1'])
    originals = {p:(ROOT / p).read_bytes() for p in FILES}
    if any(git_hash(originals[p]) != EXPECTED[p] for p in FILES):
        raise RuntimeError('서버 원본 파일이 승인 기준과 다릅니다.')
    web = inspect('management-web')
    paths = require_stack(web['Config']['Labels']['com.docker.compose.project.config_files'].split(','))
    peers = {s:inspect(s) for s in PEERS}
    blackbox, alloy = inspect('blackbox'), inspect('otel-collector')
    if not blackbox['State']['Running'] or not alloy['State']['Running']:
        raise RuntimeError('기존 수집 컨테이너 실행 확인 필요')
    snapshot = sample()
    probe_labels = json.loads(json.dumps([list(k) for k in sorted(index(snapshot['probe']))]))
    manifest = {
        'stack': paths,
        'peers': {s:{'id':v['Id'], 'image':v['Image'], 'restarts':v['RestartCount']}
                  for s,v in peers.items()},
        'alloy': {'image':alloy['Image'], 'volumes':{
            m['Destination']:m['Source'] for m in alloy['Mounts']
            if m['Destination'] == '/var/lib/alloy/data'}},
        'blackbox_id': blackbox['Id'],
        'blackbox_restart':blackbox['HostConfig']['RestartPolicy'],
        'probe_labels':probe_labels,
        'original_hashes':{p:sha(v) for p,v in originals.items()},
        'unchanged':{},
    }
    for path in [p for p in paths if p not in [str(ROOT/f) for f in FILES]] + [str(ROOT/'.env'),str(ROOT/'.management.env')]:
        p=Path(path);manifest['unchanged'][path]=sha(p.read_bytes()) if p.is_file() else None
    baseline_ok(manifest)
    web_health()
    if not samples_ok(snapshot, probe_labels, time.time()-60, False):
        raise RuntimeError('전환 전 정상 수집 기준 미충족')
    target = candidates(asset_root, originals)
    # Validate full integration without touching live files or contacting targets.
    with tempfile.TemporaryDirectory(prefix='schutz-blackbox-validate-') as temp:
        folder=Path(temp);folder.chmod(0o755)
        for key,data in [('config.alloy',target[FILES[1]]),('prometheus.yaml',target[FILES[2]])]:
            (folder/key).write_bytes(data);(folder/key).chmod(0o644)
        call(['docker','run','--rm','--pull=never','--network','none',
              '--volumes-from',PREFIX+'blackbox-1:ro','-v',str(folder/'config.alloy')+':/tmp/config.alloy:ro',
              'grafana/alloy:v1.9.1','validate','/tmp/config.alloy'])
        call(['docker','run','--rm','--pull=never','--network','none','--entrypoint','promtool',
              '-v',str(folder)+':/check:ro','-v',str(ROOT/'monitoring/alerts.yaml')+':/etc/prometheus/alerts.yaml:ro',
              'prom/prometheus:v3.4.1','check','config','/check/prometheus.yaml'])
    BACKUP.mkdir(parents=True,mode=0o700)
    for path,data in originals.items():
        saved=BACKUP/path;saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(data);saved.chmod(0o600)
    (BACKUP/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (BACKUP/'manifest.json').chmod(0o600)
    # A root-owned, persistent script is required for unattended rollback.
    script=Path(__file__).resolve()
    if script.stat().st_uid != 0 or script.stat().st_mode & 0o022:
        raise RuntimeError('실행 스크립트는 root 소유·쓰기 제한 상태여야 합니다.')
    call(['systemd-run','--unit='+UNIT,'--on-active=6m','/usr/bin/timeout',
          '--signal=TERM','--kill-after=30s','360s',sys.executable,str(script),'rollback',
          '--confirmation','ROLLBACK_BLACKBOX','--watchdog'])
    signal.alarm(240)
    try:
        write_contents(target)
        compose(paths,'config','-q')
        # Confirm same secret and data volume paths via merged model before recreation.
        merged=merged_candidate(paths)
        config=merged['services']['otel-collector']
        if (config['image']!='grafana/alloy:v1.9.1'
                or 'manual-blackbox' not in merged['services']['blackbox'].get('profiles',[])):
            raise RuntimeError('병합 후보 구성 확인 실패')
        compose(paths,'up','-d','--no-deps','--no-build','--pull','never','otel-collector')
        at=time.time();call(['docker','kill','--signal=HUP',PREFIX+'prometheus-1'])
        wait_healthy(manifest,at,True)
        if inspect('blackbox')['Id'] != manifest['blackbox_id']:
            raise RuntimeError('기존 Blackbox가 변경됐습니다.')
        call(['docker','update','--restart=no',PREFIX+'blackbox-1'])
        call(['docker','stop','--time','10',PREFIX+'blackbox-1'])
        at=time.time();wait_healthy(manifest,at,True)
        baseline_ok(manifest)
        timer_stop()
        signal.alarm(0)
        (BACKUP/'applied.ok').write_text('검증 성공\n')
        print('BLACKBOX_ALLOY_RELEASE_SUCCESS',flush=True)
        print('WEB_WORKER_DB_PROMETHEUS_UNCHANGED',flush=True)
        print('BACKUP='+str(BACKUP),flush=True)
    except BaseException:
        signal.alarm(0)
        # Allow recovery to finish after a termination request.
        for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):
            signal.signal(sig,signal.SIG_IGN)
        print('전환 실패 — 기존 구성 복구 시작',flush=True)
        try:
            restore(manifest)
        except BaseException:
            print('복구 확인 실패 — 백업과 타이머를 보존했습니다. 결과를 전달해주세요.',flush=True)
        raise

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['apply','rollback'])
    parser.add_argument('--confirmation',required=True)
    parser.add_argument('--watchdog',action='store_true')
    args=parser.parse_args()
    expected='APPLY_BLACKBOX' if args.mode=='apply' else 'ROLLBACK_BLACKBOX'
    if args.confirmation != expected:
        raise SystemExit('확인 문구 불일치')
    if os.geteuid()!=0 or call(['hostname']).strip()!='ip-10-20-20-10':
        raise SystemExit('모니터링 서버의 sudo 권한으로 실행해주세요.')
    os.umask(0o077)
    os.chdir(ROOT)
    # Same lock as Web/Worker releases; never deploy concurrently.
    with (ROOT/'.management-release.lock').open('a') as lock:
        deadline=time.monotonic()+120 if args.watchdog else time.monotonic()
        while True:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise RuntimeError('공통 배포 잠금 사용 중')
                time.sleep(1)
        def interrupted(*_):raise SystemExit('중단 요청')
        for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP,signal.SIGALRM):signal.signal(sig,interrupted)
        if args.mode=='apply':
            apply(Path(__file__).resolve().parent.parent)
        else:
            if args.watchdog and (BACKUP/'applied.ok').exists():
                print('자동 원복 생략 — 배포 검증 완료');return
            manifest=json.loads((BACKUP/'manifest.json').read_text())
            restore(manifest)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('실행 중지:',type(error).__name__,str(error),flush=True)
        sys.exit(1)

