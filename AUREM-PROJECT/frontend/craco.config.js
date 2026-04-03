// craco.config.js
const path = require("path");
require("dotenv").config();

// Check if we're in development/preview mode (not production build)
// Craco sets NODE_ENV=development for start, NODE_ENV=production for build
const isDevServer = process.env.NODE_ENV !== "production";

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
  enableVisualEdits: isDevServer, // Only enable during dev server
};

// Conditionally load visual edits modules only in dev mode
let setupDevServer;
let babelMetadataPlugin;

if (config.enableVisualEdits) {
  setupDevServer = require("./plugins/visual-edits/dev-server-setup");
  babelMetadataPlugin = require("./plugins/visual-edits/babel-metadata-plugin");
}

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

// Custom webpack plugin to make CSS non-render-blocking
class NonBlockingCSSPlugin {
  apply(compiler) {
    compiler.hooks.compilation.tap('NonBlockingCSSPlugin', (compilation) => {
      // For CRA 5+ with Webpack 5
      const HtmlWebpackPlugin = require('html-webpack-plugin');
      
      HtmlWebpackPlugin.getHooks(compilation).alterAssetTagGroups.tapAsync(
        'NonBlockingCSSPlugin',
        (data, cb) => {
          // Convert CSS links to non-blocking
          data.headTags = data.headTags.map(tag => {
            if (tag.tagName === 'link' && tag.attributes && tag.attributes.rel === 'stylesheet') {
              // Add media="print" and onload handler for non-blocking CSS
              return {
                ...tag,
                attributes: {
                  ...tag.attributes,
                  media: 'print',
                  onload: "this.media='all'"
                }
              };
            }
            return tag;
          });
          cb(null, data);
        }
      );
    });
  }
}

const webpackConfig = {
  eslint: {
    configure: {
      extends: ["plugin:react-hooks/recommended"],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {

      // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
        ],
      };

      // ===========================================
      // PERFORMANCE: Split chunks for mobile score
      // Only apply in production to avoid dev server issues
      // ===========================================
      if (!isDevServer && webpackConfig.optimization) {
        webpackConfig.optimization.splitChunks = {
          ...webpackConfig.optimization.splitChunks,
          chunks: 'all',
          maxInitialRequests: 25,
          minSize: 20000,
          cacheGroups: {
            // DnD-kit - Admin only, lazy loaded
            dndKit: {
              test: /[\\/]node_modules[\\/](@dnd-kit)[\\/]/,
              name: 'vendor-dnd-kit',
              chunks: 'async', // Only load when admin accesses it
              priority: 40,
            },
            // Framer Motion - Split into async chunk since it's lazy loaded
            framerMotion: {
              test: /[\\/]node_modules[\\/](framer-motion)[\\/]/,
              name: 'vendor-framer-motion',
              chunks: 'async', // Changed to async - loaded on demand
              priority: 30,
            },
            // Radix UI - Split by component type for better tree shaking
            radixUI: {
              test: /[\\/]node_modules[\\/](@radix-ui)[\\/]/,
              name: 'vendor-radix-ui',
              chunks: 'async', // Changed to async - only load when needed
              priority: 25,
            },
            // Floating UI - Used by popovers/tooltips, async load
            floatingUI: {
              test: /[\\/]node_modules[\\/](@floating-ui)[\\/]/,
              name: 'vendor-floating-ui',
              chunks: 'async',
              priority: 24,
            },
            // Sonner - Toast notifications, async load
            sonner: {
              test: /[\\/]node_modules[\\/](sonner)[\\/]/,
              name: 'vendor-sonner',
              chunks: 'async',
              priority: 23,
            },
            // TanStack Virtual - Admin tables only
            tanstackVirtual: {
              test: /[\\/]node_modules[\\/](@tanstack[\\/]react-virtual)[\\/]/,
              name: 'vendor-tanstack-virtual',
              chunks: 'async',
              priority: 22,
            },
            // React Window - List virtualization
            reactWindow: {
              test: /[\\/]node_modules[\\/](react-window)[\\/]/,
              name: 'vendor-react-window',
              chunks: 'async',
              priority: 20,
            },
            // PayPal - Payment modal, lazy loaded
            paypal: {
              test: /[\\/]node_modules[\\/](@paypal)[\\/]/,
              name: 'vendor-paypal',
              chunks: 'async',
              priority: 15,
            },
            // html2canvas - Lazy loaded for share cards
            html2canvas: {
              test: /[\\/]node_modules[\\/](html2canvas)[\\/]/,
              name: 'vendor-html2canvas',
              chunks: 'async',
              priority: 12,
            },
            // QRCode - Lazy loaded for QR generation
            qrcode: {
              test: /[\\/]node_modules[\\/](qrcode|qrcode\.react)[\\/]/,
              name: 'vendor-qrcode',
              chunks: 'async',
              priority: 10,
            },
            // Default vendor splitting
            defaultVendors: {
              test: /[\\/]node_modules[\\/]/,
              name: 'vendors',
              chunks: 'initial',
              priority: -10,
              reuseExistingChunk: true,
            },
            // React core - must be initial for app to work
            react: {
              test: /[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/,
              name: 'vendor-react',
              chunks: 'initial',
              priority: 50,
            },
            // React Router - async load for non-initial routes
            reactRouter: {
              test: /[\\/]node_modules[\\/](react-router|react-router-dom)[\\/]/,
              name: 'vendor-router',
              chunks: 'all',
              priority: 45,
            },
          },
        };
      }

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      
      // Add non-blocking CSS plugin for production builds
      if (!isDevServer) {
        webpackConfig.plugins.push(new NonBlockingCSSPlugin());
      }
      
      return webpackConfig;
    },
  },
};

// Only add babel metadata plugin during dev server
if (config.enableVisualEdits && babelMetadataPlugin) {
  webpackConfig.babel = {
    plugins: [babelMetadataPlugin],
  };
}

webpackConfig.devServer = (devServerConfig) => {
  // CRITICAL: Enable historyApiFallback for SPA routing
  devServerConfig.historyApiFallback = {
    disableDotRule: true,
    index: '/index.html'
  };
  
  // Apply visual edits dev server setup only if enabled
  if (config.enableVisualEdits && setupDevServer) {
    devServerConfig = setupDevServer(devServerConfig);
  }

  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

  return devServerConfig;
};

module.exports = webpackConfig;
