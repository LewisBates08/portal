"""Local bootstrap commands. Run from backend/, or set PYTHONPATH=backend."""

import argparse
import getpass
from pydantic import TypeAdapter, EmailStr
from sqlalchemy import select
from .database import SessionLocal
from .models import (
    Agency,
    User,
)
from .security import passwords
from .mail import queue_action


def create_admin():
    email = str(
        TypeAdapter(EmailStr).validate_python(input("Admin email: ").strip())
    ).lower()
    name = input("Admin name: ").strip()
    agency_name = input("Agency name: ").strip()
    password = getpass.getpass("Password (at least 10 characters): ")
    if not name or not agency_name or not 10 <= len(password) <= 128:
        raise SystemExit("Provide names and a password between 10 and 128 characters.")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("That email already exists. No changes made.")
        agency = Agency(name=agency_name)
        db.add(agency)
        db.flush()
        user = User(
            name=name,
            email=email,
            role="admin",
            agency_id=agency.id,
            password_hash=passwords.hash(password),
        )
        db.add(user)
        db.flush()
        queue_action(db, email, "verify", {"user_id": user.id}, 1440)
        db.commit()
    print(
        "Agency and administrator created. Check the verification email before signing in."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a verified agency administrator"
    )
    parser.add_argument("command", choices=["create-admin"])
    parser.parse_args()
    create_admin()
