import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { createPrediction } from '../services/api';
import { usePolling } from './usePolling';

export const usePredictionManager = () => {
    const { refreshUser } = useAuth();
    const [state, setState] = useState({
        ticker: 'AAPL',
        modelType: 'multihead',
        taskId: null,
        result: null,
        loading: false,
        error: '',
        showBuyCredits: false
    });

    const { status, result: pollResult, error: pollError } = usePolling(state.taskId);

    // Sync polling results to local state
    useEffect(() => {
        if (status === 'completed' && pollResult) {
            setState(prev => ({ ...prev, result: pollResult, loading: false, taskId: null }));
            refreshUser();
        } else if (status === 'failed' || status === 'timeout') {
            setState(prev => ({ ...prev, error: pollError || 'Prediction failed', loading: false, taskId: null }));
        }
    }, [status, pollResult, pollError, refreshUser]);

    const runPrediction = async () => {
        const tickerRegex = /^[A-Z0-9.-]+$/;
        if (!tickerRegex.test(state.ticker)) {
            setState(prev => ({ ...prev, error: '⚠️ Invalid ticker format.' }));
            return;
        }

        setState(prev => ({ ...prev, error: '', loading: true, result: null }));

        try {
            const response = await createPrediction(state.ticker, 60, state.modelType);
            if (response.task_id) {
                setState(prev => ({ ...prev, taskId: response.task_id }));
            }
        } catch (err) {
            const isInsufficientCredits = err.response?.status === 402;
            setState(prev => ({
                ...prev,
                loading: false,
                showBuyCredits: isInsufficientCredits,
                error: isInsufficientCredits
                    ? `⚠️ Insufficient Credits! Requires ${state.modelType === 'additive' ? 3 : 2} credits.`
                    : (err.response?.data?.detail || 'Failed to initiate prediction')
            }));
        }
    };

    const updateField = (field, value) => setState(prev => ({ ...prev, [field]: value }));

    return { ...state, runPrediction, updateField };
};
