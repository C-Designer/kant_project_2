# 따뜻한 관계 도감 — 구현 및 QA 기록

2026-10-11. 사용자 요청: 전체 UI UX 개선, 모바일 검증, GitHub push.

대상: localhost:3100 Next production build, localhost:8100 FastAPI. Codex 내장 브라우저 직접 조작. 로그인 없이 가상 정보만 사용. 실제 모델 호출 없음. 외부 서비스 접촉은 최종 GitHub push뿐이다.

## 실행 전 기대 동작

홈에서 궁합/예시/유형으로 진입해야 한다. 입력은 3단계이며 빈 필수값을 차단하고 이전/예시 복귀 시 값을 유지해야 한다. 최종 확인에서 입력값과 동의가 보여야 한다. 분석이 준비되지 않으면 제출이 비활성화되어야 한다. 모의 연결에서는 외부 처리 동의가 필수이며 결과·공유 읽기·삭제 확인/취소가 동작해야 한다. 320/390px에서 가로 넘침이 없어야 한다.

## 관측 결과

| 여정 | 결과 | 관측 근거 |
| --- | --- | --- |
| 홈 → 입력 / 예시 바로보기 | PASS | 홈 링크 클릭으로 입력 또는 T14 예시 결과 도착 |
| 빈 입력 → 다음 | PASS | 첫 단계 유지, 성별에 포커스 |
| 두 사람 단계 입력 / 이전 | PASS | 가상 생일, MBTI, 모름 상태, 두 번째 사람 시각 보존 |
| 확인 / 예시 / 입력 복귀 | PASS | 두 사람 요약 표시, 예시에서 돌아온 뒤 기존 값 유지 |
| 실제 분석 비활성 | PASS | 준비 중 안내와 최종 분석 버튼 비활성 |
| 모의 OpenAI 분석 | PASS | 외부 동의 미선택 제출 시 해당 체크박스에 포커스. 동의 후 AI 초안 T14 결과. 실제 분석 route를 사용하며 OpenAI transport만 mock |
| 공유 저장 / 새 읽기 | PASS | 동의 후 저장 성공, 공유 URL을 새로 열어 동일 유형 표시 |
| 관리 오류 / 확인 / 취소 | PASS | 잘못된 삭제 정보 안내, 올바른 정보 확인 dialog, 돌아가기 정상 |
| 검증 결과 정리 / 삭제 링크 | PASS | 검증용 결과를 로컬 API로 삭제(204), 같은 공유 URL의 불가 화면 확인. UI 최종 삭제 버튼은 이번 회차 미실행 |
| 4×4 목록 / 상세 | PASS | 320px 16카드, Enter로 탐험 메이트 상세 이동 |
| 반응형 | PASS (관측 범위) | 홈 390/768/1280px, 입력 320/390px, 결과 390/1280px, 공유 결과·관리·목록·상세 320px. 측정한 홈768/1280, 입력320, 공유320, 목록320에서 scrollWidth=innerWidth |

## 검증 / 정리 / 한계

- Next build 및 TypeScript 성공. pytest 56 passed. git diff --check 통과.
- 모의 API는 별도 lovecode_test DB 사용. 생성한 공유 결과는 정리했고 임시 키 파일도 제거했다. 일반 backend를 복구해 analysis_ready=false, verification_mode=false 확인.
- 네트워크 전체 trace는 수집하지 않았다. 삭제된 링크 조회의 오류는 의도된 실패다. 실제 OpenAI 모델, 배포, iOS Safari/실기기 키보드, 스크린리더 및 전체 접근성 적합성은 미검증.
- 소스 수준 미검수 표시/개인정보 정책 유지. 사용자 선호나 전환율 개선을 증명하는 사용성 실험은 수행하지 않았다.
- 이미지 원본은 유지. 4열 모바일의 작은 이미지 속 문구는 상세 그림과 HTML 텍스트가 보완한다.
- 캡처: atlas-home390.png, atlas-home768.png, atlas-home1280.png, atlas-review390.png, atlas-result390.png, atlas-result1280.png, atlas-shared320.png, atlas-deleted320.png, atlas-types320.png. 모두 이 폴더의 로컬 Git 제외 파일. 공유/삭제 키가 표시된 화면은 저장하지 않았다.
