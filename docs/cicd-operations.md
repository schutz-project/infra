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

- FastAPI 실패 배포의 실제 롤백 실증은 별도 확인한다.
- DB 백업 복원 및 스키마 변경 복구는 별도 시험한다.
- DB 컨테이너 유지 검사는 데이터 복원 시험을 대신하지 않는다.
- 모니터링 관리자 화면 로고 표시 문제는 별도 개선한다.
- 장애·반복 로그인 실패·리소스 부하 통합 시험은 별도로 관리한다.
- /gh 요청에 따른 코드 작성·업로드 연결은 전체 구축 후 진행한다.
- 비밀번호·세션·토큰·Authorization 값은 운영 기록에 남기지 않는다.
