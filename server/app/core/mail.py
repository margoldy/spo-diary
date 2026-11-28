import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from html import escape
from pathlib import Path
from string import Template

from app.core.config import get_settings
from app.core.errors import ApiError

CODE_TEMPLATE = Template((Path(__file__).resolve().parents[1] / "templates/login_code.html").read_text("utf-8"))


def code_message(email: str, code: str, sender: str) -> EmailMessage:
    message = EmailMessage()
    name, address = parseaddr(sender)
    message["From"] = formataddr((name or "Моя библиотека", address))
    message["To"] = email
    message["Subject"] = "Код входа в Мою библиотеку"
    message.set_content(
        f"Моя библиотека\n\nВаш код входа: {code}\n"
        "Введите его на сайте, чтобы войти в аккаунт.\n"
        "Код действует 10 минут. Не сообщайте его другим.\n\n"
        "Если вы не запрашивали код, просто проигнорируйте письмо."
    )
    message.add_alternative(CODE_TEMPLATE.substitute(code=escape(code)), subtype="html")
    return message


def send_code(email: str, code: str) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise ApiError(503, "EMAIL_UNAVAILABLE", "Отправка писем не настроена")
    message = code_message(email, code, settings.smtp_from)
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
