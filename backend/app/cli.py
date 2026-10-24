"""Administrative commands. Elevated roles are only granted here or by an existing ADMIN via the API.

Usage:
    python -m app.cli create-admin --email admin@example.edu --name "Campus Admin"
    python -m app.cli set-role --email person@example.edu --role STAFF
    python -m app.cli rematch    (recompute suggestions after changing MATCH_* settings)
    python -m app.cli cleanup [--dry-run]    (dead sessions and tokens, expired QR codes, orphaned uploads)
"""

import argparse
import getpass

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.enums import ReportType, UserRole
from app.db.models import Item, User
from app.db.session import SessionLocal
from app.db.types import utcnow
from app.schemas.auth import NewPassword
from app.services import audit, maintenance, matching
from app.services.auth import normalise_email

_password_adapter = TypeAdapter(NewPassword)


def create_admin(db: Session, email: str, name: str, password: str) -> User:
    email = normalise_email(email)
    if not name.strip():
        raise SystemExit("Name is required.")
    if email.rsplit("@", 1)[-1] not in get_settings().allowed_email_domains:
        raise SystemExit("Email domain is not in ALLOWED_EMAIL_DOMAINS.")
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise SystemExit("A user with this email already exists. Use set-role instead.")
    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(_password_adapter.validate_python(password)),
        role=UserRole.ADMIN,
        email_verified_at=utcnow(),
    )
    db.add(user)
    db.flush()
    audit.record(db, "cli.admin_created", "user", user.id, details={"source": "cli"})
    db.commit()
    return user


def set_role(db: Session, email: str, role: UserRole) -> User:
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    if user is None:
        raise SystemExit("No user with this email.")
    previous = user.role
    user.role = role
    audit.record(db, "cli.role_changed", "user", user.id, details={"role": [previous.value, role.value]})
    db.commit()
    return user


def rematch(db: Session) -> int:
    """Recompute suggestions for every open LOST report (each pair is scored from the lost side once)."""
    settings = get_settings()
    lost_reports = db.scalars(
        select(Item)
        .options(joinedload(Item.category), joinedload(Item.location))
        .where(Item.report_type == ReportType.LOST, Item.status.in_(matching.MATCHABLE_STATUSES))
    ).all()
    created = sum(matching.refresh_matches(db, item, settings, actor_id=None) for item in lost_reports)
    audit.record(db, "cli.rematch", "match", details={"reports": len(lost_reports), "created": created})
    db.commit()
    return created


def _prompt_password() -> str:
    password = getpass.getpass("Password (min 12 characters): ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    role_cmd = sub.add_parser("set-role")
    role_cmd.add_argument("--email", required=True)
    role_cmd.add_argument("--role", required=True, choices=[r.value for r in UserRole])
    sub.add_parser("rematch")
    cleanup_cmd = sub.add_parser("cleanup")
    cleanup_cmd.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.command == "create-admin":
            try:
                user = create_admin(db, args.email, args.name, _prompt_password())
            except ValidationError as exc:
                raise SystemExit(f"Invalid password: {exc.errors()[0]['msg']}") from None
            print(f"Created admin user {user.email} (id {user.id}).")
        elif args.command == "set-role":
            user = set_role(db, args.email, UserRole(args.role))
            print(f"{user.email} now has role {user.role.value}.")
        elif args.command == "rematch":
            print(f"Rematch complete: {rematch(db)} new suggestions.")
        else:
            counts = maintenance.cleanup(db, get_settings(), dry_run=args.dry_run)
            verb = "Would remove" if args.dry_run else "Removed"
            print(f"{verb}: " + ", ".join(f"{n} {name.replace('_', ' ')}" for name, n in counts.items()))


if __name__ == "__main__":
    main()
