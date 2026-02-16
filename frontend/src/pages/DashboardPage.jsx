import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { createPrediction } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import PredictionChart from '../components/PredictionChart';
import BuyCreditsModal from '../components/BuyCreditsModal';
import './DashboardPage.css';

const isValidTicker = (ticker) => {
    if (!ticker) return true;
    return /^[A-Z0-9.-]+$/.test(ticker);
};

const DashboardPage = () => {
    const { user, refreshUser } = useAuth();
    const [ticker, setTicker] = useState('AAPL');
    const [modelType, setModelType] = useState('multihead');
    const [showBuyCredits, setShowBuyCredits] = useState(false);
    const [taskId, setTaskId] = useState(null);
    const [predictionResult, setPredictionResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const { status, result, error: pollError } = usePolling(taskId);

    const handleRunPrediction = async () => {
        if (!isValidTicker(ticker)) {
            setError('⚠️ Invalid ticker format. Only letters, numbers, \'.\', and \'-\' are allowed.');
            return;
        }

        setError('');
        setLoading(true);
        setPredictionResult(null);

        try {
            const response = await createPrediction(ticker, 60, modelType);
            if (response.task_id) {
                setTaskId(response.task_id);
            }
        } catch (err) {
            if (err.response?.status === 402) {
                const cost = modelType === 'additive' ? 3 : 2;
                setError(`⚠️ Insufficient Credits! This model requires ${cost} credits.`);
                setShowBuyCredits(true);
            } else {
                setError(err.response?.data?.detail || 'Failed to initiate prediction');
            }
            setLoading(false);
        }
    };

    // Handle polling results
    if (status === 'completed' && result && result !== predictionResult) {
        setPredictionResult(result);
        setLoading(false);
        setTaskId(null);
        refreshUser();
    } else if (status === 'failed' || status === 'timeout') {
        setError(pollError || 'Prediction failed');
        setLoading(false);
        setTaskId(null);
    }

    const handleBuyCreditsSuccess = () => {
        setShowBuyCredits(false);
        refreshUser();
    };

    return (
        <div className="dashboard-page">
            <div className="dashboard-container">
                <h1>Analysis for {ticker || 'Stock'}</h1>

                <div className="controls-section">
                    <div className="control-group">
                        <label>Stock Ticker</label>
                        <input
                            type="text"
                            value={ticker}
                            onChange={(e) => setTicker(e.target.value.toUpperCase())}
                            placeholder="e.g., AAPL"
                            disabled={loading}
                        />
                    </div>

                    <div className="control-group">
                        <label>Prediction Model</label>
                        <select
                            value={modelType}
                            onChange={(e) => setModelType(e.target.value)}
                            disabled={loading}
                        >
                            <option value="multihead">Multihead Attention</option>
                            <option value="additive">Additive Attention</option>
                        </select>
                    </div>

                    <button
                        className="run-prediction-btn"
                        onClick={handleRunPrediction}
                        disabled={loading || !ticker}
                    >
                        {loading ? 'Processing...' : 'Run Prediction & Forecast'}
                    </button>
                </div>

                {error && <div className="error-message">{error}</div>}

                {loading && (
                    <div className="loading-section">
                        <div className="spinner"></div>
                        <p>Model is training... This may take a few minutes.</p>
                    </div>
                )}

                {predictionResult && !loading && (
                    <PredictionChart result={predictionResult} showMetrics={true} />
                )}
            </div>

            {showBuyCredits && (
                <BuyCreditsModal
                    onClose={() => setShowBuyCredits(false)}
                    onSuccess={handleBuyCreditsSuccess}
                />
            )}
        </div>
    );
};

export default DashboardPage;
