import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { CreditCard, LogOut, LayoutDashboard, History } from 'lucide-react';
import BuyCreditsModal from './BuyCreditsModal';
import { useState } from 'react';
import './Layout.css';

const Layout = () => {
    const { user, logout, refreshUser } = useAuth();
    const navigate = useNavigate();
    const [showBuyCredits, setShowBuyCredits] = useState(false);

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const handleBuyCreditsSuccess = () => {
        setShowBuyCredits(false);
        refreshUser();
    };

    return (
        <div className="layout">
            <aside className="sidebar">
                <div className="sidebar-header">
                    <h2>📈 Stock Predictor</h2>
                </div>

                <div className="credits-display">
                    <div className="credits-label">💎 Credits</div>
                    <div className="credits-value">{user?.credits || 0}</div>
                    <button
                        className="buy-credits-sidebar-btn"
                        onClick={() => setShowBuyCredits(true)}
                    >
                        <CreditCard size={16} />
                        Buy Credits
                    </button>
                </div>

                <nav className="sidebar-nav">
                    <Link to="/dashboard" className="nav-item">
                        <LayoutDashboard size={20} />
                        Dashboard
                    </Link>
                    <Link to="/history" className="nav-item">
                        <History size={20} />
                        History
                    </Link>
                </nav>

                <div className="sidebar-footer">
                    <div className="sidebar-warning">
                        ⚠️ This dashboard is for educational and research purposes only.
                        It is not financial advice. Use at your own risk.
                    </div>

                    <button className="logout-btn" onClick={handleLogout}>
                        <LogOut size={20} />
                        Logout
                    </button>
                </div>
            </aside>

            <main className="main-content">
                <Outlet />
            </main>

            {showBuyCredits && (
                <BuyCreditsModal
                    onClose={() => setShowBuyCredits(false)}
                    onSuccess={handleBuyCreditsSuccess}
                />
            )}
        </div>
    );
};

export default Layout;
