import React, { useState } from 'react';
import { authAPI } from './api/auth.api';
import './auth.css';

export function ForgotPassword({ onBack }) {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const validateEmail = (value) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(value);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');

    if (!email) {
      setError('Пожалуйста, введите email.');
      return;
    }

    if (!validateEmail(email)) {
      setError('Пожалуйста, введите корректный email.');
      return;
    }

    setLoading(true);

    try {
      const response = await authAPI.forgotPassword(email);
      setMessage(response.data?.message || 'Ссылка для восстановления пароля отправлена на указанный email.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось отправить письмо. Попробуйте позже.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">Восстановление пароля</h1>
          <p className="auth-subtitle">Введите email, и мы отправим ссылку для сброса пароля.</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group-auth">
            <label className="form-label-auth">Email</label>
            <input
              type="email"
              name="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="form-control-auth"
              placeholder="example@mail.com"
              disabled={loading}
            />
          </div>

          {error && <div className="auth-error">{error}</div>}
          {message && <div className="auth-success">{message}</div>}

          <button
            type="submit"
            className="btn btn-primary auth-submit-btn"
            disabled={loading}
          >
            {loading ? 'Отправка...' : 'Отправить ссылку'}
          </button>

          <button
            type="button"
            className="btn auth-link-btn"
            onClick={onBack}
            disabled={loading}
            style={{
              marginTop: '12px',
              background: 'transparent',
              border: 'none',
              color: '#2563eb',
              cursor: 'pointer',
              textDecoration: 'underline',
              padding: 0
            }}
          >
            Вернуться к входу
          </button>
        </form>
      </div>
    </div>
  );
}
