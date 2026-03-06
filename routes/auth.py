import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from schemas.auth import GoogleAuthRequest, AuthResponse, UserOut
from utils.jwt import create_access_token
from utils.dependencies import get_current_user

router = APIRouter()


async def verify_google_token(id_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    data = resp.json()
    if data.get("aud") != os.getenv("GOOGLE_CLIENT_ID"):
        raise HTTPException(status_code=401, detail="Invalid Google token audience")
    return data  # contains: email, name, sub (google_id)


@router.post("/google", response_model=AuthResponse)
async def google_auth(
    body: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify Google idToken, upsert user, return JWT + user."""
    google_data = await verify_google_token(body.id_token)

    google_id = google_data["sub"]
    email = google_data["email"]
    name = google_data.get("name", email)

    # Upsert user
    result = await db.execute(
        select(User).where(User.google_id == google_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            name=name,
            email=email,
            google_id=google_id,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
    else:
        # Update name/email if changed
        user.name = name
        user.email = email
        await db.flush()

    token = create_access_token(str(user.id))

    return AuthResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserOut.model_validate(current_user)
