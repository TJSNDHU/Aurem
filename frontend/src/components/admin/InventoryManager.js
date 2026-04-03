import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Package, AlertTriangle, AlertCircle, CheckCircle, 
  Search, RefreshCw, Plus, Minus, Save, Filter,
  TrendingDown, TrendingUp, Box
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Label } from '../ui/label';
import { useAdminBrand } from './useAdminBrand';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const InventoryManager = () => {
  const { activeBrand } = useAdminBrand();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('all'); // all, low, out, ok
  const [editingProduct, setEditingProduct] = useState(null);
  const [stockAdjustment, setStockAdjustment] = useState(0);
  const [adjustmentNote, setAdjustmentNote] = useState('');

  // Stock thresholds
  const LOW_STOCK_THRESHOLD = 10;
  const WARNING_STOCK_THRESHOLD = 25;

  const fetchProducts = useCallback(async () => {
    try {
      const token = localStorage.getItem('reroots_token');
      const response = await axios.get(`${API}/products?brand=${activeBrand}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setProducts(response.data || []);
    } catch (error) {
      console.error('Failed to fetch products:', error);
      toast.error('Failed to load inventory');
    } finally {
      setLoading(false);
    }
  }, [activeBrand]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts, activeBrand]);

  const getStockStatus = (stock) => {
    if (stock <= 0) return { status: 'out', label: 'Out of Stock', color: 'bg-red-500', icon: AlertCircle };
    if (stock <= LOW_STOCK_THRESHOLD) return { status: 'low', label: 'Low Stock', color: 'bg-orange-500', icon: AlertTriangle };
    if (stock <= WARNING_STOCK_THRESHOLD) return { status: 'warning', label: 'Warning', color: 'bg-yellow-500', icon: TrendingDown };
    return { status: 'ok', label: 'In Stock', color: 'bg-green-500', icon: CheckCircle };
  };

  const filteredProducts = products.filter(product => {
    const matchesSearch = product.name?.toLowerCase().includes(searchQuery.toLowerCase());
    const stockStatus = getStockStatus(product.stock || 0);
    
    if (filter === 'all') return matchesSearch;
    if (filter === 'low') return matchesSearch && (stockStatus.status === 'low' || stockStatus.status === 'warning');
    if (filter === 'out') return matchesSearch && stockStatus.status === 'out';
    if (filter === 'ok') return matchesSearch && stockStatus.status === 'ok';
    return matchesSearch;
  });

  const stats = {
    total: products.length,
    inStock: products.filter(p => (p.stock || 0) > WARNING_STOCK_THRESHOLD).length,
    lowStock: products.filter(p => (p.stock || 0) > 0 && (p.stock || 0) <= WARNING_STOCK_THRESHOLD).length,
    outOfStock: products.filter(p => (p.stock || 0) <= 0).length,
  };

  const handleStockUpdate = async () => {
    if (!editingProduct) return;
    
    const newStock = Math.max(0, (editingProduct.stock || 0) + stockAdjustment);
    
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.put(`${API}/products/${editingProduct.id}`, {
        ...editingProduct,
        stock: newStock
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setProducts(products.map(p => 
        p.id === editingProduct.id ? { ...p, stock: newStock } : p
      ));
      
      toast.success(`Stock updated: ${editingProduct.name} → ${newStock} units`);
      setEditingProduct(null);
      setStockAdjustment(0);
      setAdjustmentNote('');
    } catch (error) {
      toast.error('Failed to update stock');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#2D2A2E]">Inventory Management</h1>
          <p className="text-[#5A5A5A]">Monitor stock levels and manage inventory</p>
        </div>
        <Button onClick={fetchProducts} variant="outline" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setFilter('all')}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100">
                <Box className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#2D2A2E]">{stats.total}</p>
                <p className="text-sm text-[#5A5A5A]">Total Products</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setFilter('ok')}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-100">
                <CheckCircle className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600">{stats.inStock}</p>
                <p className="text-sm text-[#5A5A5A]">In Stock</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setFilter('low')}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-orange-100">
                <AlertTriangle className="h-5 w-5 text-orange-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-orange-600">{stats.lowStock}</p>
                <p className="text-sm text-[#5A5A5A]">Low Stock</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setFilter('out')}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-red-100">
                <AlertCircle className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600">{stats.outOfStock}</p>
                <p className="text-sm text-[#5A5A5A]">Out of Stock</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#5A5A5A]" />
          <Input
            placeholder="Search products..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex gap-2">
          {['all', 'low', 'out', 'ok'].map((f) => (
            <Button
              key={f}
              variant={filter === f ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilter(f)}
              className={filter === f ? 'bg-[#F8A5B8] hover:bg-[#E88DA0]' : ''}
            >
              {f === 'all' ? 'All' : f === 'low' ? 'Low Stock' : f === 'out' ? 'Out' : 'In Stock'}
            </Button>
          ))}
        </div>
      </div>

      {/* Products Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-4 font-medium text-[#5A5A5A]">Product</th>
                  <th className="text-left p-4 font-medium text-[#5A5A5A]">SKU</th>
                  <th className="text-center p-4 font-medium text-[#5A5A5A]">Stock</th>
                  <th className="text-center p-4 font-medium text-[#5A5A5A]">Status</th>
                  <th className="text-right p-4 font-medium text-[#5A5A5A]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredProducts.map((product) => {
                  const stockStatus = getStockStatus(product.stock || 0);
                  const StatusIcon = stockStatus.icon;
                  
                  return (
                    <tr key={product.id} className="hover:bg-gray-50">
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          {product.images?.[0] ? (
                            <img 
                              src={product.images[0]} 
                              alt={product.name}
                              className="w-12 h-12 rounded-lg object-cover"
                            />
                          ) : (
                            <div className="w-12 h-12 rounded-lg bg-gray-100 flex items-center justify-center">
                              <Package className="h-6 w-6 text-gray-400" />
                            </div>
                          )}
                          <div>
                            <p className="font-medium text-[#2D2A2E]">{product.name}</p>
                            <p className="text-sm text-[#5A5A5A]">${product.price?.toFixed(2)}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4 text-[#5A5A5A]">
                        {product.sku || product.id?.slice(0, 8)}
                      </td>
                      <td className="p-4 text-center">
                        <span className={`text-lg font-bold ${
                          stockStatus.status === 'out' ? 'text-red-600' :
                          stockStatus.status === 'low' ? 'text-orange-600' :
                          stockStatus.status === 'warning' ? 'text-yellow-600' :
                          'text-green-600'
                        }`}>
                          {product.stock || 0}
                        </span>
                      </td>
                      <td className="p-4 text-center">
                        <Badge className={`${stockStatus.color} text-white gap-1`}>
                          <StatusIcon className="h-3 w-3" />
                          {stockStatus.label}
                        </Badge>
                      </td>
                      <td className="p-4 text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingProduct(product);
                            setStockAdjustment(0);
                          }}
                        >
                          Adjust Stock
                        </Button>
                      </td>
                    </tr>
                  );
                })}
                {filteredProducts.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-[#5A5A5A]">
                      No products found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Stock Adjustment Dialog */}
      <Dialog open={!!editingProduct} onOpenChange={() => setEditingProduct(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Adjust Stock</DialogTitle>
          </DialogHeader>
          {editingProduct && (
            <div className="space-y-4 py-4">
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                {editingProduct.images?.[0] ? (
                  <img 
                    src={editingProduct.images[0]} 
                    alt={editingProduct.name}
                    className="w-16 h-16 rounded-lg object-cover"
                  />
                ) : (
                  <div className="w-16 h-16 rounded-lg bg-gray-200 flex items-center justify-center">
                    <Package className="h-8 w-8 text-gray-400" />
                  </div>
                )}
                <div>
                  <p className="font-medium text-[#2D2A2E]">{editingProduct.name}</p>
                  <p className="text-sm text-[#5A5A5A]">Current stock: {editingProduct.stock || 0}</p>
                </div>
              </div>

              <div>
                <Label>Adjustment</Label>
                <div className="flex items-center gap-2 mt-2">
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => setStockAdjustment(prev => prev - 1)}
                  >
                    <Minus className="h-4 w-4" />
                  </Button>
                  <Input
                    type="number"
                    value={stockAdjustment}
                    onChange={(e) => setStockAdjustment(parseInt(e.target.value) || 0)}
                    className="text-center text-lg font-bold w-24"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => setStockAdjustment(prev => prev + 1)}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-sm text-[#5A5A5A] mt-2">
                  New stock: <strong>{Math.max(0, (editingProduct.stock || 0) + stockAdjustment)}</strong>
                </p>
              </div>

              <div>
                <Label>Note (optional)</Label>
                <Input
                  placeholder="e.g., Restocked from supplier"
                  value={adjustmentNote}
                  onChange={(e) => setAdjustmentNote(e.target.value)}
                />
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setEditingProduct(null)}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleStockUpdate}
                  className="bg-[#F8A5B8] hover:bg-[#E88DA0] text-white gap-2"
                >
                  <Save className="h-4 w-4" />
                  Update Stock
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default InventoryManager;
