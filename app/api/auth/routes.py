from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.spotify import (
    SpotifyTokenMissing,
    build_spotify_auth_url,
    exchange_code_for_token,
    get_current_user_id,
    load_spotify_token,
)

router = APIRouter()


@router.get("/url")
def get_auth_url() -> dict:
    """
    Retourne l'URL d'auth Spotify pour rediriger l'utilisateur côté front.
    """
    return {"auth_url": build_spotify_auth_url()}


@router.get("/status")
def auth_status() -> dict:
    """
    Indique si un token Spotify valide est disponible.
    """
    try:
        token_info = load_spotify_token()
    except SpotifyTokenMissing:
        return {
            "authenticated": False,
            "reason": "missing_or_invalid_token",
            "expires_at": None,
        }

    return {
        "authenticated": True,
        "reason": None,
        "expires_at": token_info.get("expires_at"),
    }


@router.get("/profile")
def auth_profile() -> dict:
    """
    Snapshot simple du compte Spotify (user id).
    """
    try:
        token_info = load_spotify_token()
    except SpotifyTokenMissing as e:
        raise HTTPException(
            status_code=401,
            detail={
                "status": "unauthenticated",
                "message": str(e) or "Spotify authorization required.",
                "auth_url": build_spotify_auth_url(),
            },
        )

    user_id = get_current_user_id(token_info)
    return {
        "authenticated": True,
        "user": {"id": user_id},
    }


@router.get("/callback", response_class=HTMLResponse)
def auth_callback(
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    """
    Redirect Spotify → échange le code contre un token et le persiste.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Spotify authorization failed: {error}",
        )

    if code is None:
        raise HTTPException(status_code=400, detail="Missing 'code' parameter.")

    exchange_code_for_token(code)

    return """
    <html>
      <body>
        <h1>Spotify authorization complete ✅</h1>
        <p>You can close this window and return to the application.</p>
      </body>
    </html>
    """
