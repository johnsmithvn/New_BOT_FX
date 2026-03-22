/**
 * dashboard/static/charts.js
 * 
 * Shared utilities for the Forex Bot Dashboard.
 * API calls, Chart.js defaults, formatting, auto-refresh.
 */

// ── API Client ──────────────────────────────────────────────────

const API = {
    _key: '',

    setKey(key) {
        this._key = key;
    },

    async get(endpoint) {
        const headers = {};
        if (this._key) headers['X-API-Key'] = this._key;

        try {
            const resp = await fetch(`/api${endpoint}`, { headers });
            if (!resp.ok) {
                throw new Error(`API ${resp.status}: ${resp.statusText}`);
            }
            return await resp.json();
        } catch (err) {
            console.error(`API error: ${endpoint}`, err);
            throw err;
        }
    }
};

// ── Formatting ──────────────────────────────────────────────────

function formatPnL(value) {
    const num = parseFloat(value) || 0;
    const sign = num >= 0 ? '+' : '';
    return `${sign}$${num.toFixed(2)}`;
}

function formatPercent(value) {
    return `${parseFloat(value || 0).toFixed(1)}%`;
}

function formatDate(dateStr) {
    if (!dateStr) return '--';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatDateTime(dateStr) {
    if (!dateStr) return '--';
    const d = new Date(dateStr);
    return d.toLocaleString('en-US', {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

function pnlClass(value) {
    return parseFloat(value) >= 0 ? 'positive' : 'negative';
}

function pnlTableClass(value) {
    return parseFloat(value) >= 0 ? 'pnl-positive' : 'pnl-negative';
}

// ── Chart.js Global Defaults ────────────────────────────────────

Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = 'rgba(148, 163, 184, 0.06)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.display = false;
Chart.defaults.animation.duration = 1000;
Chart.defaults.animation.easing = 'easeInOutQuart';

// Premium tooltip defaults
const premiumTooltip = {
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    borderColor: 'rgba(148, 163, 184, 0.15)',
    borderWidth: 1,
    padding: { top: 10, bottom: 10, left: 14, right: 14 },
    cornerRadius: 10,
    titleFont: { family: "'Inter', sans-serif", size: 11, weight: '500' },
    titleColor: '#64748b',
    bodyFont: { family: "'JetBrains Mono', monospace", size: 13, weight: '600' },
    bodySpacing: 6,
    displayColors: true,
    boxWidth: 8,
    boxHeight: 8,
    boxPadding: 4,
    usePointStyle: true,
    caretSize: 6,
    caretPadding: 8,
};

// ── Chart Helpers ───────────────────────────────────────────────

function createPnLChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const colors = data.map(v => v >= 0 ? '#00e676' : '#ff5252');
    const bgColors = data.map(v =>
        v >= 0 ? 'rgba(0, 230, 118, 0.2)' : 'rgba(255, 82, 82, 0.2)'
    );

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Daily PnL',
                data,
                backgroundColor: bgColors,
                borderColor: colors,
                borderWidth: 1.5,
                borderRadius: 4,
                borderSkipped: false,
                maxBarThickness: 36,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    ...premiumTooltip,
                    callbacks: {
                        label: (ctx) => ` PnL: ${formatPnL(ctx.raw)}`,
                        labelTextColor: (ctx) => ctx.raw >= 0 ? '#22c55e' : '#ef4444',
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45, font: { size: 10 }, color: '#64748b' },
                },
                y: {
                    grid: { color: 'rgba(148,163,184,0.05)' },
                    ticks: { callback: (v) => `$${v}`, font: { family: "'JetBrains Mono', monospace", size: 11 } },
                },
            },
        },
    });
}

function createChannelBarChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const colors = data.map(v => v >= 0 ? '#00e676' : '#ff5252');

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Total PnL',
                data,
                backgroundColor: colors.map(c => c + '33'),
                borderColor: colors,
                borderWidth: 1.5,
                borderRadius: 6,
                maxBarThickness: 22,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    ...premiumTooltip,
                    callbacks: {
                        label: (ctx) => ` PnL: ${formatPnL(ctx.raw)}`,
                        labelTextColor: (ctx) => ctx.raw >= 0 ? '#22c55e' : '#ef4444',
                    },
                },
            },
            scales: {
                x: {
                    grid: { color: 'rgba(148,163,184,0.05)' },
                    ticks: { callback: (v) => `$${v}`, font: { family: "'JetBrains Mono', monospace", size: 11 } },
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' },
                },
            },
        },
    });
}

function createEquityChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const lastVal = data.length > 0 ? data[data.length - 1] : 0;
    const lineColor = lastVal >= 0 ? '#00e676' : '#ff5252';

    // Gradient fill
    const chartCtx = ctx.getContext('2d');
    const gradient = chartCtx.createLinearGradient(0, 0, 0, 300);
    if (lastVal >= 0) {
        gradient.addColorStop(0, 'rgba(0, 230, 118, 0.3)');
        gradient.addColorStop(1, 'rgba(0, 230, 118, 0.01)');
    } else {
        gradient.addColorStop(0, 'rgba(255, 82, 82, 0.3)');
        gradient.addColorStop(1, 'rgba(255, 82, 82, 0.01)');
    }

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Equity',
                data,
                borderColor: lineColor,
                backgroundColor: gradient,
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#0a0e1a',
                pointHoverBorderColor: lineColor,
                pointHoverBorderWidth: 2.5,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                tooltip: {
                    ...premiumTooltip,
                    callbacks: {
                        label: (ctx) => ` Equity: ${formatPnL(ctx.raw)}`,
                        labelTextColor: (ctx) => ctx.raw >= 0 ? '#22c55e' : '#ef4444',
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45, font: { size: 10 }, maxTicksLimit: 12, color: '#64748b' },
                },
                y: {
                    grid: { color: 'rgba(148,163,184,0.05)' },
                    ticks: { callback: (v) => `$${v}`, font: { family: "'JetBrains Mono', monospace", size: 11 } },
                },
            },
        },
    });
}

function createSymbolChart(canvasId, labels, winRates) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const colors = winRates.map(wr => {
        if (wr >= 60) return '#00e676';
        if (wr >= 45) return '#ffab40';
        return '#ff5252';
    });

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Win Rate',
                data: winRates,
                backgroundColor: colors.map(c => c + '33'),
                borderColor: colors,
                borderWidth: 1.5,
                borderRadius: 6,
                maxBarThickness: 22,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    ...premiumTooltip,
                    callbacks: {
                        label: (ctx) => ` Win Rate: ${ctx.raw.toFixed(1)}%`,
                        labelTextColor: (ctx) => {
                            if (ctx.raw >= 60) return '#22c55e';
                            if (ctx.raw >= 45) return '#f59e0b';
                            return '#ef4444';
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: { color: 'rgba(148,163,184,0.05)' },
                    ticks: { callback: (v) => `${v}%`, font: { family: "'JetBrains Mono', monospace", size: 11 } },
                    max: 100,
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' },
                },
            },
        },
    });
}

// ── Status Indicator ────────────────────────────────────────────

function setStatus(connected) {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    if (dot) {
        dot.className = 'status-dot ' + (connected ? 'connected' : 'error');
    }
    if (text) {
        text.textContent = connected ? 'Connected' : 'Disconnected';
    }
}

function updateLastRefresh() {
    const el = document.getElementById('last-update');
    if (el) {
        el.textContent = `Last update: ${new Date().toLocaleTimeString()}`;
    }
}

// ── Auto Refresh ────────────────────────────────────────────────

function startAutoRefresh(callback, intervalMs = 30000) {
    callback(); // Initial load
    setInterval(() => {
        callback();
    }, intervalMs);
}
