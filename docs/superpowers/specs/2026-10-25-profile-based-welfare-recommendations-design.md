# 사용자 프로필 기반 복지서비스 추천 분류 설계

## 의도

사용자가 최초 진단에서 입력한 정보로 확인할 수 있는 복지서비스 후보를 유용하게 제시하면서, 미확인 조건을 충족한 것으로 간주하지 않는다. 현재 자격 분석과 사용자 표시용 추천 분류를 분리한다.

## 목표와 제외 범위

- 기존 `status`, `gap_conditions`, `review_conditions`, `match_score` 값을 그대로 보존한다.
- 백엔드가 `analysis_results` 전체를 기준으로 별도 추천 분류와 사유를 만든다.
- 화면에서 통과한 조건, 미충족·추가 확인 조건, 예비 진단 안내를 구분해 표시한다.
- DB 모델과 마이그레이션은 변경하지 않는다.
- 조건 파서, 자격 비교 규칙, OR/예외 해석, 점수 계산을 변경하지 않는다.
- `match_score`를 신청 확률로 표현하지 않는다.

## 현재 구조

`EligibilityMatchingService.analyze_service()`는 자동 평가 결과와 검토 목록을 만든 뒤 Policy B로 기존 상태를 결정한다. `analyze_user()`는 전체 `analysis_results`와 `eligible` 상태만 담은 `policies`를 반환한다. `/api/v1/welfare/matched`는 `MatchedPoliciesResponse`로 응답한다. 프런트엔드 `policyResults()`는 전체 `analysis_results`로 카드를 만들고 기존 `policies`를 보충하며, `AnalysisPolicyCard`가 조건을 표시한다. 현재 응답에는 통과 조건 상세가 없어 별도 목록이 필요하다.

## 접근 방식과 선택

1. 프런트엔드에서 상태를 조합한다. API 변경은 작지만 자격 판정 규칙이 프런트엔드에 중복되고 백엔드 전체 분석에서 파생해야 하는 정책이 UI에 종속된다.
2. 기존 백엔드 상태 필드를 추천 상태로 재사용한다. 변경량은 작지만 기존 계약의 의미를 바꾸고 `needs_review`의 불확실성을 숨길 수 있다.
3. 백엔드가 `analysis_results`를 기반으로 추천 필드를 별도 생성한다. 기존 판정을 유지하고 화면은 분류 규칙을 구현하지 않는다. 이 방식을 선택한다.

## 추천 분류와 우선순위

`condition_mismatch`는 자동 비교로 만들어진 gap이 모두 `selection_criteria` 출처이고, 분석 대상 조건이 하나의 동일한 `(source_field, source_text)` 그룹에 속하며, 원문에 OR·대안·예외 표현이 없을 때에만 허용한다. 서로 다른 원문 조각으로 나뉜 조건의 관계는 현재 구조에서 복원할 수 없으므로, 실패가 있으면 `additional_review`로 둔다. 명시적인 관계 표현이 있는데 검토 목록에 나타나지 않은 경우도 `additional_review`로 보수 처리한다.

응답의 새 `recommendation_status`는 다음 값 중 하나다.

- `priority_recommendation` (우선 추천): 자동 평가 조건이 1개 이상 있고 모두 통과했으며 gap과 review가 모두 없다.
- `priority_consideration` (우선 검토 추천): 자동 평가 통과 조건이 1개 이상 있고 gap은 없지만 review 조건이 있다. `recommendation_uncertainty`에 미확인 조건이 핵심 자격요건인지 현재 데이터로 판별할 수 없음을 명시한다.
- `condition_mismatch` (현재 정보상 조건 불일치): gap이 있고 review가 없으며, 모든 실패 조건이 `selection_criteria`에서 추출된 자동 비교 결과이고, 원문에 OR·예외 등 불확실한 관계 표현이 없다. 이 요건이 확인되지 않으면 이 분류를 사용하지 않는다.
- `additional_review` (추가 확인 필요): 평가 조건이 없거나, 통과 조건이 없거나, gap과 review가 함께 있거나, 실패 조건의 필수성·논리 관계를 안전하게 확인할 수 없는 경우.

추천 분류는 기존 분석 상태를 대체하지 않는다. 예를 들어 gap과 review가 함께 있으면 기존 `needs_review`와 목록을 그대로 유지하고 추천은 `additional_review`로 표시한다. 확인된 필수 조건의 실패가 분명한 경우에만 `condition_mismatch`를 사용한다. 분류 규칙은 결과 데이터에 남은 검토 항목과 원문 출처에 한정하며 condition type 이름만으로 필수성을 추정하지 않는다.

## API 변경 범위

`EligibilityAnalysis`에 다음 필드를 추가한다. 모든 필드는 분석마다 백엔드가 생성한다.

- `recommendation_status: str`: 위 네 분류 중 하나
- `recommendation_reason: str`: 해당 분류의 짧은 설명
- `recommendation_uncertainty: str | None`: 분류에 필요한 판단 한계가 있을 때의 안내
- `confirmed_conditions: list[ConditionAnalysis]`: 기존 자동 평가 결과 중 통과한 조건의 상세 목록

기존 필드와 `policies` 구조는 바꾸지 않는다. 추가 필드는 additive API 변경이며, 프런트엔드의 저장된 과거 세션에서는 신규 필드가 없을 수 있으므로 안전한 `additional_review` 표시로 처리한다. DB는 변경하지 않는다.

## 화면 표시

카드의 주 분류는 `recommendation_status`를 사용한다. 기존 분석 상태는 보조 정보로 보존한다. 카드에는 추천 사유, 확인된 조건 목록, 기존 gap/review 조건 목록과 review 안내를 표시한다. review가 남은 우선 검토 카드에는 미확인 조건이 필수인지 확정할 수 없다는 안내를 표시한다. 전체 결과에는 사용자의 입력을 기준으로 한 예비 진단이며 최종 수급 결정은 행정기관 심사에 달린다는 안내를 둔다. `match_score`는 확률로 렌더링하지 않는다.

## 경계 사례

- 자동 평가가 없고 review도 없는 서비스: `additional_review`; 조건 데이터가 없다는 이유로 추천 또는 탈락으로 보지 않는다.
- pass와 review만 있는 서비스: `priority_consideration`; review 목록과 필수 여부의 불확실성을 표시한다.
- gap과 review가 동시에 있는 서비스: `additional_review`; gap 및 review 원문을 각각 그대로 표시한다.
- gap만 있는 서비스: `selection_criteria` 출처와 논리 모호성 부재가 확인될 때만 `condition_mismatch`; 나머지는 `additional_review`.
- review가 없는 모든 자동 조건 통과: `priority_recommendation`.
- 선택 필드가 빠진 구버전 프런트 저장 데이터: 분류를 추가 확인으로 표시하고 기존 카드 내용을 유지한다.

## 테스트 계획

- 백엔드 단위 테스트로 네 분류, 경계 조합, 기존 상태·gap/review·점수 보존, 확인 조건 생성, 출처가 불명확한 실패의 보수적 처리, `analyze_user()` 전체 서비스 산출을 검증한다.
- 스키마 테스트로 새 필드 직렬화와 기존 응답 필드 호환성을 검증한다.
- 프런트엔드는 TypeScript 검사와 production build로 새 응답 필드, 과거 스냅샷 fallback, 카드 및 예비 진단 안내 렌더 경로를 검증한다. 저장소에 UI 테스트 프레임워크가 없어 테스트 라이브러리를 새로 설치하지 않는다.
- 브라우저 자동화 환경이 준비되어 있지 않으면 브라우저 검증은 수행하지 않았다고 보고한다.
