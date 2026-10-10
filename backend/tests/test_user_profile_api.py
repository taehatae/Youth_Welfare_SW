import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.users import router as users_router
from app.api.routes.welfare import router as welfare_router
from app.database.connection import Base, create_database_engine, get_db
from app.models.user import User, UserEligibilityConditions
from app.models.welfare_eligibility_condition import (
    WelfareEligibilityCondition,  # noqa: F401
)
from app.models.welfare_service import WelfareService  # noqa: F401
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserProfileCreate


@pytest.fixture
def test_database():
    engine = create_database_engine(
        "sqlite://",
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    with test_session_factory() as db:
        yield db

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(test_database: Session):
    app = FastAPI()
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(welfare_router, prefix="/api/v1")

    def override_get_db():
        yield test_database

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def valid_profile(**overrides):
    payload = {
        "age": 25,
        "region": "서울특별시 관악구",
        "income_level": 2_000_000,
        "employment_status": "EMPLOYED_SME",
    }
    payload.update(overrides)
    return payload


def test_profile_is_saved_and_returns_existing_response_contract(client):
    response = client.post(
        "/api/v1/users/profile",
        json=valid_profile(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"]
    assert body["status"] == "success"
    assert body["message"]
    assert set(body) == {"user_id", "status", "message"}


def test_eligibility_conditions_round_trip_without_coercion(
    client,
    test_database: Session,
):
    conditions = {
        "gender": "UNKNOWN",
        "household_size": None,
        "income_type": "UNKNOWN",
        "asset_range": [],
        "housing_type": {},
        "owns_home": False,
        "disability_status": None,
        "student_status": "UNKNOWN",
        "marital_status": "UNKNOWN",
        "children_count": 0,
        "qualifications": [],
        "additional_conditions": {"notes": [], "confirmed": False},
    }

    response = client.post(
        "/api/v1/users/profile",
        json=valid_profile(eligibility_conditions=conditions),
    )
    user_id = response.json()["user_id"]

    stored = UserRepository().get_eligibility_conditions(
        test_database,
        user_id,
    )

    assert response.status_code == 200
    assert stored is not None
    assert stored.conditions == conditions
    assert stored.conditions["owns_home"] is False
    assert stored.conditions["household_size"] is None
    assert stored.conditions["asset_range"] == []
    assert stored.conditions["housing_type"] == {}


@pytest.mark.parametrize("conditions", [None, {}])
def test_null_and_empty_eligibility_conditions_are_preserved(
    client,
    test_database: Session,
    conditions,
):
    response = client.post(
        "/api/v1/users/profile",
        json=valid_profile(eligibility_conditions=conditions),
    )
    stored = UserRepository().get_eligibility_conditions(
        test_database,
        response.json()["user_id"],
    )

    assert response.status_code == 200
    assert stored is not None
    assert stored.conditions == conditions


@pytest.mark.parametrize(
    "overrides",
    [
        {"age": None},
        {"employment_status": "UNKNOWN"},
        {"employment_status": None},
    ],
)
def test_missing_or_invalid_required_values_are_rejected(client, overrides):
    payload = valid_profile(**overrides)
    response = client.post("/api/v1/users/profile", json=payload)
    assert response.status_code == 422


def test_required_profile_fields_are_rejected_when_missing(client):
    payload = valid_profile()
    del payload["region"]

    response = client.post("/api/v1/users/profile", json=payload)
    assert response.status_code == 422


def test_sqlite_foreign_keys_and_one_to_one_constraint_are_enforced(
    test_database: Session,
):
    foreign_keys_enabled = test_database.connection().exec_driver_sql(
        "PRAGMA foreign_keys"
    ).scalar_one()
    assert foreign_keys_enabled == 1

    response_profile = UserRepository().create(
        test_database,
        UserProfileCreate.model_validate(valid_profile()),
    )

    test_database.add(
        UserEligibilityConditions(
            user_id=response_profile.user_id,
            conditions={},
        )
    )
    with pytest.raises(IntegrityError):
        test_database.commit()
    test_database.rollback()

    test_database.add(
        UserEligibilityConditions(
            user_id="missing-user",
            conditions={},
        )
    )
    with pytest.raises(IntegrityError):
        test_database.commit()
    test_database.rollback()


def test_failed_condition_insert_rolls_back_profile_and_cleans_session(
    client,
    test_database: Session,
):
    test_database.execute(text(
        """
        CREATE TRIGGER reject_condition_insert
        BEFORE INSERT ON user_eligibility_conditions
        BEGIN
            SELECT RAISE(ABORT, 'forced condition insert failure');
        END
        """
    ))
    test_database.commit()

    response = client.post(
        "/api/v1/users/profile",
        json=valid_profile(eligibility_conditions={"owns_home": False}),
    )

    assert response.status_code == 500
    assert test_database.query(User).count() == 0
    assert test_database.query(UserEligibilityConditions).count() == 0
    assert test_database.execute(text("SELECT 1")).scalar_one() == 1


def test_existing_users_table_and_records_survive_create_all():
    engine = create_database_engine(
        "sqlite://",
        poolclass=StaticPool,
    )
    test_session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE users (
                user_id VARCHAR(36) PRIMARY KEY NOT NULL,
                age INTEGER NOT NULL,
                region VARCHAR(100) NOT NULL,
                income_level INTEGER NOT NULL,
                employment_status VARCHAR(30) NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            text(
                """
                INSERT INTO users (
                    user_id, age, region, income_level,
                    employment_status, created_at
                ) VALUES (
                    :user_id, :age, :region, :income_level,
                    :employment_status, :created_at
                )
                """
            ),
            {
                "user_id": "existing-user",
                "age": 27,
                "region": "서울특별시",
                "income_level": 1_500_000,
                "employment_status": "EMPLOYED",
                "created_at": "2025-01-01 00:00:00",
            },
        )

    old_user_columns = [
        column["name"]
        for column in inspect(engine).get_columns("users")
    ]
    Base.metadata.create_all(bind=engine)

    assert inspect(engine).has_table("user_eligibility_conditions")
    assert [
        column["name"]
        for column in inspect(engine).get_columns("users")
    ] == old_user_columns

    with test_session_factory() as db:
        existing_user = db.get(User, "existing-user")
        assert existing_user is not None
        assert existing_user.region == "서울특별시"

    app = FastAPI()
    app.include_router(users_router, prefix="/api/v1")

    def override_get_db():
        with test_session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/users/profile",
            json=valid_profile(),
        )

    assert response.status_code == 200
    assert set(response.json()) == {"user_id", "status", "message"}
    engine.dispose()


def test_welfare_routes_keep_existing_response_contracts(client):
    profile_response = client.post(
        "/api/v1/users/profile",
        json=valid_profile(),
    )
    user_id = profile_response.json()["user_id"]

    matched = client.get(
        "/api/v1/welfare/matched",
        params={"user_id": user_id},
    )
    reverse = client.get(
        "/api/v1/welfare/reverse-engineering",
        params={"user_id": user_id},
    )

    assert matched.status_code == 200
    assert set(matched.json()) == {
        "matched_count",
        "policies",
        "evaluated_count",
        "needs_review_count",
        "ineligible_count",
        "analysis_results",
    }
    assert isinstance(matched.json()["policies"], list)
    assert reverse.status_code == 200
    assert reverse.json() == {"recommendations": []}
