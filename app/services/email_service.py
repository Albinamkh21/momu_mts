"""Email service for sending verification and password reset emails"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails (file mode or SMTP)"""

    @staticmethod
    def _get_email_mode() -> str:
        """Get email mode from environment: 'file' or 'smtp'"""
        return os.getenv('EMAIL_MODE', 'file')

    @staticmethod
    def _get_frontend_url() -> str:
        """Get frontend URL from environment"""
        return os.getenv('FRONTEND_URL', 'http://localhost:5173')

    @staticmethod
    async def send_verification_email(email: str, token: str) -> None:
        """Send verification email to user"""
        frontend_url = EmailService._get_frontend_url()
        verification_link = f"{frontend_url}/verify-email?token={token}"
        
        subject = 'Подтверждение регистрации MOMU'
        html_content = f"""
        <div style="font-family: sans-serif; padding: 20px;">
            <h2>Добро пожаловать!</h2>
            <p>Пожалуйста, подтвердите ваш email, перейдя по ссылке ниже:</p>
            <a href="{verification_link}" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                Подтвердить Email
            </a>
            <p style="margin-top: 20px; font-size: 12px; color: #666;">
                Если кнопка не работает, скопируйте эту ссылку в браузер:<br>
                {verification_link}
            </p>
        </div>
        """
        
        await EmailService._send_email(email, subject, html_content, 'verification')

    @staticmethod
    async def send_password_reset_email(email: str, token: str) -> None:
        """Send password reset email to user"""
        frontend_url = EmailService._get_frontend_url()
        reset_link = f"{frontend_url}/reset-password?token={token}"
        
        subject = 'Сброс пароля MOMU'
        html_content = f"""
        <div style="font-family: sans-serif; padding: 20px;">
            <h2>Сброс пароля</h2>
            <p>Чтобы изменить пароль, перейдите по ссылке ниже:</p>
            <a href="{reset_link}" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                Сбросить пароль
            </a>
            <p style="margin-top: 20px; font-size: 12px; color: #666;">
                Если кнопка не работает, скопируйте эту ссылку в браузер:<br>
                {reset_link}
            </p>
        </div>
        """
        
        await EmailService._send_email(email, subject, html_content, 'reset')

    @staticmethod
    async def _send_email(
        email: str, 
        subject: str, 
        html_content: str, 
        email_type: str
    ) -> None:
        """Internal method to send email (file or SMTP)"""
        email_mode = EmailService._get_email_mode()
        
        # MODE 1: Save to file (development mode)
        if email_mode == 'file':
            try:
                # Create logs/emails directory if it doesn't exist
                email_dir = Path(__file__).parent.parent / 'logs' / 'emails'
                email_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate filename
                timestamp = int(datetime.now().timestamp() * 1000)
                filename = f"{timestamp}_{email}_{email_type}.html"
                filepath = email_dir / filename
                
                # Write HTML content to file
                filepath.write_text(html_content, encoding='utf-8')
                
                logger.info(f"[EMAIL MOCK] Email for {email} saved to file: logs/emails/{filename}")
                
            except Exception as err:
                logger.error(f"[EMAIL MOCK ERROR] Error saving email: {err}")
                
        # MODE 2: Send via SMTP (production mode)
        # MODE 2: Send via SMTP (production mode)
        elif email_mode == 'smtp':
            try:
                import aiosmtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                # 1. Используем переменные в точности как в вашем .env
                smtp_host = os.getenv('mail_server', 'smtp.gmail.com')
                smtp_port = int(os.getenv('mail_port', '587'))
                smtp_user = os.getenv('EMAIL_USER')
                smtp_password = os.getenv('EMAIL_PASS')
                
                # Отправитель (оставляем MOMU)
                smtp_from = os.getenv('SMTP_FROM', '"MOMU" <noreply@momu.kz>')
                
                if not smtp_user or not smtp_password:
                    logger.error("[EMAIL ERROR] EMAIL_USER or EMAIL_PASS not set")
                    return
                
                # Создаем сообщение
                message = MIMEMultipart('alternative')
                message['Subject'] = subject
                message['From'] = smtp_from
                message['To'] = email
                
                # Добавляем HTML
                html_part = MIMEText(html_content, 'html')
                message.attach(html_part)
                
                # 2. Отправляем письмо
                await aiosmtplib.send(
                    message,
                    hostname=smtp_host,
                    port=smtp_port,
                    username=smtp_user,
                    password=smtp_password,
                    start_tls=True  # ВАЖНО: для 587 порта (Gmail) нужен STARTTLS, а не use_tls!
                )
                
                logger.info(f"[EMAIL] Письмо успешно отправлено на {email}")
                
            except Exception as err:
                logger.error(f"[EMAIL ERROR] Error sending email: {err}")
      
