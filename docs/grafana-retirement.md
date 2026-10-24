# Grafana 기본 실행 제외 및 검증 결과

기준일: 2026-10-24 (한국 시간)

## 적용 결과

모니터링 EC2에서 Grafana를 시험 중지한 뒤 Management Web·Prometheus 수집·Loki 응답 검사를 20초 간격으로 3회 통과했습니다. Worker 실행 및 관리 DB 건강 상태 검사도 통과했습니다. 관리자 화면에서 앱·프록시 지표 표시를 확인했습니다.

- Grafana 컨테이너: `schutz-monitoring-grafana-1`
- 최종 실행 상태: false
- 현재 컨테이너 재시작 정책: no
- 서버 Compose: `/opt/schutz-monitoring/compose.grafana-only.yaml`
- Grafana 서비스에 `profiles: ["manual-grafana"]` 추가
- 기존 Management 배포 Compose 파일 8개 유지, 전체 병합 검사 통과
- 컨테이너·볼륨·이미지 삭제 없음
- 다른 서비스 재시작 없이 설정 적용

수동 프로필은 기본 Compose 실행에서 제외하기 위한 것입니다. 프로필 활성화 또는 서비스 명시 실행은 여전히 가능하므로 완전 삭제나 실행 차단을 의미하지 않습니다. 기존 Compose의 restart 값과 현재 컨테이너에 적용한 restart=no는 구분해야 합니다.

## 백업

서버 경로: `/opt/schutz-monitoring/.release-backups/grafana-retirement-eiql94j0`

- `grafana.db`: SQLite backup API로 생성, integrity_check 통과, 대시보드 3개 확인
- `compose.grafana-only.yaml`: 최초 Compose 백업
- `compose.before-profile.yaml`: 프로필 적용 직전 Compose 백업
- `provisioning/`, `dashboards/`: 존재하는 디렉터리 복사
- `image.txt`: 기존 이미지 참조

백업과 Grafana 볼륨은 서버에 유지하며 GitHub에 올리지 않습니다. 현재 백업은 같은 서버에 있으므로 서버 손실에 대비한 외부 백업을 대신하지 않습니다.

## 관리자 화면으로 옮긴 항목

Management Web PR #9: https://github.com/schutz-project/management-web/pull/9

자동 배포 성공: https://github.com/schutz-project/management-web/actions/runs/40100080416

- Prometheus 발생 중 경보와 수집 대상 상태
- 경로별 앱 요청량 및 응답 시간 p95
- Loki 기반 경로별 Nginx 요청량·5xx·전체 응답 및 업스트림 응답 p95
- 기존 서버 자원 및 최근 로그 화면 유지

조회 범위는 최근 15분으로 고정되고 표시 개수에 제한이 있습니다. Grafana의 임의 시간 범위·자유 쿼리 및 Prometheus 자체 진단 대시보드 전체를 대체한 것은 아닙니다. 이번 시험은 정상 상태에서의 조회·수집 지속 확인이며 장애 주입·Slack·AI 전체 재시험은 포함하지 않았습니다.

## 긴급 복구

모니터링 서버 SSM 터미널에서 실행:

```bash
sudo -n docker start schutz-monitoring-grafana-1
```

기존 컨테이너와 볼륨이 유지되어 있을 때 사용하는 명령입니다. 시작 후 상태·접속을 확인해야 합니다. 자동 재시작까지 복원하려면 별도로 기존 Compose 설정과 컨테이너 재시작 정책을 복구합니다. Compose 전체 up이나 볼륨 삭제 명령을 사용하지 않습니다.

## GitHub와 서버 설정의 관계

서버의 전체 Grafana Compose 파일은 아직 이 저장소에 수집되지 않았습니다. 이 문서는 적용 결과를 기록하며 자동 배포를 실행하지 않습니다. 기존 배포 스크립트의 Compose 8개 요구 조건을 유지하기 위해 파일을 삭제하지 않았습니다.

다음 정리 항목은 관리자 화면의 Grafana 링크 제거와 알림 역할 분석입니다. Prometheus 규칙과 Worker 알림을 확인하기 전 경보 규칙을 삭제하지 않습니다.
