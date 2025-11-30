from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.spotify import exchange_code_for_token

router = APIRouter()


@router.get("/callback", response_class=HTMLResponse)
def auth_callback(
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    """
    Spotify redirect target.

    Exemples d'URLs :
      - /auth/callback?code=...
      - /auth/callback?error=access_denied
    """
    if error:
        # L'utilisateur a refusé, ou autre erreur côté Spotify
        raise HTTPException(status_code=400, detail=f"Spotify auth error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing 'code' parameter.")

    # Échange du code contre un token + persisté sur disque
    exchange_code_for_token(code)

    # Réponse simple (tu pourras faire une page plus jolie plus tard)
    return """
    <html>
      <body>
        <h1>Spotify authorization complete ✅</h1>
        <p>You can close this window and return to the application.</p>
      </body>
    </html>
    """
