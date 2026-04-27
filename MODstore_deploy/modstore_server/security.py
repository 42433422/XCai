"""MODstore 安全相关工具和配置"""

from __future__ import annotations

import os
import secrets
import string
from pathlib import Path


def generate_secure_key(length: int = 32) -> str:
    """生成安全的随机密钥"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_env_var(name: str, default: str | None = None) -> str:
    """获取环境变量，确保敏感数据不被硬编码"""
    value = os.environ.get(name)
    if value is None:
        return default
    return value


def ensure_secure_config() -> None:
    """确保安全配置正确设置"""
    # 检查JWT密钥
    jwt_secret = get_env_var("MODSTORE_JWT_SECRET")
    if not jwt_secret or jwt_secret == "your-random-secret-key-change-in-production":
        print("警告: MODSTORE_JWT_SECRET 未设置或使用默认值，建议设置为强随机密钥")
        print(f"建议使用: {generate_secure_key()}")
    
    # 检查管理员充值令牌
    admin_token = get_env_var("MODSTORE_ADMIN_RECHARGE_TOKEN")
    if not admin_token or admin_token == "your-admin-token-change-this":
        print("警告: MODSTORE_ADMIN_RECHARGE_TOKEN 未设置或使用默认值，建议设置为强随机密钥")
        print(f"建议使用: {generate_secure_key()}")
    
    # 检查支付宝配置
    alipay_app_id = get_env_var("ALIPAY_APP_ID")
    if not alipay_app_id or alipay_app_id == "your-alipay-app-id":
        print("警告: ALIPAY_APP_ID 未设置或使用默认值")
    
    # 检查邮箱配置
    smtp_password = get_env_var("MODSTORE_SMTP_PASSWORD")
    if not smtp_password or smtp_password == "your-qq-smtp-password":
        print("警告: MODSTORE_SMTP_PASSWORD 未设置或使用默认值")


def secure_file_permissions(file_path: Path) -> None:
    """设置文件的安全权限"""
    if file_path.exists():
        # 在不同操作系统上设置适当的权限
        if os.name == "posix":
            # Unix/Linux系统
            os.chmod(file_path, 0o600)  # 只有所有者可读写
        elif os.name == "nt":
            # Windows系统
            # Windows权限设置较为复杂，这里简化处理
            pass


def validate_secure_config() -> dict[str, bool]:
    """验证安全配置是否正确"""
    return {
        "jwt_secret_set": bool(get_env_var("MODSTORE_JWT_SECRET") and get_env_var("MODSTORE_JWT_SECRET") != "your-random-secret-key-change-in-production"),
        "admin_token_set": bool(get_env_var("MODSTORE_ADMIN_RECHARGE_TOKEN") and get_env_var("MODSTORE_ADMIN_RECHARGE_TOKEN") != "your-admin-token-change-this"),
        "alipay_configured": bool(get_env_var("ALIPAY_APP_ID") and get_env_var("ALIPAY_APP_ID") != "your-alipay-app-id"),
        "smtp_configured": bool(get_env_var("MODSTORE_SMTP_PASSWORD") and get_env_var("MODSTORE_SMTP_PASSWORD") != "your-qq-smtp-password"),
    }
