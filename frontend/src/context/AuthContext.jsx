import { createContext, useContext, useState, useEffect } from 'react';
import { login as apiLogin, register as apiRegister, getUserInfo } from '../services/api';

const AuthContext = createContext(null);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem('token'));
    const [loading, setLoading] = useState(true);
    const [isAuthenticated, setIsAuthenticated] = useState(false);

    useEffect(() => {
        const initAuth = async () => {
            if (token) {
                try {
                    const userInfo = await getUserInfo();
                    setUser(userInfo);
                    setIsAuthenticated(true);
                } catch (error) {
                    console.error('Failed to fetch user info:', error);
                    localStorage.removeItem('token');
                    setToken(null);
                    setIsAuthenticated(false);
                }
            }
            setLoading(false);
        };

        initAuth();
    }, [token]);

    const login = async (email, password) => {
        const data = await apiLogin(email, password);
        const newToken = data.access_token;
        localStorage.setItem('token', newToken);
        setToken(newToken);
        const userInfo = await getUserInfo();
        setUser(userInfo);
        setIsAuthenticated(true);
        return data;
    };

    const register = async (email, password) => {
        const data = await apiRegister(email, password);
        return data;
    };

    const logout = () => {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
        setIsAuthenticated(false);
    };

    const refreshUser = async () => {
        if (token) {
            try {
                const userInfo = await getUserInfo();
                setUser(userInfo);
            } catch (error) {
                console.error('Failed to refresh user info:', error);
            }
        }
    };

    const value = {
        user,
        token,
        isAuthenticated,
        loading,
        login,
        register,
        logout,
        refreshUser,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
