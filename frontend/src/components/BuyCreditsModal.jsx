import { useState } from 'react';
import { createOrder } from '../services/api';
import RazorpayCheckout from './RazorpayCheckout';
import './BuyCreditsModal.css';

const BuyCreditsModal = ({ onClose, onSuccess }) => {
    const [selectedPackage, setSelectedPackage] = useState(null);
    const [order, setOrder] = useState(null);
    const [loading, setLoading] = useState(false);

    const packages = [
        { id: 'starter', name: 'Starter', credits: 10, price: 100 },
        { id: 'pro', name: 'Pro', credits: 50, price: 500 },
        { id: 'whale', name: 'Whale', credits: 100, price: 1000 },
    ];

    const handleBuyPackage = async (pkg) => {
        setLoading(true);
        try {
            const orderData = await createOrder(pkg.credits);
            setOrder(orderData);
            setSelectedPackage(pkg);
        } catch (error) {
            alert('Order creation failed: ' + (error.response?.data?.detail || error.message));
            setLoading(false);
        }
    };

    const handlePaymentSuccess = () => {
        setOrder(null);
        setLoading(false);
        if (onSuccess) onSuccess();
    };

    const handlePaymentFailure = () => {
        setOrder(null);
        setLoading(false);
    };

    return (
        <>
            <div className="modal-overlay" onClick={onClose}></div>
            <div className="modal-content">
                <div className="modal-header">
                    <h2>💎 Purchase Credits</h2>
                    <button className="modal-close" onClick={onClose}>×</button>
                </div>

                <p className="modal-info">Rate: 1 Credit = ₹10. Secure payment via Razorpay.</p>

                <div className="packages-grid">
                    {packages.map((pkg) => (
                        <div key={pkg.id} className="package-card">
                            <h3>{pkg.name}</h3>
                            <div className="package-price">₹{pkg.price}</div>
                            <div className="package-credits">{pkg.credits} Credits</div>
                            <button
                                className="package-btn"
                                onClick={() => handleBuyPackage(pkg)}
                                disabled={loading}
                            >
                                {loading ? 'Creating Order...' : `Buy ${pkg.name}`}
                            </button>
                        </div>
                    ))}
                </div>

                {order && (
                    <RazorpayCheckout
                        order={order}
                        onSuccess={handlePaymentSuccess}
                        onFailure={handlePaymentFailure}
                    />
                )}
            </div>
        </>
    );
};

export default BuyCreditsModal;
