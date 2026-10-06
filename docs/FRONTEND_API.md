# Frontend API contract

The frontend reads `VITE_API_BASE_URL` and defaults to `http://localhost:8000/api/v1`. Copy `.env.example` to `.env.local` and change the URL when the backend runs elsewhere.

## Diagnosis flow

1. `POST /users/profile` with `age`, `region`, `income_level`, and `employment_status`.
2. Read `user_id` from the response.
3. Request `GET /welfare/matched?user_id={user_id}` and `GET /welfare/reverse-engineering?user_id={user_id}` in parallel.
4. Show the returned matched policies and qualification recommendations on the results screen.

The diagnosis form collects monthly income in ten-thousand-won units and sends `income_level` in won. The region is sent as a full string, for example `서울특별시 관악구`.

## Employment status values

The current frontend sends `EMPLOYED`, `EMPLOYED_SME`, `UNEMPLOYED`, `STUDENT`, `SELF_EMPLOYED`, `FREELANCER`, or `OTHER`. The initial API draft only lists three values, while its reverse-engineering example requires `EMPLOYED_SME`; the backend should accept the expanded values or publish the final enum before deployment.

## Response fields used by the UI

- Profile: `user_id`, `status`, and `message`.
- Matched response: `matched_count` and `policies[]` with `policy_id`, `title`, `category`, `support_amount`, and `match_score`.
- Reverse response: `recommendations[]` with `target_policy`, `current_eligibility`, and `missing_conditions[]` containing `field`, `current_value`, `required_value`, and `action_guide`.

The backend must allow browser requests from the frontend origin through CORS. The frontend displays connection and HTTP errors rather than inventing eligibility results when the API is unavailable.
