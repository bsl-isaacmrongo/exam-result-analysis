"""Administrator CLI for provisioning accounts (there is no self-registration).

    python -m app.cli create-user staff@school.org --name "Jane Doe" --role admin
    python -m app.cli create-user staff@school.org --password   # prompts
    python -m app.cli set-password staff@school.org             # prompts, revokes sessions
    python -m app.cli disable-user staff@school.org             # revokes sessions
    python -m app.cli unlock-user staff@school.org

    python -m app.cli create-school bge --name "Braeburn Garden Estate" --curricula ib,igcse
    python -m app.cli update-school bge --curricula ib,igcse,a-level   # or --name / --disable / --enable
    python -m app.cli list-schools
"""

import argparse
import getpass
import sys

from app.core.security import hash_password, validate_password_strength
from app.core.sessions import revoke_all_sessions
from app.database import SessionLocal
from pydantic import ValidationError

from app.features.auth.service import find_user_by_email, normalize_email
from app.features.schools.schemas import SchoolCreate, SchoolUpdate
from app.features.schools.service import find_school, list_schools
from app.models.school import School
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

    create_school = sub.add_parser("create-school")
    create_school.add_argument("code")
    create_school.add_argument("--name", required=True)
    create_school.add_argument(
        "--curricula", default="", help="comma-separated, e.g. ib,igcse"
    )
    update_school = sub.add_parser("update-school")
    update_school.add_argument("code")
    update_school.add_argument("--name")
    update_school.add_argument("--curricula", help="comma-separated, replaces the list")
    state = update_school.add_mutually_exclusive_group()
    state.add_argument("--disable", action="store_true")
    state.add_argument("--enable", action="store_true")
    sub.add_parser("list-schools")

    args = parser.parse_args(argv)

    if args.command in ("create-school", "update-school", "list-schools"):
        return _school_command(args)

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


def _split(value: str) -> list[str]:
    return [part for part in (p.strip() for p in value.split(",")) if part]


def _school_command(args: argparse.Namespace) -> int:
    with SessionLocal() as db:
        if args.command == "list-schools":
            for school in list_schools(db, include_inactive=True):
                state = "" if school.is_active else " (disabled)"
                print(f"{school.code:<20} {school.name}{state}  [{', '.join(school.curricula)}]")
            return 0

        try:
            if args.command == "create-school":
                payload = SchoolCreate(
                    code=args.code, name=args.name, curricula=_split(args.curricula)
                )
                if find_school(db, payload.code) is not None:
                    print(f"School {payload.code} already exists", file=sys.stderr)
                    return 1
                school = School(**payload.model_dump(), is_active=True)
                db.add(school)
            else:
                changes: dict = {}
                if args.name is not None:
                    changes["name"] = args.name
                if args.curricula is not None:
                    changes["curricula"] = _split(args.curricula)
                if args.disable or args.enable:
                    changes["is_active"] = args.enable
                update = SchoolUpdate(**changes)
                school = find_school(db, args.code)
                if school is None:
                    print(f"No school with code {args.code}", file=sys.stderr)
                    return 1
                for field, value in update.model_dump(exclude_unset=True).items():
                    setattr(school, field, value)
        except ValidationError as exc:
            for error in exc.errors():
                print(f"{'.'.join(map(str, error['loc']))}: {error['msg']}", file=sys.stderr)
            return 1

        db.commit()
        print(f"{args.command}: {school.code} - {school.name} [{', '.join(school.curricula)}]")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
