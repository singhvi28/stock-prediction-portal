import { useState, useEffect, useRef } from 'react';
import { getPredictionStatus } from '../services/api';

export const usePolling = (taskId, interval = 15000, maxAttempts = 40) => {
    const [status, setStatus] = useState('pending');
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [attempts, setAttempts] = useState(0);
    const intervalRef = useRef(null);

    useEffect(() => {
        if (!taskId) return;

        const poll = async () => {
            try {
                const data = await getPredictionStatus(taskId);

                if (data.status === 'completed') {
                    setStatus('completed');
                    setResult(data.result);
                    if (intervalRef.current) {
                        clearInterval(intervalRef.current);
                    }
                } else if (data.status === 'failed') {
                    setStatus('failed');
                    setError(data.error || 'Prediction failed');
                    if (intervalRef.current) {
                        clearInterval(intervalRef.current);
                    }
                } else {
                    setAttempts((prev) => prev + 1);
                }
            } catch (err) {
                console.error('Polling error:', err);
                setAttempts((prev) => prev + 1);
            }
        };

        // Start polling
        intervalRef.current = setInterval(poll, interval);

        // Cleanup on unmount
        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [taskId, interval]);

    // Check max attempts
    useEffect(() => {
        if (attempts >= maxAttempts) {
            setStatus('timeout');
            setError('Prediction timed out');
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        }
    }, [attempts, maxAttempts]);

    return { status, result, error, attempts };
};
