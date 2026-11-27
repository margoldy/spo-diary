import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.errors import ApiError


def send_code(email: str, code: str) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise ApiError(503, "EMAIL_UNAVAILABLE", "Отправка писем не настроена")
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = email
    message["Subject"] = "Код входа"
    message.set_content(f"Ваш код входа: {code}\nКод действует 10 минут.")
    try:
        factory = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
        with factory(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_tls and not settings.smtp_ssl:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            refused = smtp.send_message(message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
    except (OSError, smtplib.SMTPException):
        raise ApiError(503, "EMAIL_UNAVAILABLE", "Не удалось отправить письмо") from None
