import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.connection import get_db
from app.models.account import Account, AccountSession, AuthAttempt

COOKIE_NAME = "youth_session"
SESSION_SECONDS = 7 * 24 * 60 * 60
ITERATIONS = 600_000


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt, expected = encoded.split("$")
        if scheme != "pbkdf2_sha256" or int(iterations) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# 존재하지 않는 아이디도 동일한 비밀번호 검증 비용을 사용한다.
DUMMY_HASH = password_hash(secrets.token_urlsafe(32))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def throttle(request: Request, db: Session) -> None:
    # 프록시 헤더를 임의로 신뢰하지 않는다. 로컬/단일 서버용 시도 제한.
    bucket = token_hash(request.client.host if request.client else "unknown")
    cutoff = utcnow() - timedelta(minutes=15)
    db.execute(delete(AuthAttempt).where(AuthAttempt.created_at < cutoff))
    count = db.scalar(select(func.count()).select_from(AuthAttempt).where(AuthAttempt.bucket == bucket))
    if count >= 40:
        db.commit()
        raise HTTPException(429, "로그인 시도가 많아요. 15분 뒤 다시 시도해주세요.")
    db.add(AuthAttempt(bucket=bucket, created_at=utcnow()))
    db.commit()


def start_session(account: Account, request: Request, response: Response, db: Session) -> None:
    previous = request.cookies.get(COOKIE_NAME)
    if previous:
        db.execute(delete(AccountSession).where(AccountSession.token_hash == token_hash(previous)))
    db.execute(delete(AccountSession).where(AccountSession.expires_at <= utcnow()))
    token = secrets.token_urlsafe(32)
    db.add(AccountSession(token_hash=token_hash(token), account_id=account.account_id,
                          expires_at=utcnow() + timedelta(seconds=SESSION_SECONDS)))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/api/v1")


def current_account(request: Request, db: Session = Depends(get_db)) -> Account:
    token = request.cookies.get(COOKIE_NAME)
    session = db.get(AccountSession, token_hash(token)) if token else None
    if not session or session.expires_at <= utcnow():
        raise HTTPException(401, "로그인이 필요해요. 다시 로그인해주세요.")
    account = db.get(Account, session.account_id)
    if not account:
        raise HTTPException(401, "로그인이 필요해요.")
    expected = request.headers.get("x-account-id")
    if expected and expected != account.account_id:
        raise HTTPException(401, "다른 창에서 계정이 변경됐어요. 다시 로그인해주세요.")
    return account


def require_owned_profile(account: Account, user_id: str) -> None:
    if account.profile_id != user_id:
        raise HTTPException(404, "저장된 프로필을 찾지 못했어요.")
