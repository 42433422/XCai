"""XC AGI 邮件发送服务：基于 QQ邮箱 SMTP 发送验证码。"""

from __future__ import annotations

import os
import random
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

from sqlalchemy import func

from modstore_server.models import User, get_session_factory

_MODSTORE_ROOT = Path(__file__).resolve().parent.parent


def _load_modstore_env() -> None:
    """加载 ``MODstore_deploy/.env``。优先 ``python-dotenv``；未安装时做简单 KEY=VALUE 解析。"""
    path = _MODSTORE_ROOT / ".env"
    if not path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(path, override=False)
    except ImportError:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key, _, val = s.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_modstore_env()


def _smtp_host() -> str:
    return (os.environ.get("MODSTORE_SMTP_HOST") or "smtp.qq.com").strip()


def _smtp_port() -> int:
    try:
        return int(os.environ.get("MODSTORE_SMTP_PORT") or "465")
    except ValueError:
        return 465


def _smtp_user() -> str:
    return (os.environ.get("MODSTORE_SMTP_USER") or "").strip()


def _smtp_password() -> str:
    return (os.environ.get("MODSTORE_SMTP_PASSWORD") or "").strip()


def _sender_email() -> str:
    u = _smtp_user()
    return (os.environ.get("MODSTORE_SENDER_EMAIL") or u).strip()


def _sender_name() -> str:
    return (os.environ.get("MODSTORE_SENDER_NAME") or "XC AGI").strip()


_CODE_EXPIRE_MINUTES = 5
_CODE_LENGTH = 6


def _email_debug_enabled() -> bool:
    return os.environ.get("MODSTORE_EMAIL_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")


def _generate_code() -> str:
    return "".join([str(random.randint(0, 9)) for _ in range(_CODE_LENGTH)])


def generate_verification_code() -> str:
    """生成 6 位数字验证码（不入库、不发信）。"""
    return _generate_code()


def assert_email_outbound_configured() -> None:
    """
    在写入验证码前调用：未配置 SMTP 且未开 DEBUG 时立即失败，避免先 202 再发现不能发信。
    """
    _load_modstore_env()
    if _email_debug_enabled():
        return
    user = _smtp_user()
    password = _smtp_password()
    if not user or not password:
        raise RuntimeError(
            "未配置邮件服务：请在 MODstore_deploy/.env 或环境变量中设置 MODSTORE_SMTP_USER 与 "
            "MODSTORE_SMTP_PASSWORD；也可安装 python-dotenv 后使用 .env。"
            "本地调试可设 MODSTORE_EMAIL_DEBUG=1 跳过发信并在控制台打印验证码。"
        )


def send_verification_email(email: str, code: str, purpose: str = "login") -> None:
    """
    将已有验证码发到邮箱（供 HTTP 先返回后再由后台任务调用）。
    ``purpose``: ``login`` | ``register``，仅影响邮件文案。
    """
    _load_modstore_env()

    if _email_debug_enabled():
        print(f"[MODSTORE_EMAIL_DEBUG] to={email} purpose={purpose} code={code}", flush=True)
        return

    user = _smtp_user()
    password = _smtp_password()
    if not user or not password:
        raise RuntimeError(
            "未配置邮件服务：请在 MODstore_deploy/.env 或环境变量中设置 MODSTORE_SMTP_USER 与 "
            "MODSTORE_SMTP_PASSWORD；也可安装 python-dotenv 后使用 .env。"
            "本地调试可设 MODSTORE_EMAIL_DEBUG=1 跳过发信并在控制台打印验证码。"
        )

    action = "完成注册" if purpose == "register" else "完成登录"
    sender_name = _sender_name()

    subject = f"{sender_name} - 邮箱验证码"
    body = f"""
<html>
<body style="font-family: sans-serif; padding: 20px;">
  <h2 style="color: #333;">{sender_name} 邮箱验证码</h2>
  <p>您的验证码是：</p>
  <h1 style="color: #60a5fa; letter-spacing: 4px; font-size: 32px;">{code}</h1>
  <p>验证码将在 <b>{_CODE_EXPIRE_MINUTES} 分钟</b>后过期，请尽快{action}。</p>
  <p style="color: #999; font-size: 12px;">如果不是您本人操作，请忽略此邮件。</p>
</body>
</html>
"""

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{_sender_email()}>"
    msg["To"] = email

    with smtplib.SMTP_SSL(_smtp_host(), _smtp_port()) as server:
        server.login(user, password)
        server.sendmail(_sender_email(), email, msg.as_string())


def send_verification_code(email: str, purpose: str = "login") -> str:
    """
    同步：生成验证码并立即发信（测试或无需队列的场景）。
    返回验证码字符串。
    """
    assert_email_outbound_configured()
    code = generate_verification_code()
    send_verification_email(email, code, purpose)
    return code


def find_user_by_email(email: str) -> User | None:
    """根据邮箱查找用户（不区分大小写）。"""
    norm = (email or "").strip().lower()
    if not norm:
        return None
    sf = get_session_factory()
    with sf() as session:
        return session.query(User).filter(func.lower(User.email) == norm).first()
