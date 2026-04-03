import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

// UI Components
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Textarea } from '../ui/textarea';

// Icons
import { 
  Settings, Users, Coins, TrendingUp, TrendingDown, Gift,
  Save, RefreshCw, AlertCircle, Check, Search, Plus, Minus,
  DollarSign, Sparkles, ArrowUpRight, ArrowDownRight
} from 'lucide-react';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const LoyaltyPointsManager = () => {
  const [activeTab, setActiveTab] = useState('settings');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Config state
  const [config, setConfig] = useState({
    points_per_product: 250,
    point_value: 0.05,
    points_per_dollar: 20,
    points_for_30_discount: 600,
    thirty_percent_discount: 30,
    max_redemption_percent: 30,  // 30% cap on redemption
    thirty_percent_discount: 30,
    enabled: true,
    allow_gift_points: true,
    allow_buy_points: true,
  });
  
  // Users state
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  
  // Adjust points dialog
  const [showAdjustDialog, setShowAdjustDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [adjustAmount, setAdjustAmount] = useState('');
  const [adjustReason, setAdjustReason] = useState('');
  const [adjusting, setAdjusting] = useState(false);

  const token = localStorage.getItem('reroots_token');
  const headers = { Authorization: `Bearer ${token}` };

  // Load config
  const loadConfig = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/loyalty/config`);
      setConfig(res.data);
    } catch (err) {
      console.error('Failed to load loyalty config:', err);
      toast.error('Failed to load loyalty settings');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load users with points
  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const res = await axios.get(`${API}/admin/loyalty/users`, { headers });
      setUsers(res.data.users || []);
    } catch (err) {
      console.error('Failed to load users:', err);
      toast.error('Failed to load users');
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
    loadUsers();
  }, [loadConfig, loadUsers]);

  // Save config
  const saveConfig = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/admin/loyalty/config`, config, { headers });
      toast.success('Loyalty settings saved!');
    } catch (err) {
      console.error('Failed to save config:', err);
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  // Adjust user points
  const handleAdjustPoints = async () => {
    if (!selectedUser || !adjustAmount || !adjustReason) {
      toast.error('Please fill in all fields');
      return;
    }

    setAdjusting(true);
    try {
      const res = await axios.post(`${API}/admin/loyalty/adjust-points`, {
        user_email: selectedUser.email,
        adjustment: parseInt(adjustAmount),
        reason: adjustReason
      }, { headers });

      toast.success(`Points adjusted! New balance: ${res.data.new_balance}`);
      setShowAdjustDialog(false);
      setSelectedUser(null);
      setAdjustAmount('');
      setAdjustReason('');
      loadUsers(); // Refresh users list
    } catch (err) {
      console.error('Failed to adjust points:', err);
      toast.error(err.response?.data?.detail || 'Failed to adjust points');
    } finally {
      setAdjusting(false);
    }
  };

  // Filter users by search
  const filteredUsers = users.filter(user => 
    user.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Calculate dollar value from points
  const getPointsValue = (points) => {
    return (points * config.point_value).toFixed(2);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="loyalty-points-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-amber-500" />
            Loyalty Points Manager
          </h2>
          <p className="text-gray-500 mt-1">Configure points earning and manage customer balances</p>
        </div>
        
        <Badge variant={config.enabled ? "default" : "secondary"} className={config.enabled ? "bg-green-500" : ""}>
          {config.enabled ? 'Active' : 'Disabled'}
        </Badge>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Points Per Purchase</p>
                <p className="text-2xl font-bold text-[#2D2A2E]">{config.points_per_product}</p>
              </div>
              <Coins className="h-8 w-8 text-amber-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Point Value</p>
                <p className="text-2xl font-bold text-[#2D2A2E]">${config.point_value}</p>
              </div>
              <DollarSign className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Points Per $1</p>
                <p className="text-2xl font-bold text-[#2D2A2E]">{config.points_per_dollar}</p>
              </div>
              <TrendingUp className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Members</p>
                <p className="text-2xl font-bold text-[#2D2A2E]">{users.length}</p>
              </div>
              <Users className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="settings" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Settings
          </TabsTrigger>
          <TabsTrigger value="members" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Members ({users.length})
          </TabsTrigger>
        </TabsList>

        {/* Settings Tab */}
        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle>Loyalty Program Configuration</CardTitle>
              <CardDescription>
                Configure how customers earn and redeem points
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Enable/Disable Toggle */}
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <Label className="text-base font-medium">Enable Loyalty Program</Label>
                  <p className="text-sm text-gray-500">Turn the entire loyalty program on or off</p>
                </div>
                <Switch
                  checked={config.enabled}
                  onCheckedChange={(checked) => setConfig({ ...config, enabled: checked })}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Points Per Product */}
                <div className="space-y-2">
                  <Label htmlFor="points_per_product">Points Earned Per Product</Label>
                  <Input
                    id="points_per_product"
                    type="number"
                    min="0"
                    value={config.points_per_product}
                    onChange={(e) => setConfig({ ...config, points_per_product: parseInt(e.target.value) || 0 })}
                    className="font-mono"
                  />
                  <p className="text-xs text-gray-500">
                    Each product purchased earns this many points
                  </p>
                </div>

                {/* Point Value */}
                <div className="space-y-2">
                  <Label htmlFor="point_value">Point Value ($)</Label>
                  <Input
                    id="point_value"
                    type="number"
                    step="0.01"
                    min="0"
                    value={config.point_value}
                    onChange={(e) => setConfig({ ...config, point_value: parseFloat(e.target.value) || 0 })}
                    className="font-mono"
                  />
                  <p className="text-xs text-gray-500">
                    {config.point_value > 0 ? `${Math.round(1 / config.point_value)} points = $1.00` : 'Set a value'}
                  </p>
                </div>

                {/* Points Per Dollar (for buying) */}
                <div className="space-y-2">
                  <Label htmlFor="points_per_dollar">Points Per Dollar (Buying)</Label>
                  <Input
                    id="points_per_dollar"
                    type="number"
                    min="1"
                    value={config.points_per_dollar}
                    onChange={(e) => setConfig({ ...config, points_per_dollar: parseInt(e.target.value) || 20 })}
                    className="font-mono"
                  />
                  <p className="text-xs text-gray-500">
                    Customers can buy {config.points_per_dollar} points for $1
                  </p>
                </div>

                {/* Special Discount Threshold */}
                <div className="space-y-2">
                  <Label htmlFor="points_for_30_discount">Points for {config.thirty_percent_discount}% Discount</Label>
                  <Input
                    id="points_for_30_discount"
                    type="number"
                    min="0"
                    value={config.points_for_30_discount}
                    onChange={(e) => setConfig({ ...config, points_for_30_discount: parseInt(e.target.value) || 0 })}
                    className="font-mono"
                  />
                  <p className="text-xs text-gray-500">
                    Redeem this many points for a one-time {config.thirty_percent_discount}% discount
                  </p>
                </div>

                {/* Discount Percentage */}
                <div className="space-y-2">
                  <Label htmlFor="thirty_percent_discount">Special Discount Percentage</Label>
                  <Input
                    id="thirty_percent_discount"
                    type="number"
                    min="0"
                    max="100"
                    value={config.thirty_percent_discount}
                    onChange={(e) => setConfig({ ...config, thirty_percent_discount: parseInt(e.target.value) || 0 })}
                    className="font-mono"
                  />
                  <p className="text-xs text-gray-500">
                    The percentage discount for special redemption
                  </p>
                </div>

                {/* Max Redemption Percent (CAP) */}
                <div className="space-y-2">
                  <Label htmlFor="max_redemption_percent" className="flex items-center gap-2">
                    Max Redemption Cap (%)
                    <Badge variant="outline" className="text-xs bg-red-50 text-red-700 border-red-200">Important</Badge>
                  </Label>
                  <Input
                    id="max_redemption_percent"
                    type="number"
                    min="5"
                    max="100"
                    value={config.max_redemption_percent}
                    onChange={(e) => setConfig({ ...config, max_redemption_percent: parseInt(e.target.value) || 30 })}
                    className="font-mono"
                  />
                  <p className="text-xs text-gray-500">
                    Maximum discount customers can redeem (% of order subtotal). Set to 30 means max 30% off.
                  </p>
                </div>
              </div>

              {/* Feature Toggles */}
              <div className="space-y-4 pt-4 border-t">
                <h3 className="font-semibold text-[#2D2A2E]">Feature Controls</h3>
                
                <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                  <div>
                    <Label>Allow Buying Points</Label>
                    <p className="text-xs text-gray-500">Customers can purchase additional points</p>
                  </div>
                  <Switch
                    checked={config.allow_buy_points}
                    onCheckedChange={(checked) => setConfig({ ...config, allow_buy_points: checked })}
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-pink-50 rounded-lg">
                  <div>
                    <Label>Allow Gifting Points</Label>
                    <p className="text-xs text-gray-500">Customers can gift points to others</p>
                  </div>
                  <Switch
                    checked={config.allow_gift_points}
                    onCheckedChange={(checked) => setConfig({ ...config, allow_gift_points: checked })}
                  />
                </div>
              </div>

              {/* Value Calculator */}
              <div className="p-4 bg-gradient-to-r from-amber-50 to-yellow-50 rounded-lg border border-amber-200">
                <h3 className="font-semibold text-amber-800 mb-2 flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  Value Preview
                </h3>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-amber-600">1 Purchase =</p>
                    <p className="font-bold text-amber-800">{config.points_per_product} pts</p>
                    <p className="text-xs text-amber-600">(${getPointsValue(config.points_per_product)} value)</p>
                  </div>
                  <div>
                    <p className="text-amber-600">$10 Buy =</p>
                    <p className="font-bold text-amber-800">{config.points_per_dollar * 10} pts</p>
                  </div>
                  <div>
                    <p className="text-amber-600">{config.thirty_percent_discount}% Off =</p>
                    <p className="font-bold text-amber-800">{config.points_for_30_discount} pts</p>
                  </div>
                </div>
              </div>

              {/* Save Button */}
              <div className="flex justify-end pt-4">
                <Button 
                  onClick={saveConfig} 
                  disabled={saving}
                  className="bg-[#2D2A2E] hover:bg-[#2D2A2E]/90"
                >
                  {saving ? (
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  Save Configuration
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Members Tab */}
        <TabsContent value="members">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Members with Points</CardTitle>
                  <CardDescription>View and manage customer point balances</CardDescription>
                </div>
                <Button variant="outline" onClick={loadUsers} disabled={loadingUsers}>
                  <RefreshCw className={`h-4 w-4 mr-2 ${loadingUsers ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {/* Search */}
              <div className="mb-4 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search by email or name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>

              {/* Users Table */}
              <div className="border rounded-lg overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Customer</TableHead>
                      <TableHead className="text-right">Balance</TableHead>
                      <TableHead className="text-right">Value</TableHead>
                      <TableHead className="text-right">Lifetime Earned</TableHead>
                      <TableHead className="text-right">Redeemed</TableHead>
                      <TableHead className="text-center">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loadingUsers ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-8">
                          <RefreshCw className="h-6 w-6 animate-spin mx-auto text-gray-400" />
                        </TableCell>
                      </TableRow>
                    ) : filteredUsers.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-8 text-gray-500">
                          No members found
                        </TableCell>
                      </TableRow>
                    ) : (
                      filteredUsers.map((user) => (
                        <TableRow key={user.user_id}>
                          <TableCell>
                            <div>
                              <p className="font-medium">{user.name || 'N/A'}</p>
                              <p className="text-sm text-gray-500">{user.email}</p>
                            </div>
                          </TableCell>
                          <TableCell className="text-right">
                            <Badge variant="outline" className="font-mono">
                              {user.balance.toLocaleString()} pts
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-medium text-green-600">
                            ${getPointsValue(user.balance)}
                          </TableCell>
                          <TableCell className="text-right text-gray-600">
                            {user.lifetime_earned.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right text-gray-600">
                            {user.lifetime_redeemed.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-center">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setSelectedUser(user);
                                setShowAdjustDialog(true);
                              }}
                            >
                              Adjust
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Adjust Points Dialog */}
      <Dialog open={showAdjustDialog} onOpenChange={setShowAdjustDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Adjust Points Balance</DialogTitle>
            <DialogDescription>
              Add or remove points from {selectedUser?.email}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {selectedUser && (
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-500">Current Balance</p>
                <p className="text-2xl font-bold">{selectedUser.balance.toLocaleString()} pts</p>
                <p className="text-sm text-green-600">(${getPointsValue(selectedUser.balance)} value)</p>
              </div>
            )}
            
            <div className="space-y-2">
              <Label>Adjustment Amount</Label>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setAdjustAmount(prev => String(Math.max(-10000, (parseInt(prev) || 0) - 100)))}
                >
                  <Minus className="h-4 w-4" />
                </Button>
                <Input
                  type="number"
                  placeholder="Enter amount (+ or -)"
                  value={adjustAmount}
                  onChange={(e) => setAdjustAmount(e.target.value)}
                  className="font-mono text-center"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setAdjustAmount(prev => String((parseInt(prev) || 0) + 100))}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-gray-500">
                Use positive number to add, negative to remove
              </p>
            </div>

            {adjustAmount && (
              <div className={`p-3 rounded-lg ${parseInt(adjustAmount) >= 0 ? 'bg-green-50' : 'bg-red-50'}`}>
                <p className="text-sm flex items-center gap-1">
                  {parseInt(adjustAmount) >= 0 ? (
                    <>
                      <ArrowUpRight className="h-4 w-4 text-green-600" />
                      <span className="text-green-700">New Balance: {((selectedUser?.balance || 0) + parseInt(adjustAmount)).toLocaleString()} pts</span>
                    </>
                  ) : (
                    <>
                      <ArrowDownRight className="h-4 w-4 text-red-600" />
                      <span className="text-red-700">New Balance: {Math.max(0, (selectedUser?.balance || 0) + parseInt(adjustAmount)).toLocaleString()} pts</span>
                    </>
                  )}
                </p>
              </div>
            )}
            
            <div className="space-y-2">
              <Label>Reason for Adjustment</Label>
              <Textarea
                placeholder="e.g., Customer service credit, Manual correction, Promotional bonus..."
                value={adjustReason}
                onChange={(e) => setAdjustReason(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAdjustDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleAdjustPoints}
              disabled={adjusting || !adjustAmount || !adjustReason}
              className={parseInt(adjustAmount) >= 0 ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}
            >
              {adjusting ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : parseInt(adjustAmount) >= 0 ? (
                <Plus className="h-4 w-4 mr-2" />
              ) : (
                <Minus className="h-4 w-4 mr-2" />
              )}
              {parseInt(adjustAmount) >= 0 ? 'Add Points' : 'Remove Points'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default LoyaltyPointsManager;
