import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Plus,
  RefreshCw,
  Loader2,
  Package,
  Users,
  Trash2,
  Pencil,
  Crown,
  Star,
  TrendingUp,
  Sparkles,
  Heart,
  Gift
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// Get backend URL from environment
const getBackendUrl = () => {
  return process.env.REACT_APP_BACKEND_URL || window.location.origin;
};

const API = `${getBackendUrl()}/api`;

/**
 * LA VELA BIANCA Command Center - Teen Skincare Brand Administration
 */
const LaVelaCommandCenter = ({ initialTab = "dashboard" }) => {
  // State
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState([]);
  const [glowClubMembers, setGlowClubMembers] = useState([]);
  const [stats, setStats] = useState(null);
  const [activeTab, setActiveTab] = useState(initialTab);
  
  // Product form state
  const [productFormOpen, setProductFormOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [productForm, setProductForm] = useState({
    name: "",
    price_cad: 49,
    description: "",
    short_description: "",
    ingredients: "",
    how_to_use: "",
    hero_image_url: "",
    image_urls: [],
    age_range: "8-16",
    skin_concerns: [],
    is_bestseller: false,
    stock: 100
  });
  
  const headers = {
    Authorization: `Bearer ${localStorage.getItem("reroots_token")}`
  };
  
  // Fetch all data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [productsRes, membersRes, statsRes] = await Promise.all([
        axios.get(`${API}/admin/lavela/products`, { headers }).catch(() => ({ data: { products: [] } })),
        axios.get(`${API}/admin/lavela/glow-club`, { headers }).catch(() => ({ data: { members: [], stats: {} } })),
        axios.get(`${API}/admin/lavela/stats`, { headers }).catch(() => ({ data: {} }))
      ]);
      
      setProducts(productsRes.data.products || []);
      setGlowClubMembers(membersRes.data.members || []);
      setStats(statsRes.data);
    } catch (error) {
      console.error("Error fetching LA VELA data:", error);
    }
    setLoading(false);
  }, []);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  // Create/Update product
  const handleProductSubmit = async () => {
    try {
      if (editingProduct) {
        await axios.put(`${API}/admin/lavela/products/${editingProduct.id}`, productForm, { headers });
        toast.success("Product updated!");
      } else {
        await axios.post(`${API}/admin/lavela/products`, productForm, { headers });
        toast.success("Product created!");
      }
      setProductFormOpen(false);
      setEditingProduct(null);
      resetProductForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save product");
    }
  };
  
  // Delete product
  const handleDeleteProduct = async (productId) => {
    if (!window.confirm("Delete this product?")) return;
    try {
      await axios.delete(`${API}/admin/lavela/products/${productId}`, { headers });
      toast.success("Product deleted");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete product");
    }
  };
  
  // Edit product
  const handleEditProduct = (product) => {
    setEditingProduct(product);
    setProductForm({
      name: product.name || "",
      price_cad: product.price_cad || 49,
      description: product.description || "",
      short_description: product.short_description || "",
      ingredients: product.ingredients || "",
      how_to_use: product.how_to_use || "",
      hero_image_url: product.hero_image_url || "",
      image_urls: product.image_urls || [],
      age_range: product.age_range || "8-16",
      skin_concerns: product.skin_concerns || [],
      is_bestseller: product.is_bestseller || false,
      stock: product.stock || 100
    });
    setProductFormOpen(true);
  };
  
  // Reset form
  const resetProductForm = () => {
    setProductForm({
      name: "",
      price_cad: 49,
      description: "",
      short_description: "",
      ingredients: "",
      how_to_use: "",
      hero_image_url: "",
      image_urls: [],
      age_range: "8-16",
      skin_concerns: [],
      is_bestseller: false,
      stock: 100
    });
  };
  
  // Update member tier
  const handleUpdateMemberTier = async (memberId, newTier) => {
    try {
      await axios.put(`${API}/admin/lavela/glow-club/${memberId}`, { tier: newTier }, { headers });
      toast.success("Member tier updated!");
      fetchData();
    } catch (error) {
      toast.error("Failed to update member");
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-[#E6BE8A]" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#FADBD8] to-[#E6BE8A] flex items-center justify-center">
            <Sparkles className="h-6 w-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[#2D2A2E]">LA VELA BIANCA</h2>
            <p className="text-sm text-gray-500">Teen Skincare Command Center</p>
          </div>
        </div>
        <Button onClick={fetchData} variant="outline" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>
      
      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="overflow-x-auto pb-2" style={{ WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none' }}>
          <TabsList className="bg-gradient-to-r from-[#FADBD8]/30 to-[#E6BE8A]/30 inline-flex min-w-max">
            <TabsTrigger value="overview" className="data-[state=active]:bg-white whitespace-nowrap">
              📊 Overview
            </TabsTrigger>
            <TabsTrigger value="products" className="data-[state=active]:bg-white whitespace-nowrap">
              🧴 Products
            </TabsTrigger>
            <TabsTrigger value="glow-club" className="data-[state=active]:bg-white whitespace-nowrap">
              ✨ Glow Club
            </TabsTrigger>
          </TabsList>
        </div>
        
        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="bg-gradient-to-br from-pink-50 to-white border-pink-200">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Package className="h-5 w-5 text-pink-500" />
                  <span className="text-sm text-pink-600 font-medium">Products</span>
                </div>
                <p className="text-3xl font-bold text-pink-700">{stats?.products?.total || 0}</p>
                <p className="text-xs text-pink-500">{stats?.products?.total_stock || 0} in stock</p>
              </CardContent>
            </Card>
            
            <Card className="bg-gradient-to-br from-amber-50 to-white border-amber-200">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Users className="h-5 w-5 text-amber-500" />
                  <span className="text-sm text-amber-600 font-medium">Glow Club</span>
                </div>
                <p className="text-3xl font-bold text-amber-700">{stats?.glow_club?.total_members || 0}</p>
                <p className="text-xs text-amber-500">{stats?.glow_club?.active_members || 0} active</p>
              </CardContent>
            </Card>
            
            <Card className="bg-gradient-to-br from-purple-50 to-white border-purple-200">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="h-5 w-5 text-purple-500" />
                  <span className="text-sm text-purple-600 font-medium">This Week</span>
                </div>
                <p className="text-3xl font-bold text-purple-700">+{stats?.growth?.weekly_signups || 0}</p>
                <p className="text-xs text-purple-500">new signups</p>
              </CardContent>
            </Card>
            
            <Card className="bg-gradient-to-br from-emerald-50 to-white border-emerald-200">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Crown className="h-5 w-5 text-emerald-500" />
                  <span className="text-sm text-emerald-600 font-medium">Queen Tier</span>
                </div>
                <p className="text-3xl font-bold text-emerald-700">{stats?.glow_club?.tiers?.queen || 0}</p>
                <p className="text-xs text-emerald-500">{stats?.growth?.conversion_rate || 0}% of members</p>
              </CardContent>
            </Card>
          </div>
          
          {/* Tier Distribution */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Star className="h-5 w-5 text-[#E6BE8A]" />
                Glow Club Tier Distribution
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 bg-gray-50 rounded-xl">
                  <p className="text-3xl font-bold text-gray-600">{stats?.glow_club?.tiers?.starter || 0}</p>
                  <p className="text-sm text-gray-500">🌱 Starter</p>
                </div>
                <div className="text-center p-4 bg-pink-50 rounded-xl">
                  <p className="text-3xl font-bold text-pink-600">{stats?.glow_club?.tiers?.pro || 0}</p>
                  <p className="text-sm text-pink-500">💖 Pro</p>
                </div>
                <div className="text-center p-4 bg-gradient-to-br from-amber-50 to-pink-50 rounded-xl">
                  <p className="text-3xl font-bold text-[#E6BE8A]">{stats?.glow_club?.tiers?.queen || 0}</p>
                  <p className="text-sm text-amber-600">👑 Queen</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        {/* Products Tab */}
        <TabsContent value="products" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Product Catalog</h3>
            <Button 
              onClick={() => { resetProductForm(); setEditingProduct(null); setProductFormOpen(true); }}
              className="bg-gradient-to-r from-[#FADBD8] to-[#E6BE8A] text-white hover:opacity-90"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Product
            </Button>
          </div>
          
          {products.length === 0 ? (
            <Card className="text-center py-12">
              <CardContent>
                <Package className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">No products yet. Create your first LA VELA BIANCA product!</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {products.map(product => (
                <Card key={product.id} className="overflow-hidden">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-4">
                      {/* Product Image */}
                      <div className="w-20 h-20 rounded-xl bg-gradient-to-br from-[#FADBD8] to-[#F5B7B1] flex items-center justify-center overflow-hidden">
                        {product.hero_image_url ? (
                          <img src={product.hero_image_url} alt={product.name} className="w-full h-full object-cover" />
                        ) : (
                          <span className="text-2xl">🧴</span>
                        )}
                      </div>
                      
                      {/* Product Info */}
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-[#2D2A2E]">{product.name}</h4>
                          {product.is_bestseller && (
                            <Badge className="bg-pink-100 text-pink-700 text-xs">Bestseller</Badge>
                          )}
                        </div>
                        <p className="text-sm text-gray-500 line-clamp-1">{product.short_description || product.description}</p>
                        <div className="flex items-center gap-4 mt-2">
                          <span className="text-lg font-bold text-[#E6BE8A]">${product.price_cad} CAD</span>
                          <span className="text-sm text-gray-400">Stock: {product.stock}</span>
                          <span className="text-sm text-gray-400">Ages: {product.age_range}</span>
                        </div>
                      </div>
                      
                      {/* Actions */}
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => handleEditProduct(product)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button size="sm" variant="outline" className="text-red-500" onClick={() => handleDeleteProduct(product.id)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
        
        {/* Glow Club Tab */}
        <TabsContent value="glow-club" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Glow Club Members ({glowClubMembers.length})</h3>
          </div>
          
          {glowClubMembers.length === 0 ? (
            <Card className="text-center py-12">
              <CardContent>
                <Heart className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">No Glow Club members yet.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gradient-to-r from-[#FADBD8]/30 to-[#E6BE8A]/30">
                  <tr>
                    <th className="text-left p-3">Member</th>
                    <th className="text-left p-3">Tier</th>
                    <th className="text-right p-3">Points</th>
                    <th className="text-left p-3">Referral Code</th>
                    <th className="text-left p-3">Joined</th>
                    <th className="text-center p-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {glowClubMembers.map(member => (
                    <tr key={member.id} className="border-b hover:bg-pink-50/50">
                      <td className="p-3">
                        <div>
                          <p className="font-medium">{member.name}</p>
                          <p className="text-xs text-gray-500">{member.email}</p>
                        </div>
                      </td>
                      <td className="p-3">
                        <Select 
                          value={member.tier} 
                          onValueChange={(value) => handleUpdateMemberTier(member.id, value)}
                        >
                          <SelectTrigger className="w-28 h-8">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="starter">🌱 Starter</SelectItem>
                            <SelectItem value="pro">💖 Pro</SelectItem>
                            <SelectItem value="queen">👑 Queen</SelectItem>
                          </SelectContent>
                        </Select>
                      </td>
                      <td className="p-3 text-right">
                        <span className="font-semibold text-[#E6BE8A]">{member.points}</span>
                      </td>
                      <td className="p-3">
                        <code className="bg-gray-100 px-2 py-1 rounded text-xs">{member.referral_code}</code>
                      </td>
                      <td className="p-3 text-gray-500">
                        {new Date(member.joined_at).toLocaleDateString()}
                      </td>
                      <td className="p-3 text-center">
                        <Button size="sm" variant="ghost">
                          <Gift className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>
      
      {/* Product Form Dialog */}
      <Dialog open={productFormOpen} onOpenChange={setProductFormOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-[#E6BE8A]" />
              {editingProduct ? "Edit Product" : "Create New Product"}
            </DialogTitle>
            <DialogDescription>
              Add a new LA VELA BIANCA teen skincare product
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Product Name *</Label>
                <Input
                  value={productForm.name}
                  onChange={(e) => setProductForm({ ...productForm, name: e.target.value })}
                  placeholder="e.g., ORO ROSA Serum"
                />
              </div>
              <div>
                <Label>Price (CAD) *</Label>
                <Input
                  type="number"
                  value={productForm.price_cad}
                  onChange={(e) => setProductForm({ ...productForm, price_cad: parseFloat(e.target.value) || 0 })}
                />
              </div>
            </div>
            
            <div>
              <Label>Short Description</Label>
              <Input
                value={productForm.short_description}
                onChange={(e) => setProductForm({ ...productForm, short_description: e.target.value })}
                placeholder="One-liner for product cards"
              />
            </div>
            
            <div>
              <Label>Full Description</Label>
              <Textarea
                value={productForm.description}
                onChange={(e) => setProductForm({ ...productForm, description: e.target.value })}
                placeholder="Detailed product description..."
                rows={3}
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Target Age Range</Label>
                <Select 
                  value={productForm.age_range} 
                  onValueChange={(value) => setProductForm({ ...productForm, age_range: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="8-12">Ages 8-12</SelectItem>
                    <SelectItem value="8-16">Ages 8-16</SelectItem>
                    <SelectItem value="12-16">Ages 12-16</SelectItem>
                    <SelectItem value="13-18">Ages 13-18</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Stock Quantity</Label>
                <Input
                  type="number"
                  value={productForm.stock}
                  onChange={(e) => setProductForm({ ...productForm, stock: parseInt(e.target.value) || 0 })}
                />
              </div>
            </div>
            
            <div>
              <Label>Hero Image URL</Label>
              <Input
                value={productForm.hero_image_url}
                onChange={(e) => setProductForm({ ...productForm, hero_image_url: e.target.value })}
                placeholder="https://..."
              />
            </div>
            
            <div>
              <Label>Ingredients</Label>
              <Textarea
                value={productForm.ingredients}
                onChange={(e) => setProductForm({ ...productForm, ingredients: e.target.value })}
                placeholder="PDRN, Glutathione, Hyaluronic Acid..."
                rows={2}
              />
            </div>
            
            <div>
              <Label>How to Use</Label>
              <Textarea
                value={productForm.how_to_use}
                onChange={(e) => setProductForm({ ...productForm, how_to_use: e.target.value })}
                placeholder="Apply 2-3 drops to clean skin..."
                rows={2}
              />
            </div>
            
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="bestseller"
                checked={productForm.is_bestseller}
                onChange={(e) => setProductForm({ ...productForm, is_bestseller: e.target.checked })}
                className="rounded"
              />
              <Label htmlFor="bestseller" className="cursor-pointer">Mark as Bestseller</Label>
            </div>
          </div>
          
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setProductFormOpen(false)}>Cancel</Button>
            <Button 
              onClick={handleProductSubmit}
              className="bg-gradient-to-r from-[#FADBD8] to-[#E6BE8A] text-white"
            >
              {editingProduct ? "Update Product" : "Create Product"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default LaVelaCommandCenter;
