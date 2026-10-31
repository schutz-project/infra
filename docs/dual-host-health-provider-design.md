# LOAD-01 후보 health 공급자 — Prometheus 증거 설계

상태: v0.2 후보와 LOAD-01 v7 로컬 소비자를 대조한 설계. **구현·운영 연결·배포되지 않음.** v7은 `--candidate-health-file`로 loopback 로컬 모의 입력만 받으며, 이 문서는 실제 운영 실행을 허용하지 않는다.

`scripts/dual_host_snapshot.py`에 **이미 조회된 모의 instant vector만** 받는 순수 후보 변환기를 추가했다. 역할·instance 및 원본 메모리/디스크 시계열 중복, CPU 코어 중복, `up`의 원본 표본 시각과 지표별 stale/future, 용량·idle rate 범위를 거부한다. 원본 `timestamp(...)` 값에서 가장 오래된 입력 시각을 출력한다. `tests/test_dual_host_snapshot.py`의 로컬 fixture 회귀로 검사한다. 이 함수는 Prometheus 조회, 쿼리 문자열·응답 출처 검증, 파일 발행, dashboard probe, 권한 확인을 **수행하지 않는다**. 따라서 출력 JSON의 `source` 문자열이나 `dashboard_ok` 인자를 운영 신뢰 근거로 사용할 수 없다.

## 입력과 역할 매핑

후보 Prometheus의 `ec2-node` job에서 `up`과 node 원본 시계열을 **aggregation 이전 형태**로 조회한다. `server_role=service|monitoring`가 각 하나의 `instance`에만 매핑되는지 확인한다. 역할 누락·중복 instance·역할별 복수 instance·같은 instance의 중복 원본 시계열·0건·부분 실패는 스냅샷 발행 실패로 처리한다. `max by(instance)`와 같은 Web 표시용 집계는 중복을 숨길 수 있어 공급자 검증 근거로 사용하지 않는다. 주소 형식으로 역할을 추측하지 않는다.

| 출력 | 원본 시계열 확인 | 원본 시각 기준 |
| --- | --- | --- |
| `up` | `up{job="ec2-node"}`와 `timestamp(up{job="ec2-node"})`의 role·instance별 정확히 1개, 값 1 | timestamp 쿼리 반환 값으로 원본 scrape 시각 확인 |
| CPU | `node_cpu_seconds_total{job="ec2-node",mode="idle"}`의 각 cpu 원본 + 5분 rate 결과 | rate의 평가 시각이 아니라 입력 idle counter의 **최소 최신 표본 시각**. 각 cpu 집합·rate 유효성 확인 |
| 메모리 | `node_memory_MemAvailable_bytes`, `node_memory_MemTotal_bytes` | 두 원본 시계열 최신 시각의 최소값. 0보다 큰 total과 0~100% 확인 |
| 루트 디스크 | `node_filesystem_avail_bytes` 및 `node_filesystem_size_bytes`의 `mountpoint="/"`, 제외 fstype | 두 원본 최신 시각의 최소값. 루트 mount가 각 instance에 정확히 하나인지, size>0인지 확인 |

Prometheus instant vector의 `value[0]`은 평가 시각이다. `timestamp(raw_metric)`의 `value[1]`이 그 원본 metric의 최근 표본 시각이다. `up`도 `up_time=timestamp(up{job="ec2-node"})`를 별도로 받아 원본 시각을 검사한다. CPU rate와 메모리 비율, 디스크 비율의 `value[1]`은 **계산된 수치**이므로 시각으로 취급하지 않는다. 평가 시각만 신선하고 원본 데이터가 오래된 경우 fail-closed로 처리한다. 쌍을 이루는 값/시각 벡터의 job·role·instance와 CPU mode/cpu, 디스크 mountpoint/device/fstype가 일치해야 한다. 두 서버의 실제 exporter 구성에 따라 label과 루트 mountpoint를 읽기 전용 표본으로 대조한다.

## 발행 계약과 신뢰 경계

- 구조는 `dual-host-health/v0.2-candidate`의 `hosts.<role>.<cpu|memory|disk>.{pct,sample_at_utc}`, `instance`, `up`, `generated_at_utc`, `snapshot_id`, `dashboard_ok`다. v7 파서와 모양이 맞아도 **운영 합의 버전은 아니다**.
- `source="prometheus"`는 설명 문자열이며 인증이 아니다. 승인된 실행 프로세스·Prometheus 조회 권한·출력 파일의 소유권·접근 제한·갱신 주기를 함께 검증한다. 비밀키·토큰·인증 쿠키는 스냅샷이나 공유 로그에 포함하지 않는다.
- 지표별 최대 표본 지연과 미래 허용 오차는 운영 scrape 주기·네트워크 지연·시계 오차 실측 후 결정한다. v7 로컬 상수 15초/5초를 실제 운영으로 승격하지 않는다.
- 전체 6개 지표와 두 `up` 판정이 한 번에 성공할 때만 하나의 snapshot_id로 같은 파일시스템의 임시 파일을 완성·검증하고 원자적으로 교체한다. 부분 성공을 이전 정상값과 합성하지 않는다. 공급자 중단 시 오래된 파일은 소비자가 지연으로 거부해야 한다.
- `dashboard_ok`는 별도의 승인된 읽기 전용 기능 점검에 근거해야 하며, 단순 HTTP 200 또는 Web `resources.status=ok` 하나만으로 참이 되지 않는다. 실제 접근 방식이 정해지기 전에는 참을 발행할 수 없다.

## v7 교차검토 결론

v7 `candidate_health.py`는 로컬에서 두 역할·instance 중복·지표별 표본 시각·0~100 범위·누락/지연을 검증한다. `python3 -m unittest discover -s tests -v`는 **48/48 통과**했다. 자원 85% 30초 지속으로 멈출 때의 `stop_detail`은 role/metric만 추정하고 `snapshot_id=None`, `sample_at_utc=None`이어서 계약의 중단 증거가 아직 불완전하다. 실제 파일 갱신·원자적 발행·운영 출처 검증도 미구현이다.

관측 후보 CI의 Compose/Alloy/promtool 검사, 실제 브라우저 검수, 운영 두 호스트 표본은 별도로 확보해야 한다. 이 설계와 로컬 테스트만으로 서버 적용이나 실제 LOAD-01을 진행하지 않는다.
