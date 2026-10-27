# AWS 운영 Alloy·Blackbox 통합 상태 기록 (2026-10-27)

이 문서는 사용자가 SSM으로 제공한 AWS 운영 점검 결과에 기반합니다. PR 생성/병합만으로 AWS 설정을 변경하지 않습니다.

## 확인된 운영 상태

- 서비스 EC2 (10.20.10.62): Nginx, FastAPI, PostgreSQL 16, Grafana Alloy v1.9.1 실행. Alloy 설정은 /opt/schutz/alloy/config.host-metrics.alloy, 내부 prometheus.exporter.unix "host" 존재. 별도 Node Exporter 컨테이너는 실행 목록에 없음.
- 모니터링 EC2 (10.20.20.10): Alloy v1.9.1(기존 otel-collector 서비스명), Prometheus v3.4.1, Loki v3.5.1, Management Web/Worker/DB 실행.
- 독립 Blackbox와 Grafana 컨테이너는 중지, RestartPolicy=no. Compose는 수동 프로필로 기본 실행 제외. 수동으로 재생성할 경우 restart 정책이 달라질 수 있음.
- 서비스 EC2 ec2-node 대상 10.20.10.62:9100의 Prometheus up=1 조회 확인. 개별 node_* 최신성·장시간 안정성까지 이번 조회로 입증한 것은 아님.
- Prometheus portal-health/portal-db-health는 Alloy prometheus.exporter.blackbox.portal_check의 컴포넌트 API를 조회.
- 중복 호환용 blackbox-exporter scrape job은 운영 설정에서 삭제.

## AWS 운영본 SHA-256 (사용자 제공)

- /opt/schutz-monitoring/monitoring/alloy-otel.alloy: 7f80abca93a08de5c9868633c2ec5347ec086d76e242acbe6877ee230c056f99
- /opt/schutz-monitoring/monitoring/prometheus.ec2.yaml: 7d41486b13b61a4fd27bedebf2ed190559496d5803def95abcfe7a8bbf9ac779
- /opt/schutz-monitoring/compose.otel-only.yaml: 66f1458ef114cd716167e0e3480a5d847ed77da244e7e9fcaa3b4d5fa95e6369

AWS Alloy 운영본과 승인 후보 /opt/schutz-monitoring/approved-releases/blackbox-alloy-20261026/monitoring/alloy-otel-blackbox.alloy의 SHA-256은 일치. AWS Prometheus 운영본과 후보의 diff는 호환용 blackbox-exporter job 1개 제거뿐임. **GitHub 후보와 AWS 파일의 바이트 단위 동일성은 아직 별도로 검증해야 함**.

## PR 검토와 남은 동기화

- 이 PR은 기존 GitHub 후보의 내용을 기본 운영 경로에 옮기고, Prometheus에서 중복 job을 제외하며, Blackbox 수동 프로필을 추가하는 **검토안**.
- monitoring/compose.otel-only.yaml의 GitHub 운영 경로와 AWS /opt/schutz-monitoring/compose.otel-only.yaml 경로는 다름. 실제 AWS 운영 파일 원문과 합성 Compose 9개 파일 순서를 검증한 뒤 병합.
- AWS의 compose.grafana-only.yaml, compose.ecr.yaml, compose.management-https.yaml 등 GitHub에 없는 운영 원문은 **추정하여 생성하지 않음**. 비밀 파일/인증서/토큰 커밋 금지.
- 모니터링 Prometheus의 remote-write receiver 실행 옵션, Docker Compose 합성 결과, CI, 앱/DB probe 및 Loki 최신 표본 검증 필요.
- Alertmanager 도입 여부는 미결정. Management Worker의 AI/Slack 기능은 존재하나 최종 장애 주입→AI→Slack→복구 전체 재시험은 완료로 간주하지 않음.
- 기존 복구 스크립트는 전환 당시 상태를 전제로 할 수 있으므로, 현 운영본을 덮어쓰기 전에 별도 복구 계획 검토. PR 병합 자체로 AWS 재배포하지 않음.
