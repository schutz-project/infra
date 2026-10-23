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

로컬 Python 컴파일·YAML 구문 검증을 수행했다. 이 작성 환경에는 Docker가 없어 Alloy v1.9.1 실행 검증은 GitHub CI에서 수행한다. CI가 통과해도 EC2 실측·Loki 도착·Prometheus 전환은 별도 확인이 필요하다. 기존 에이전트 제거와 서버 적용은 아직 수행하지 않았다.

근거: grafana/alloy v1.9.1의 prometheus.exporter.unix 문서 및 exporter HTTP handler 구현. 앱 OTel SDK/Collector 통합은 이 PR의 범위가 아니다.
