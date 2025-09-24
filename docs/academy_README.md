# Academy API

This module provides the backend endpoints for PromptForge Academy.

## Endpoints
- `GET /api/academy/curriculum` — Returns curriculum structure (mocked)
- `GET /api/academy/lesson/:id` — Returns lesson content (mocked)
- `POST /api/academy/labs/run` — Proxies to prompt upgrade (mocked)
- `POST /api/academy/progress` — Records user progress (mocked)
- `POST /api/academy/quest/submit` — Submits quest solution (mocked)
- `GET /api/academy/leaderboard` — Returns leaderboard (mocked)

## How to run tests

```bash
cd pb/TOR
pytest tests/test_academy_api.py
```

## TODO
- Integrate with real content pipeline and database
- Replace mocks with real data
- Add authentication and rate limiting
