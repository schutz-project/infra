# 두 서버 관측 — 읽기 전용 운영 증거 수집

상태: 후보 적용 전 확인용. 서비스 시작·재시작·설정 변경·부하 요청 없음. 아래 출력에 환경변수·인증 토큰·전체 Compose 렌더링·컨테이너 로그를 포함하지 않는다.

## 1. 실제 실행 구성

모니터링 EC2에서 세 명령을 각각 실행하고 결과를 UTC 수집 시각과 함께 기록한다. 대상 컨테이너가 복수면 각 행을 유지하고 임의로 하나만 고르지 않는다.

```bash
date -u '+collected_at_utc=%Y-%m-%dT%H:%M:%SZ'
sudo docker ps -aq --filter label=com.docker.compose.service=prometheus |
  xargs -r sudo docker inspect --format 'project={{index .Config.Labels "com.docker.compose.project"}} files={{index .Config.Labels "com.docker.compose.project.config_files"}} workdir={{index .Config.Labels "com.docker.compose.project.working_dir"}} image_id={{.Image}} running={{.State.Running}}'
sudo docker ps -aq --filter label=com.docker.compose.service=otel-collector |
  xargs -r sudo docker inspect --format 'service={{index .Config.Labels "com.docker.compose.service"}} project={{index .Config.Labels "com.docker.compose.project"}} image_id={{.Image}} running={{.State.Running}}'
```

Compose 파일 순서와 Prometheus의 실제 설정 bind mount, 공통 네트워크는 `docker inspect`에서 **경로·이름만** 추린다. 환경변수·전체 Config·전체 NetworkSettings를 출력하지 않는다.

```bash
sudo docker ps -aq --filter label=com.docker.compose.service=prometheus |
  xargs -r sudo docker inspect --format '{{range .Mounts}}mount={{.Source}} -> {{.Destination}} read_write={{.RW}}{{println}}{{end}}{{range $name, $_ := .NetworkSettings.Networks}}network={{$name}}{{println}}{{end}}'
```

실제 mount된 설정 파일의 SHA-256과 소유권·mode만 기록한다. **파일 내용은 출력하지 않는다.** 현재 활성 파일 경로를 위 출력에서 먼저 확인해 `ACTUAL_CONFIG`를 직접 지정한다.

```bash
ACTUAL_CONFIG=/실제/확인한/경로/prometheus.yaml
sudo sha256sum -- "$ACTUAL_CONFIG"
sudo stat -c 'uid=%u gid=%g mode=%a path=%n' -- "$ACTUAL_CONFIG"
```

## 2. 현재 두 호스트 표본

Prometheus에 로컬 포트로 접속 가능한 승인된 읽기 경로에서 다음 PromQL만 조회한다. API 주소, role 라벨, sample timestamp/value만 보관한다. Prometheus가 컨테이너 내부에서만 접근 가능하다면 기존 승인된 조회 경로를 사용한다. 새 포트 공개는 하지 않는다.

| 목적 | PromQL | 판단 |
| --- | --- | --- |
| 수집 성공 | `up{job="ec2-node"}` | 각 instance·server_role 및 1/0. `up=1`만으로 자원 지표 정상 단정 금지 |
| 실제 메모리 표본 시각 | `timestamp(node_memory_MemTotal_bytes{job="ec2-node"})` | service와 monitoring 각각의 원본 시각을 UTC로 변환 |
| CPU | `100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{job="ec2-node",mode="idle"}[5m])))` | 두 호스트 개별 표본. rate 준비 전 빈 결과와 실패 구별 |
| 메모리 | `100 * (1 - node_memory_MemAvailable_bytes{job="ec2-node"} / node_memory_MemTotal_bytes{job="ec2-node"})` | 수집 시각·값의 유효성 |
| 디스크 | `100 * (1 - node_filesystem_avail_bytes{job="ec2-node",mountpoint="/",fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{job="ec2-node",mountpoint="/",fstype!~"tmpfs|overlay"})` | 실제 호스트 루트와 mountpoint/fstype 비교 |

각 쿼리에 대해 조회 UTC 시각, `instance`, `server_role`, `value[0]` 평가 시각, `value[1]` 숫자를 기록한다. 두 번째 쿼리에서 `value[1]`은 `timestamp(...)` 함수가 돌려준 **원본 표본 시각**이다. 3회 연속 scrape와 간격도 별도로 확인한다. 현재 역할 라벨이 없다면 `unknown`으로 기록하고 주소만으로 역할을 추측하지 않는다.

## 3. 적용 가능 여부

현재 설정과 Git 후보의 차이를 검토하고, Alloy 실제 버전·마운트·read-only 경로와 후보 Compose 네트워크를 확인한다. `docker compose config`는 민감한 환경변수를 렌더링할 수 있으므로 전체 출력을 공유하지 않는다. 후보에 대한 Docker Compose, Alloy validate, promtool check config 성공 로그와 위 운영 자료가 모이면 적용·복구 계약의 `미확인` 항목을 실제 값으로 채운다.

서버 적용과 LOAD-01 실제 시험은 이 자료 수집과 별개의 승인 단계다.
