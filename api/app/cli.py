"""Administrator CLI for provisioning accounts (there is no self-registration).

    python -m app.cli create-user staff@school.org --name "Jane Doe" --role admin
    python -m app.cli create-user staff@school.org --password   # prompts
    python -m app.cli set-password staff@school.org             # prompts, revokes sessions
    python -m app.cli disable-user staff@school.org             # revokes sessions
    python -m app.cli unlock-user staff@school.org
"""

import argparse
import getpass
import sys

from app.core.security import hash_password, validate_password_strength
from app.core.sessions import revoke_all_sessions
from app.database import SessionLocal
from app.features.auth.service import find_user_by_email, normalize_email
from app.models.user import User


def _prompt_password() -> str:
    while True:
        password = getpass.getpass("New password: ")
        try:
            validate_password_strength(password)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            continue
        if getpass.getpass("Confirm password: ") != password:
            print("Passwords do not match", file=sys.stderr)
            continue
        return password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-user")
    create.add_argument("email")
    create.add_argument("--name")
    create.add_argument("--role", default="user")
    create.add_argument(
        "--password", action="store_true", help="prompt for a password"
    )
    for name in ("set-password", "disable-user", "enable-user", "unlock-user"):
        sub.add_parser(name).add_argument("email")

    args = parser.parse_args(argv)

    with SessionLocal() as db:
        user = find_user_by_email(db, args.email)

        if args.command == "create-user":
            if user is not None:
                print(f"User {user.email} already exists", file=sys.stderr)
                return 1
            user = User(
                email=normalize_email(args.email),
                name=args.name,
                role=args.role,
                is_active=True,
                failed_login_attempts=0,
            )
            if args.password:
                user.password_hash = hash_password(_prompt_password())
            db.add(user)
            db.commit()
            print(f"Created {user.email} (role={user.role})")
            return 0

        if user is None:
            print(f"No user with email {args.email}", file=sys.stderr)
            return 1

        if args.command == "set-password":
            user.password_hash = hash_password(_prompt_password())
            user.failed_login_attempts = 0
            user.locked_until = None
            revoke_all_sessions(db, user)
        elif args.command == "disable-user":
            user.is_active = False
            revoke_all_sessions(db, user)
        elif args.command == "enable-user":
            user.is_active = True
        elif args.command == "unlock-user":
            user.failed_login_attempts = 0
            user.locked_until = None
        db.commit()
        print(f"{args.command}: done for {user.email}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
