"""Authentication endpoints under /api/auth."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.api.deps import (
    AppSettings,
    CurrentSession,
    CurrentUser,
    SESSION_COOKIE,
    DbSession,
    clear_session_cookies,
    set_session_cookies,
)
from app.core.rate_limit import rate_limit
from app.schemas.auth import (
    ChangePasswordRequest,
    EmailRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ProfileUpdate,
    ResetPasswordRequest,
    SessionResponse,
    TokenRequest,
    UserResponse,
)
from app.services import auth as auth_service
from app.services.email import BackgroundEmailSender, EmailSender, get_email_sender

router = APIRouter(prefix="/auth", tags=["auth"])


def get_request_sender(
    background_tasks: BackgroundTasks, inner: Annotated[EmailSender, Depends(get_email_sender)]
) -> EmailSender:
    return BackgroundEmailSender(background_tasks, inner)


Sender = Annotated[EmailSender, Depends(get_request_sender)]

CHECK_INBOX = "If this address can receive one, we have sent an email with the next step."


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("register", 10, 3600))],
)
def register(body: RegisterRequest, db: DbSession, settings: AppSettings, sender: Sender) -> MessageResponse:
    auth_service.register(db, sender, settings, body.name, body.email, body.password, body.campus_id,
                          body.department, body.phone)
    return MessageResponse(message=CHECK_INBOX)


@router.post("/verify-email", dependencies=[Depends(rate_limit("verify-email", 20, 300))])
def verify_email(body: TokenRequest, db: DbSession) -> MessageResponse:
    auth_service.verify_email(db, body.token)
    return MessageResponse(message="Email address confirmed. You can now sign in.")


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("resend-verification", 5, 900))],
)
def resend_verification(body: EmailRequest, db: DbSession, settings: AppSettings, sender: Sender) -> MessageResponse:
    auth_service.resend_verification(db, sender, settings, body.email)
    return MessageResponse(message=CHECK_INBOX)


@router.post("/login", dependencies=[Depends(rate_limit("login", 20, 300))])
def login(body: LoginRequest, response: Response, db: DbSession, settings: AppSettings) -> UserResponse:
    issued = auth_service.login(db, settings, body.email, body.password)
    set_session_cookies(response, settings, issued.session_token, issued.csrf_token, issued.expires_at)
    return UserResponse.model_validate(issued.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(session: CurrentSession, response: Response, db: DbSession, settings: AppSettings) -> None:
    auth_service.logout(db, session)
    clear_session_cookies(response, settings)


@router.get("/session")
def current_session(request: Request, db: DbSession, settings: AppSettings) -> SessionResponse:
    """Like /me, but returns {"user": null} instead of 401 so anonymous page loads stay error-free."""
    raw = request.cookies.get(SESSION_COOKIE)
    session = auth_service.resolve_session(db, raw) if raw else None
    return SessionResponse(
        user=UserResponse.model_validate(session.user) if session else None,
        allowed_email_domains=settings.allowed_email_domains,
    )


@router.get("/me")
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/me")
def update_me(body: ProfileUpdate, user: CurrentUser, db: DbSession) -> UserResponse:
    # Required fields ignore an explicit null; phone is optional, so null clears it.
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None or k == "phone"}
    return UserResponse.model_validate(auth_service.update_profile(db, user, changes))


@router.post(
    "/password/forgot",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot-password", 5, 900))],
)
def forgot_password(body: EmailRequest, db: DbSession, settings: AppSettings, sender: Sender) -> MessageResponse:
    auth_service.forgot_password(db, sender, settings, body.email)
    return MessageResponse(message=CHECK_INBOX)


@router.post("/password/reset", dependencies=[Depends(rate_limit("reset-password", 10, 900))])
def reset_password(body: ResetPasswordRequest, db: DbSession) -> MessageResponse:
    auth_service.reset_password(db, body.token, body.new_password)
    return MessageResponse(message="Password updated. Sign in with your new password.")


@router.post("/password/change", dependencies=[Depends(rate_limit("change-password", 10, 900))])
def change_password(body: ChangePasswordRequest, session: CurrentSession, db: DbSession) -> MessageResponse:
    auth_service.change_password(db, session, body.current_password, body.new_password)
    return MessageResponse(message="Password updated. Other devices have been signed out.")
