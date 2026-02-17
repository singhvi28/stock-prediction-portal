import { usePredictionManager } from '../hooks/usePredictionManager';
import PredictionChart from '../components/PredictionChart';
import BuyCreditsModal from '../components/BuyCreditsModal';
import './DashboardPage.css';

const DashboardPage = () => {
    const { 
        ticker, modelType, showBuyCredits, result, loading, error, 
        runPrediction, updateField 
    } = usePredictionManager();

    return (
        <div className="dashboard-page">
            <header className="dashboard-header">
                <h1>Analysis for {ticker || 'Stock'}</h1>
            </header>

            <section className="controls-section">
                <ControlGroup label="Stock Ticker">
                    <input
                        type="text"
                        value={ticker}
                        onChange={(e) => updateField('ticker', e.target.value.toUpperCase())}
                        placeholder="e.g., AAPL"
                        disabled={loading}
                    />
                </ControlGroup>

                <ControlGroup label="Prediction Model">
                    <select
                        value={modelType}
                        onChange={(e) => updateField('modelType', e.target.value)}
                        disabled={loading}
                    >
                        <option value="multihead">Multihead Attention</option>
                        <option value="additive">Additive Attention</option>
                    </select>
                </ControlGroup>

                <button 
                    className="run-prediction-btn" 
                    onClick={runPrediction} 
                    disabled={loading || !ticker}
                >
                    {loading ? 'Processing...' : 'Run Prediction & Forecast'}
                </button>
            </section>

            {error && <div className="error-message" role="alert">{error}</div>}

            {loading && <LoadingState />}

            {result && !loading && (
                <PredictionChart result={result} showMetrics={true} />
            )}

            {showBuyCredits && (
                <BuyCreditsModal
                    onClose={() => updateField('showBuyCredits', false)}
                    onSuccess={() => {
                        updateField('showBuyCredits', false);
                        // refreshUser is handled inside the hook or context
                    }}
                />
            )}
        </div>
    );
};

// Sub-components can be moved to their own files
const ControlGroup = ({ label, children }) => (
    <div className="control-group">
        <label>{label}</label>
        {children}
    </div>
);

const LoadingState = () => (
    <div className="loading-section">
        <div className="spinner"></div>
        <p>Model is training... This may take a few minutes.</p>
    </div>
);

export default DashboardPage;