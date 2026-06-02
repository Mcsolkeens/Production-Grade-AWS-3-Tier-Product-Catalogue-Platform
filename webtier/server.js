const express = require('express');
const axios   = require('axios');
const morgan  = require('morgan');
const path    = require('path');

const app = express();

// ── Config ─────────────────────────────────────────────────────────────
// APP_API_URL is set as an environment variable on the EC2 instance.
// It points to the Internal ALB DNS name.
const APP_API = process.env.APP_API_URL;
const PORT    = process.env.PORT || 3000;

if (!APP_API) {
    console.error('ERROR: APP_API_URL environment variable is not set');
    console.error('Set it to the Internal ALB DNS name, e.g.:');
    console.error('  http://prod-int-alb-xxxx.us-east-1.elb.amazonaws.com:3000');
    process.exit(1);
}

// ── Middleware ─────────────────────────────────────────────────────────
app.use(morgan('combined'));            // Request logging
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve static files from /public folder
app.use(express.static(path.join(__dirname, 'public')));

// ── Health check — used by External ALB ───────────────────────────────
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        tier:   'web',
        host:   require('os').hostname()
    });
});

// ── API Proxy — GET requests ───────────────────────────────────────────
// All /api/* GET requests are forwarded to the App tier (Internal ALB)
app.get('/api/*', async (req, res) => {
    try {
        const url      = `${APP_API}${req.path}`;
        const response = await axios.get(url, {
            params:  req.query,
            timeout: 8000,
            headers: { 'X-Forwarded-For': req.ip }
        });
        res.status(response.status).json(response.data);
    } catch (err) {
        const status = err.response?.status || 502;
        console.error(`App tier GET error [${req.path}]:`, err.message);
        res.status(status).json({
            error:   'App tier error',
            message: err.message
        });
    }
});

// ── API Proxy — POST requests ──────────────────────────────────────────
app.post('/api/*', async (req, res) => {
    try {
        const url      = `${APP_API}${req.path}`;
        const response = await axios.post(url, req.body, {
            timeout: 8000,
            headers: { 'Content-Type': 'application/json' }
        });
        res.status(response.status).json(response.data);
    } catch (err) {
        const status = err.response?.status || 502;
        console.error(`App tier POST error [${req.path}]:`, err.message);
        res.status(status).json({ error: 'App tier error' });
    }
});

// ── API Proxy — DELETE requests ────────────────────────────────────────
app.delete('/api/*', async (req, res) => {
    try {
        const url      = `${APP_API}${req.path}`;
        const response = await axios.delete(url, { timeout: 8000 });
        res.status(response.status).json(response.data);
    } catch (err) {
        const status = err.response?.status || 502;
        res.status(status).json({ error: 'App tier error' });
    }
});

// ── Catch-all — serve index.html for any unmatched route ──────────────
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// ── Start server ───────────────────────────────────────────────────────
app.listen(PORT, '0.0.0.0', () => {
    console.log(`Web tier running on port ${PORT}`);
    console.log(`Proxying API calls to: ${APP_API}`);
});