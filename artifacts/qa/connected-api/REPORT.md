# API 연결 가정 통합 검증

2026-10-11. Scope: localhost3100 frontend, localhost8100 mock OpenAI transport + isolated lovecode_test DB. Real request route, calendar, schema, tickets and store; OpenAI output alone is simulated. No paid calls or real user data.

Before execution: 390px input must display mock verification notice and external processing consent. Two fictional people + consent must produce an unreviewed result through /analyses, not demo-analysis. Result must share, survive fresh read, delete, then become unavailable. No keys in screenshots. Restore regular disabled backend afterward.

## Observed results

- PASS: mocked ready health displayed explicit verification banner. 390px scrollWidth matched innerWidth390.
- PASS: submitting without external consent focused external-consent checkbox and did not navigate to a result.
- PASS: fictional inputs + both consents → /analyses branch → AI draft/unreviewed result (not demo button). Saved screenshot result390.png includes mock-mode disclosure. OpenAI transport is the only mocked boundary.
- PASS: consent → share creation, saved result reload retained AI draft status, management deletion succeeded, original share URL became unavailable. deleted390.png.
- PASS: captured browser warning/error list empty. Detailed network trace not captured; HTTP contracts were separately exercised by FastAPI TestClient with real isolated PostgreSQL.
- Cleanup: created test result deleted through product; mock server stopped; normal disabled backend restored and UI verified not in mock mode. Temporary viewport reset. No real API calls. No unrelated user data touched.
- Not covered: actual model/account/quota/latency/quality, mobile Safari/device keyboard, deployment TLS/proxy/replica behavior. Evidence is local mock integration only.

Artifacts are review-owned local files under artifacts/qa/connected-api (Git ignored). Keep for this implementation review, remove this directory when no longer needed. No request keys or API secrets included.
