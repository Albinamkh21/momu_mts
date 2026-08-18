import React, { useState, useEffect } from 'react';
import { authAPI } from './api/auth.api';
import './auth.css';

export function ResetPassword({ token: initialToken, onComplete }) {
  const [token, setToken] = useState(initialToken || '');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!initialToken) {
      const params = new URLSearchParams(window.location.search);
      const resetToken = params.get('resetToken');
      if (resetToken) {
        setToken(resetToken);
      }
    }
  }, [initialToken]);

  const validatePassword = (value) => value.length >= 6;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');

    if (!token) {
      setError('Токен сброса пароля отсутствует.');
      return;
    }

    if (!password || !confirmPassword) {
      setError('Пожалуйста, заполните оба поля.');
      return;
    }

    if (!validatePassword(password)) {
      setError('Пароль должен быть не менее 6 символов.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Пароли не совпадают.');
      return;
    }

    setLoading(true);

    try {
      const response = await authAPI.resetPassword({
        token,
        password,
        confirmPassword
      });
      setMessage(response.data?.message || 'Пароль успешно изменен. Теперь вы можете войти.');
      setTimeout(() => {
        onComplete();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Не удалось изменить пароль. Попробуйте снова.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">Сброс пароля</h1>
          <p className="auth-subtitle">Введите новый пароль для своей учетной записи.</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group-auth">
            <label className="form-label-auth">Новый пароль</label>
            <input
              type="password"
              name="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="form-control-auth"
              placeholder="••••••••"
              disabled={loading}
            />
          </div>

          <div className="form-group-auth">
            <label className="form-label-auth">Подтвердите пароль</label>
            <input
              type="password"
              name="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="form-control-auth"
              placeholder="••••••••"
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
            {loading ? 'Сохранение...' : 'Сменить пароль'}
          </button>

          <button
            type="button"
            className="btn auth-link-btn"
            onClick={onComplete}
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
            Назад
          </button>
        </form>
      </div>
    </div>
  );
}
