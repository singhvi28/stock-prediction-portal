import { useState, useEffect } from 'react';
import { fetchHistory } from '../services/api';
import PredictionChart from '../components/PredictionChart';
import './HistoryPage.css';

const isValidTicker = (ticker) => {
    if (!ticker) return true;
    return /^[A-Z0-9.-]+$/.test(ticker);
};

const HistoryPage = () => {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [tickerFilter, setTickerFilter] = useState('');
    const [modelFilter, setModelFilter] = useState('All');
    const [expandedId, setExpandedId] = useState(null);
    const [visualizedId, setVisualizedId] = useState(null); // Track which item has visualization shown

    useEffect(() => {
        loadHistory();
    }, [tickerFilter, modelFilter]);

    const loadHistory = async () => {
        setLoading(true);
        try {
            const filters = { limit: 50 };
            if (tickerFilter) filters.ticker = tickerFilter;
            if (modelFilter !== 'All') filters.model = modelFilter;

            const data = await fetchHistory(filters);
            setHistory(data || []);
        } catch (error) {
            console.error('Failed to fetch history:', error);
            setHistory([]);
        } finally {
            setLoading(false);
        }
    };

    const handleTickerFilterChange = (value) => {
        const upperValue = value.toUpperCase().trim();
        if (upperValue && !isValidTicker(upperValue)) {
            return; // Don't update if invalid
        }
        setTickerFilter(upperValue);
    };

    const toggleExpand = (id) => {
        setExpandedId(expandedId === id ? null : id);
        // Clear visualization when collapsing
        if (expandedId === id) {
            setVisualizedId(null);
        }
    };

    const toggleVisualization = (id) => {
        if (visualizedId === id) {
            setVisualizedId(null); // Clear if already showing
        } else {
            setVisualizedId(id); // Show for this item
        }
    };

    return (
        <div className="history-page">
            <div className="history-container">
                <h1>📜 Prediction History</h1>

                <div className="filters">
                    <div className="filter-group">
                        <label>Filter by Ticker</label>
                        <input
                            type="text"
                            value={tickerFilter}
                            onChange={(e) => handleTickerFilterChange(e.target.value)}
                            placeholder="e.g. AAPL"
                        />
                    </div>

                    <div className="filter-group">
                        <label>Filter by Model</label>
                        <select
                            value={modelFilter}
                            onChange={(e) => setModelFilter(e.target.value)}
                        >
                            <option value="All">All</option>
                            <option value="multihead">Multihead</option>
                            <option value="additive">Additive</option>
                        </select>
                    </div>
                </div>

                {loading && (
                    <div className="loading-section">
                        <div className="spinner"></div>
                        <p>Loading history...</p>
                    </div>
                )}

                {!loading && history.length === 0 && (
                    <div className="empty-state">
                        <p>No prediction history found for this period.</p>
                    </div>
                )}

                {!loading && history.length > 0 && (
                    <div className="history-list">
                        {history.map((item) => {
                            const isExpanded = expandedId === item.id;
                            const isVisualized = visualizedId === item.id;
                            const data = item.prediction_data;
                            const timestamp = new Date(item.created_at).toLocaleString();

                            return (
                                <div key={item.id} className="history-item">
                                    <div
                                        className="history-item-header"
                                        onClick={() => toggleExpand(item.id)}
                                    >
                                        <div className="history-item-title">
                                            <strong>{item.ticker}</strong> - {timestamp} ({item.model_type})
                                        </div>
                                        <div className="expand-icon">{isExpanded ? '▼' : '▶'}</div>
                                    </div>

                                    {isExpanded && (
                                        <div className="history-item-content">
                                            {!data && (
                                                <div className="status-message warning">
                                                    ⏳ Prediction in progress...
                                                </div>
                                            )}

                                            {data?.refunded && (
                                                <div className="status-message error">
                                                    ❌ Failed & Refunded
                                                    {data.error && <p>Reason: {data.error}</p>}
                                                </div>
                                            )}

                                            {data && !data.refunded && data.metrics && (
                                                <>
                                                    <div className="metrics-quick">
                                                        <div className="metric">
                                                            <span className="label">RMSE:</span>
                                                            <span className="value">${data.metrics.rmse?.toFixed(2)}</span>
                                                        </div>
                                                        <div className="metric">
                                                            <span className="label">MAE:</span>
                                                            <span className="value">${data.metrics.mae?.toFixed(2)}</span>
                                                        </div>
                                                        <div className="metric">
                                                            <span className="label">MAPE:</span>
                                                            <span className="value">{data.metrics.mape?.toFixed(2)}%</span>
                                                        </div>
                                                        <div className="metric">
                                                            <span className="label">Directional Accuracy:</span>
                                                            <span className="value">{data.metrics.directional_accuracy?.toFixed(2)}%</span>
                                                        </div>
                                                    </div>

                                                    <button
                                                        className={isVisualized ? "clear-viz-btn" : "load-viz-btn"}
                                                        onClick={() => toggleVisualization(item.id)}
                                                    >
                                                        {isVisualized ? 'Clear Visualization' : 'Load Visualization'}
                                                    </button>

                                                    {isVisualized && (
                                                        <div className="inline-visualization">
                                                            <PredictionChart
                                                                result={{
                                                                    ...data,
                                                                    ticker: item.ticker
                                                                }}
                                                                showMetrics={false}
                                                            />
                                                        </div>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default HistoryPage;
