# Frontend API contract

The frontend reads `VITE_API_BASE_URL` and defaults to `http://localhost:8000/api/v1`. Copy `.env.example` to `.env.local` and change the URL when the backend runs elsewhere.

## Diagnosis flow

1. `POST /users/profile` with the core profile fields and an extensible `eligibility_conditions` object.
2. Read `user_id` from the response.
3. Request `GET /welfare/matched?user_id={user_id}` and `GET /welfare/reverse-engineering?user_id={user_id}` in parallel.
4. Show the returned matched policies and qualification recommendations on the results screen.

The diagnosis form collects monthly income in ten-thousand-won units and sends `income_level` in won. The region is sent as a full string, for example `서울특별시 관악구`.

### Profile request body

```json
{
  "age": 24,
  "region": "서울특별시 관악구",
  "income_level": 2100000,
  "employment_status": "UNEMPLOYED",
  "eligibility_conditions": {
    "gender": "UNKNOWN",
    "household_size": 1,
    "income_type": "LABOR",
    "asset_range": "1~2억",
    "housing_type": "월세",
    "owns_home": false,
    "disability_status": "UNKNOWN",
    "student_status": "NO",
    "marital_status": "SINGLE",
    "children_count": 0,
    "qualifications": ["사회복지사 2급"],
    "additional_conditions": {}
  }
}
```

`eligibility_conditions` keeps eligibility data grouped and leaves room for future criteria. Gender, household size, income type, assets, housing, home ownership, disability, student status, marital status, children, and qualifications are represented separately. Unknown yes/no fields use `UNKNOWN`; unknown numeric or text fields use `null`. The backend should persist these values without interpreting unknown as `false`.

## Employment status values

The current frontend sends `EMPLOYED`, `EMPLOYED_SME`, `UNEMPLOYED`, `STUDENT`, `SELF_EMPLOYED`, `FREELANCER`, or `OTHER`. The initial API draft only lists three values, while its reverse-engineering example requires `EMPLOYED_SME`; the backend should accept the expanded values or publish the final enum before deployment.

The backend profile schema must accept the `eligibility_conditions` object shown above. The profile endpoint can return a validation error until its Pydantic schema is updated to include these fields.

## Response fields used by the UI

- Profile: `user_id`, `status`, and `message`.
- Matched response: `matched_count` and `policies[]` with `policy_id`, `title`, `category`, `support_amount`, and `match_score`.
- Reverse response: `recommendations[]` with `target_policy`, `current_eligibility`, and `missing_conditions[]` containing `field`, `current_value`, `required_value`, and `action_guide`.

The backend must allow browser requests from the frontend origin through CORS. The frontend displays connection and HTTP errors rather than inventing eligibility results when the API is unavailable.
