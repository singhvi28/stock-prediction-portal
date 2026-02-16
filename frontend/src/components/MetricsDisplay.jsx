import './MetricsDisplay.css';

const MetricsDisplay = ({ metrics }) => {
    if (!metrics) return null;

    return (
        <div className="metrics-grid">
            <div className="metric-card">
                <div className="metric-label">RMSE</div>
                <div className="metric-value">${metrics.rmse?.toFixed(2) || 'N/A'}</div>
            </div>
            <div className="metric-card">
                <div className="metric-label">MAE</div>
                <div className="metric-value">${metrics.mae?.toFixed(2) || 'N/A'}</div>
            </div>
            <div className="metric-card">
                <div className="metric-label">MAPE</div>
                <div className="metric-value">{metrics.mape?.toFixed(2) || 'N/A'}%</div>
            </div>
            <div className="metric-card">
                <div className="metric-label">Directional Accuracy</div>
                <div className="metric-value">{metrics.directional_accuracy?.toFixed(2) || 'N/A'}%</div>
            </div>
        </div>
    );
};

export default MetricsDisplay;
