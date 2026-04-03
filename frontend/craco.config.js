// craco.config.js - Simplified for deployment
const path = require("path");
require("dotenv").config();

const isDevServer = process.env.NODE_ENV !== "production";

// Custom webpack plugin to make CSS non-render-blocking
class NonBlockingCSSPlugin {
  apply(compiler) {
    compiler.hooks.compilation.tap('NonBlockingCSSPlugin', (compilation) => {
      const HtmlWebpackPlugin = require('html-webpack-plugin');
      
      HtmlWebpackPlugin.getHooks(compilation).alterAssetTagGroups.tapAsync(
        'NonBlockingCSSPlugin',
        (data, cb) => {
          data.headTags = data.headTags.map(tag => {
            if (tag.tagName === 'link' && tag.attributes && tag.attributes.rel === 'stylesheet') {
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

      // Performance: Split chunks for production
      if (!isDevServer && webpackConfig.optimization) {
        webpackConfig.optimization.splitChunks = {
          ...webpackConfig.optimization.splitChunks,
          chunks: 'all',
          maxInitialRequests: 25,
          minSize: 20000,
          cacheGroups: {
            dndKit: {
              test: /[\\/]node_modules[\\/](@dnd-kit)[\\/]/,
              name: 'vendor-dnd-kit',
              chunks: 'async',
              priority: 40,
            },
            framerMotion: {
              test: /[\\/]node_modules[\\/](framer-motion)[\\/]/,
              name: 'vendor-framer-motion',
              chunks: 'async',
              priority: 30,
            },
            radixUI: {
              test: /[\\/]node_modules[\\/](@radix-ui)[\\/]/,
              name: 'vendor-radix-ui',
              chunks: 'async',
              priority: 25,
            },
            floatingUI: {
              test: /[\\/]node_modules[\\/](@floating-ui)[\\/]/,
              name: 'vendor-floating-ui',
              chunks: 'async',
              priority: 24,
            },
            react: {
              test: /[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/,
              name: 'vendor-react',
              chunks: 'initial',
              priority: 50,
            },
            reactRouter: {
              test: /[\\/]node_modules[\\/](react-router|react-router-dom)[\\/]/,
              name: 'vendor-router',
              chunks: 'all',
              priority: 45,
            },
            defaultVendors: {
              test: /[\\/]node_modules[\\/]/,
              name: 'vendors',
              chunks: 'initial',
              priority: -10,
              reuseExistingChunk: true,
            },
          },
        };
      }
      
      // Add non-blocking CSS plugin for production
      if (!isDevServer) {
        webpackConfig.plugins.push(new NonBlockingCSSPlugin());
      }
      
      return webpackConfig;
    },
  },
  devServer: (devServerConfig) => {
    devServerConfig.historyApiFallback = {
      disableDotRule: true,
      index: '/index.html'
    };
    return devServerConfig;
  },
};

module.exports = webpackConfig;
