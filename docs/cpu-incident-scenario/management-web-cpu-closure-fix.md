# Management Web — CPU 사건 종료 버튼 비활성화 해결 기록

## 증상

CPU 부하 종료 후 Prometheus 경보 상태가 정상으로 복구됐지만, SCHUTZ 관리 웹에서는 **'복구 확인 · 사건 종료' 버튼이 비활성화**됐습니다.

## 원인 분석 (당시 실행 중이던 버전)

- CPU 사건 규칙 ID: `schutz_test_cpu_high`
- Prometheus 규칙 이름: `SchutzTestCpuHigh`
- 데이터베이스 `prometheus_alert_states`에서 해당 CPU 경보 `state=normal` 및 `normal_samples=30` 확인
- **Management Worker에는 CPU 규칙 ID 매핑이 있었으나 Management Web의 `management/alert_policy.py`에는 누락**되어 있었음
- 이로 인해 CPU 전용 경보 복구 경로가 아닌 일반 헬스체크 조건으로 평가되어, 복구됐는데도 종료 제한 사유가 표시됨

당시 확인된 제한 사유:
```text
CHECK_COLLECTION_STALE
TWO_HEALTHY_CHECKS_REQUIRED
```

일반 경보에서는 정상 확인 두 차례가 요구될 수 있지만, **이 CPU 사건에서는 규칙 매핑 누락으로 잘못된 종료 조건을 적용받은 점**이 핵심이었습니다.

## 조치

Web의 `management/alert_policy.py`에서 CPU 규칙 이름을 사건 ID에 매핑하도록 변경했습니다. 다음은 수정 핵심을 보여주는 **예시**이며, 서버의 전체 원본 파일을 그대로 옮긴 것이 아닙니다.

```python
# 기존 규칙 매핑에 추가한 CPU 규칙
'SchutzTestCpuHigh': 'schutz_test_cpu_high',
```

당시 서버에서 수행한 절차:
1. 기존 Management Web 컨테이너 이미지를 백업 태그로 보존
2. 수정 코드가 포함된 신규 이미지 `schutz-management-web:cpu-fix` 생성
3. Compose의 별도 override 파일로 **management-web 서비스만** 재생성
4. 실제 실행 이미지에서 CPU 규칙 등록 여부 확인
5. 복구 조건 함수 `closure_reasons(db, incident)` 출력 확인

검증 결과:
```text
CPU_RULE: schutz_test_cpu_high
CLOSURE_REASONS: []
```

운영 화면을 새로고침한 후 실제 사건 종료가 가능함을 확인했습니다.

## 실행 환경 및 GitHub 동기화 주의

- 변경 당시 서비스: `schutz-monitoring-management-web-1`
- 수정을 담은 테스트 이미지: `schutz-management-web:cpu-fix`
- 서버의 임시 Dockerfile/Compose override 경로: `/home/ubuntu/schutz-cpu-incident/web-fix/`
- **2026-11-17 GitHub의 `schutz-project/management-web` 기본 브랜치 `management/alert_policy.py`에는 이 CPU 규칙 매핑이 아직 보이지 않습니다.**

따라서 본 기록은 해결 과정을 재현 가능하게 정리한 문서이지, GitHub 배포 코드 자체에 해당 패치가 반영됐다는 증거는 아닙니다.

## 보안

실제 `.env`, 비밀번호, DB 연결 문자열, Slack Webhook, 인증 키, API 토큰은 기록·업로드하지 않았습니다.
