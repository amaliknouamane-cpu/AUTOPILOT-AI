
import getpass
import bcrypt
from backend.database import get_connection

username = input("Nom d'utilisateur : ").strip()
password = getpass.getpass("Mot de passe : ")
confirm_password = getpass.getpass("Confirmer le mot de passe : ")

if not username or not password:
    print("Erreur : les champs sont obligatoires.")
    raise SystemExit

if password != confirm_password:
    print("Erreur : les mots de passe ne correspondent pas.")
    raise SystemExit

password_hash = bcrypt.hashpw(
    password.encode("utf-8"),
    bcrypt.gensalt()
).decode("utf-8")

try:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dashboard_users
                    (username, password_hash, role)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (username, password_hash, "admin")
            )
            user_id = cur.fetchone()[0]

    print(f"Administrateur créé avec succès. ID : {user_id}")

except Exception as error:
    print(f"Erreur : {error}")
