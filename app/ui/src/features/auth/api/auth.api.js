import { httpClient } from '../../../api/httpClient';

export const authAPI = {
  register: (data) => httpClient.post('/v1/auth/register', data),
  login: (data) => httpClient.post('/v1/auth/login', data),
  verifyEmail: (token) => httpClient.post('/v1/auth/verify-email', { token }),
  forgotPassword: (email) => httpClient.post('/v1/auth/forgot-password', { email }),
  resetPassword: (data) => httpClient.post('/v1/auth/reset-password', data),
  refreshToken: (refreshToken) => httpClient.post('/v1/auth/refresh', { refresh_token: refreshToken }), // <-- Обрати внимание, здесь FastAPI ждет snake_case: refresh_token
  logout: () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    delete httpClient.defaults.headers.common['Authorization'];
  }
};