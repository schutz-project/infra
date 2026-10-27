#!/usr/bin/env python3
"""격리 Docker 환경에서 기존 Collector와 Alloy의 저장 지표를 비교합니다."""
import json
import os
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = f'schutz-otel-check-{os.getpid()}'
NETWORK = PREFIX
CREATED = []
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()

def get(url):
    with OPENER.open(url, timeout=10) as response:
        return json.load(response)

def run(name, image, *args, volumes=(), publish=(), alias=None):
    full_name = PREFIX + '-' + name
    command = ['run', '-d', '--name', full_name, '--network', NETWORK]
    if alias:
        command += ['--network-alias', alias]
    for source, target in volumes:
        command += ['-v', f'{source}:{target}:ro']
    for mapping in publish:
        command += ['-p', mapping]
    command += [image, *args]
    docker(*command)
    CREATED.append(full_name)
    return full_name

def post(port, payload):
    request = urllib.request.Request(
        f'http://127.0.0.1:{port}/v1/metrics',
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'},
    )
    with OPENER.open(request, timeout=10) as response:
        result = json.load(response)
    assert not result.get('partialSuccess'), result

def query(job):
    expression = '{__name__=~"portal_.*",job="' + job + '"}'
    result = get('http://127.0.0.1:18091/api/v1/query?' +
                 urllib.parse.urlencode({'query': expression}))
    assert result['status'] == 'success', result
    return {
        tuple(sorted((key, value) for key, value in row['metric'].items() if key != 'job')):
        float(row['value'][1]) for row in result['data']['result']
    }

with tempfile.TemporaryDirectory(prefix='schutz-otel-ci-') as directory:
    work = Path(directory)
    work.chmod(0o755)
    prom = work / 'prometheus.yaml'
    prom.write_text('global:\n  scrape_interval: 1s\nscrape_configs:\n'
                    '  - job_name: portal-otel\n    static_configs:\n'
                    '      - targets: [otel-collector:8889]\n')
    # 통합 운영 Alloy 설정이 참조하는 Blackbox 파일과 인증 파일을
    # 격리 CI 컨테이너에만 제공하며 실제 운영 비밀값은 사용하지 않습니다.
    secret_dir = work / 'secrets'
    secret_dir.mkdir(mode=0o755)
    test_token = secret_dir / 'internal-check-token'
    test_token.write_text('ci-only-placeholder-token\\n')
    test_token.chmod(0o644)
    alloy = work / 'config.alloy'
    alloy.write_text((ROOT / 'monitoring/alloy-otel.alloy').read_text().replace(
        'replacement  = "portal-otel"', 'replacement  = "portal-otel-candidate"'))
    try:
        docker('network', 'create', NETWORK)
        run('prometheus', 'prom/prometheus:v3.4.1',
            '--config.file=/etc/prometheus/prometheus.yaml',
            '--web.enable-remote-write-receiver',
            volumes=[(prom, '/etc/prometheus/prometheus.yaml')],
            publish=['127.0.0.1:18091:9090'], alias='prometheus')
        run('legacy', 'otel/opentelemetry-collector-contrib:0.128.0',
            '--config=/etc/otelcol/config.yaml',
            volumes=[(ROOT / 'monitoring/otel.yaml', '/etc/otelcol/config.yaml')],
            publish=['127.0.0.1:14318:4318'], alias='otel-collector')
        run('alloy', 'grafana/alloy:v1.9.1', 'run',
            '--storage.path=/tmp/alloy', '--server.http.listen-addr=0.0.0.0:8889',
            '/etc/alloy/config.alloy',
            volumes=[(alloy, '/etc/alloy/config.alloy'),
                     (ROOT / 'monitoring/blackbox.yaml', '/etc/blackbox/config.yaml'),
                     (test_token, '/run/secrets/internal-check-token')],
            publish=['127.0.0.1:14319:4318'])

        # 신규 WAL 초기 재생을 마친 뒤 실제 앱처럼 연속된 표본을 전송합니다.
        time.sleep(5)
        stamp = time.time_ns()
        attributes = [
            {'key': 'http.route', 'value': {'stringValue': '/health'}},
            {'key': 'http.response.status_code', 'value': {'intValue': '200'}},
        ]
        point = {'attributes': attributes, 'startTimeUnixNano': str(stamp - 1_000_000_000),
                 'timeUnixNano': str(stamp)}
        metrics = [{
            'name': 'portal.http.requests', 'unit': '{request}',
            'sum': {'aggregationTemporality': 2, 'isMonotonic': True,
                    'dataPoints': [{**point, 'asInt': '3'}]},
        }]
        for metric in ('portal.http.duration', 'portal.db.duration'):
            metrics.append({
                'name': metric, 'unit': 'ms',
                'histogram': {'aggregationTemporality': 2, 'dataPoints': [{
                    **point, 'count': '3', 'sum': 12,
                    'explicitBounds': [5, 10], 'bucketCounts': ['2', '1', '0'],
                }]},
            })
        payload = {'resourceMetrics': [{
            'resource': {'attributes': [
                {'key': 'service.name', 'value': {'stringValue': 'portal-api'}},
                {'key': 'deployment.environment.name', 'value': {'stringValue': 'test'}},
            ]},
            'scopeMetrics': [{'scope': {'name': 'portal'}, 'metrics': metrics}],
        }]}

        for port in (14318, 14319):
            last = None
            for attempt in range(30):
                try:
                    post(port, payload)
                    break
                except Exception as error:
                    last = error
                    time.sleep(2)
            else:
                raise RuntimeError(f'OTLP 수신 실패: {port}') from last

        for attempt in range(45):
            baseline = query('portal-otel')
            candidate = query('portal-otel-candidate')
            if baseline and candidate:
                names = {dict(key)['__name__'] for key in baseline}
                required = {'portal_http_requests', 'portal_http_duration_bucket',
                            'portal_http_duration_count', 'portal_http_duration_sum',
                            'portal_db_duration_bucket', 'portal_db_duration_count',
                            'portal_db_duration_sum'}
                assert required <= names, names
                if baseline == candidate:
                    print('OTLP HTTP 수신·메트릭 이름·라벨·카운터·히스토그램 일치')
                    print('OTEL_ALLOY_PIPELINE_VERIFIED')
                    break
            time.sleep(2)
        else:
            print('기존:', baseline)
            print('후보:', candidate)
            print('후보 전체 지표:', get('http://127.0.0.1:18091/api/v1/query?' +
                  urllib.parse.urlencode({'query': '{job="portal-otel-candidate"}'})))
            print('전체 이름:', get('http://127.0.0.1:18091/api/v1/label/__name__/values'))
            address = json.loads(docker('inspect', PREFIX + '-alloy'))[0]['NetworkSettings']['Networks'][NETWORK]['IPAddress']
            with OPENER.open(f'http://{address}:8889/metrics', timeout=10) as response:
                diagnostic = response.read().decode()
            print('후보 처리 통계:', '\n'.join(line for line in diagnostic.splitlines()
                  if not line.startswith('#') and any(word in line for word in
                  ('metric_points', 'samples_', 'dropped', 'failed', 'queue_', 'exporter_sent'))))
            raise AssertionError('기존 Collector와 Alloy의 저장 지표 불일치')
    finally:
        for name in reversed(CREATED):
            subprocess.run(['docker', 'logs', '--tail', '30', name], check=False)
            subprocess.run(['docker', 'rm', '-f', name], check=False)
        subprocess.run(['docker', 'network', 'rm', NETWORK], check=False)
