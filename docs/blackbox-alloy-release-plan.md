# Blackbox Alloy 운영 전환 실행안

기준일: 2026-10-26 KST. 스크립트 준비 단계이며 서버 적용 미실행.

## 승인 범위

모니터링 서버에서 Alloy만 재생성하고 Prometheus는 설정 재로드한다. 기능 점검 경로가 검증되면 기존 Blackbox를 중지하고 restart=no·manual-blackbox 프로필로 기본 재실행을 제외한다. 컨테이너·이미지·인증 파일·데이터 볼륨은 삭제하지 않는다.

Web·Worker·DB·Prometheus 컨테이너 ID/이미지와 HTTPS·ECR·환경 파일을 유지한다. Terraform·네트워크·이전 발표 시연 환경은 변경하지 않는다. Alloy가 잠시 재생성되므로 OTLP 수신의 짧은 중단 가능성이 있다. 무중단 전환을 보장하지 않는다. Worker의 기존 자동 탐지·알림 정책은 계속 동작하며, 스크립트는 별도 사건 생성·AI 호출·Slack 시험 발송을 하지 않는다.

## 고정 경로

- 준비 디렉터리: /opt/schutz-monitoring/approved-releases/blackbox-alloy-20261026/
- 백업: /opt/schutz-monitoring/.release-backups/blackbox-alloy-20261026/
- 타이머: schutz-blackbox-rollback-20261026.timer
- 준비 디렉터리에는 scripts/blackbox-release.py, scripts/blackbox-release.sha256 및 monitoring 아래 세 후보 파일을 저장한다. 모두 승인된 PR 커밋에서 가져오고 root 소유로 보관한다. 스크립트는 600 권한, 상위 준비 디렉터리는 700으로 제한한다.

아직 위 서버 경로를 생성하거나 타이머를 등록하지 않았다. 기존 백업 디렉터리가 있으면 스크립트는 덮어쓰지 않고 중단한다.

## 실행 전 기준

1. 모니터링 hostname=ip-10-20-20-10, root 실행, 공통 .management-release.lock 확보. 다른 Web/Worker 배포 중에는 진행하지 않는다.
2. 기존 네 파일 Git blob SHA가 사전 점검 값과 일치하고 Web 라벨의 기존 9개 Compose 경로·순서가 같아야 한다.
3. 기존 세 probe 정상, 앱 지표 7종 최신, Web HTTPS 및 DB healthy 확인. Alloy·Blackbox 실행 중 확인.
4. 고정된 Alloy v1.9.1·Prometheus v3.4.1 로컬 이미지가 있어야 하며 이미지 pull은 하지 않는다.
5. 전체 통합 Alloy와 Prometheus 후보를 임시 컨테이너에서 검증한다. 운영 파일 변경 전 validate/promtool을 통과해야 한다.
6. 원본 네 파일, 원본 해시, 유지 대상 컨테이너·이미지 ID, 환경파일·유지 Compose 해시, 기존 Blackbox 재시작 정책을 백업한다. 비밀정보 원문이나 환경변수를 출력하지 않는다.

## 승인 후 적용 명령

파일 준비·소유권·해시 확인이 끝난 모니터링 SSM 창에서만 실행한다. 이 문서 제공이나 PR 병합만으로 승인된 것으로 간주하지 않는다.

```bash
sudo -n bash -c '
set -e
cd /opt/schutz-monitoring/approved-releases/blackbox-alloy-20261026
sha256sum -c scripts/blackbox-release.sha256
timeout --signal=TERM --kill-after=120s 300s python3 scripts/blackbox-release.py apply --confirmation APPLY_BLACKBOX
'
```

스크립트의 변경 단계는 240초 알람으로 제한한다. 실패·중단 시 같은 프로세스에서 원복을 시도한다. 추가로 6분 뒤 독립 systemd 원복 타이머를 등록하며, 성공하면 타이머를 중지한다. 성공 마커가 있으면 늦게 시작한 watchdog은 원복하지 않는다. 호스트 장애·강제 종료·디스크 장애 등 모든 실패에서 자동 원복을 보장하는 것은 아니다.

성공 조건:

- 기존 9개 Compose 순서 유지, Alloy 이미지와 데이터 볼륨 유지
- 신규 경로에서 세 probe의 같은 전체 라벨과 성공값 1·HTTP 200·전환 이후 최신 표본 확인
- 호환용 blackbox-exporter job·instance 유지와 up=1 확인
- 앱 지표 7종이 전환 이후 갱신
- Web·Worker·DB·Prometheus 컨테이너 ID/이미지/재시작 횟수 유지, DB healthy, Web 건강 응답
- 전환 이후 Worker의 기능 점검·로그 수집 완료 및 unavailable 없음
- 위 검증 후 기존 Blackbox 중지·restart=no, 중지 이후 새 표본과 OTLP·Worker 상태까지 다시 확인

성공 출력: BLACKBOX_ALLOY_RELEASE_SUCCESS, WEB_WORKER_DB_PROMETHEUS_UNCHANGED. 백업 경로도 출력한다. 오류 또는 출력 불명확 시 재실행하지 않고 현재 상태를 조회한다.

## 수동 롤백

```bash
sudo -n bash -c '
set -e
cd /opt/schutz-monitoring/approved-releases/blackbox-alloy-20261026
sha256sum -c scripts/blackbox-release.sha256
timeout --signal=TERM --kill-after=30s 360s python3 scripts/blackbox-release.py rollback --confirmation ROLLBACK_BLACKBOX
'
```

백업 네 파일을 복원하고 기존 Blackbox 재시작 정책·실행을 복원한다. Alloy만 재생성한 뒤 Prometheus를 HUP 재로드하고, 기존 /probe 경로의 신규 정상 표본과 OTLP·Worker·Web을 확인한다. 복구 성공 출력은 BLACKBOX_ROLLBACK_HEALTHY이다.

수동 롤백도 Web·Worker·DB·Prometheus 또는 보존 대상 설정이 기준과 다르면 중단한다. 이후 다른 배포나 서버 관리자 변경이 있었을 때 과거 백업으로 무조건 덮어쓰지 않기 위한 조건이다. 사건·조치·알림 DB 이력은 되돌리지 않는다.

## 검증 근거와 남은 확인

- 기존·임시 Alloy의 세 기능 점검 성공과 HTTP 200 비교 완료
- 별도 Prometheus에서 probe 3종 전체 라벨과 값 두 차례 비교 완료
- 로컬 Python 문법 검사 및 안전 조건·JSON 백업 라벨 호환·오래된 표본 거부·mock 복원·완료 watchdog 중복 복구 방지 등 14개 테스트 통과
- 실제 systemd 타이머 실행, 합친 9개 서버 Compose 실행, 운영 전환 및 자동 롤백 실증은 아직 미실행
- 후보 YAML/Alloy/Prometheus 검증은 CI 결과와 구분해 확인한다. 실제 운영 성공은 적용 후 출력·조회 결과로 판단한다.

## 운영 후 인계

운영 전환과 후속 확인이 성공한 뒤 최종 파일명·포트·남은 컨테이너 및 복구 방법을 Terraform 담당자에게 전달한다. 기존 AWS 자원 import는 유지한다. Blackbox 중지를 이유로 보안 그룹이나 기존 네트워크 규칙을 자동 삭제하지 않는다.

