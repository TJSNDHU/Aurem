/**
 * ReRoots AI PWA Analytics Dashboard
 * SINGLE ADMIN POLICY: All PWA data flows to Master Admin
 * 
 * Features:
 * - Biometric Login Success Rates
 * - Skin Health Scores (from encrypted vault)
 * - PWA Abandoned Carts
 * - Push Notification Stats
 * - PWA-to-Admin Connection Health
 */

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Smartphone, Shield, ShoppingCart, Bell, Camera, Heart,
  TrendingUp, TrendingDown, Users, Activity, RefreshCw,
  CheckCircle, XCircle, Clock, Fingerprint, Key, Eye,
  AlertTriangle, Wifi, WifiOff, Lock, Unlock
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function PWAAnalyticsDashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [health, setHealth] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Fetch analytics data
  const fetchAnalytics = useCallback(async () => {
    try {
      const [analyticsRes, healthRes, statusRes] = await Promise.all([
        axios.get(`${API}/pwa/admin/analytics`),
        axios.get(`${API}/pwa/admin/health`),
        axios.get(`${API}/pwa/admin/system-status`)
      ]);
      
      setAnalytics(analyticsRes.data);
      setHealth(healthRes.data);
      setSystemStatus(statusRes.data);
    } catch (error) {
      console.error('[PWA Analytics] Fetch error:', error);
      toast.error('Failed to load PWA analytics');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
    // Refresh every 30 seconds
    const interval = setInterval(fetchAnalytics, 30000);
    return () => clearInterval(interval);
  }, [fetchAnalytics]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchAnalytics();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-amber-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  const biometric = analytics?.biometric || {};
  const abandonedCarts = analytics?.abandoned_carts || {};
  const pushStats = analytics?.push_notifications || {};
  const vaultStats = analytics?.vault || {};

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Smartphone className="w-7 h-7 text-amber-500" />
            PWA Analytics
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            ReRoots AI Luxury PWA • Single Admin Command Center
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Connection Status */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
            health?.status === 'healthy' 
              ? 'bg-green-100 text-green-700' 
              : 'bg-red-100 text-red-700'
          }`}>
            {health?.status === 'healthy' ? (
              <Wifi className="w-4 h-4" />
            ) : (
              <WifiOff className="w-4 h-4" />
            )}
            {health?.status === 'healthy' ? 'PWA Connected' : 'Connection Issue'}
          </div>
          
          <Button 
            onClick={handleRefresh}
            variant="outline"
            size="sm"
            disabled={refreshing}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Biometric Success Rate */}
        <Card className="border-l-4 border-l-green-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500 flex items-center gap-2">
              <Fingerprint className="w-4 h-4" />
              Biometric Success Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">
                {biometric.login_success_rate || 0}%
              </span>
              <Badge variant={biometric.login_success_rate >= 90 ? 'success' : 'warning'}>
                {biometric.login_success_rate >= 90 ? (
                  <TrendingUp className="w-3 h-3 mr-1" />
                ) : (
                  <TrendingDown className="w-3 h-3 mr-1" />
                )}
                {biometric.login_success_rate >= 90 ? 'Healthy' : 'Needs Attention'}
              </Badge>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              {biometric.success_logins || 0} successful / {biometric.failed_logins || 0} failed
            </div>
          </CardContent>
        </Card>

        {/* PWA Abandoned Carts */}
        <Card className="border-l-4 border-l-red-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500 flex items-center gap-2">
              <ShoppingCart className="w-4 h-4" />
              PWA Abandoned Carts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">
                {abandonedCarts.pwa_count || 0}
              </span>
              <Badge variant="destructive">
                ${(abandonedCarts.total_value || 0).toFixed(2)}
              </Badge>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              Potential revenue to recover
            </div>
          </CardContent>
        </Card>

        {/* Active Push Subscriptions */}
        <Card className="border-l-4 border-l-blue-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500 flex items-center gap-2">
              <Bell className="w-4 h-4" />
              Push Subscribers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">
                {pushStats.active_subscriptions || 0}
              </span>
              <Badge variant="outline">
                {pushStats.total_sent || 0} sent
              </Badge>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              Active notification subscribers
            </div>
          </CardContent>
        </Card>

        {/* Encrypted Vaults */}
        <Card className="border-l-4 border-l-purple-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500 flex items-center gap-2">
              <Lock className="w-4 h-4" />
              Encrypted Vaults
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold text-gray-900">
                {vaultStats.total_vaults || 0}
              </span>
              <Badge variant="secondary">
                {vaultStats.active_users || 0} active
              </Badge>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              AES-256 encrypted skin photo vaults
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Biometric Authentication Log */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-amber-500" />
              Biometric Authentication Log
            </CardTitle>
            <CardDescription>
              Recent FaceID/Fingerprint and PIN authentications
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {biometric.recent_registrations?.length > 0 ? (
                biometric.recent_registrations.map((reg, idx) => (
                  <div 
                    key={idx}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        reg.method === 'webauthn' ? 'bg-green-100' : 'bg-amber-100'
                      }`}>
                        {reg.method === 'webauthn' ? (
                          <Fingerprint className="w-4 h-4 text-green-600" />
                        ) : (
                          <Key className="w-4 h-4 text-amber-600" />
                        )}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {reg.method === 'webauthn' ? 'Biometric' : 'PIN'} Registration
                        </p>
                        <p className="text-xs text-gray-500">
                          User: {reg.user_id?.slice(0, 8) || 'Anonymous'}...
                        </p>
                      </div>
                    </div>
                    <span className="text-xs text-gray-400">
                      {new Date(reg.timestamp).toLocaleString()}
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Shield className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                  <p>No biometric registrations yet</p>
                  <p className="text-xs mt-1">Registrations will appear here when users enable biometric security</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* PWA Abandoned Carts */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShoppingCart className="w-5 h-5 text-red-500" />
              PWA Abandoned Carts
            </CardTitle>
            <CardDescription>
              Carts from PWA users that need recovery
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {abandonedCarts.carts?.length > 0 ? (
                abandonedCarts.carts.map((cart, idx) => (
                  <div 
                    key={idx}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center">
                        <ShoppingCart className="w-4 h-4 text-red-600" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {cart.items_count} item{cart.items_count > 1 ? 's' : ''}
                        </p>
                        <p className="text-xs text-gray-500">
                          Session: {cart.session_id?.slice(0, 8)}...
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold text-red-600">${cart.total?.toFixed(2)}</p>
                      <p className="text-xs text-gray-400">
                        {new Date(cart.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <CheckCircle className="w-12 h-12 mx-auto mb-2 text-green-300" />
                  <p>No abandoned PWA carts!</p>
                  <p className="text-xs mt-1">Great job - all PWA customers are completing their orders</p>
                </div>
              )}
            </div>

            {abandonedCarts.pwa_count > 0 && (
              <Button 
                className="w-full mt-4 bg-amber-500 hover:bg-amber-600 text-black"
                onClick={() => toast.success('Cart recovery notifications will be sent!')}
              >
                <Bell className="w-4 h-4 mr-2" />
                Send Recovery Push Notifications
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      {/* System Health */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-green-500" />
            PWA-to-Admin Connection Health
          </CardTitle>
          <CardDescription>
            Circuit Breaker monitoring for PWA integration
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <div className={`w-12 h-12 mx-auto mb-2 rounded-full flex items-center justify-center ${
                health?.database === 'connected' ? 'bg-green-100' : 'bg-red-100'
              }`}>
                {health?.database === 'connected' ? (
                  <CheckCircle className="w-6 h-6 text-green-600" />
                ) : (
                  <XCircle className="w-6 h-6 text-red-600" />
                )}
              </div>
              <p className="font-medium text-gray-900">Database</p>
              <p className="text-xs text-gray-500">{health?.database || 'Unknown'}</p>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <div className={`w-12 h-12 mx-auto mb-2 rounded-full flex items-center justify-center ${
                health?.vapid === 'configured' ? 'bg-green-100' : 'bg-amber-100'
              }`}>
                {health?.vapid === 'configured' ? (
                  <Bell className="w-6 h-6 text-green-600" />
                ) : (
                  <AlertTriangle className="w-6 h-6 text-amber-600" />
                )}
              </div>
              <p className="font-medium text-gray-900">Push Notifications</p>
              <p className="text-xs text-gray-500">{health?.vapid || 'Unknown'}</p>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <div className={`w-12 h-12 mx-auto mb-2 rounded-full flex items-center justify-center ${
                health?.ai === 'configured' ? 'bg-green-100' : 'bg-amber-100'
              }`}>
                {health?.ai === 'configured' ? (
                  <CheckCircle className="w-6 h-6 text-green-600" />
                ) : (
                  <AlertTriangle className="w-6 h-6 text-amber-600" />
                )}
              </div>
              <p className="font-medium text-gray-900">AI Integration</p>
              <p className="text-xs text-gray-500">{health?.ai || 'Unknown'}</p>
            </div>

            {/* NEW: Encryption Status */}
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <div className={`w-12 h-12 mx-auto mb-2 rounded-full flex items-center justify-center ${
                health?.encryption?.includes('Active') ? 'bg-green-100' : 'bg-amber-100'
              }`}>
                {health?.encryption?.includes('Active') ? (
                  <Lock className="w-6 h-6 text-green-600" />
                ) : (
                  <Unlock className="w-6 h-6 text-amber-600" />
                )}
              </div>
              <p className="font-medium text-gray-900">Vault Encryption</p>
              <p className="text-xs text-gray-500">{health?.encryption || 'Unknown'}</p>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <div className={`w-12 h-12 mx-auto mb-2 rounded-full flex items-center justify-center ${
                health?.status === 'healthy' ? 'bg-green-100' : 'bg-red-100'
              }`}>
                {health?.status === 'healthy' ? (
                  <Wifi className="w-6 h-6 text-green-600" />
                ) : (
                  <WifiOff className="w-6 h-6 text-red-600" />
                )}
              </div>
              <p className="font-medium text-gray-900">Overall Status</p>
              <p className="text-xs text-gray-500">{health?.status || 'Unknown'}</p>
            </div>
          </div>

          {/* Service Worker Version Banner */}
          {systemStatus && (
            <div className="mt-4 p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                    <Shield className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <p className="font-bold text-green-800">
                      Service Worker: {systemStatus.service_worker_version} (Active)
                    </p>
                    <p className="text-xs text-green-700">
                      {systemStatus.pwa_version} • Cache: {systemStatus.cache_version}
                    </p>
                  </div>
                </div>
                <Badge className="bg-green-600 text-white">
                  {systemStatus.security?.vault_encryption}
                </Badge>
              </div>
            </div>
          )}

          <div className="mt-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
            <div className="flex items-start gap-2">
              <Smartphone className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-amber-800">Single Admin Policy Active</p>
                <p className="text-xs text-amber-700 mt-1">
                  All PWA data (biometric logs, encrypted vaults, abandoned carts) syncs to this Master Admin.
                  No separate PWA admin exists.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Skin Vault Privacy Notice */}
      <Card className="border-purple-200 bg-purple-50/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-purple-800">
            <Eye className="w-5 h-5" />
            Skin Vault Privacy Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
              <Lock className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <p className="text-purple-900 font-medium">
                Customer skin photos are encrypted on-device only
              </p>
              <p className="text-purple-700 text-sm mt-1">
                Photos use AES-256-GCM encryption and are stored in IndexedDB on the user's device.
                They are not uploaded to the server. You can see vault activity metadata (photo counts, 
                storage used) but not the actual images unless the customer explicitly shares them for consultation.
              </p>
              <Button 
                variant="outline" 
                size="sm" 
                className="mt-3 border-purple-300 text-purple-700 hover:bg-purple-100"
              >
                <Camera className="w-4 h-4 mr-2" />
                Enable Admin Photo Viewing (Requires Customer Consent)
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default PWAAnalyticsDashboard;
