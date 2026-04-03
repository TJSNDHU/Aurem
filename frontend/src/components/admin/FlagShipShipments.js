import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import {
  RefreshCw,
  Package,
  Truck,
  ExternalLink,
  MapPin,
  Calendar,
  Search,
  CheckCircle2,
  Clock,
  Download,
  DollarSign,
  Printer,
  CloudDownload,
  Globe,
  Home,
  Filter
} from 'lucide-react';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

const FlagShipShipments = () => {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedShipments, setSelectedShipments] = useState([]);
  const [sourceFilter, setSourceFilter] = useState('all');
  const [internalCount, setInternalCount] = useState(0);
  const [externalCount, setExternalCount] = useState(0);
  const [lastSyncTime, setLastSyncTime] = useState(null);

  const fetchShipments = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const response = await axios.get(`${API}/api/admin/flagship/all-shipments?limit=100&source=${sourceFilter}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.data.success) {
        setShipments(response.data.shipments || []);
        setInternalCount(response.data.internal_count || 0);
        setExternalCount(response.data.external_count || 0);
      } else {
        toast.error('Failed to load shipments');
      }
    } catch (error) {
      console.error('Error fetching shipments:', error);
      toast.error('Failed to load shipments');
    } finally {
      setLoading(false);
    }
  }, [sourceFilter]);

  const syncFromFlagShip = async () => {
    setSyncing(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const response = await axios.post(`${API}/api/admin/flagship/sync`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.data.success) {
        toast.success(response.data.message);
        setLastSyncTime(new Date().toLocaleTimeString());
        // Refresh the shipments list
        await fetchShipments();
      } else {
        toast.error('Failed to sync from FlagShip');
      }
    } catch (error) {
      console.error('Error syncing:', error);
      toast.error(error.response?.data?.detail || 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    fetchShipments();
  }, [fetchShipments]);

  const getStatusColor = (status) => {
    const statusLower = (status || '').toLowerCase();
    if (statusLower.includes('delivered')) return 'bg-green-100 text-green-800';
    if (statusLower.includes('transit') || statusLower.includes('shipped')) return 'bg-blue-100 text-blue-800';
    if (statusLower.includes('pending') || statusLower.includes('created')) return 'bg-yellow-100 text-yellow-800';
    if (statusLower.includes('cancelled') || statusLower.includes('voided')) return 'bg-red-100 text-red-800';
    return 'bg-gray-100 text-gray-800';
  };

  const getStatusIcon = (status) => {
    const statusLower = (status || '').toLowerCase();
    if (statusLower.includes('delivered')) return <CheckCircle2 className="w-4 h-4" />;
    if (statusLower.includes('transit') || statusLower.includes('shipped')) return <Truck className="w-4 h-4" />;
    if (statusLower.includes('pending') || statusLower.includes('created')) return <Clock className="w-4 h-4" />;
    return <Package className="w-4 h-4" />;
  };

  const toggleSelection = (id) => {
    setSelectedShipments(prev => 
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedShipments.length === filteredShipments.length) {
      setSelectedShipments([]);
    } else {
      setSelectedShipments(filteredShipments.map(s => s.id));
    }
  };

  const filteredShipments = shipments.filter(s => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      (s.tracking_number || '').toLowerCase().includes(query) ||
      (s.order_number || '').toLowerCase().includes(query) ||
      (s.to?.name || '').toLowerCase().includes(query) ||
      (s.to?.city || '').toLowerCase().includes(query) ||
      (s.courier_name || '').toLowerCase().includes(query)
    );
  });

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleDateString('en-CA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  };

  const printSelectedLabels = async () => {
    const selected = shipments.filter(s => selectedShipments.includes(s.id) && s.label_url);
    if (selected.length === 0) {
      toast.error('No labels available for selected shipments');
      return;
    }
    
    // Open each label in new tab
    selected.forEach((s, i) => {
      setTimeout(() => window.open(s.label_url, '_blank'), i * 500);
    });
    toast.success(`Opening ${selected.length} label(s)`);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
            <Package className="w-7 h-7 text-blue-600" />
            FlagShip Shipments
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            All shipments from FlagShip • {internalCount} internal + {externalCount} external
            {lastSyncTime && <span className="ml-2 text-green-600">• Last synced: {lastSyncTime}</span>}
          </p>
        </div>
        
        <div className="flex gap-2">
          {selectedShipments.length > 0 && (
            <Button 
              onClick={printSelectedLabels}
              className="bg-amber-500 hover:bg-amber-600 text-white"
            >
              <Printer className="w-4 h-4 mr-2" />
              Print Labels ({selectedShipments.length})
            </Button>
          )}
          <Button 
            onClick={syncFromFlagShip} 
            disabled={syncing}
            className="bg-green-600 hover:bg-green-700 text-white"
            data-testid="sync-from-flagship-btn"
          >
            <CloudDownload className={`w-4 h-4 mr-2 ${syncing ? 'animate-bounce' : ''}`} />
            {syncing ? 'Syncing...' : 'Sync from FlagShip'}
          </Button>
          <Button 
            onClick={fetchShipments} 
            disabled={loading}
            variant="outline"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Source Filter Tabs */}
      <div className="flex gap-2 border-b pb-3">
        <Button
          variant={sourceFilter === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setSourceFilter('all')}
          className={sourceFilter === 'all' ? 'bg-blue-600' : ''}
        >
          <Filter className="w-4 h-4 mr-1" />
          All ({internalCount + externalCount})
        </Button>
        <Button
          variant={sourceFilter === 'internal' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setSourceFilter('internal')}
          className={sourceFilter === 'internal' ? 'bg-emerald-600' : ''}
        >
          <Home className="w-4 h-4 mr-1" />
          Internal ({internalCount})
        </Button>
        <Button
          variant={sourceFilter === 'external' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setSourceFilter('external')}
          className={sourceFilter === 'external' ? 'bg-purple-600' : ''}
        >
          <Globe className="w-4 h-4 mr-1" />
          External ({externalCount})
        </Button>
      </div>

      {/* Search & Select All */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search by tracking, order #, name, city..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        
        <Button 
          variant="outline" 
          size="sm" 
          onClick={selectAll}
          className={selectedShipments.length === filteredShipments.length && filteredShipments.length > 0 ? 'bg-blue-50' : ''}
        >
          {selectedShipments.length === filteredShipments.length && filteredShipments.length > 0 
            ? 'Deselect All' 
            : 'Select All'
          }
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-5 gap-4">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-blue-600">Total Shipped</p>
                <p className="text-3xl font-bold text-blue-800">{shipments.length}</p>
              </div>
              <Package className="w-10 h-10 text-blue-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-emerald-600">Internal</p>
                <p className="text-3xl font-bold text-emerald-800">{internalCount}</p>
              </div>
              <Home className="w-10 h-10 text-emerald-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-purple-600">External</p>
                <p className="text-3xl font-bold text-purple-800">{externalCount}</p>
              </div>
              <Globe className="w-10 h-10 text-purple-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-green-600">Delivered</p>
                <p className="text-3xl font-bold text-green-800">
                  {shipments.filter(s => (s.status || '').toLowerCase().includes('delivered')).length}
                </p>
              </div>
              <CheckCircle2 className="w-10 h-10 text-green-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-amber-600">Shipping Cost</p>
                <p className="text-3xl font-bold text-amber-800">
                  ${shipments.reduce((sum, s) => sum + (s.total_price || 0), 0).toFixed(2)}
                </p>
              </div>
              <DollarSign className="w-10 h-10 text-amber-400" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Shipments List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
          <span className="ml-3 text-gray-500">Loading shipments...</span>
        </div>
      ) : filteredShipments.length === 0 ? (
        <Card className="py-16">
          <CardContent className="text-center">
            <Package className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">No shipped orders found</p>
            <p className="text-sm text-gray-400 mt-1">
              {searchQuery ? 'Try a different search term' : 'Orders will appear here once shipped'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredShipments.map((shipment, index) => {
            const isSelected = selectedShipments.includes(shipment.id);
            
            return (
              <Card 
                key={shipment.id || index} 
                className={`hover:shadow-lg transition-all cursor-pointer ${
                  isSelected ? 'ring-2 ring-blue-500 bg-blue-50/50' : ''
                }`}
                onClick={() => toggleSelection(shipment.id)}
              >
                <CardContent className="py-4">
                  <div className="flex items-center gap-4">
                    {/* Selection indicator */}
                    <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                      isSelected ? 'bg-blue-500 border-blue-500 text-white' : 'border-gray-300'
                    }`}>
                      {isSelected && <span className="text-xs font-bold">{selectedShipments.indexOf(shipment.id) + 1}</span>}
                    </div>
                    
                    {/* Main content */}
                    <div className="flex-1 grid grid-cols-5 gap-4">
                      {/* Order & Tracking */}
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-bold text-blue-700">
                            #{shipment.order_number}
                          </p>
                          {shipment.source === 'external' ? (
                            <Badge className="bg-purple-100 text-purple-700 text-xs px-1.5 py-0">
                              <Globe className="w-3 h-3 mr-0.5" />
                              External
                            </Badge>
                          ) : (
                            <Badge className="bg-emerald-100 text-emerald-700 text-xs px-1.5 py-0">
                              <Home className="w-3 h-3 mr-0.5" />
                              Internal
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm font-mono text-gray-600 mt-1">
                          {shipment.tracking_number || 'No tracking'}
                        </p>
                        <div className="mt-2">
                          <Badge className={getStatusColor(shipment.status)}>
                            {getStatusIcon(shipment.status)}
                            <span className="ml-1 capitalize">{shipment.status || 'Unknown'}</span>
                          </Badge>
                        </div>
                      </div>
                      
                      {/* Customer */}
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Ship To</p>
                        <p className="font-semibold text-gray-800">{shipment.to?.name || 'N/A'}</p>
                        <p className="text-sm text-gray-600 flex items-center gap-1 mt-1">
                          <MapPin className="w-3 h-3" />
                          {shipment.to?.city}, {shipment.to?.state}
                        </p>
                      </div>
                      
                      {/* Carrier */}
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Carrier</p>
                        <p className="flex items-center gap-1 text-gray-800">
                          <Truck className="w-4 h-4 text-blue-500" />
                          {shipment.courier_name}
                        </p>
                        {shipment.total_price > 0 && (
                          <p className="text-sm text-green-700 mt-1 font-medium">
                            ${shipment.total_price.toFixed(2)}
                          </p>
                        )}
                      </div>
                      
                      {/* Date */}
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Shipped</p>
                        <p className="text-sm text-gray-800 flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {formatDate(shipment.shipped_at)}
                        </p>
                      </div>
                      
                      {/* Order Total */}
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Order Value</p>
                        <p className="text-lg font-bold text-gray-800">
                          ${(shipment.order_total || 0).toFixed(2)}
                        </p>
                      </div>
                    </div>
                    
                    {/* Actions */}
                    <div className="flex flex-col gap-2" onClick={e => e.stopPropagation()}>
                      {shipment.label_url && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-blue-600 border-blue-200 hover:bg-blue-50"
                          onClick={() => window.open(shipment.label_url, '_blank')}
                        >
                          <Download className="w-3 h-3 mr-1" />
                          Label
                        </Button>
                      )}
                      
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-gray-600"
                        onClick={() => window.open(
                          shipment.tracking_url || `https://www.google.com/search?q=${shipment.tracking_number}+tracking`, 
                          '_blank'
                        )}
                      >
                        <ExternalLink className="w-3 h-3 mr-1" />
                        Track
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default FlagShipShipments;
