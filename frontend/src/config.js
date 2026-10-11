// Centralized API Base URL Configuration for AEGIS-COP Frontend
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

// Base host URL without trailing /api for endpoints mounted directly at root
export const BACKEND_HOST = API_BASE_URL.replace(/\/api\/?$/, '');
