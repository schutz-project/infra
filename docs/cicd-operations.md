# CI/CD 운영 및 검증 기록

기준일: 2026-10-23

## 저장소와 배포 대상

| 저장소 | 역할 | 대상 |
|---|---|---|
| infra | 인프라 설정·운영 문서 | Terraform·YAML·Shell 검증 |
| fast-api | 사내 포털 API·화면 | 서비스 EC2 |
| management-web | 모니터링 관리자 화면 | 모니터링 EC2 |
| management-worker | 상태·로그 수집 및 작업 처리 | 모니터링 EC2 |

- 조직: schutz-project
- 리전: ap-northeast-2
- 서비스 EC2: i-09af34fe68b6c200c
- 모니터링 EC2: i-066c8eee143b5cdff

## 일반 배포 절차

1. main 최신 내용을 받고 작업 브랜치를 생성한다.
2. 코드를 수정하고 필요한 검증을 수행한다.
3. 커밋·push 후 PR을 생성한다.
4. PR의 CI 성공을 확인한다.
5. 검증한 커밋을 main으로 병합한다.
6. main push 실행의 이미지 등록과 EC2 배포를 확인한다.
7. 실제 화면과 기능을 확인한다.

PR에서 이미지 등록·배포가 생략되는 것은 정상일 수 있다.
배포 결과는 병합 커밋과 실행의 head SHA를 대조하여 확인한다.

GitHub Actions는 OIDC로 AWS 역할을 사용한다.
EC2 배포 명령은 SSM으로 실행한다.
이미지 태그는 커밋 SHA·실행 ID·실행 시도 번호로 구성한다.

## 실행 확인 명령

각 저장소 디렉터리에서 실행한다.

- 실행 목록: gh run list --branch main --event push --limit 5
- 실행 대기: gh run watch 실행ID --exit-status
- 실패 로그: gh run view 실행ID --log-failed
- 커밋 확인: gh run view 실행ID --json headSha,status,conclusion,url

## 배포와 복구

FastAPI:
- 기존 서비스 상태와 배포 이미지를 점검한다.
- API 컨테이너를 교체하고 Nginx 검사·reload를 수행한다.
- 상태 검사 실패 시 기존 이미지와 설정으로 복구하도록 구성되어 있다.
- 자동 배포에서 DB 마이그레이션은 수행하지 않는다.

Management 자동 배포:
- Web과 Worker를 각각 배포한다.
- 상대 서비스와 DB 컨테이너 유지 여부를 검사한다.
- Web 정상 응답과 Worker 수집 완료를 검사한다.
- 실패 시 배포 대상 서비스의 기존 이미지로 복구하도록 구성되어 있다.

Management 수동 워크플로: management-release.yml
- CHECK: 설정·이미지 사전 점검. 지정 이미지는 서버에 준비되어 있어야 한다.
- DEPLOY: 지정한 Web·Worker 이미지 배포.
- rollback_test=YES: 배포 후 의도한 실패와 복구 검증.
- confirmation=DEPLOY: 컨테이너 변경 확인.
- 대상 인스턴스는 모니터링 EC2로 제한한다.
- 기본 태그를 현재 운영 버전으로 간주하지 않는다.
- 롤백 시험 중 관리자 화면이 일시적으로 끊길 수 있다.
- SSM 결과가 불명확하면 기존 명령 상태를 먼저 확인하고 재실행한다.

## 로컬 접속

| 화면 | 주소 | 대상 포트 |
|---|---|---|
| 포털 | http://localhost:18080 | 서비스 EC2 8080 |
| 모니터링 관리자 | http://localhost:18001 | 모니터링 EC2 8001 |
| Grafana | http://localhost:13000 | 모니터링 EC2 3000 |

SSM 포트 전달 터미널은 실행 상태로 유지한다.
Git 작업은 별도 터미널에서 수행한다.
localhost 접속 실패 시 포트 전달 세션부터 확인한다.

## 실제 검증 결과

| 검증 | 근거 | 결과 |
|---|---|---|
| FastAPI 테스트·ECR 등록·자동 배포 | fast-api 실행 39932064030 | 성공 |
| Worker ECR 등록·자동 배포 | management-worker 실행 39933611005 | 성공 |
| Management 동일 이미지 재배포 | management-web 실행 39928231075 | 성공 |
| Management 의도한 실패 후 롤백 | management-web 실행 39929490912 | 성공 |
| Management 다른 태그 배포 후 롤백 | management-web 실행 39942160198 | 성공 |
| 새로고침 메뉴 유지·로그인 화면 깜빡임 수정 | fast-api PR #7·사용자 화면 확인 | 성공 |

다른 태그 롤백 시험에서 확인한 로그:
- MANAGEMENT_PREFLIGHT_OK
- MANAGEMENT_ROLLBACK_BACKUP_OK
- MANAGEMENT_ROLLBACK_TEST_TRIGGERED
- MANAGEMENT_DEPLOY_FAILED_ROLLBACK_START
- MANAGEMENT_ROLLBACK_HEALTHY
- MANAGEMENT_ROLLBACK_TEST_SUCCESS

복구 시 기존 이미지 ID·Compose 설정 복원, Web 정상 응답,
Worker 수집 재개, DB 컨테이너 유지를 검사했다.
서로 다른 태그만으로 이미지 내용의 차이까지 증명하지는 않는다.

## 후속 검증 및 개선

- FastAPI 실패 배포의 실제 롤백 실증 완료: 실행 39944921758.
- DB 백업·복원 실증 완료. 스키마 변경 배포의 복구는 별도 시험한다.
- DB 컨테이너 유지 검사는 데이터 복원 시험을 대신하지 않는다.
- 모니터링 관리자 화면 로고 표시 문제는 별도 개선한다.
- 장애·반복 로그인 실패·리소스 부하 통합 시험은 별도로 관리한다.
- /gh 요청에 따른 코드 작성·업로드 연결은 전체 구축 후 진행한다.
- 비밀번호·세션·토큰·Authorization 값은 운영 기록에 남기지 않는다.

## FastAPI 롤백 추가 검증 — 2026-10-23

- 시험 기능 추가: fast-api PR #8
- 일반 자동 배포 성공: 실행 39944532134
- 실제 롤백 시험 성공: 실행 39944921758
- 대상 이미지가 기존 이미지와 다른 ID임을 확인했다.
- 대상 배포 및 정상 상태 확인 후 의도적으로 실패시켰다.
- 기존 이미지 ID와 태그, Compose 설정 복원을 확인했다.
- API 직접 응답, Nginx 경유 응답, 인증된 내부 직원 조회를 확인했다.
- DB와 Nginx 컨테이너 유지를 확인했다.

확인 로그:
- FASTAPI_DIFFERENT_IMAGE_VERIFIED
- FASTAPI_ROLLBACK_TEST_TRIGGERED
- RELEASE_FAILED_ROLLBACK_START
- ROLLBACK_OK
- FASTAPI_ROLLBACK_TEST_SUCCESS

이 시험은 애플리케이션 이미지 복구 검증이다.
DB 백업·복원은 아래 추가 시험에서 검증했다. 스키마 변경 배포의 복구는 별도 시험 대상으로 유지한다.

## DB 백업·복원 실증 결과 — 2026-10-23

| 대상 | fast-api 워크플로 실행 ID | 결과 |
|---|---|---|
| 포털 DB | 39947080330 | 성공 |
| 관리 DB | 39947148029 | 성공 |

워크플로: db-backup-restore.yml

검증 내용:
- 같은 PostgreSQL 스냅샷에서 백업과 public 테이블별 행 수를 수집했다.
- 네트워크가 분리된 임시 PostgreSQL 컨테이너에 복원했다.
- 복원된 public 테이블 목록과 테이블별 행 수의 일치를 확인했다.
- 운영 DB 컨테이너 ID·재시작 횟수 유지와 정상 상태를 확인했다.
- 시험용 임시 컨테이너와 볼륨을 제거했다.
- 운영 DB에 복원하거나 운영 서비스를 재배포하지 않았다.

확인 로그:
- DB_BACKUP_CREATED
- DB_RESTORE_TABLE_COUNTS_MATCH
- SOURCE_DB_UNCHANGED
- DB_BACKUP_RESTORE_SUCCESS

백업 저장 위치:
- 포털: /opt/schutz/employee-portal-p0/.db-backups
- 관리: /opt/schutz-monitoring/.db-backups

범위:
- EC2 내부 논리 백업의 실제 복원 가능성을 검증했다.
- 행 내용 전체 비교, 역할·권한 복원, 외부 백업, 시점 복구,
  스키마 변경 배포의 복구는 별도 검증 대상이다.
- 이 워크플로는 수동 시험이며 정기 백업 스케줄은 설정하지 않았다.

## S03 반복 로그인 실패 통합 검증 — 2026-10-23

- 시험 ID: S03_20261023T120116_1c31e821add0
- 사건 ID: 7e4af80c-51ce-4c18-a18b-fc825fc05776
- 대상: portal-login
- 탐지 규칙: login_failures
- 사건 종료: 2026-10-23 21:38:28 KST

### 시험과 확인 결과

1. 기존 계정과 겹치지 않는 시험용 이름을 사용했다.
2. 서명한 모의 시험 정보를 포함해 로그인 실패 요청 5회를 전송했다.
3. HTTP 401 및 모의 로그인 실패 이벤트 5건을 확인했다.
4. 관리 DB에 증거 5건이 수집되고 사건이 생성된 것을 확인했다.
5. 최초 사건 Slack 알림의 실제 수신을 확인했다.
6. AI 시간 초과를 수정한 후 기존 사건의 분석을 복구했다.
7. AI 분석 완료 후속 Slack 알림의 실제 수신을 확인했다.
8. 사건 접수·조치 기록·시험 중지 확인 후 정상 종료했다.
9. 시험 요청 전송 후 서비스 정상 응답을 확인했다.

### AI 시간 초과 발견 및 수정

- 기존 AI 호출은 15초 제한으로 두 번 실패했다.
- 짧은 진단 요청은 정상 HTTP 200이었으나 13.9초가 소요됐다.
- AI 제한을 ai_timeout_seconds 설정으로 분리했다.
- 기본값은 60초이며 설정 범위는 5~120초다.
- AI 작업 잠금은 호출 제한보다 30초 길게 유지한다.
- Slack 호출 제한 5초와 작업 잠금 45초는 유지한다.
- 수정 PR: management-worker #4
- 회귀 검사 및 배포 성공: 실행 39952331908

배포 후 기존 AI 작업을 명시적으로 1회 재실행했다.
기존 실패 이력을 보존했으며 누적 3번째 시도에서 성공했다.
이 복구는 실패 작업의 자동 재개 또는 화면 재시도 기능 검증이 아니다.

### 검증 범위

모의 표시가 있는 반복 로그인 실패의 실제 수집·탐지·AI·알림·종료
흐름을 검증했다. 일반 로그인 실패 전체의 탐지, 자동 차단,
계정 잠금 기능까지 검증한 것은 아니다.

서비스 장애·응답 지연·리소스 부하 시나리오는 별도 시험한다.


## 2026-10-26 경보·복구 알림 실증

[시험 방법·결과·개선 항목](validation/2026-10-26-alert-recovery.md)에 실제 MonitoringTargetDown 경보부터 Slack·AI·복구 알림까지 확인한 결과를 기록했습니다. 관리자 수동 사건 종료는 확인 대기로 구분합니다.

