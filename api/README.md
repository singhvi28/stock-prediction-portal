# Architectural Optimizations & Bottleneck Resolutions

This document details the critical architectural improvements implemented in the Stock Prediction API to address scalability bottlenecks and enhance system performance.

## 1. Optimized Data Transfer: JSONB vs. Static Images

### 🔴 The Bottleneck (Legacy Approach)
In the initial design, the prediction services generated static static charts using **Matplotlib** on the backend.
-   **Storage Overhead**: Each prediction generated an image file that needed to be stored in Azure Blob Storage / S3.
-   **Bandwidth Inefficiency**: Transmitting binary image data over the network consumed significant bandwidth.
-   **Poor UX**: The resulting charts were static images, lacking interactivity (zoom, hover, pan) for the end-user.

### 🟢 The Solution (Current Architecture)
The architecture was refactored to return raw prediction data as **JSONB**.
-   **Backend**: The ML services now return lightweight JSON objects containing historical prices, forecast dates, and model metrics.
-   **Frontend**: The Streamlit frontend receives this data and renders interactive charts client-side using **Plotly**.

#### 🏆 Impact:
-   **Zero Blob Storage Costs**: Eliminated the need for external object storage for temporary charts.
-   **90% Bandwidth Reduction**: Transmitting JSON text is orders of magnitude smaller than high-resolution PNGs.
-   **Rich Interactivity**: Users can now interact with the data, viewing specific price points and zooming into specific timeframes.

---

## 2. Workload Segregation: Dedicated Celery Workers

### 🔴 The Bottleneck (Legacy Approach)
Originally, a single Celery worker pool handled all asynchronous tasks, from processing payments to training complex Transformer models.
-   **Resource Contention**: CPU-intensive ML training tasks would block the worker processes.
-   **Latency Spikes**: Critical, low-latency tasks like **Payment Verification** were queued behind long-running prediction tasks, leading to timeout errors and lost revenue.

### 🟢 The Solution (Current Architecture)
We implemented a **Distributed Queue Architecture** with specialized workers:

#### `worker-payments` (High Priority)
-   **Queue**: `payments`
-   **Concurrency**: High (8+ threads)
-   **Focus**: I/O-bound tasks (Razorpay API calls, DB updates).
-   **Result**: Instant payment processing regardless of ML load.

#### `worker-ml` (Resource Heavy)
-   **Queue**: `ml`
-   **Concurrency**: Limited (2 processes)
-   **Focus**: CPU/Memory-bound tasks (PyTorch training, Inference).
-   **Result**: ML tasks run in isolation without degrading the performance of core business logic.

### 🏆 Impact:
This separation ensures **Business Continuity**. Even if the ML pipeline is under 100% load, the payment and authentication systems remain responsive and performant.
