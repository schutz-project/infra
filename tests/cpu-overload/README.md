# CPU 과부하 장애 대응 테스트 환경 — 확인 기록 (2026-11-18)

## 목적
기존 직원 포털의 코드를 직접 바꾸지 않고, 같은 서비스 EC2에서 별도의 Docker 컨테이너로 CPU 과부하·지연·장애 탐지·복구를 반복 검증하는 구성입니다.

## 실제 확인 사항
- 서비스 EC2 내부 주소: `10.20.10.62` (SSM 터미널의 호스트 이름과 사용자 제공 결과 기준).
- 기존 직원 포털 컨테이너: `employee-portal-p0-api-1`, `employee-portal-p0-nginx-1`, `employee-portal-p0-db-1`.
- 테스트용 컨테이너: `schutz-release-test-a`, `schutz-cpu-test-b`, `schutz-cpu-test-c`, `schutz-complex-test-db` 등. 컨테이너 목록에는 목적별 B/C, CPU 테스트 버전도 다수 존재합니다.
- `schutz-release-test-a` Docker Compose 레이블에 기록된 프로젝트: `schutz-release-rollback`.
- 해당 컨테이너의 Compose 파일: `/home/ubuntu/schutz-release-rollback/deploy/compose.normal.yaml`; 서비스 이름은 `employee-a`.
- [compose.normal.yaml](./compose.normal.yaml)은 사용자가 2026-11-18에 서버 터미널에서 출력한 **정상 버전 Compose 파일의 사본**입니다. `SEARCH_CPU_WORK_ITERATIONS: "0"`, `cpus: 0.75`, `mem_limit: 256m` 설정이 확인됐습니다.
- 위 파일은 정상 버전 설정이며, CPU 과부하를 일으킨 당시의 실행 Compose 파일 또는 전체 테스트 구성을 증명하지 않습니다.

## 시나리오 결과 (사용자 보고 기반)
1. k6 부하 테스트로 테스트용 A 직원 검색 API에 CPU 과부하를 유도했습니다.
2. A의 CPU 사용률 상승, 응답 지연 및 일부 오류를 관찰했습니다.
3. SCHUTZ의 장애 탐지, Slack 알림 및 롤백/복구 흐름을 검증했습니다.
4. 해당 테스트 중 홈페이지 B 및 커뮤니티 C는 정상 응답을 유지했습니다.

B와 C에 장애가 확산되지 않은 원인은 **아직 확정되지 않았습니다**. A에 적용된 자원 제한은 가능성 중 하나이지만, 실제 부하 당시 컨테이너 자원 제한, 호스트 CPU 여유, 라우팅 및 서비스별 통신 경로를 확인해야 합니다.

## 기존 구성과의 차이
기존 직원 포털 Compose는 `service/employee-portal/compose.yaml`에 있으며 API·Nginx·DB·migrate·seed를 포함합니다. 이 테스트용 Compose는 별도의 `employee-a` 서비스만 정의합니다. 기존 Compose 파일을 그대로 복사해서 만들었는지 여부는 Git 기록만으로 확인되지 않았습니다.

## 보안·재현 안내
- **절대 커밋 금지**: `base.env`, `.env`, 토큰, DB 비밀번호, Slack Webhook, AWS 인증정보, 세션 비밀키.
- 본 스냅샷만으로 배포할 수 없습니다. 로컬 이미지 태그, 외부 Docker 네트워크, 분리 보관 중인 설정이 필요합니다.
- 이 폴더는 기록용이며, 현재 운영 중인 서버의 Compose 파일을 수정하거나 재배포한 것이 아닙니다.
- 최종 발표에서는 '별도 EC2'가 아니라 '**기존 EC2 내부에 테스트용 Docker 컨테이너를 분리 구성**'했다고 설명하는 것이 정확합니다.
