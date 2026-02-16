import { useState, useEffect } from 'react';
import './Notification.css';

let notificationId = 0;

const Notification = ({ message, type = 'info', duration = 5000, onClose }) => {
    const [visible, setVisible] = useState(true);

    useEffect(() => {
        const timer = setTimeout(() => {
            setVisible(false);
            if (onClose) onClose();
        }, duration);

        return () => clearTimeout(timer);
    }, [duration, onClose]);

    if (!visible) return null;

    return (
        <div className={`notification notification-${type}`}>
            <span>{message}</span>
            <button
                className="notification-close"
                onClick={() => {
                    setVisible(false);
                    if (onClose) onClose();
                }}
            >
                ×
            </button>
        </div>
    );
};

// Notification manager hook
export const useNotification = () => {
    const [notifications, setNotifications] = useState([]);

    const addNotification = (message, type = 'info') => {
        const id = notificationId++;
        setNotifications(prev => [...prev, { id, message, type }]);
    };

    const removeNotification = (id) => {
        setNotifications(prev => prev.filter(n => n.id !== id));
    };

    const NotificationContainer = () => (
        <div className="notification-container">
            {notifications.map(notification => (
                <Notification
                    key={notification.id}
                    message={notification.message}
                    type={notification.type}
                    onClose={() => removeNotification(notification.id)}
                />
            ))}
        </div>
    );

    return { addNotification, NotificationContainer };
};

export default Notification;
