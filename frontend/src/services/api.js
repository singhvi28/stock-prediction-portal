import axios from 'axios';
import { API_BASE_URL } from '../config';

// Create axios instance
const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor to add auth token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

// Auth APIs
export const login = async (email, password) => {
    const response = await api.post('/api/auth/login', { email, password });
    return response.data;
};

export const register = async (email, password) => {
    const response = await api.post('/api/auth/register', { email, password });
    return response.data;
};

export const forgotPassword = async (email) => {
    const response = await api.post('/api/auth/forgot-password', { email });
    return response.data;
};

export const resetPassword = async (token, newPassword) => {
    const response = await api.post('/api/auth/reset-password', {
        token,
        new_password: newPassword,
    });
    return response.data;
};

export const getUserInfo = async () => {
    const response = await api.get('/api/auth/me');
    return response.data;
};

// Prediction APIs
export const createPrediction = async (ticker, lookback, model) => {
    const response = await api.post('/api/predict', {
        ticker,
        lookback,
        model,
    });
    return response.data;
};

export const getPredictionStatus = async (taskId) => {
    const response = await api.get(`/api/predict/${taskId}`);
    return response.data;
};

// History API
export const fetchHistory = async (filters = {}) => {
    const response = await api.get('/api/history', { params: filters });
    return response.data;
};

// Payment APIs
export const createOrder = async (credits) => {
    const response = await api.post('/payment/order', { credits });
    return response.data;
};

export const verifyPayment = async (paymentData) => {
    const response = await api.post('/payment/verify', paymentData);
    return response.data;
};

export default api;
