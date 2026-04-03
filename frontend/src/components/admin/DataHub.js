import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Users, Mail, Download, Search, Filter, RefreshCw, Send,
  UserPlus, Crown, TestTube, ClipboardList, Star, Eye,
  ChevronDown, ChevronRight, Copy, ExternalLink, Loader2,
  Check, X, MoreHorizontal, Gift, TrendingUp, Clock,
  Database, Sparkles, MessageSquare, UserCheck, AlertCircle
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription
} from '../ui/dialog';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '../ui/select';
import { useAdminBrand } from './useAdminBrand';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL);

// ============ STAT CARD ============
const StatCard = ({ label, value, icon: Icon, color = 'blue', trend, onClick }) => (
  <Card 
    className={`cursor-pointer hover:shadow-md transition-all ${onClick ? 'hover:ring-2 hover:ring-pink-200' : ''}`}
    onClick={onClick}
  >
    <CardContent className="p-4">
      <div className="flex items-center justify-between">
        <div className={`p-2 rounded-lg bg-${color}-100`}>
          <Icon className={`h-5 w-5 text-${color}-600`} />
        </div>
        {trend && (
          <Badge className={trend > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
            {trend > 0 ? '+' : ''}{trend}%
          </Badge>
        )}
      </div>
      <p className="text-2xl font-bold mt-3 text-[#2D2A2E]">{value}</p>
      <p className="text-sm text-[#5A5A5A]">{label}</p>
    </CardContent>
  </Card>
);

// ============ DATA TABLE ============
const DataTable = ({ data, columns, onRowClick, emptyMessage = "No data found" }) => {
  if (!data || data.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Database className="h-12 w-12 mx-auto mb-3 text-gray-300" />
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            {columns.map((col, idx) => (
              <th key={idx} className="px-4 py-3 text-left font-medium text-gray-600">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr 
              key={row.id || idx} 
              className="border-b hover:bg-pink-50/50 cursor-pointer transition-colors"
              onClick={() => onRowClick?.(row)}
            >
              {columns.map((col, colIdx) => (
                <td key={colIdx} className="px-4 py-3">
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// ============ MAIN DATA HUB ============
const DataHub = ({ initialTab = 'overview' }) => {
  const { shortName, activeBrand } = useAdminBrand();
  
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(initialTab);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Data states
  const [stats, setStats] = useState({
    partners: 0,
    partnerApplications: 0,
    waitlist: 0,
    foundingMembers: 0,
    quizSubmissions: 0,
    bioAgeScans: 0,
    newsletterSubscribers: 0,
    totalLeads: 0
  });
  
  const [partners, setPartners] = useState([]);
  const [partnerApplications, setPartnerApplications] = useState([]);
  const [waitlistEntries, setWaitlistEntries] = useState([]);
  const [foundingMembers, setFoundingMembers] = useState([]);
  const [quizSubmissions, setQuizSubmissions] = useState([]);
  const [bioAgeScans, setBioAgeScans] = useState([]);
  const [subscribers, setSubscribers] = useState([]);
  
  // Modal states
  const [selectedItem, setSelectedItem] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showSendOfferModal, setShowSendOfferModal] = useState(false);
  const [sendingOffer, setSendingOffer] = useState(false);
  const [exportingReport, setExportingReport] = useState(false);
  const [approvingPartner, setApprovingPartner] = useState(false);
  const [rejectingPartner, setRejectingPartner] = useState(false);
  const [offerData, setOfferData] = useState({
    type: 'email',
    subject: '',
    message: '',
    discount_code: '',
    discount_percent: 10
  });

  const token = localStorage.getItem('reroots_token');
  const headers = { Authorization: `Bearer ${token}` };
  
  // Update activeTab when initialTab changes
  useEffect(() => {
    if (initialTab && initialTab !== activeTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  // Fetch all data
  const fetchAllData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch data from multiple endpoints with brand filter
      const brandParam = `?brand=${activeBrand}`;
      const [
        partnersRes,
        applicationsRes,
        waitlistRes,
        foundersRes,
        quizRes,
        scansRes,
        subscribersRes
      ] = await Promise.allSettled([
        axios.get(`${API}/api/admin/influencers${brandParam}`, { headers }),
        axios.get(`${API}/api/admin/partner-applications${brandParam}`, { headers }),
        axios.get(`${API}/api/admin/waitlist${brandParam}`, { headers }),
        axios.get(`${API}/api/admin/founding-members${brandParam}`, { headers }),
        axios.get(`${API}/api/admin/quiz-submissions${brandParam}`, { headers }),
        axios.get(`${API}/api/admin/bio-age-scans${brandParam}`, { headers }),
        axios.get(`${API}/api/admin/subscribers${brandParam}`, { headers })
      ]);

      // Process partners
      if (partnersRes.status === 'fulfilled') {
        const pData = partnersRes.value.data;
        setPartners(pData.applications || []);
        setStats(prev => ({ ...prev, partners: pData.stats?.total || 0 }));
      }

      // Process applications
      if (applicationsRes.status === 'fulfilled') {
        setPartnerApplications(applicationsRes.value.data || []);
        setStats(prev => ({ ...prev, partnerApplications: applicationsRes.value.data?.length || 0 }));
      }

      // Process waitlist
      if (waitlistRes.status === 'fulfilled') {
        setWaitlistEntries(waitlistRes.value.data?.entries || waitlistRes.value.data || []);
        setStats(prev => ({ ...prev, waitlist: waitlistRes.value.data?.total || waitlistRes.value.data?.length || 0 }));
      }

      // Process founding members
      if (foundersRes.status === 'fulfilled') {
        setFoundingMembers(foundersRes.value.data?.members || foundersRes.value.data || []);
        setStats(prev => ({ ...prev, foundingMembers: foundersRes.value.data?.total || foundersRes.value.data?.length || 0 }));
      }

      // Process quiz submissions
      if (quizRes.status === 'fulfilled') {
        setQuizSubmissions(quizRes.value.data?.submissions || quizRes.value.data || []);
        setStats(prev => ({ ...prev, quizSubmissions: quizRes.value.data?.total || quizRes.value.data?.length || 0 }));
      }

      // Process bio-age scans
      if (scansRes.status === 'fulfilled') {
        setBioAgeScans(scansRes.value.data?.scans || scansRes.value.data || []);
        setStats(prev => ({ ...prev, bioAgeScans: scansRes.value.data?.total || scansRes.value.data?.length || 0 }));
      }

      // Process subscribers
      if (subscribersRes.status === 'fulfilled') {
        setSubscribers(subscribersRes.value.data?.subscribers || subscribersRes.value.data || []);
        setStats(prev => ({ ...prev, newsletterSubscribers: subscribersRes.value.data?.total || subscribersRes.value.data?.length || 0 }));
      }

      // Calculate total leads
      setStats(prev => ({
        ...prev,
        totalLeads: prev.partners + prev.waitlist + prev.foundingMembers + prev.quizSubmissions + prev.bioAgeScans + prev.newsletterSubscribers
      }));

    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to load some data');
    } finally {
      setLoading(false);
    }
  }, [activeBrand]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData, activeBrand]);

  // Export data as CSV
  const exportData = (dataType) => {
    let data, filename, headers;
    
    switch (dataType) {
      case 'partners':
        data = partners;
        filename = 'partners.csv';
        headers = ['Name', 'Email', 'Status', 'Code', 'Sales', 'Clicks'];
        break;
      case 'waitlist':
        data = waitlistEntries;
        filename = 'waitlist.csv';
        headers = ['Name', 'Email', 'Position', 'Joined'];
        break;
      case 'founding':
        data = foundingMembers;
        filename = 'founding_members.csv';
        headers = ['Name', 'Email', 'Position', 'Referral Code', 'Joined'];
        break;
      case 'quiz':
        data = quizSubmissions;
        filename = 'quiz_submissions.csv';
        headers = ['Email', 'Concern', 'Recommended Product', 'Submitted'];
        break;
      case 'subscribers':
        data = subscribers;
        filename = 'subscribers.csv';
        headers = ['Email', 'Subscribed'];
        break;
      default:
        return;
    }

    if (!data || data.length === 0) {
      toast.error('No data to export');
      return;
    }

    // Create CSV
    const csvContent = [
      headers.join(','),
      ...data.map(row => {
        switch (dataType) {
          case 'partners':
            return [row.name, row.email, row.status, row.partner_code || row.code, row.sales || 0, row.clicks || 0].join(',');
          case 'waitlist':
            return [row.name, row.email, row.position, row.created_at?.split('T')[0]].join(',');
          case 'founding':
            return [row.name, row.email, row.position, row.referral_code, row.created_at?.split('T')[0]].join(',');
          case 'quiz':
            return [row.email, row.primary_concern, row.recommended_product, row.created_at?.split('T')[0]].join(',');
          case 'subscribers':
            return [row.email, row.created_at?.split('T')[0]].join(',');
          default:
            return '';
        }
      })
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
    toast.success(`Exported ${data.length} records to ${filename}`);
  };

  // Export Lab-Ready Concern Report
  const exportConcernReport = async () => {
    setExportingReport(true);
    try {
      const response = await axios.get(`${API}/api/admin/export/concern-report`, { headers });
      const { data, columns, total_records, generated_at } = response.data;
      
      if (!data || data.length === 0) {
        toast.error('No scan data to export');
        setExportingReport(false);
        return;
      }

      // Create clean CSV with proper escaping
      const escapeCSV = (value) => {
        if (value === null || value === undefined) return '';
        const str = String(value);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      };

      // Lab-ready headers
      const csvHeaders = [
        'Email', 'Phone', 'Whapi Verified', 'Name', 'Actual Age', 'Bio-Age',
        'Age Gap', 'Top Concerns', 'Skin Type', 'Recommended Products',
        'Referral Code', 'Verified Referrals', 'Scan Date', 'Source'
      ];

      const csvRows = data.map(row => [
        escapeCSV(row.email),
        escapeCSV(row.phone),
        escapeCSV(row.whapi_verified),
        escapeCSV(row.name),
        escapeCSV(row.actual_age),
        escapeCSV(row.bio_age),
        escapeCSV(row.age_gap),
        escapeCSV(row.top_concerns),
        escapeCSV(row.skin_type),
        escapeCSV(row.recommended_products),
        escapeCSV(row.referral_code),
        escapeCSV(row.verified_referrals),
        escapeCSV(row.scan_date),
        escapeCSV(row.source)
      ].join(','));

      const csvContent = [csvHeaders.join(','), ...csvRows].join('\n');
      
      // Generate filename with date
      const dateStr = new Date().toISOString().split('T')[0];
      const filename = `${shortName}_Lab_Concern_Report_${dateStr}.csv`;

      // Download
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      toast.success(`Lab Report exported: ${total_records} records`);
    } catch (error) {
      console.error('Export error:', error);
      toast.error(error.response?.data?.detail || 'Failed to export concern report');
    } finally {
      setExportingReport(false);
    }
  };

  // Send offer/message
  const sendOffer = async () => {
    if (!selectedItem?.email) {
      toast.error('No email address available');
      return;
    }

    setSendingOffer(true);
    try {
      await axios.post(`${API}/api/admin/send-offer`, {
        email: selectedItem.email,
        name: selectedItem.name || 'Valued Customer',
        ...offerData
      }, { headers });
      
      toast.success(`Offer sent to ${selectedItem.email}!`);
      setShowSendOfferModal(false);
      setOfferData({ type: 'email', subject: '', message: '', discount_code: '', discount_percent: 10 });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to send offer');
    } finally {
      setSendingOffer(false);
    }
  };

  // Copy email
  const copyEmail = (email) => {
    navigator.clipboard.writeText(email);
    toast.success('Email copied!');
  };

  // Approve partner application
  const approvePartner = async (partnerId) => {
    setApprovingPartner(true);
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.put(`${API}/api/admin/influencers/${partnerId}/approve`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Partner approved! Their code has been generated.');
      setShowDetailModal(false);
      loadData(); // Refresh data
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to approve partner');
    } finally {
      setApprovingPartner(false);
    }
  };

  // Reject partner application
  const rejectPartner = async (partnerId, reason = "Does not meet requirements at this time") => {
    setRejectingPartner(true);
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.put(`${API}/api/admin/influencers/${partnerId}/reject`, { reason }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Partner application rejected');
      setShowDetailModal(false);
      loadData(); // Refresh data
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to reject partner');
    } finally {
      setRejectingPartner(false);
    }
  };

  // Open detail modal
  const openDetail = (item, type) => {
    setSelectedItem({ ...item, _type: type });
    setShowDetailModal(true);
  };

  // Filter data by search
  const filterData = (data) => {
    if (!searchQuery.trim()) return data;
    const q = searchQuery.toLowerCase();
    return data.filter(item => 
      item.email?.toLowerCase().includes(q) ||
      item.name?.toLowerCase().includes(q) ||
      item.first_name?.toLowerCase().includes(q)
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-pink-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-[#2D2A2E] flex items-center gap-2">
            <Database className="h-6 w-6 text-pink-500" />
            Data Hub
          </h2>
          <p className="text-sm text-[#5A5A5A]">Your gold mine - all collected leads, partners, and program data</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchAllData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Lab Export Banner */}
      <Card className="bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-200" data-testid="concern-report-banner">
        <CardContent className="p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500">
              <TestTube className="h-6 w-6 text-white" />
            </div>
            <div>
              <p className="font-semibold text-[#2D2A2E]">Lab-Ready Concern Report</p>
              <p className="text-sm text-[#5A5A5A]">Export Bio-Age data, skin concerns & referral stats for R&D analysis</p>
            </div>
          </div>
          <Button 
            className="bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600"
            onClick={exportConcernReport}
            disabled={exportingReport}
            data-testid="export-concern-report-btn"
          >
            {exportingReport ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Download className="h-4 w-4 mr-2" />
                Download Concern Report
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <StatCard 
          label="Partners/Influencers" 
          value={stats.partners} 
          icon={Star} 
          color="purple"
          onClick={() => setActiveTab('partners')}
        />
        <StatCard 
          label="Waitlist" 
          value={stats.waitlist} 
          icon={ClipboardList} 
          color="blue"
          onClick={() => setActiveTab('waitlist')}
        />
        <StatCard 
          label="Founding Members" 
          value={stats.foundingMembers} 
          icon={Crown} 
          color="yellow"
          onClick={() => setActiveTab('founding')}
        />
        <StatCard 
          label="Quiz Submissions" 
          value={stats.quizSubmissions} 
          icon={Sparkles} 
          color="pink"
          onClick={() => setActiveTab('quiz')}
        />
        <StatCard 
          label="Bio-Age Scans" 
          value={stats.bioAgeScans} 
          icon={TestTube} 
          color="green"
          onClick={() => setActiveTab('scans')}
        />
        <StatCard 
          label="Newsletter" 
          value={stats.newsletterSubscribers} 
          icon={Mail} 
          color="orange"
          onClick={() => setActiveTab('subscribers')}
        />
      </div>

      {/* Total Leads Banner */}
      <Card className="bg-gradient-to-r from-pink-50 to-purple-50 border-pink-200">
        <CardContent className="p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-full bg-gradient-to-r from-pink-500 to-purple-500">
              <TrendingUp className="h-6 w-6 text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[#2D2A2E]">{stats.totalLeads} Total Leads</p>
              <p className="text-sm text-[#5A5A5A]">Collected across all programs</p>
            </div>
          </div>
          <Button 
            className="bg-gradient-to-r from-pink-500 to-purple-500 text-white"
            onClick={() => exportData('all')}
          >
            <Download className="h-4 w-4 mr-2" />
            Export All
          </Button>
        </CardContent>
      </Card>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input
          placeholder="Search by name or email..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Data Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-6 mb-4">
          <TabsTrigger value="partners" className="flex items-center gap-1">
            <Star className="h-4 w-4" />
            <span className="hidden sm:inline">Partners</span>
          </TabsTrigger>
          <TabsTrigger value="waitlist" className="flex items-center gap-1">
            <ClipboardList className="h-4 w-4" />
            <span className="hidden sm:inline">Waitlist</span>
          </TabsTrigger>
          <TabsTrigger value="founding" className="flex items-center gap-1">
            <Crown className="h-4 w-4" />
            <span className="hidden sm:inline">Founders</span>
          </TabsTrigger>
          <TabsTrigger value="quiz" className="flex items-center gap-1">
            <Sparkles className="h-4 w-4" />
            <span className="hidden sm:inline">Quiz</span>
          </TabsTrigger>
          <TabsTrigger value="scans" className="flex items-center gap-1">
            <TestTube className="h-4 w-4" />
            <span className="hidden sm:inline">Scans</span>
          </TabsTrigger>
          <TabsTrigger value="subscribers" className="flex items-center gap-1">
            <Mail className="h-4 w-4" />
            <span className="hidden sm:inline">Email</span>
          </TabsTrigger>
        </TabsList>

        {/* Partners Tab */}
        <TabsContent value="partners">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Partners & Influencers</CardTitle>
                <CardDescription>{partners.length} partners in your program</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => exportData('partners')}>
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </CardHeader>
            <CardContent>
              <DataTable
                data={filterData(partners)}
                columns={[
                  { header: 'Name', key: 'name', render: (row) => (
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
                        <span className="text-purple-600 font-medium text-sm">
                          {(row.name || 'P')[0].toUpperCase()}
                        </span>
                      </div>
                      <span className="font-medium">{row.name || 'Partner'}</span>
                    </div>
                  )},
                  { header: 'Email', key: 'email', render: (row) => (
                    <div className="flex items-center gap-2">
                      <span className="text-gray-600">{row.email}</span>
                      <button onClick={(e) => { e.stopPropagation(); copyEmail(row.email); }}>
                        <Copy className="h-3 w-3 text-gray-400 hover:text-pink-500" />
                      </button>
                    </div>
                  )},
                  { header: 'Status', key: 'status', render: (row) => (
                    <Badge className={
                      row.status === 'approved' ? 'bg-green-100 text-green-700' :
                      row.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-700'
                    }>
                      {row.status || 'pending'}
                    </Badge>
                  )},
                  { header: 'Code', key: 'partner_code', render: (row) => (
                    <code className="bg-gray-100 px-2 py-1 rounded text-xs">
                      {row.partner_code || row.code || 'N/A'}
                    </code>
                  )},
                  { header: 'Sales', key: 'sales', render: (row) => (
                    <span className="font-medium text-green-600">${row.sales || 0}</span>
                  )},
                  { header: 'Actions', key: 'actions', render: (row) => (
                    <Button 
                      size="sm" 
                      variant="ghost"
                      onClick={(e) => { e.stopPropagation(); setSelectedItem(row); setShowSendOfferModal(true); }}
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  )}
                ]}
                onRowClick={(row) => openDetail(row, 'partner')}
                emptyMessage="No partners yet. Share your partner program to recruit influencers!"
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Waitlist Tab */}
        <TabsContent value="waitlist">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Waitlist Signups</CardTitle>
                <CardDescription>{waitlistEntries.length} people waiting for access</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => exportData('waitlist')}>
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </CardHeader>
            <CardContent>
              <DataTable
                data={filterData(waitlistEntries)}
                columns={[
                  { header: 'Name', key: 'name' },
                  { header: 'Email', key: 'email', render: (row) => (
                    <div className="flex items-center gap-2">
                      <span>{row.email}</span>
                      <button onClick={(e) => { e.stopPropagation(); copyEmail(row.email); }}>
                        <Copy className="h-3 w-3 text-gray-400 hover:text-pink-500" />
                      </button>
                    </div>
                  )},
                  { header: 'Position', key: 'position', render: (row) => (
                    <Badge className="bg-blue-100 text-blue-700">#{row.position}</Badge>
                  )},
                  { header: 'Referrals', key: 'referral_count', render: (row) => row.referral_count || 0 },
                  { header: 'Joined', key: 'created_at', render: (row) => row.created_at?.split('T')[0] },
                  { header: 'Actions', key: 'actions', render: (row) => (
                    <Button 
                      size="sm" 
                      variant="ghost"
                      onClick={(e) => { e.stopPropagation(); setSelectedItem(row); setShowSendOfferModal(true); }}
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  )}
                ]}
                onRowClick={(row) => openDetail(row, 'waitlist')}
                emptyMessage="No waitlist signups yet"
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Founding Members Tab */}
        <TabsContent value="founding">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Founding Members</CardTitle>
                <CardDescription>{foundingMembers.length} exclusive founding members</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => exportData('founding')}>
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </CardHeader>
            <CardContent>
              <DataTable
                data={filterData(foundingMembers)}
                columns={[
                  { header: 'Name', key: 'name', render: (row) => (
                    <div className="flex items-center gap-2">
                      <Crown className="h-4 w-4 text-yellow-500" />
                      <span className="font-medium">{row.name || 'Member'}</span>
                    </div>
                  )},
                  { header: 'Email', key: 'email', render: (row) => (
                    <div className="flex items-center gap-2">
                      <span>{row.email}</span>
                      <button onClick={(e) => { e.stopPropagation(); copyEmail(row.email); }}>
                        <Copy className="h-3 w-3 text-gray-400 hover:text-pink-500" />
                      </button>
                    </div>
                  )},
                  { header: 'Position', key: 'position', render: (row) => (
                    <Badge className="bg-yellow-100 text-yellow-700">#{row.position}</Badge>
                  )},
                  { header: 'Referral Code', key: 'referral_code', render: (row) => (
                    <code className="bg-gray-100 px-2 py-1 rounded text-xs">{row.referral_code}</code>
                  )},
                  { header: 'Referrals', key: 'referral_count', render: (row) => row.referral_count || 0 },
                  { header: 'Joined', key: 'created_at', render: (row) => row.created_at?.split('T')[0] },
                ]}
                onRowClick={(row) => openDetail(row, 'founding')}
                emptyMessage="No founding members yet"
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Quiz Submissions Tab */}
        <TabsContent value="quiz">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Quiz Submissions</CardTitle>
                <CardDescription>{quizSubmissions.length} quiz completions with email capture</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => exportData('quiz')}>
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </CardHeader>
            <CardContent>
              <DataTable
                data={filterData(quizSubmissions)}
                columns={[
                  { header: 'Email', key: 'email', render: (row) => (
                    <div className="flex items-center gap-2">
                      <span>{row.email}</span>
                      <button onClick={(e) => { e.stopPropagation(); copyEmail(row.email); }}>
                        <Copy className="h-3 w-3 text-gray-400 hover:text-pink-500" />
                      </button>
                    </div>
                  )},
                  { header: 'Primary Concern', key: 'primary_concern', render: (row) => (
                    <Badge className="bg-pink-100 text-pink-700">
                      {row.primary_concern || row.concern || 'General'}
                    </Badge>
                  )},
                  { header: 'Recommended', key: 'recommended_product', render: (row) => (
                    <span className="font-medium text-purple-600">
                      {row.recommended_product || 'AURA-GEN'}
                    </span>
                  )},
                  { header: 'Age Group', key: 'age_group' },
                  { header: 'Submitted', key: 'created_at', render: (row) => row.created_at?.split('T')[0] },
                  { header: 'Actions', key: 'actions', render: (row) => (
                    <Button 
                      size="sm" 
                      variant="ghost"
                      onClick={(e) => { e.stopPropagation(); setSelectedItem(row); setShowSendOfferModal(true); }}
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  )}
                ]}
                onRowClick={(row) => openDetail(row, 'quiz')}
                emptyMessage="No quiz submissions yet. Share the quiz to capture leads!"
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Bio-Age Scans Tab */}
        <TabsContent value="scans">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Bio-Age Scan Results</CardTitle>
                <CardDescription>{bioAgeScans.length} scan completions</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => exportData('scans')}>
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </CardHeader>
            <CardContent>
              <DataTable
                data={filterData(bioAgeScans)}
                columns={[
                  { header: 'Email', key: 'email' },
                  { header: 'Bio-Age Result', key: 'bio_age', render: (row) => (
                    <span className="font-medium">{row.bio_age || row.result || 'N/A'}</span>
                  )},
                  { header: 'Concerns', key: 'concerns', render: (row) => (
                    <div className="flex gap-1 flex-wrap">
                      {(row.concerns || []).slice(0, 2).map((c, i) => (
                        <Badge key={i} variant="outline" className="text-xs">{c}</Badge>
                      ))}
                    </div>
                  )},
                  { header: 'Scanned', key: 'created_at', render: (row) => row.created_at?.split('T')[0] },
                ]}
                onRowClick={(row) => openDetail(row, 'scan')}
                emptyMessage="No bio-age scans yet"
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Subscribers Tab */}
        <TabsContent value="subscribers">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Newsletter Subscribers</CardTitle>
                <CardDescription>{subscribers.length} email subscribers</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => exportData('subscribers')}>
                <Download className="h-4 w-4 mr-2" />
                Export CSV
              </Button>
            </CardHeader>
            <CardContent>
              <DataTable
                data={filterData(subscribers)}
                columns={[
                  { header: 'Email', key: 'email', render: (row) => (
                    <div className="flex items-center gap-2">
                      <Mail className="h-4 w-4 text-orange-500" />
                      <span>{row.email}</span>
                      <button onClick={(e) => { e.stopPropagation(); copyEmail(row.email); }}>
                        <Copy className="h-3 w-3 text-gray-400 hover:text-pink-500" />
                      </button>
                    </div>
                  )},
                  { header: 'Source', key: 'source', render: (row) => row.source || 'Website' },
                  { header: 'Subscribed', key: 'created_at', render: (row) => row.created_at?.split('T')[0] },
                  { header: 'Actions', key: 'actions', render: (row) => (
                    <Button 
                      size="sm" 
                      variant="ghost"
                      onClick={(e) => { e.stopPropagation(); setSelectedItem(row); setShowSendOfferModal(true); }}
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  )}
                ]}
                onRowClick={(row) => openDetail(row, 'subscriber')}
                emptyMessage="No subscribers yet"
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Detail Modal */}
      <Dialog open={showDetailModal} onOpenChange={setShowDetailModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selectedItem?._type === 'partner' && <Star className="h-5 w-5 text-purple-500" />}
              {selectedItem?._type === 'founding' && <Crown className="h-5 w-5 text-yellow-500" />}
              {selectedItem?._type === 'quiz' && <Sparkles className="h-5 w-5 text-pink-500" />}
              {selectedItem?.name || selectedItem?.email || 'Details'}
            </DialogTitle>
          </DialogHeader>
          {selectedItem && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                {Object.entries(selectedItem).filter(([k]) => !k.startsWith('_') && k !== 'id').map(([key, value]) => (
                  <div key={key} className="space-y-1">
                    <Label className="text-gray-500 capitalize">{key.replace(/_/g, ' ')}</Label>
                    <p className="font-medium">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</p>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 pt-4 border-t flex-wrap">
                {/* Approve/Reject for pending partners */}
                {selectedItem._type === 'partner' && selectedItem.status === 'pending' && (
                  <>
                    <Button 
                      className="flex-1 bg-green-500 hover:bg-green-600 text-white"
                      onClick={() => approvePartner(selectedItem.id)}
                      disabled={approvingPartner || rejectingPartner}
                    >
                      {approvingPartner ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
                      Approve Partner
                    </Button>
                    <Button 
                      variant="destructive"
                      className="flex-1"
                      onClick={() => rejectPartner(selectedItem.id)}
                      disabled={approvingPartner || rejectingPartner}
                    >
                      {rejectingPartner ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <X className="h-4 w-4 mr-2" />}
                      Reject
                    </Button>
                  </>
                )}
                {/* Regular actions */}
                {!(selectedItem._type === 'partner' && selectedItem.status === 'pending') && (
                  <>
                    <Button 
                      className="flex-1"
                      onClick={() => { setShowDetailModal(false); setShowSendOfferModal(true); }}
                    >
                      <Send className="h-4 w-4 mr-2" />
                      Send Offer
                    </Button>
                    <Button variant="outline" onClick={() => copyEmail(selectedItem.email)}>
                      <Copy className="h-4 w-4 mr-2" />
                      Copy Email
                    </Button>
                  </>
                )}
                {/* Copy email for pending partners too */}
                {selectedItem._type === 'partner' && selectedItem.status === 'pending' && (
                  <Button variant="outline" onClick={() => copyEmail(selectedItem.email)} className="w-full mt-2">
                    <Copy className="h-4 w-4 mr-2" />
                    Copy Email
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Send Offer Modal */}
      <Dialog open={showSendOfferModal} onOpenChange={setShowSendOfferModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Send Offer to {selectedItem?.name || selectedItem?.email}</DialogTitle>
            <DialogDescription>
              Send a personalized offer or message to this lead
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Subject</Label>
              <Input
                value={offerData.subject}
                onChange={(e) => setOfferData({ ...offerData, subject: e.target.value })}
                placeholder="Special offer just for you!"
              />
            </div>
            <div>
              <Label>Message</Label>
              <Textarea
                value={offerData.message}
                onChange={(e) => setOfferData({ ...offerData, message: e.target.value })}
                placeholder="Write your personalized message..."
                rows={4}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Discount Code</Label>
                <Input
                  value={offerData.discount_code}
                  onChange={(e) => setOfferData({ ...offerData, discount_code: e.target.value.toUpperCase() })}
                  placeholder="SPECIAL20"
                />
              </div>
              <div>
                <Label>Discount %</Label>
                <Input
                  type="number"
                  value={offerData.discount_percent}
                  onChange={(e) => setOfferData({ ...offerData, discount_percent: parseInt(e.target.value) })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSendOfferModal(false)}>
              Cancel
            </Button>
            <Button onClick={sendOffer} disabled={sendingOffer}>
              {sendingOffer ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
              Send Offer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default DataHub;
