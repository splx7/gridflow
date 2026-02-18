import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.config import settings
from app.core.deps import get_current_user
from app.core.rate_limit import auth_limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.models.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email and password. Returns JWT access and refresh tokens.",
)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    auth_limiter.check(request)

    pwd_error = validate_password_strength(body.password)
    if pwd_error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pwd_error)

    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    description="Authenticate with email and password. Returns JWT access and refresh tokens.",
)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    auth_limiter.check(request)
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access/refresh token pair.",
)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(body.refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post(
    "/anonymous",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Anonymous login",
    description="Create an anonymous user account and return tokens. Intended for dev/demo convenience.",
)
async def anonymous_login(db: AsyncSession = Depends(get_db)):
    anon_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"anon-{anon_id}@gridflow.local",
        hashed_password=hash_password(uuid.uuid4().hex),
        full_name=f"Anonymous User",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Return the profile of the currently authenticated user.",
)
async def me(user: User = Depends(get_current_user)):
    return user
