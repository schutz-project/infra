# 테스트 서버 최신 코드 GitHub 백업 체크리스트

현재 GitHub 업로드 범위는 **확인된 작업 기록(문서)**입니다. EC2 내 실행 코드, k6 시험 스크립트와 CPU 수정 Dockerfile은 이 대화에서 직접 접근할 수 없어 원본 파일을 아직 올리지 않았습니다.

## 별도 원본 확인 대상

| 구성 | 우선 확인할 파일 | 주의 |
| --- | --- | --- |
| k6 부하 테스트 | Windows에서 실행한 `employee_search_cpu_recovery_test.js` 및 결과 요약 | `summary` JSON에 개인/내부 URL 포함 여부 검토 |
| 서비스 EC2 | A/B/C 테스트 Compose, FastAPI 검색 API, 안전 감시 스크립트 | `.env`, 토큰, 실제 내부 접속정보 삭제 |
| 모니터링 EC2 | CPU 경보 규칙, Prometheus 타깃 설정 | 공개 저장소에 상세 네트워크 구성 공개 시 주의 |
| 관리 웹 수정 | `management/alert_policy.py`, 테스트 이미지 Dockerfile/override | 기존 프로젝트 코드와 버전/경로 대조 |
| 사건 기록 | CPU 그래프, P95, 탐지/복구 시간, 테스트 로그 | 사내 주소, 개인 식별 정보, 인증정보 익명화 |

## 공개 저장소에 절대 올리지 말 것

```gitignore
.env
.env.*
!.env.example
*.tfstate
*.tfstate.*
.terraform/
*.tfvars
*.tfvars.json
*.pem
*.key
*.p12
*.pfx
**/secrets/
**/credentials/
```

**GitHub에 올리기 전에 저장소 공개/비공개 설정과 멘토님의 저장소 운영 방침을 재확인하세요.**

## 동기화 원칙

1. 기존 파일을 덮어쓰지 않고 신규 브랜치에서 검토합니다.
2. 서버 원본을 확보한 뒤 비밀값 제거 및 실제 실행 설정과 비교합니다.
3. 경보와 관리 웹의 규칙 ID가 일치하는지 확인합니다.
4. 테스트가 모두 통과한 변경만 병합합니다.
5. GitHub 커밋이 자동으로 실행 중인 EC2에 배포되는지는 CI/CD 설정에 따라 다르므로 별도로 확인합니다.
