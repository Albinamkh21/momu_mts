# Модуль аутентификации и авторизации

## Описание

Модуль аутентификации предоставляет полный функционал для регистрации, входа, подтверждения email, восстановления пароля и управления сессиями пользователей.

## Структура

### Backend

```
app/
├── __models/
│   └── auth.py                    # Модели: Role, User, RefreshToken, PasswordResetToken
├── __schemas/
│   └── auth.py                    # Pydantic схемы для валидации запросов/ответов
├── __crud/
│   └── user_repository.py         # Репозиторий для работы с БД
├── services/
│   ├── auth_service.py            # Бизнес-логика авторизации
│   └── email_service.py           # Сервис отправки email
├── api/
│   ├── deps.py                    # Зависимости (get_db, get_current_user)
│   └── v1/endpoints/
│       └── auth.py                # REST API endpoints
└── migrations/versions/
    └── e3a4b5c6d7e8_add_auth_tables.py  # Миграция для создания таблиц
```

### Frontend

```
app/ui/src/features/auth/
├── api/
│   └── auth.api.js               # API клиент
├── AuthPage.jsx                  # Страница входа/регистрации
├── VerifyEmail.jsx               # Подтверждение email
├── ForgotPassword.jsx            # Запрос сброса пароля
├── ResetPassword.jsx             # Сброс пароля
└── auth.css                      # Стили
```

## Установка и настройка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

Новые зависимости:
- `bcrypt` - хеширование паролей
- `PyJWT` - работа с JWT токенами
- `aiosmtplib` - отправка email (асинхронно)

### 2. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и настройте:

```bash
cp .env.example .env
```

Основные переменные:

```env
# JWT секреты (ОБЯЗАТЕЛЬНО измените в production!)
JWT_ACCESS_SECRET=your-super-secret-access-key
JWT_REFRESH_SECRET=your-super-secret-refresh-key

# Email конфигурация
EMAIL_MODE=file                    # 'file' - разработка, 'smtp' - продакшн
FRONTEND_URL=http://localhost:5173

# SMTP (только для EMAIL_MODE=smtp)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 3. Применение миграций

```bash
cd app
alembic upgrade head
```

Это создаст таблицы:
- `role` - роли пользователей (USER, ADMIN)
- `user` - пользователи
- `refresh_token` - refresh токены
- `password_reset_token` - токены сброса пароля

### 4. Проверка ролей

После миграции автоматически создаются роли:
- **USER** - обычный пользователь
- **ADMIN** - администратор

## API Endpoints

Все endpoints доступны по префиксу `/api/v1/auth`:

### 1. Регистрация
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "confirmPassword": "password123",
  "name": "John Doe"
}

Response:
{
  "success": true,
  "message": "Регистрация успешна. Проверьте почту для подтверждения."
}
```

### 2. Вход
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

Response:
{
  "accessToken": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refreshToken": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "role": "USER"
  }
}
```

### 3. Подтверждение email
```http
POST /api/v1/auth/verify-email
Content-Type: application/json

{
  "token": "verification_token_from_email"
}

Response:
{
  "success": true,
  "message": "Email успешно подтвержден. Теперь вы можете войти."
}
```

### 4. Запрос сброса пароля
```http
POST /api/v1/auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}

Response:
{
  "success": true,
  "message": "Если этот email зарегистрирован, ссылка для восстановления будет отправлена."
}
```

### 5. Сброс пароля
```http
POST /api/v1/auth/reset-password
Content-Type: application/json

{
  "token": "reset_token_from_email",
  "password": "newpassword123",
  "confirmPassword": "newpassword123"
}

Response:
{
  "success": true,
  "message": "Пароль успешно изменен. Теперь вы можете войти."
}
```

### 6. Обновление токена
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refreshToken": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

Response:
{
  "accessToken": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refreshToken": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

## Защищенные endpoints

Для доступа к защищенным endpoints используйте `get_current_user` зависимость:

```python
from fastapi import Depends
from api.deps import get_current_user, get_current_active_user
from __models.auth import User

@router.get("/protected")
async def protected_route(
    current_user: User = Depends(get_current_user)
):
    return {"message": f"Hello, {current_user.email}"}

@router.get("/active-only")
async def active_only_route(
    current_user: User = Depends(get_current_active_user)
):
    # Только для подтвержденных пользователей
    return {"message": "You are verified"}
```

## Email в режиме разработки

По умолчанию `EMAIL_MODE=file`, все письма сохраняются в `app/logs/emails/`:

```
app/logs/emails/
├── 1692345678901_user@example.com_verification.html
└── 1692345678902_user@example.com_reset.html
```

Открывайте файлы в браузере для просмотра писем.

## Email в production

Установите `EMAIL_MODE=smtp` и настройте SMTP параметры:

```env
EMAIL_MODE=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM="MOMU Project" <noreply@momu.kz>
```

**Для Gmail**: используйте App Password (не основной пароль):
1. Включите 2FA в Google аккаунте
2. Создайте App Password: https://myaccount.google.com/apppasswords
3. Используйте сгенерированный пароль в `SMTP_PASSWORD`

## Безопасность

### JWT токены
- **Access token**: действителен 15 минут
- **Refresh token**: действителен 30 дней

### Хеширование паролей
Используется `bcrypt` с автоматической генерацией соли.

### Защита от перебора
- Всегда возвращаем одинаковое сообщение при восстановлении пароля (не раскрываем существование email)
- Минимальная длина пароля: 6 символов

## Frontend интеграция

### Хранение токенов

```javascript
// После успешного логина
localStorage.setItem('accessToken', accessToken);
localStorage.setItem('refreshToken', refreshToken);
localStorage.setItem('user', JSON.stringify(user));

// Установка заголовка Authorization
httpClient.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
```

### Автоматическое обновление токена

Добавьте interceptor в httpClient:

```javascript
httpClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const refreshToken = localStorage.getItem('refreshToken');
        const { data } = await httpClient.post('/auth/refresh', { refreshToken });
        
        localStorage.setItem('accessToken', data.accessToken);
        localStorage.setItem('refreshToken', data.refreshToken);
        
        originalRequest.headers['Authorization'] = `Bearer ${data.accessToken}`;
        return httpClient(originalRequest);
      } catch (err) {
        // Redirect to login
        window.location.href = '/login';
      }
    }
    
    return Promise.reject(error);
  }
);
```

## Тестирование

```bash
# Запуск сервера
cd app
uvicorn main:app --reload

# API документация доступна по адресу:
http://localhost:8000/docs
```

## Troubleshooting

### Ошибка "Роль по умолчанию не найдена"
Проверьте, что миграция создала роли:
```sql
SELECT * FROM role;
```

Если ролей нет, выполните:
```sql
INSERT INTO role (name, description) VALUES
('USER', 'Default user role'),
('ADMIN', 'Administrator role');
```

### Письма не отправляются
- В режиме `file`: проверьте папку `app/logs/emails/`
- В режиме `smtp`: проверьте SMTP настройки и логи

### JWT токен невалиден
Проверьте, что `JWT_ACCESS_SECRET` одинаковый в `.env` и не изменился после создания токена.

## Дальнейшее развитие

- [ ] Rate limiting для защиты от bruteforce
- [ ] 2FA (двухфакторная аутентификация)
- [ ] OAuth (Google, GitHub)
- [ ] Логирование действий пользователей
- [ ] Email templates с использованием Jinja2
- [ ] Роли и права доступа (RBAC)
