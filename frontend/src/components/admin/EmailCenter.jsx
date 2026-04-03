/**
 * EmailCenter.jsx
 * Admin dashboard for email automation system
 * Shows email types, previews, send test, and logs
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Mail,
  Send,
  Eye,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Copy,
  User,
  ShoppingBag,
  Star,
  UserX,
  Package,
  Inbox,
  PlayCircle
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Email type icons and colors
const EMAIL_CONFIG = {
  welcome: {
    icon: User,
    color: 'bg-blue-500',
    lightColor: 'bg-blue-50 border-blue-200',
    textColor: 'text-blue-600'
  },
  post_purchase: {
    icon: ShoppingBag,
    color: 'bg-green-500',
    lightColor: 'bg-green-50 border-green-200',
    textColor: 'text-green-600'
  },
  review_request: {
    icon: Star,
    color: 'bg-yellow-500',
    lightColor: 'bg-yellow-50 border-yellow-200',
    textColor: 'text-yellow-600'
  },
  reengagement: {
    icon: UserX,
    color: 'bg-purple-500',
    lightColor: 'bg-purple-50 border-purple-200',
    textColor: 'text-purple-600'
  },
  low_stock: {
    icon: Package,
    color: 'bg-red-500',
    lightColor: 'bg-red-50 border-red-200',
    textColor: 'text-red-600'
  }
};

// Email type card
const EmailTypeCard = ({ type, config, isSelected, onClick, sendgridConfigured }) => {
  const Icon = EMAIL_CONFIG[type]?.icon || Mail;
  const colors = EMAIL_CONFIG[type] || EMAIL_CONFIG.welcome;
  
  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
        isSelected 
          ? `${colors.lightColor} border-current shadow-md` 
          : 'bg-white border-gray-100 hover:border-gray-200'
      }`}
      data-testid={`email-type-${type}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${colors.color}`}>
            <Icon className="h-5 w-5 text-white" />
          </div>
          <div>
            <h4 className="font-medium text-gray-900">{config.name}</h4>
            <p className="text-xs text-gray-500 mt-0.5">{config.trigger}</p>
          </div>
        </div>
        <Badge 
          variant={sendgridConfigured ? "default" : "secondary"}
          className="text-[10px]"
        >
          {sendgridConfigured ? "Active" : "Queued"}
        </Badge>
      </div>
      <p className="text-xs text-gray-500 mt-3">{config.description}</p>
      <div className="mt-3 pt-3 border-t border-gray-100">
        <p className="text-xs text-gray-400 truncate">
          Subject: {config.subject}
        </p>
      </div>
    </div>
  );
};

// Email preview panel
const PreviewPanel = ({ preview, loading }) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }
  
  if (!preview) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center p-6">
        <Eye className="h-12 w-12 text-gray-300 mb-4" />
        <p className="text-gray-500 font-medium">Select an email type to preview</p>
        <p className="text-xs text-gray-400 mt-1">AI-generated content will appear here</p>
      </div>
    );
  }
  
  const handleCopy = () => {
    // Copy HTML content
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = preview.body;
    navigator.clipboard.writeText(tempDiv.textContent || tempDiv.innerText);
    toast.success('Email content copied!');
  };
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="font-medium text-gray-900">{preview.config?.name}</h4>
          <p className="text-sm text-gray-500">{preview.subject}</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleCopy}>
          <Copy className="h-4 w-4 mr-1" />
          Copy
        </Button>
      </div>
      
      {preview.personalization?.has_profile && (
        <div className="flex items-center gap-2 p-2 bg-green-50 rounded-lg">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <span className="text-xs text-green-700">
            Personalized with customer profile
            {preview.personalization.skin_type && ` (${preview.personalization.skin_type})`}
          </span>
        </div>
      )}
      
      <div 
        className="p-4 bg-white border rounded-xl prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: preview.body }}
      />
    </div>
  );
};

// Email log entry
const EmailLogEntry = ({ log }) => {
  const config = EMAIL_CONFIG[log.email_type] || EMAIL_CONFIG.welcome;
  const Icon = config.icon;
  
  const statusIcons = {
    sent: <CheckCircle className="h-4 w-4 text-green-600" />,
    queued: <Clock className="h-4 w-4 text-yellow-600" />,
    failed: <XCircle className="h-4 w-4 text-red-600" />
  };
  
  return (
    <div className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
      <div className={`p-1.5 rounded-lg ${config.color}`}>
        <Icon className="h-4 w-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900 truncate">
            {log.to_email}
          </span>
          <Badge variant="outline" className="text-[10px]">
            {log.email_type}
          </Badge>
        </div>
        <p className="text-xs text-gray-500 truncate">{log.subject}</p>
      </div>
      <div className="flex items-center gap-2">
        {statusIcons[log.status] || statusIcons.queued}
        <span className="text-xs text-gray-400">
          {new Date(log.created_at).toLocaleString()}
        </span>
      </div>
    </div>
  );
};

export default function EmailCenter() {
  const [emailTypes, setEmailTypes] = useState({});
  const [selectedType, setSelectedType] = useState(null);
  const [preview, setPreview] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const [sendgridConfigured, setSendgridConfigured] = useState(false);
  const [testEmail, setTestEmail] = useState('');
  const [queuedCount, setQueuedCount] = useState(0);
  
  // Fetch email types and logs
  const fetchData = useCallback(async () => {
    const token = localStorage.getItem('reroots_token');
    if (!token) return;
    
    try {
      const [typesRes, logsRes, statusRes] = await Promise.all([
        fetch(`${API}/api/email/types`),
        fetch(`${API}/api/email/logs?limit=20`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        fetch(`${API}/api/email/status`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);
      
      if (typesRes.ok) {
        const data = await typesRes.json();
        setEmailTypes(data.types || {});
        setSendgridConfigured(data.sendgrid_configured);
      }
      
      if (logsRes.ok) {
        const data = await logsRes.json();
        setLogs(data.logs || []);
      }
      
      if (statusRes.ok) {
        const data = await statusRes.json();
        setQueuedCount(data.stats?.total_queued || 0);
      }
    } catch (error) {
      console.error('Failed to fetch email data:', error);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  // Fetch preview when type selected
  const handleSelectType = async (type) => {
    setSelectedType(type);
    setPreviewLoading(true);
    
    const token = localStorage.getItem('reroots_token');
    try {
      const res = await fetch(`${API}/api/email/preview/${type}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        const data = await res.json();
        setPreview(data);
      } else {
        toast.error('Failed to load preview');
      }
    } catch (error) {
      toast.error('Error loading preview');
    } finally {
      setPreviewLoading(false);
    }
  };
  
  // Send test email
  const handleSendTest = async () => {
    if (!selectedType) {
      toast.error('Select an email type first');
      return;
    }
    
    const email = testEmail || 'admin@reroots.ca';
    setSendingTest(true);
    
    const token = localStorage.getItem('reroots_token');
    try {
      const res = await fetch(`${API}/api/email/send`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          email_type: selectedType,
          to_email: email,
          test_mode: true
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.sendgrid_configured) {
          toast.success(`Test email sent to ${email}`);
        } else {
          toast.success(`Email queued (SendGrid not configured)`);
        }
        fetchData(); // Refresh logs
      } else {
        toast.error('Failed to send test email');
      }
    } catch (error) {
      toast.error('Error sending test email');
    } finally {
      setSendingTest(false);
    }
  };
  
  // Process queue
  const handleProcessQueue = async () => {
    const token = localStorage.getItem('reroots_token');
    try {
      const res = await fetch(`${API}/api/email/process-queue`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const data = await res.json();
      if (data.success) {
        toast.success(`Processed ${data.processed} emails`);
        fetchData();
      } else {
        toast.info(data.message);
      }
    } catch (error) {
      toast.error('Error processing queue');
    }
  };
  
  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6" data-testid="email-center">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-pink-500 to-rose-600">
            <Mail className="h-6 w-6 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Email Center</h2>
            <p className="text-sm text-gray-500">AI-powered email automation</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {/* SendGrid status */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
            sendgridConfigured ? 'bg-green-50' : 'bg-yellow-50'
          }`}>
            {sendgridConfigured ? (
              <CheckCircle className="h-4 w-4 text-green-600" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-yellow-600" />
            )}
            <span className={`text-sm ${
              sendgridConfigured ? 'text-green-700' : 'text-yellow-700'
            }`}>
              {sendgridConfigured ? 'SendGrid Active' : 'SendGrid Pending'}
            </span>
          </div>
          
          {queuedCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleProcessQueue}
              disabled={!sendgridConfigured}
            >
              <Inbox className="h-4 w-4 mr-1" />
              {queuedCount} Queued
            </Button>
          )}
          
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>
      
      {/* SendGrid notice */}
      {!sendgridConfigured && (
        <div className="p-4 bg-yellow-50 rounded-xl border border-yellow-200">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
            <div>
              <p className="font-medium text-yellow-800">SendGrid Not Configured</p>
              <p className="text-sm text-yellow-700 mt-1">
                Emails will be queued and sent automatically once you add <code className="bg-yellow-100 px-1 rounded">SENDGRID_API_KEY</code> to your environment variables.
              </p>
            </div>
          </div>
        </div>
      )}
      
      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Email types */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Mail className="h-4 w-4" />
            Email Types
          </h3>
          <div className="space-y-3">
            {Object.entries(emailTypes).map(([type, config]) => (
              <EmailTypeCard
                key={type}
                type={type}
                config={config}
                isSelected={selectedType === type}
                onClick={() => handleSelectType(type)}
                sendgridConfigured={sendgridConfigured}
              />
            ))}
          </div>
        </div>
        
        {/* Preview panel */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
              <Eye className="h-4 w-4" />
              Preview
            </h3>
            
            {selectedType && (
              <div className="flex items-center gap-2">
                <Input
                  type="email"
                  placeholder="Test email (default: admin@reroots.ca)"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  className="w-64 h-9 text-sm"
                />
                <Button
                  size="sm"
                  onClick={handleSendTest}
                  disabled={sendingTest}
                  className="bg-rose-600 hover:bg-rose-700"
                  data-testid="send-test-btn"
                >
                  {sendingTest ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <Send className="h-4 w-4 mr-1" />
                      Send Test
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
          
          <div className="bg-gray-50 rounded-xl border p-4 min-h-[300px]">
            <PreviewPanel preview={preview} loading={previewLoading} />
          </div>
        </div>
      </div>
      
      {/* Email logs */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
          <Clock className="h-4 w-4" />
          Recent Emails
          <Badge variant="secondary" className="text-xs">
            {logs.length}
          </Badge>
        </h3>
        
        {logs.length === 0 ? (
          <div className="p-8 text-center bg-gray-50 rounded-xl border border-dashed border-gray-200">
            <Mail className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No emails sent yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Emails will appear here when triggered or sent manually
            </p>
          </div>
        ) : (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {logs.map((log, idx) => (
              <EmailLogEntry key={idx} log={log} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
