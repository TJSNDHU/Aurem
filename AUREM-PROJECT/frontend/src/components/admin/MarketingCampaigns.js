import React, { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { 
  Megaphone, Plus, Search, Edit, Trash2, Calendar, Tag,
  DollarSign, Percent, Users, TrendingUp, Copy, Eye, EyeOff,
  Play, Pause, BarChart3
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const MarketingCampaigns = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingCampaign, setEditingCampaign] = useState(null);
  const [isCreating, setIsCreating] = useState(false);

  // Load campaigns
  useEffect(() => {
    const saved = localStorage.getItem('reroots_campaigns');
    if (saved) {
      setCampaigns(JSON.parse(saved));
    } else {
      setCampaigns([
        {
          id: '1',
          name: 'New Year Sale',
          description: '20% off all products',
          type: 'discount',
          discountType: 'percent',
          discountValue: 20,
          code: 'NEWYEAR20',
          startDate: '2025-01-01',
          endDate: '2025-01-15',
          active: false,
          stats: { clicks: 234, conversions: 45, revenue: 2340 }
        },
        {
          id: '2',
          name: 'VIP Early Access',
          description: 'Exclusive early access for VIP customers',
          type: 'exclusive',
          discountType: 'percent',
          discountValue: 15,
          code: 'VIPACCESS',
          startDate: '2025-02-01',
          endDate: '2025-02-28',
          active: true,
          stats: { clicks: 89, conversions: 12, revenue: 890 }
        }
      ]);
    }
    setLoading(false);
  }, []);

  const saveCampaigns = (newCampaigns) => {
    setCampaigns(newCampaigns);
    localStorage.setItem('reroots_campaigns', JSON.stringify(newCampaigns));
  };

  const generateCode = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let code = '';
    for (let i = 0; i < 8; i++) {
      code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return code;
  };

  const handleCreateCampaign = () => {
    const today = new Date().toISOString().split('T')[0];
    const nextMonth = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    
    setEditingCampaign({
      id: Date.now().toString(),
      name: '',
      description: '',
      type: 'discount',
      discountType: 'percent',
      discountValue: 10,
      code: generateCode(),
      startDate: today,
      endDate: nextMonth,
      active: false,
      stats: { clicks: 0, conversions: 0, revenue: 0 }
    });
    setIsCreating(true);
  };

  const handleSaveCampaign = () => {
    if (!editingCampaign.name.trim()) {
      toast.error('Campaign name is required');
      return;
    }
    if (!editingCampaign.code.trim()) {
      toast.error('Discount code is required');
      return;
    }

    let newCampaigns;
    if (isCreating) {
      newCampaigns = [editingCampaign, ...campaigns];
      toast.success('Campaign created!');
    } else {
      newCampaigns = campaigns.map(c => c.id === editingCampaign.id ? editingCampaign : c);
      toast.success('Campaign updated!');
    }

    saveCampaigns(newCampaigns);
    setEditingCampaign(null);
  };

  const handleDeleteCampaign = (id) => {
    if (!window.confirm('Delete this campaign?')) return;
    saveCampaigns(campaigns.filter(c => c.id !== id));
    toast.success('Campaign deleted');
  };

  const toggleCampaign = (id) => {
    const newCampaigns = campaigns.map(c => 
      c.id === id ? { ...c, active: !c.active } : c
    );
    saveCampaigns(newCampaigns);
    toast.success(newCampaigns.find(c => c.id === id)?.active ? 'Campaign activated!' : 'Campaign paused');
  };

  const copyCode = (code) => {
    navigator.clipboard.writeText(code);
    toast.success('Code copied!');
  };

  const getCampaignStatus = (campaign) => {
    const now = new Date();
    const start = new Date(campaign.startDate);
    const end = new Date(campaign.endDate);

    if (!campaign.active) return { label: 'Paused', color: 'bg-gray-500' };
    if (now < start) return { label: 'Scheduled', color: 'bg-blue-500' };
    if (now > end) return { label: 'Ended', color: 'bg-red-500' };
    return { label: 'Active', color: 'bg-green-500' };
  };

  const filteredCampaigns = campaigns.filter(c =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const stats = {
    active: campaigns.filter(c => c.active).length,
    totalClicks: campaigns.reduce((sum, c) => sum + (c.stats?.clicks || 0), 0),
    totalConversions: campaigns.reduce((sum, c) => sum + (c.stats?.conversions || 0), 0),
    totalRevenue: campaigns.reduce((sum, c) => sum + (c.stats?.revenue || 0), 0)
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#F8A5B8] border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#2D2A2E]">Marketing Campaigns</h1>
          <p className="text-[#5A5A5A]">Create and manage promotional campaigns</p>
        </div>
        <Button onClick={handleCreateCampaign} className="bg-[#F8A5B8] hover:bg-[#E88DA0] text-white gap-2">
          <Plus className="h-4 w-4" />
          Create Campaign
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-100">
                <Play className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600">{stats.active}</p>
                <p className="text-sm text-[#5A5A5A]">Active</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100">
                <Eye className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-blue-600">{stats.totalClicks}</p>
                <p className="text-sm text-[#5A5A5A]">Total Clicks</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-100">
                <Users className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-purple-600">{stats.totalConversions}</p>
                <p className="text-sm text-[#5A5A5A]">Conversions</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-orange-100">
                <DollarSign className="h-5 w-5 text-orange-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-orange-600">${stats.totalRevenue}</p>
                <p className="text-sm text-[#5A5A5A]">Revenue</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#5A5A5A]" />
        <Input
          placeholder="Search campaigns..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Campaigns List */}
      <div className="space-y-4">
        {filteredCampaigns.map((campaign) => {
          const status = getCampaignStatus(campaign);
          return (
            <Card key={campaign.id} className="overflow-hidden">
              <CardContent className="p-4">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                  {/* Campaign Info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-semibold text-[#2D2A2E]">{campaign.name}</h3>
                      <Badge className={`${status.color} text-white`}>{status.label}</Badge>
                    </div>
                    <p className="text-sm text-[#5A5A5A] mb-2">{campaign.description}</p>
                    <div className="flex flex-wrap items-center gap-4 text-sm">
                      <span className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded font-mono">
                        <Tag className="h-3 w-3" />
                        {campaign.code}
                        <button onClick={() => copyCode(campaign.code)} className="ml-1 hover:text-[#F8A5B8]">
                          <Copy className="h-3 w-3" />
                        </button>
                      </span>
                      <span className="flex items-center gap-1 text-[#5A5A5A]">
                        {campaign.discountType === 'percent' ? <Percent className="h-3 w-3" /> : <DollarSign className="h-3 w-3" />}
                        {campaign.discountValue}{campaign.discountType === 'percent' ? '%' : ''} off
                      </span>
                      <span className="flex items-center gap-1 text-[#5A5A5A]">
                        <Calendar className="h-3 w-3" />
                        {campaign.startDate} - {campaign.endDate}
                      </span>
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="flex items-center gap-6 text-sm">
                    <div className="text-center">
                      <p className="font-bold text-[#2D2A2E]">{campaign.stats?.clicks || 0}</p>
                      <p className="text-[#5A5A5A]">Clicks</p>
                    </div>
                    <div className="text-center">
                      <p className="font-bold text-[#2D2A2E]">{campaign.stats?.conversions || 0}</p>
                      <p className="text-[#5A5A5A]">Sales</p>
                    </div>
                    <div className="text-center">
                      <p className="font-bold text-green-600">${campaign.stats?.revenue || 0}</p>
                      <p className="text-[#5A5A5A]">Revenue</p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant={campaign.active ? 'outline' : 'default'}
                      onClick={() => toggleCampaign(campaign.id)}
                      className={!campaign.active ? 'bg-green-500 hover:bg-green-600 text-white' : ''}
                    >
                      {campaign.active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditingCampaign(campaign);
                        setIsCreating(false);
                      }}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDeleteCampaign(campaign.id)}
                      className="text-red-500 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}

        {filteredCampaigns.length === 0 && (
          <Card className="p-8 text-center">
            <Megaphone className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-[#5A5A5A]">No campaigns yet</p>
            <Button onClick={handleCreateCampaign} variant="link" className="text-[#F8A5B8]">
              Create your first campaign
            </Button>
          </Card>
        )}
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={!!editingCampaign} onOpenChange={() => setEditingCampaign(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{isCreating ? 'Create Campaign' : 'Edit Campaign'}</DialogTitle>
          </DialogHeader>
          {editingCampaign && (
            <div className="space-y-4 py-4">
              <div>
                <Label>Campaign Name *</Label>
                <Input
                  value={editingCampaign.name}
                  onChange={(e) => setEditingCampaign({ ...editingCampaign, name: e.target.value })}
                  placeholder="e.g., Summer Sale"
                />
              </div>

              <div>
                <Label>Description</Label>
                <Textarea
                  value={editingCampaign.description}
                  onChange={(e) => setEditingCampaign({ ...editingCampaign, description: e.target.value })}
                  placeholder="Describe this campaign..."
                  rows={2}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Discount Code *</Label>
                  <div className="flex gap-2">
                    <Input
                      value={editingCampaign.code}
                      onChange={(e) => setEditingCampaign({ ...editingCampaign, code: e.target.value.toUpperCase() })}
                      placeholder="CODE"
                      className="font-mono"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setEditingCampaign({ ...editingCampaign, code: generateCode() })}
                    >
                      Generate
                    </Button>
                  </div>
                </div>
                <div>
                  <Label>Discount</Label>
                  <div className="flex gap-2">
                    <Input
                      type="number"
                      value={editingCampaign.discountValue}
                      onChange={(e) => setEditingCampaign({ ...editingCampaign, discountValue: parseFloat(e.target.value) || 0 })}
                      className="flex-1"
                    />
                    <Select
                      value={editingCampaign.discountType}
                      onValueChange={(value) => setEditingCampaign({ ...editingCampaign, discountType: value })}
                    >
                      <SelectTrigger className="w-20">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="percent">%</SelectItem>
                        <SelectItem value="fixed">$</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Start Date</Label>
                  <Input
                    type="date"
                    value={editingCampaign.startDate}
                    onChange={(e) => setEditingCampaign({ ...editingCampaign, startDate: e.target.value })}
                  />
                </div>
                <div>
                  <Label>End Date</Label>
                  <Input
                    type="date"
                    value={editingCampaign.endDate}
                    onChange={(e) => setEditingCampaign({ ...editingCampaign, endDate: e.target.value })}
                  />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={editingCampaign.active}
                  onCheckedChange={(checked) => setEditingCampaign({ ...editingCampaign, active: checked })}
                />
                <Label>Activate campaign immediately</Label>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setEditingCampaign(null)}>
                  Cancel
                </Button>
                <Button onClick={handleSaveCampaign} className="bg-[#F8A5B8] hover:bg-[#E88DA0] text-white">
                  {isCreating ? 'Create Campaign' : 'Save Changes'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default MarketingCampaigns;
