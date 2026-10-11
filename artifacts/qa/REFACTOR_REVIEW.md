# 코드 정리 회귀 검증 — 2026-10-11

대상: 로컬 Next production build(:3100), FastAPI(:8100), 기존 모의 API 실행기의 별도 lovecode_test DB. Codex 내장 브라우저 직접 조작. 실사용자 정보나 유료 API 없음.

## 검증 전 기대 동작

코드 분리와 CSS 제거 후 화면과 흐름이 유지되어야 한다. 빈 필수값과 미동의 분석을 차단하고, 단계 입력/확인/결과/복귀가 동작해야 한다. 새 SharePanel은 동의 후 저장, 링크 읽기, 삭제 확인/취소 흐름을 유지해야 한다. 미사용 CSS 제거가 모바일 가로 넘침이나 스타일 소실을 만들지 않아야 한다.

## 관측 결과

- PASS: 최종 production build의 1280px 홈 수평 넘침 없음 및 기존 배치 유지. 홈 → 예시 결과 바로보기 정상.
- PASS: 390px 홈의 기존 배치·일러스트·색 유지. 빈 입력 제출 시 첫 단계 유지.
- PASS: 가상 인물 2명의 단계 입력/생시 모름/확인 요약. 모의 분석에서 외부 처리 동의 미체크 시 해당 필드로 포커스, 체크 후 T14 AI 초안 결과.
- PASS: 분리한 SharePanel의 동의 → 저장 성공. 입력으로 복귀 시 기존 값 유지. 저장 URL 새 읽기로 동일 유형 표시.
- PASS: 320px 공유 결과 scrollWidth=innerWidth=320, 이름·축 표시 정상. 관리 화면 확인창 열기/취소 정상.
- PASS: 이번 QA 결과만 로컬 API로 삭제(204), 임시 키 파일 제거. 같은 링크 재조회 시 결과 불가 화면. UI 최종 삭제 버튼은 이번 회차 미실행, API 삭제 테스트는 pytest에 포함.
- PASS: 320px 16유형 목록 16개/수평 넘침 없음. Enter로 탐험 메이트 상세 이동.
- 관측 브라우저 warning/error 로그 없음. 전체 네트워크 trace 미수집.
- 정상 backend 복구: 실분석 비활성·모의 모드 해제. 검증 키는 보고서/스크린샷에 포함하지 않았다.

## 자동 루프

`scripts/verify.py`: Ruff, pytest 57개, TypeScript(미사용 선언 포함), Node 회귀 2개, Prettier check, production build, 데이터 검증과 annotate/train/experiment/pipeline dry-run 모두 통과. Node 모듈 유형 경고를 발견해 package type을 명시했다. 반복 실행에서 기존 만료 테스트가 모듈 import 시각에 의존해 간헐적으로 실패하는 것을 재현했다. 발급한 티켓의 expires_at 경계를 기준으로 바꾼 뒤 전체 루프를 재실행해 통과하고 만료 회귀 테스트를 3회 더 실행해 모두 통과했다. 결과는 artifacts/reports/offline-verification.json.

회귀 테스트는 JSON 속성 순서가 바뀌어도 축 이름이 맞는지, 알 수 없는 값의 표시, backend 16유형과 frontend ID/축/라벨/이미지 영역의 일치를 검사한다.

검증하지 않은 범위: 실제 OpenAI 모델 품질/지연, 배포, 모바일 실기기 Safari, 스크린리더. 코드와 사용처 검토로 유지할 학습/실험 경로를 구분했으며 모든 코드의 모든 실행 분기를 증명한 것은 아니다.

증거: refactor-result390.png, refactor-home1280.png (이 폴더의 Git 제외 로컬 파일). 이전 화면 비교는 atlas-home390.png 및 atlas-result390.png를 참고한다.
