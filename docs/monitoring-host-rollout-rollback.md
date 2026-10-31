# 두 서버 관측 후보 적용·복구 계약 v0.2

상태: 검토 초안. 실제 운영 경로 확인 및 별도 승인 전 실행 금지.

## 적용 전 채워야 할 운영 정보

| 항목 | 상태 |
|---|---|
| 실제 Compose project directory·name·전체 -f 목록과 순서 | 미확인 |
| Prometheus 현재 실행 이미지·명령·설정 bind mount의 호스트 경로 | 미확인 |
| 현재 Prometheus 설정 및 alert rule의 SHA-256 | 미확인 |
| 공통 네트워크 실제 이름·기존 호스트 exporter 유무 | 미확인 |
| 호스트 root mountpoint 및 /host/proc·/host/sys 읽기 결과 | 미확인 |
| 운영 백업 디렉터리·보존기간·복구 담당자 | 미확정 |

이 값들을 임의로 추정해 적용 명령을 만들지 않습니다. GitHub 설정과 실제 서버 파일은 같다고 가정하지 않습니다. 기존 release script와 승인된 Compose 9개 파일의 계약을 임의 수정하지 않습니다.

## 최소 권한 검토

- 대안 A: 기존 monitoring Alloy에 exporter를 합침. 컨테이너 수는 줄지만 OTLP·Blackbox 컨테이너에 호스트 마운트·namespace 접근과 재시작 영향이 추가됨.
- 대안 B(현 후보): 별도 host exporter Alloy. 기존 수집 경로에 새 host mount를 부여하지 않고 새 컨테이너로 격리. 전체 host 읽기 접근과 host PID namespace는 여전히 존재함.
- 대안 C: host rootfs 마운트 없이 /proc·/sys 등만 제공. CPU·메모리에 적용 가능성을 검토할 수 있으나 실제 호스트 루트 디스크 가용량·mountpoint를 정확히 얻는지는 별도 검증 필요. 디스크 요구를 충족한다고 가정하지 않음.

현 후보 B는 최소 권한 확정안이 아닙니다. exporter에서 불필요한 collector를 제한하고 pid:host 제거 가능성을 검증할 여지가 있습니다. 현 단계에서는 동작·권한을 검증하지 않고 옵션을 줄여 검증 완료라고 주장하지 않습니다. Docker 소켓·쓰기 가능한 host 경로·host 포트 publish는 추가하지 않습니다. read-only rootfs도 호스트 파일 읽기 범위를 넓히므로 배포 전 검토가 필요합니다.

## 적용 절차 — 승인 후 수행할 순서

1. 운영 정보를 채우고 기존 Compose·Prometheus·rules 파일을 접근 제한된 경로에 백업. 파일별 해시·권한·실행 컨테이너 이미지·원래 mount 경로를 기록. 비밀 파일은 공개 증거에 포함하지 않음.
2. 실제 운영 Prometheus 설정을 기준으로 ec2-node에 service·monitoring target 라벨만 추가한 차이를 검토. Git 후보 사본을 운영 설정에 덮어쓰지 않음. 다른 scrape job·rules·retention·remote_write 수신 옵션 변경 금지.
3. 합의한 실제 project directory와 전체 -f 순서에 후보 overlay를 마지막으로 둔 Compose config를 로컬 제한 파일에 렌더링. stdout에는 secret/env 전체를 출력하지 않음. 대상 서비스·mount·network·port만 검토.
4. 고정 버전 Alloy validate, promtool check config, Compose config 검사 성공 확인. 승인된 변경안과 해시가 일치하는지 확인.
5. monitoring-host-metrics만 시작하고 Docker 내부에서 ready 및 exporter endpoint 확인. node_memory_MemTotal_bytes와 실제 메모리, node_filesystem 루트 mountpoint와 호스트 df, CPU 표본의 라벨·시각을 비교. 부하 시험은 하지 않음.
6. Prometheus 설정 경로 변경은 컨테이너 재생성이 필요할 수 있으므로 무조건 reload로 처리하지 않음. 현재 bind mount와 실제 배포 방식을 확인해 Prometheus 서비스에만 검토한 반영 방법 사용. 전체 compose up/down 금지.
7. 연속 3회 scrape 성공과 두 role의 메모리 원본 시각 갱신 확인. CPU rate 표본이 쌓일 시간을 확보한 후 두 서버 CPU·메모리·루트 디스크 검증. 기존 OTLP·probe·logs 수집과 경보 상태 비교.
8. Web 후보를 별도 승인된 경로로 반영하고 서버 선택·기간·미수집·수집 지연 표시를 검증. API 또는 UI에 오류가 있으면 아래 복구 절차 적용.

## 중단·복구 조건

후보 target이 연속 3회 수집 실패, mountpoint가 호스트 루트와 불일치, 기존 수집 job의 신규 실패, Web API 오류 또는 예상하지 못한 서비스 재생성 발견 시 중단합니다. 짧은 롤링 쿼리에 표본이 아직 없는 경우와 실제 실패를 구분합니다.

1. LOAD-01은 실행하지 않음. 다른 동시 변경을 중지하고 증상 시각 기록.
2. Prometheus를 백업한 원래 설정 mount·Compose 파일 순서로 되돌림. 기존 runtime 방식에 맞춰 Prometheus 서비스만 복원. 데이터 volume은 삭제하지 않음.
3. 기존 scrape job·기능 점검·remote_write 수신 상태가 기준으로 회복됐는지 확인.
4. 후보 monitoring-host-metrics 서비스만 중지. 전체 compose down·volume 삭제·기존 Alloy 재시작 금지. 문제 분석을 위해 후보 volume은 보존.
5. Web 변경이 원인이면 원래 이미지 digest와 원래 실행 구성을 사용한 기존 승인 복구 절차 수행. DB migration은 이번 변경에 없음.
6. 복구 후 이미지·설정 해시·API 응답·수집 결과를 기록. 원래 target 역할 라벨이 없으면 Web의 역할 미지정/미수집 표시는 예상된 결과로 구분.

## 승인 경계

이 문서는 적용·복구 순서를 정의한 설계안이며 실행 가능한 운영 runbook의 확정본은 아닙니다. 운영 정보 미확인, Docker 도구 검증 로그 및 실제 host 검증이 누락된 상태이므로 운영 적용 NO-GO를 유지합니다. GitHub 검증과 서버 반영, LOAD-01 실행은 서로 별도 단계입니다.
