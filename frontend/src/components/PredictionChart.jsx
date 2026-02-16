import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import MetricsDisplay from './MetricsDisplay';
import './PredictionChart.css';

const PredictionChart = ({ result, showMetrics = true }) => {
    if (!result) return null;

    const {
        ticker,
        historical_dates = [],
        historical_prices = [],
        model_historical_predictions = [],
        forecast_dates = [],
        forecast_prices = [],
        metrics,
    } = result;

    // Prepare data for chart
    const historicalData = historical_dates.map((date, index) => ({
        date,
        actual: historical_prices[index],
        predicted: model_historical_predictions[index],
    }));

    // Combine historical and forecast data
    const forecastData = forecast_dates.map((date, index) => ({
        date,
        forecast: forecast_prices[index],
    }));

    // Add connection point between historical and forecast
    if (historicalData.length > 0 && forecastData.length > 0) {
        const lastHistorical = historicalData[historicalData.length - 1];
        forecastData.unshift({
            date: lastHistorical.date,
            forecast: lastHistorical.predicted,
        });
    }

    const allData = [...historicalData, ...forecastData];

    return (
        <div className="prediction-chart-container">
            <h3>Historical Analysis: {ticker}</h3>

            {showMetrics && metrics && <MetricsDisplay metrics={metrics} />}

            <ResponsiveContainer width="100%" height={400}>
                <LineChart data={allData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis
                        dataKey="date"
                        stroke="#9aa0a6"
                        tick={{ fill: '#9aa0a6', fontSize: 12 }}
                    />
                    <YAxis
                        stroke="#9aa0a6"
                        tick={{ fill: '#9aa0a6', fontSize: 12 }}
                        label={{ value: 'Price ($)', angle: -90, position: 'insideLeft', fill: '#9aa0a6' }}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: '#1a1d29',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '4px',
                            color: '#fff'
                        }}
                    />
                    <Legend
                        wrapperStyle={{ color: '#9aa0a6' }}
                    />
                    <Line
                        type="monotone"
                        dataKey="actual"
                        stroke="#818cf8"
                        strokeWidth={2}
                        name="Actual Price"
                        dot={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="predicted"
                        stroke="#34d399"
                        strokeWidth={1.5}
                        strokeDasharray="5 5"
                        name="Model Fitted (Past)"
                        dot={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="forecast"
                        stroke="#fb923c"
                        strokeWidth={2}
                        strokeDasharray="3 3"
                        name="Future Forecast"
                        dot={false}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
};

export default PredictionChart;
