// setupProxy.js - Configure dev server proxies
// This ensures /health and /ready return proper JSON responses IMMEDIATELY
// IMPORTANT: These endpoints must respond before webpack compiles for deployment health checks

const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Health check endpoint - ALWAYS return healthy immediately
  // This is critical for deployment health probes that run before webpack compiles
  app.get('/health', (req, res) => {
    res.setHeader('Content-Type', 'application/json');
    res.status(200).json({ status: 'healthy', service: 'reroots-frontend' });
  });

  // Readiness check endpoint - ALWAYS return ready
  app.get('/ready', (req, res) => {
    res.setHeader('Content-Type', 'application/json');
    res.status(200).json({ status: 'ready', service: 'reroots-frontend' });
  });

  // Also handle /health/simple for compatibility
  app.get('/health/simple', (req, res) => {
    res.setHeader('Content-Type', 'text/plain');
    res.status(200).send('OK');
  });

  // Proxy API requests to backend
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:8001',
      changeOrigin: true,
      pathRewrite: {
        '^/api': '/api', // Keep /api prefix
      },
    })
  );
};
