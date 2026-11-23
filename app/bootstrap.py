"""Run python -m app.bootstrap to create the initial manager locally."""

from getpass import getpass
from app.core import db, passwords

if __name__ == "__main__":
    username = input("Manager username: ").strip()
    password = getpass("Password (at least 10 characters): ")
    if len(username) < 3 or len(password) < 10:
        raise SystemExit("Username or password too short")
    with db() as c:
        c.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,'manager')",
            (username, passwords.hash(password)),
        )
    print("Manager created.")
