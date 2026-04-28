import axios from 'axios';

const backendUri = import.meta.env.VITE_BACKEND_URI || 'http://localhost:8000';

export const httpClient = axios.create({
  baseURL: `${backendUri}/api`,
  headers: { 'Content-Type': 'application/json' },
});