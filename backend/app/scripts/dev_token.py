"""
Print the decrypted Strava access token for the first user.

Usage (from backend/):
    python -m app.scripts.dev_token

Outputs the raw token and a ready-to-paste curl header.
"""

from app.database import get_db
from app.models.user import User
from app.services.crypto import decrypt_token


def main() -> None:
    db = next(get_db())
    user = db.query(User).first()
    if not user:
        print("No users found in the database.")
        return

    try:
        token = decrypt_token(user.access_token_encrypted)
    except Exception as exc:
        print(f"Failed to decrypt token: {exc}")
        return

    print(f"User:  {user.display_name} (id={user.id})")
    print(f"Token: {token}")
    print()
    print("curl header:")
    print(f'  -H "Authorization: Bearer {token}"')
    print()
    print("Example:")
    print(f'  curl -s http://localhost:8000/api/v1/coverage/city/1 -H "Authorization: Bearer {token}" | python -m json.tool')


if __name__ == "__main__":
    main()
