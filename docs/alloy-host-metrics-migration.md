# Node Exporter의 Alloy 통합

## 변경 범위

infra 전용 변경이다. fast-api, management-web, management-worker와 현재 운영 파일은 수정하지 않는다. PR 병합만으로 EC2 설정이 적용되지 않는다. 기존 Compose/config.alloy/prometheus.ec2.yaml은 그대로 두고 전환용 파일을 추가한다.

실제 확인한 기존 설정:
- Node Exporter prom/node-exporter:v1.9.1, PID host, network exporters_default.
- /:/host:ro,rslave와 --path.rootfs=/host.
- filesystem 제외 규칙은 새 Alloy 설정에 그대로 반영.
- 기존 포트 10.20.10.62:9100.
- Alloy grafana/alloy:v1.9.1, /opt/schutz/alloy/compose.yaml, 영구 저장소 schutz-alloy_alloy-data.
- 기존 Alloy 로그 파일 수집은 유지한다.

## 구성 파일

| 파일 | 용도 |
| --- | --- |
| service/alloy/host-metrics-check.alloy | 로그를 수집하지 않는 임시 호스트 메트릭 비교 |
| service/alloy/compose.host-metrics-check.yaml | 별도 프로젝트, 호스트 loopback 19100에서만 후보 실행 |
| scripts/check-host-metrics.py | 실제 Linux 호스트의 CPU 식별자·메모리·루트 파일시스템·네트워크와 비교 |
| service/alloy/config.host-metrics.alloy | 기존 로그 수집과 unix exporter를 합친 최종 설정 |
| service/alloy/compose.host-metrics.yaml | 기존 Alloy의 호스트 마운트·PID/네트워크와 private 9100 설정 |
| monitoring/prometheus.alloy-host.yaml | ec2-node의 metrics_path만 변경한 최종 Prometheus 설정 |
| .github/workflows/alloy-host-metrics.yml | v1.9.1 문법, Compose, Prometheus 및 실제 호스트 비교 CI |

최종 경로는 Prometheus → 10.20.10.62:9100/api/v0/component/prometheus.exporter.unix.host/metrics이다. job=ec2-node, instance=10.20.10.62:9100과 node_* 이름을 유지한다. remote_write receiver를 새로 열지 않고 기존 pull 방식을 유지한다. Alloy 내부 exporter target의 instance 라벨을 별도로 전달하지 않고, 외부 Prometheus scrape가 기존 라벨을 부여한다.

Alloy의 HTTP 관리 인터페이스도 같은 listener에 있으므로 이 포트는 기존 모니터링 서버 등 허용된 출처에만 제한한다. 공개 보안 그룹을 추가하지 않는다. 호스트 network/PID는 실제 네트워크 메트릭을 수집하기 위한 권한 변경이다. 기존 Exporter는 bridge 네트워크였으므로 네트워크 값은 기존 컨테이너 값과 같다는 이유만으로 통과시키지 않고 호스트 /proc/net/dev와 비교한다.

## 1. 임시 비교 — 기존 Node Exporter와 Alloy 유지

서비스 EC2에 다음 두 파일을 같은 임시 디렉터리로 복사한다:
- compose.host-metrics-check.yaml
- host-metrics-check.alloy

그 디렉터리에서 실행한다:

```bash
docker compose -p schutz-alloy-host-check -f compose.host-metrics-check.yaml config -q
docker compose -p schutz-alloy-host-check -f compose.host-metrics-check.yaml up -d
curl --noproxy '*' -fsS http://127.0.0.1:19100/-/ready
python3 /path/to/check-host-metrics.py
```

검사기는 root 권한의 서비스 호스트에서 실행한다. 파일 경로는 실제 복사 경로로 대체한다. 성공 표시는 ALLOY_HOST_METRICS_VERIFIED이다. 현재 CPU 사용률과 메모리 가용량은 시간에 따라 달라지므로 CPU 카운터의 절대값 일치를 요구하지 않는다. 메모리·디스크 가용값은 제한된 오차만 허용한다. 기존 Node Exporter의 /metrics도 보존해 핵심 이름·단위·filesystem fstype/device와 기존 쿼리가 선택하는 시계열을 비교한다. 이 비교가 끝나기 전 기존 수집기를 중지하지 않는다.

검사가 끝나면 임시 프로젝트만 종료한다:

```bash
docker compose -p schutz-alloy-host-check -f compose.host-metrics-check.yaml down
```

운영 로그를 이 임시 컨테이너가 읽지 않으므로 로그 중복 전송과 영구 positions 충돌을 피한다. 서비스와 같은 호스트에서 임시 Alloy가 추가 실행되므로 자원 여유도 확인한다.

## 2. 최종 전환 — 서비스와 모니터링을 함께 조정

이 단계는 1단계 비교와 CI 통과 후 수행한다.

1. 실제 /opt/schutz/alloy의 Compose/config와 모니터링 Prometheus의 실제 bind mount·명령 인자를 확인한다. 필요한 파일과 기존 이미지/컨테이너 설정을 권한 제한 디렉터리에 백업한다. 비밀 환경 변수는 커밋하지 않는다.
2. 포털 정상 상태, Loki 최신 로그, Prometheus 기존 ec2-node up=1을 기록한다. 별도 Node Exporter의 재시작 정책도 보존한다.
3. Grafana/관리 웹 소비 쿼리의 job·instance·필수 node_* 이름을 비교한다. 관리 웹은 ec2-node를 사용하므로 앱 코드는 바꾸지 않는다.
4. 서비스 서버에 최종 config.host-metrics.alloy와 compose.host-metrics.yaml을 복사하고 config와 Alloy validate를 실행한다. 기존 로그 수집 설정이 서버 실제 파일과 동일한지도 대조한다.
5. 배포/구성 변경을 직렬화한다. 기존 schutz-node-exporter를 stop하여 9100을 확보한다. 삭제하지 않는다. 이후 재부팅 때 자동 재시작하지 않도록 최종 성공 후 restart=no로 변경하고 기존 정책을 복구 기록에 남긴다.
6. /opt/schutz/alloy에서 기존 프로젝트 이름 schutz-alloy와 원래 Compose를 유지한 채 최종 override를 마지막에 적용한다:

```bash
docker compose -p schutz-alloy -f compose.yaml -f compose.host-metrics.yaml config -q
docker compose -p schutz-alloy -f compose.yaml -f compose.host-metrics.yaml up -d --no-deps alloy
python3 /path/to/check-host-metrics.py --url http://10.20.10.62:9100/api/v0/component/prometheus.exporter.unix.host/metrics
```

7. 호스트 지표와 Alloy 준비 상태, Loki 로그 도착을 확인한다. 기존 Alloy 저장 볼륨/positions를 새로 만들거나 지우지 않는다.
8. Prometheus 실제 활성 설정을 백업하고 ec2-node에 metrics_path: /api/v0/component/prometheus.exporter.unix.host/metrics를 추가한다. 현재 파일이 저장소 기준과 같을 때만 prometheus.alloy-host.yaml 전체를 사용할 수 있다. 추가된 운영 scrape job이 있으면 전체 덮어쓰기를 금지한다.
9. promtool check config 성공 후 기존 운영 방식으로 reload한다. HTTP reload는 --web.enable-lifecycle이 확인된 경우만 사용하고, 그 외에는 컨테이너 SIGHUP 등의 기존 경로를 따른다.
10. 최소 3회 scrape 동안 up=1, node_scrape_collector_success, 최신 timestamp, 중복 instance 부재를 확인한다. CPU rate는 카운터 리셋으로 잠시 비어 있거나 낮게 보일 수 있으므로 5분 구간도 확인한다.
11. 관리 웹 CPU/메모리/디스크, 앱/DB 점검, Loki 앱·Nginx 로그, 로그인 실패 수집 경로를 확인한다. 두 exporter 버전의 추가 지표 차이가 있으면 문서화한다.

9100의 경로와 exporter가 바뀌므로 전환 중 일시적 수집 공백이 있을 수 있다. 0초 무중단을 보장하지 않는다. 알려진 수집 경보·사건이 새로 발생했는지 확인하고 시험으로 식별한다. 새 포트를 외부에 열지 않는다.

## 복구

성공 조건에 미달하면 기존 Node Exporter를 삭제하거나 볼륨을 정리하지 않는다.

1. 원래 schutz-alloy 프로젝트에서 원본 Compose만 사용하여 Alloy를 원래 명령·bridge 네트워크·로그 설정으로 복원한다. 9100 listener가 해제됐는지 확인한다.
2. 기존 Node Exporter의 재시작 정책을 복원하고 start한다.
3. Prometheus의 기존 설정 백업을 복원하고 promtool 검증 후 reload한다.
4. 기존 /metrics, ec2-node up=1, 최신 지표와 Loki 로그 도착, 포털 기능을 확인한다.

실제 활성 Compose 경로가 바뀌므로 이후 Alloy 운영 명령에는 최종 override를 반드시 포함한다. 서비스 API의 기존 CI/CD와 배포 잠금·롤백 파일은 변경하지 않는다.

## 검증 상태와 제한

### 실제 적용 결과 — 2026-10-24 (한국 시각)

사용자가 서비스/모니터링 EC2에서 실행한 출력과 관리자 화면으로 확인했다. 작성 에이전트가 AWS에 직접 접속한 결과는 아니다.

- GitHub CI: 고정 Alloy v1.9.1 설정 검증, Compose 병합·Prometheus 설정 검사, Linux 호스트 비교 검사 통과.
- 서비스 EC2 실측: CPU 2개 식별자, 전체/가용 메모리, 루트 파일시스템 크기, ens5와 호스트 네트워크 인터페이스 일치. 필수 cpu/meminfo/filesystem/netdev 수집 성공. ALLOY_HOST_METRICS_VERIFIED 확인.
- 서비스 전환: 실제 서버의 기존 로그 config에 unix exporter를 추가하고 Compose override 적용. ALLOY_SERVICE_SWITCH_OK와 포털 HTTP 정상 확인.
- Prometheus: 실제 활성 파일 /opt/schutz-monitoring/monitoring/prometheus.ec2.yaml에 metrics_path를 추가하고 promtool 검증 후 SIGHUP 적용. 새 scrape URL health=up, lastError 비어 있음, job/instance 유지. PROMETHEUS_ALLOY_SWITCH_OK 확인.
- 대시보드: CPU 2.35%, 메모리 21.88%, 루트 디스크 21.47% 표시. 최근 Nginx HTTP 200 로그 확인.
- 기존 schutz-node-exporter: running=false, restart=no. NODE_EXPORTER_RETIRED 확인. 컨테이너와 이미지·백업은 삭제하지 않고 복구용 보존.
- 실제 적용한 compose.host-metrics.yaml은 의미상 동일한 JSON 문법으로 작성했다. 운영 명령에 원본 Compose와 이 override를 모두 포함해야 한다.

### 실행 중 확인한 문제

처음에는 서비스 서버 전환이 실행되지 않은 상태에서 모니터링 설정만 변경해 새 경로 수집 확인에 실패했다. Prometheus 원본 설정으로 복구 후 기존 /metrics의 up 상태를 확인했다. 이후 호스트명을 확인하고 서비스 → 모니터링 순서로 적용해 성공했다. 시간 문자열 해석 문제는 Python 3.12.3 검사로 배제했다.

docker cp로 복사한 promtool 검사 파일은 root 전용 권한 때문에 Prometheus 사용자가 읽지 못했다. 컨테이너 내부 임시 설정 파일만 chmod 644 후 검사했다. 운영 원본 파일 권한을 무조건 완화하지 않는다.

### 백업 및 복구 위치

- 서비스: /opt/schutz/alloy/.node-to-alloy-backup/ — 원본 compose/config, 기존 Node Exporter inspect 기록, rollback.sh, 새 metrics 확인 파일.
- 모니터링: /opt/schutz-monitoring/.alloy-host-migration/ — original.yaml과 candidate.yaml.
- 서비스 rollback.sh는 restart=no 변경 전에 작성됐다. 완전 복구 시 node-exporter.json에 보존한 기존 RestartPolicy도 복원해야 한다. 알려지지 않은 정책을 임의로 설정하지 않는다.
- 두 서버 원본 설정 복구와 Prometheus SIGHUP은 함께 수행한다. 서비스만 복구하면 Prometheus가 Alloy 전용 경로를 계속 요청하므로 지표가 끊긴다.

### 남은 확인

최종 Alloy 경로로 전환한 이후 호스트 전체 비교 검사 재실행, 최소 3회 최신 scrape/5분 CPU rate 확인, 최신 앱 이벤트 로그와 로그인 수집, 전환 중 생성됐을 수 있는 사건 확인은 별도 점검 대상으로 남긴다. 최종 화면에서 확인한 로그는 Nginx 로그이므로 앱 로그까지 확인했다고 기록하지 않는다.

management-web의 “Node Exporter로 수집한” 안내 문구는 현재 구현에 맞춰 별도 수정해야 한다. OTel SDK/별도 Collector, Grafana 통합과 기존 Node Exporter 컨테이너 삭제는 이번 적용에 포함하지 않았다.

근거: grafana/alloy v1.9.1의 prometheus.exporter.unix 문서 및 exporter HTTP handler 구현. 앱 OTel SDK/Collector 통합은 이 PR의 범위가 아니다.
