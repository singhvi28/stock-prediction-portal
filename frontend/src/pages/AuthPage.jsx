import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { forgotPassword, resetPassword } from '../services/api';
import './AuthPage.css';

const AuthPage = () => {
    const [activeTab, setActiveTab] = useState('login');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState({ text: '', type: '' });

    const navigate = useNavigate();
    const { login, register } = useAuth();

    // Login state
    const [loginEmail, setLoginEmail] = useState('');
    const [loginPassword, setLoginPassword] = useState('');

    // Register state
    const [registerEmail, setRegisterEmail] = useState('');
    const [registerPassword, setRegisterPassword] = useState('');

    // Forgot password state
    const [forgotEmail, setForgotEmail] = useState('');

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage({ text: '', type: '' });

        try {
            await login(loginEmail, loginPassword);
            setMessage({ text: 'Logged in successfully!', type: 'success' });
            navigate('/dashboard');
        } catch (error) {
            setMessage({ text: error.response?.data?.detail || 'Invalid credentials', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage({ text: '', type: '' });

        if (!registerEmail || !registerPassword) {
            setMessage({ text: 'Please fill all fields', type: 'error' });
            setLoading(false);
            return;
        }

        try {
            await register(registerEmail, registerPassword);
            setMessage({ text: 'Registration successful! Please login.', type: 'success' });
            setActiveTab('login');
        } catch (error) {
            setMessage({ text: error.response?.data?.detail || 'Registration failed', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    const handleForgotPassword = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage({ text: '', type: '' });

        if (!forgotEmail) {
            setMessage({ text: 'Please enter your email', type: 'error' });
            setLoading(false);
            return;
        }

        try {
            const response = await forgotPassword(forgotEmail);
            setMessage({ text: response.message || 'Password reset link sent!', type: 'success' });
        } catch (error) {
            setMessage({ text: error.response?.data?.detail || 'Request failed', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-page">
            <div className="auth-container">
                <h1 className="auth-title">🔐 Access Portal</h1>

                <div className="tabs">
                    <button
                        className={`tab ${activeTab === 'login' ? 'active' : ''}`}
                        onClick={() => setActiveTab('login')}
                    >
                        Login
                    </button>
                    <button
                        className={`tab ${activeTab === 'register' ? 'active' : ''}`}
                        onClick={() => setActiveTab('register')}
                    >
                        Register
                    </button>
                    <button
                        className={`tab ${activeTab === 'forgot' ? 'active' : ''}`}
                        onClick={() => setActiveTab('forgot')}
                    >
                        Forgot Password
                    </button>
                </div>

                {message.text && (
                    <div className={`message ${message.type}`}>
                        {message.text}
                    </div>
                )}

                {activeTab === 'login' && (
                    <form onSubmit={handleLogin} className="auth-form">
                        <input
                            type="email"
                            placeholder="Email"
                            value={loginEmail}
                            onChange={(e) => setLoginEmail(e.target.value)}
                            required
                        />
                        <input
                            type="password"
                            placeholder="Password"
                            value={loginPassword}
                            onChange={(e) => setLoginPassword(e.target.value)}
                            required
                        />
                        <button type="submit" disabled={loading}>
                            {loading ? 'Loading...' : 'Login'}
                        </button>
                    </form>
                )}

                {activeTab === 'register' && (
                    <form onSubmit={handleRegister} className="auth-form">
                        <input
                            type="email"
                            placeholder="Email"
                            value={registerEmail}
                            onChange={(e) => setRegisterEmail(e.target.value)}
                            required
                        />
                        <input
                            type="password"
                            placeholder="Password"
                            value={registerPassword}
                            onChange={(e) => setRegisterPassword(e.target.value)}
                            required
                        />
                        <button type="submit" disabled={loading}>
                            {loading ? 'Loading...' : 'Register'}
                        </button>
                    </form>
                )}

                {activeTab === 'forgot' && (
                    <form onSubmit={handleForgotPassword} className="auth-form">
                        <p className="form-description">Enter your email to receive a password reset token.</p>
                        <input
                            type="email"
                            placeholder="Email"
                            value={forgotEmail}
                            onChange={(e) => setForgotEmail(e.target.value)}
                            required
                        />
                        <button type="submit" disabled={loading}>
                            {loading ? 'Loading...' : 'Send Reset Link'}
                        </button>
                    </form>
                )}
            </div>
        </div>
    );
};

export default AuthPage;
