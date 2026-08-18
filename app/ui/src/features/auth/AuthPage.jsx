import React, { useState } from 'react';

import { httpClient } from '../../api/httpClient';
import { authAPI } from './api/auth.api';
import './auth.css';

export function AuthPage({ onAuthSuccess, onShowForgot }) {
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Расширили стейт полями confirmPassword и nickname (ловушка)
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    nickname: '' // Honeypot-поле
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setError('');
  };

  const validateEmail = (email) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      // Базовая проверка на заполнение обязательных полей
      if (!formData.name || !formData.email || !formData.password || !formData.confirmPassword) {
        throw new Error('Пожалуйста, заполните все поля');
      }

      if (!validateEmail(formData.email)) {
        throw new Error('Пожалуйста, введите корректный email');
      }

      if (formData.password.length < 6) {
        throw new Error('Пароль должен быть не менее 6 символов');
      }

      // Валидация совпадения паролей перед отправкой на сервер
      if (formData.password !== formData.confirmPassword) {
        throw new Error('Пароли не совпадают');
      }

      const response = await authAPI.register({
            name: formData.name,
            email: formData.email,
            password: formData.password,
            confirmPassword: formData.confirmPassword,
            nickname: formData.nickname
          });

      setSuccess(response.data?.message || 'Регистрация успешна! Проверьте почту для подтверждения.');
      setFormData({ name: '', email: '', password: '', confirmPassword: '', nickname: '' });
      setTimeout(() => {
        setIsLogin(true);
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при регистрации');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      if (!formData.email || !formData.password) {
        throw new Error('Пожалуйста, заполните все поля');
      }

      if (!validateEmail(formData.email)) {
        throw new Error('Пожалуйста, введите корректный email');
      }

      const response = await authAPI.login({
        email: formData.email,
        password: formData.password
      });

      const { accessToken, refreshToken, user } = response.data;
      
      localStorage.setItem('accessToken', accessToken);
      localStorage.setItem('refreshToken', refreshToken);
      localStorage.setItem('user', JSON.stringify(user));

      httpClient.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;

      setSuccess('Вы успешно вошли!');
      setFormData({ name: '', email: '', password: '', confirmPassword: '', nickname: '' });
      
      setTimeout(() => {
        onAuthSuccess(user);
      }, 500);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Ошибка при входе');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">
            {isLogin ? '🔐 Вход' : '📝 Регистрация'}
          </h1>
          <p className="auth-subtitle">
            {isLogin 
              ? 'Введите ваши учетные данные' 
              : 'Создайте новый аккаунт'}
          </p>
        </div>

        <form onSubmit={isLogin ? handleLogin : handleRegister} className="auth-form">
          
          {/* --- НЕВИДИМАЯ ЛОВУШКА ДЛЯ БОТОВ (HONEYPOT) --- */}
          {/* Реальный человек его не видит и не может сфокусироваться, а бот обязательно заполнит */}
          <div style={{ display: 'none' }} aria-hidden="true">
            <input
              type="text"
              name="nickname"
              tabIndex="-1"
              autoComplete="off"
              value={formData.nickname}
              onChange={handleInputChange}
            />
          </div>
          {/* ----------------------------------------------- */}

          {!isLogin && (
            <div className="form-group-auth">
              <label className="form-label-auth">Имя</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                className="form-control-auth"
                placeholder="Ваше имя"
                disabled={loading}
              />
            </div>
          )}

          <div className="form-group-auth">
            <label className="form-label-auth">Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleInputChange}
              className="form-control-auth"
              placeholder="example@mail.com"
              disabled={loading}
            />
          </div>

          <div className="form-group-auth">
            <label className="form-label-auth">Пароль</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleInputChange}
              className="form-control-auth"
              placeholder="••••••••"
              disabled={loading}
            />
          </div>

          {/* Дополнительное поле подтверждения пароля при регистрации */}
          {!isLogin && (
            <div className="form-group-auth">
              <label className="form-label-auth">Подтвердите пароль</label>
              <input
                type="password"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleInputChange}
                className="form-control-auth"
                placeholder="••••••••"
                disabled={loading}
              />
            </div>
          )}

          {error && <div className="auth-error">{error}</div>}
          {success && <div className="auth-success">{success}</div>}

          <button
            type="submit"
            className="btn btn-primary auth-submit-btn"
            disabled={loading}
          >
            {loading 
              ? (isLogin ? 'Вход...' : 'Регистрация...') 
              : (isLogin ? 'Войти' : 'Зарегистрироваться')}
          </button>

          {isLogin && (
            <button
              type="button"
              className="btn auth-link-btn"
              onClick={onShowForgot}
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
              Забыли пароль?
            </button>
          )}
        </form>

        <div className="auth-footer">
          <p className="auth-toggle-text">
            {isLogin ? 'Нет аккаунта? ' : 'Уже есть аккаунт? '}
            <button
              type="button"
              onClick={() => {
                setIsLogin(!isLogin);
                setError('');
                setSuccess('');
                setFormData({ name: '', email: '', password: '', confirmPassword: '', nickname: '' });
              }}
              className="auth-toggle-btn"
              disabled={loading}
            >
              {isLogin ? 'Зарегистрируйтесь' : 'Войдите'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}