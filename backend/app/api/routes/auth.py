from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.account import Account, AccountSession
from app.schemas.account import AccountView, LoginInput, SignupInput
from app.services.auth_service import (
    COOKIE_NAME, DUMMY_HASH, current_account, password_hash, start_session,
    throttle, token_hash, verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def view(account: Account) -> AccountView:
    return AccountView(account_id=account.account_id, username=account.username, display_name=account.display_name)


@router.post("/signup", response_model=AccountView, status_code=201)
def signup(data: SignupInput, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(request, db)
    account = Account(username=data.username, display_name=data.display_name, password_hash=password_hash(data.password))
    db.add(account)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "이미 사용 중인 아이디예요.")
    start_session(account, request, response, db)
    return view(account)


@router.post("/login", response_model=AccountView)
def login(data: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(request, db)
    account = db.scalar(select(Account).where(Account.username == data.username))
    valid = verify_password(data.password, account.password_hash if account else DUMMY_HASH)
    if not account or not valid:
        raise HTTPException(401, "아이디 또는 비밀번호가 일치하지 않아요.")
    start_session(account, request, response, db)
    return view(account)


@router.get("/me", response_model=AccountView)
def me(account: Account = Depends(current_account)):
    return view(account)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        current_account(request, db)
        db.execute(delete(AccountSession).where(AccountSession.token_hash == token_hash(token)))
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/api/v1", httponly=True, samesite="lax")
