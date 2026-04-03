import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { 
  Shield, ShieldCheck, ShieldOff, Lock, Unlock, Bot, Globe, 
  AlertTriangle, CheckCircle, RefreshCw, Loader2, Eye, EyeOff,
  Server, Wrench
} from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

const SecuritySettings = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(null);
  const [securityData, setSecurityData] = useState(null);
  const token = localStorage.getItem('token');

  const fetchSecurityStatus = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/admin/security-status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSecurityData(res.data);
    } catch (err) {
      toast.error('Failed to load security settings');
      console.error(err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchSecurityStatus();
  }, []);

  const toggleSetting = async (setting, currentValue) => {
    setSaving(setting);
    try {
      await axios.post(`${API}/api/admin/security-settings`, {
        setting: setting,
        enabled: !currentValue
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(`${setting.replace(/_/g, ' ')} ${!currentValue ? 'enabled' : 'disabled'}`);
      fetchSecurityStatus();
    } catch (err) {
      toast.error('Failed to update setting: ' + (err.response?.data?.detail || err.message));
    }
    setSaving(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  const siteProtection = securityData?.site_protection || {};
  const securityFeatures = securityData?.security_features || {};
  const currentStatus = securityData?.current_status || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <Shield className="h-6 w-6 text-purple-600" />
            Security Settings
          </h1>
          <p className="text-sm text-gray-500">Control site access, bot protection, and crawl settings</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchSecurityStatus}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Site Protection Toggles - Main Feature */}
      <Card className="border-2 border-purple-200">
        <CardHeader className="bg-gradient-to-r from-purple-50 to-indigo-50">
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-purple-600" />
            Site Protection Controls
          </CardTitle>
          <CardDescription>Toggle these settings to control who can access your site</CardDescription>
        </CardHeader>
        <CardContent className="pt-6 space-y-6">
          
          {/* Crawl/Bot Access - THE MAIN TOGGLE */}
          <div className="flex items-center justify-between p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border-2 border-green-200">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                siteProtection.crawl_enabled 
                  ? 'bg-green-500 text-white' 
                  : 'bg-red-500 text-white'
              }`}>
                {siteProtection.crawl_enabled ? <Bot className="h-6 w-6" /> : <ShieldOff className="h-6 w-6" />}
              </div>
              <div>
                <h3 className="font-semibold text-lg">Search Engine & Bot Access</h3>
                <p className="text-sm text-gray-600">
                  {siteProtection.crawl_enabled 
                    ? 'Crawlers and bots CAN access your site (SEO enabled)' 
                    : 'Crawlers and bots are BLOCKED (SEO disabled)'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Badge className={siteProtection.crawl_enabled ? 'bg-green-500' : 'bg-red-500'}>
                {siteProtection.crawl_enabled ? 'ACTIVE' : 'BLOCKED'}
              </Badge>
              <Button
                onClick={() => toggleSetting('crawl_enabled', siteProtection.crawl_enabled)}
                disabled={saving === 'crawl_enabled'}
                className={siteProtection.crawl_enabled 
                  ? 'bg-red-500 hover:bg-red-600' 
                  : 'bg-green-500 hover:bg-green-600'}
              >
                {saving === 'crawl_enabled' ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : siteProtection.crawl_enabled ? (
                  <>Deactivate</>
                ) : (
                  <>Activate</>
                )}
              </Button>
            </div>
          </div>

          {/* Password Protection */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border">
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                siteProtection.password_protection 
                  ? 'bg-amber-500 text-white' 
                  : 'bg-gray-300 text-gray-600'
              }`}>
                {siteProtection.password_protection ? <Lock className="h-5 w-5" /> : <Unlock className="h-5 w-5" />}
              </div>
              <div>
                <h3 className="font-medium">Password Protection</h3>
                <p className="text-sm text-gray-500">Require password to access storefront</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">
                {siteProtection.password_protection ? 'Enabled' : 'Disabled'}
              </span>
              <Switch
                checked={siteProtection.password_protection}
                onCheckedChange={() => toggleSetting('password_protection', siteProtection.password_protection)}
                disabled={saving === 'password_protection'}
              />
            </div>
          </div>

          {/* Maintenance Mode */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border">
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                siteProtection.maintenance_mode 
                  ? 'bg-orange-500 text-white' 
                  : 'bg-gray-300 text-gray-600'
              }`}>
                <Wrench className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-medium">Maintenance Mode</h3>
                <p className="text-sm text-gray-500">Show "Under Maintenance" page to visitors</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">
                {siteProtection.maintenance_mode ? 'Enabled' : 'Disabled'}
              </span>
              <Switch
                checked={siteProtection.maintenance_mode}
                onCheckedChange={() => toggleSetting('maintenance_mode', siteProtection.maintenance_mode)}
                disabled={saving === 'maintenance_mode'}
              />
            </div>
          </div>

        </CardContent>
      </Card>

      {/* Security Features Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-green-600" />
            Active Security Features
          </CardTitle>
          <CardDescription>Built-in protections that are always active</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(securityFeatures).map(([feature, enabled]) => (
              <div 
                key={feature}
                className={`p-3 rounded-lg border ${enabled ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'}`}
              >
                <div className="flex items-center gap-2">
                  {enabled ? (
                    <CheckCircle className="h-4 w-4 text-green-600" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-gray-400" />
                  )}
                  <span className="text-xs font-medium capitalize">
                    {feature.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Current Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5 text-blue-600" />
            Current Security Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">{currentStatus.accounts_with_failed_logins || 0}</div>
              <div className="text-xs text-gray-500">Failed Login Attempts</div>
            </div>
            <div className="text-center p-4 bg-amber-50 rounded-lg">
              <div className="text-2xl font-bold text-amber-600">{currentStatus.locked_accounts || 0}</div>
              <div className="text-xs text-gray-500">Locked Accounts</div>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <div className="text-2xl font-bold text-red-600">{currentStatus.rate_limited_ips || 0}</div>
              <div className="text-xs text-gray-500">Rate Limited IPs</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recommendations */}
      <Card className="border-amber-200 bg-amber-50">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-amber-800">
            <AlertTriangle className="h-5 w-5" />
            Security Recommendations
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {securityData?.recommendations?.map((rec, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-amber-900">
                <CheckCircle className="h-4 w-4 mt-0.5 text-amber-600 flex-shrink-0" />
                {rec}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
};

export default SecuritySettings;
