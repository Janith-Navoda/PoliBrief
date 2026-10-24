"""
PoliBrief — Administrator Setup Script
Run this once to create your administrator account.
Usage: python scripts/setup_admin.py
"""
import sys
import os

# Make the project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import getpass
import re

from backend.app.core.logging_config import setup_logging
from backend.app.database.session import init_db, SessionLocal
from backend.app.auth.service import admin_exists, create_admin, get_admin_by_username

setup_logging()


def validate_username(username: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_]{3,64}$", username))


def validate_password(password: str) -> bool:
    return len(password) >= 10


def main():
    print("\n" + "=" * 50)
    print("  PoliBrief V1 — Administrator Setup")
    print("=" * 50)

    # Initialise database and tables
    init_db()

    db = SessionLocal()
    try:
        if admin_exists(db):
            print("\n✓ An administrator account already exists.")
            print("  To reset, delete the database and re-run this script.")
            print("  Database: storage/database/polibrief.db\n")
            return

        print("\nCreate your administrator account.\n")

        # Username
        while True:
            username = input("Username (3–64 chars, letters/numbers/underscore): ").strip()
            if validate_username(username):
                break
            print("  ✗ Invalid username. Use only letters, numbers, and underscores (3–64 chars).")

        # Password
        while True:
            password = getpass.getpass("Password (minimum 10 characters): ")
            if not validate_password(password):
                print("  ✗ Password must be at least 10 characters.")
                continue
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("  ✗ Passwords do not match.")
                continue
            break

        admin = create_admin(db, username, password)
        print(f"\n✓ Administrator account '{admin.username}' created successfully.")
        print("\nYou can now start PoliBrief with:")
        print("  scripts\\start.ps1")
        print("  — or —")
        print("  python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000\n")

    except KeyboardInterrupt:
        print("\n\n  Setup cancelled.\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
