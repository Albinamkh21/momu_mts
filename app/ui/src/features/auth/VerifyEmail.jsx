import React, { useEffect, useState, useRef } from 'react';
import { publicClient } from '../../api/httpClient'; 
import { authAPI } from './api/auth.api';


export function VerifyEmail({ token, onComplete }) {
  
  const [message, setMessage] = useState('Проверяем ваш email...');
  const [status, setStatus] = useState('loading'); 
  const requestSent = useRef(false);

  useEffect(() => {
      // 1. Проверяем наличие токена перед отправкой
      if (!token) {
        setStatus('error');
        setMessage('Токен подтверждения не найден.');
        return;
      }

    
      if (requestSent.current) return; 
      requestSent.current = true;
      // --------------------------------------------

      authAPI.verifyEmail(token)
        .then((res) => {
          setStatus('success');
          setMessage(res.data?.message || 'Email успешно подтвержден. Теперь вы можете войти.');
        })
        .catch((err) => {
          setStatus('error');
          
          // 2. Безопасно извлекаем текст ошибки (защита от массива валидации FastAPI)
          const detail = err.response?.data?.detail;
          const errorMessage = typeof detail === 'string' 
            ? detail 
            : (Array.isArray(detail) ? detail[0]?.msg : 'Недействительный или истекший токен.');

          setMessage(errorMessage);
        });
    }, [token]);

  return (
    <div className="auth-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <div className="auth-card" style={{ textAlign: 'center', padding: '30px', border: '1px solid #eee', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', maxWidth: '400px', width: '100%' }}>
        <h2>Статус подтверждения</h2>
        <p style={{ margin: '20px 0', color: status === 'error' ? '#e74c3c' : (status === 'success' ? '#2ecc71' : '#333') }}>
          {message}
        </p>
        
        {status === 'success' && (
          <button onClick={onComplete} style={{ marginTop: '15px', padding: '10px 20px', cursor: 'pointer', backgroundColor: '#2ecc71', color: '#fff', border: 'none', borderRadius: '4px' }}>
            Войти в систему
          </button>
        )}
        
        {status === 'error' && (
          <button onClick={() => window.location.href = '/'} style={{ marginTop: '15px', padding: '10px 20px', cursor: 'pointer', backgroundColor: '#e74c3c', color: '#fff', border: 'none', borderRadius: '4px' }}>
            На главную
          </button>
        )}
      </div>
    </div>
  );
}