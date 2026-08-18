import axios from 'axios';

const backendUri = import.meta.env.VITE_BACKEND_URI || 'http://localhost:8000';

export const httpClient = axios.create({
  baseURL: `${backendUri}/api`,
  headers: { 'Content-Type': 'application/json' },
});

// Public client for unauthenticated requests
export const publicClient = axios.create({
  baseURL: `${backendUri}/api`,
  headers: { 'Content-Type': 'application/json' },
});

// Add token from localStorage to authenticated requests
httpClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Auto-refresh token on 401
httpClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Игнорируем 401 для авторизации (login, register, refresh, etc.)
    const isAuthRoute = originalRequest.url?.includes('/auth/');

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthRoute) {
      originalRequest._retry = true;
      
      try {
        const refreshToken = localStorage.getItem('refreshToken');
        if (!refreshToken) {
          throw new Error('No refresh token');
        }
        
        // Добавлен /v1/ и правильное имя поля refresh_token для FastAPI
        const { data } = await publicClient.post('/v1/auth/refresh', { 
          refresh_token: refreshToken 
        });
        
        const newAccessToken = data.accessToken || data.access_token;
        const newRefreshToken = data.refreshToken || data.refresh_token;

        localStorage.setItem('accessToken', newAccessToken);
        localStorage.setItem('refreshToken', newRefreshToken);
        
        originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
        return httpClient(originalRequest);
      } catch (err) {
        // Очищаем сессию только если рефреш реально не удался
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('user');
        window.location.href = '/';
        return Promise.reject(err);
      }
    }
    
    return Promise.reject(error);
  }
);