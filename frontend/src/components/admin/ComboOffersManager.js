import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Package, Plus, Trash2, Sparkles, Loader2, Edit, Eye,
  Clock, Target, CheckCircle2, X, Save, Image, Power, ToggleLeft, ToggleRight,
  AlertTriangle, Zap, Shield, TrendingUp, Beaker, RefreshCw, Calendar
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Switch } from '../ui/switch';
import { useAdminBrand } from './useAdminBrand';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Active concentration data for known products
const ACTIVE_CONCENTRATIONS = {
  'prod-aura-gen': {
    total: 17.35,
    label: 'Accelerator',
    type: 'Engine',
    keyActives: ['Mandelic Acid (5%)', 'Matrixyl 3000 (3%)', 'Alpha Arbutin (2%)', 'HPR Retinoid (2%)']
  },
  'prod-copper-peptide': {
    total: 37.67,
    label: 'Recovery',
    type: 'Buffer',
    keyActives: ['Argireline (10%)', 'Tranexamic Acid (5%)', 'Niacinamide (4%)', 'PDRN (2%)']
  }
};

const ComboOffersManager = () => {
  const { activeBrand } = useAdminBrand();
  const [combos, setCombos] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingCombo, setEditingCombo] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [togglingPopup, setTogglingPopup] = useState(null);
  const [calendarPreview, setCalendarPreview] = useState(null);
  const [loadingCalendar, setLoadingCalendar] = useState(false);
  const [labelStyle, setLabelStyle] = useState('engine_buffer'); // or 'sooth_protect'
  
  // Form state
  const [selectedProducts, setSelectedProducts] = useState([]);
  const [comboData, setComboData] = useState({
    name: '',
    slug: '',
    tagline: '',
    description: '',
    discount_percent: 15,
    discount_type: 'percent', // 'percent' or 'fixed'
    fixed_price: 0,
    is_active: true,
    popup_enabled: true,
    popup_headline: '', // Custom popup headline
    popup_message: '', // Custom popup message
    image: '',
    results_timeline: [],
    skin_concerns: [],
    usage_order: [],
    // Enhanced fields
    comparison_table: [],
    warnings: [],
    do_not_use_with: [],
    usage_frequency: '',
    // New: Active concentration data
    total_active_percent: 0,
    active_breakdown: {}
  });

  useEffect(() => {
    fetchData();
  }, [activeBrand]);

  const fetchData = async () => {
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      
      // Fetch combos and products filtered by brand
      const [combosRes, productsRes] = await Promise.all([
        axios.get(`${API}/admin/combo-offers?brand=${activeBrand}`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/products?brand=${activeBrand}`)
      ]);
      
      setCombos(combosRes.data || []);
      setProducts(productsRes.data || []);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddProduct = (productId) => {
    if (selectedProducts.length >= 4) {
      toast.error('Maximum 4 products per combo');
      return;
    }
    const product = products.find(p => p.id === productId);
    if (product && !selectedProducts.find(p => p.id === productId)) {
      setSelectedProducts([...selectedProducts, product]);
    }
  };

  const handleRemoveProduct = (productId) => {
    setSelectedProducts(selectedProducts.filter(p => p.id !== productId));
  };

  // Calculate total active concentration for selected products
  const calculateActiveLoad = () => {
    let total = 0;
    const breakdown = {};
    
    selectedProducts.forEach((product, idx) => {
      // Use product's engine data from database
      const productActive = product.active_concentration || 0;
      
      // Fallback to hardcoded data if not set in database
      const hardcodedData = ACTIVE_CONCENTRATIONS[product.id];
      const activeAmount = productActive > 0 ? productActive : (hardcodedData?.total || 0);
      
      // Use product's engine metadata if available
      const engineLabel = product.engine_label || hardcodedData?.label || product.name?.substring(0, 25) || 'Product';
      const engineType = product.engine_type || hardcodedData?.type || (idx === 0 ? 'Engine' : 'Buffer');
      const keyActives = product.key_actives || hardcodedData?.keyActives || [];
      const primaryBenefit = product.primary_benefit || '';
      
      total += activeAmount;
      breakdown[product.id] = {
        total: activeAmount,
        label: engineLabel,
        type: engineType,
        keyActives: keyActives,
        primaryBenefit: primaryBenefit
      };
    });
    
    return { total: total.toFixed(2), breakdown };
  };

  // Full Sync: Recalculate active load, fetch tags, generate calendar preview
  const handleFullSync = async () => {
    if (selectedProducts.length < 2) {
      toast.error('Select at least 2 products first');
      return;
    }
    
    setLoadingCalendar(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const activeLoad = calculateActiveLoad();
      
      // Update combo data with recalculated values
      setComboData(prev => ({
        ...prev,
        total_active_percent: parseFloat(activeLoad.total),
        active_breakdown: activeLoad.breakdown
      }));
      
      // Generate calendar preview based on product tags
      const res = await axios.post(`${API}/admin/clinical-logic/generate-calendar`, {
        product_ids: selectedProducts.map(p => p.id)
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.data?.success) {
        setCalendarPreview(res.data);
        setLabelStyle(res.data.label_style || 'engine_buffer');
        
        // Show potency warning if needed
        if (res.data.potency_warning) {
          toast.warning(res.data.potency_warning);
        }
        
        toast.success('Sync complete! Calendar preview generated.');
      }
    } catch (err) {
      console.error('Full sync failed:', err);
      toast.error('Failed to sync data');
    } finally {
      setLoadingCalendar(false);
    }
  };

  const generateWithAI = async () => {
    if (selectedProducts.length < 2) {
      toast.error('Select at least 2 products first');
      return;
    }
    
    setGenerating(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await axios.post(`${API}/generate-combo-benefits`, {
        products: selectedProducts.map(p => ({
          name: p.name,
          ingredients: p.ingredients || p.short_description || '',
          short_description: p.short_description
        }))
      }, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 60000
      });
      
      if (res.data?.success && res.data?.benefits) {
        const benefits = res.data.benefits;
        const activeLoad = calculateActiveLoad();
        
        setComboData({
          ...comboData,
          name: benefits.combo_name || '',
          tagline: benefits.tagline || '',
          description: benefits.synergy_description || '',
          results_timeline: benefits.results_timeline || [],
          skin_concerns: benefits.skin_concerns_addressed || [],
          usage_order: benefits.usage_order || [],
          comparison_table: benefits.comparison_table || [],
          warnings: benefits.warnings || [],
          do_not_use_with: benefits.do_not_use_with || [],
          usage_frequency: benefits.usage_frequency || '',
          total_active_percent: activeLoad.total,
          active_breakdown: activeLoad.breakdown
        });
        toast.success('AI generated combo details!');
      }
    } catch (err) {
      console.error('AI generation failed:', err);
      toast.error('Failed to generate. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const calculatePrices = () => {
    const original = selectedProducts.reduce((sum, p) => sum + (p.compare_price || p.price || 0), 0);
    
    // Handle both discount types
    let discounted;
    if (comboData.discount_type === 'fixed' && comboData.fixed_price > 0) {
      discounted = comboData.fixed_price;
    } else {
      discounted = original * (1 - (comboData.discount_percent || 0) / 100);
    }
    
    return { 
      original, 
      originalPrice: original, // For backward compatibility
      discounted, 
      savings: original - discounted 
    };
  };

  const handleSave = async () => {
    if (selectedProducts.length < 2) {
      toast.error('Select at least 2 products');
      return;
    }
    if (!comboData.name) {
      toast.error('Combo name is required');
      return;
    }
    
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      const prices = calculatePrices();
      const activeLoad = calculateActiveLoad();
      
      const payload = {
        ...comboData,
        product_ids: selectedProducts.map(p => p.id),
        original_price: prices.original,
        combo_price: prices.discounted,
        discount_type: comboData.discount_type || 'percent',
        discount_percent: comboData.discount_percent || 15,
        fixed_price: comboData.fixed_price || 0,
        popup_headline: comboData.popup_headline || '',
        popup_message: comboData.popup_message || '',
        total_active_percent: activeLoad.total,
        active_breakdown: activeLoad.breakdown
      };
      
      if (editingCombo) {
        await axios.put(`${API}/admin/combo-offers/${editingCombo.id}`, payload, { headers });
        toast.success('Combo updated!');
      } else {
        await axios.post(`${API}/admin/combo-offers`, payload, { headers });
        toast.success('Combo created!');
      }
      
      setShowDialog(false);
      resetForm();
      fetchData();
    } catch (err) {
      console.error('Save failed:', err);
      toast.error(err.response?.data?.detail || 'Failed to save combo');
    }
  };

  // Toggle popup enabled/disabled
  const handleTogglePopup = async (combo) => {
    setTogglingPopup(combo.id);
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      
      const newPopupEnabled = !combo.popup_enabled;
      
      await axios.put(`${API}/admin/combo-offers/${combo.id}`, {
        ...combo,
        popup_enabled: newPopupEnabled
      }, { headers });
      
      setCombos(combos.map(c => 
        c.id === combo.id ? { ...c, popup_enabled: newPopupEnabled } : c
      ));
      
      toast.success(`Upsell popup ${newPopupEnabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      console.error('Toggle failed:', err);
      toast.error('Failed to update popup setting');
    } finally {
      setTogglingPopup(null);
    }
  };

  // Toggle combo active/inactive
  const handleToggleActive = async (combo) => {
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      
      const newIsActive = !combo.is_active;
      
      await axios.put(`${API}/admin/combo-offers/${combo.id}`, {
        ...combo,
        is_active: newIsActive
      }, { headers });
      
      setCombos(combos.map(c => 
        c.id === combo.id ? { ...c, is_active: newIsActive } : c
      ));
      
      toast.success(`Combo ${newIsActive ? 'activated' : 'deactivated'}`);
    } catch (err) {
      console.error('Toggle failed:', err);
      toast.error('Failed to update combo status');
    }
  };

  const handleEdit = (combo) => {
    setEditingCombo(combo);
    setSelectedProducts(products.filter(p => combo.product_ids?.includes(p.id)));
    setComboData({
      name: combo.name || '',
      tagline: combo.tagline || '',
      description: combo.description || '',
      discount_percent: combo.discount_percent || 15,
      discount_type: combo.discount_type || 'percent',
      fixed_price: combo.fixed_price || 0,
      is_active: combo.is_active ?? true,
      popup_enabled: combo.popup_enabled ?? true,
      popup_headline: combo.popup_headline || '',
      popup_message: combo.popup_message || '',
      image: combo.image || '',
      results_timeline: combo.results_timeline || [],
      skin_concerns: combo.skin_concerns || [],
      usage_order: combo.usage_order || [],
      comparison_table: combo.comparison_table || [],
      warnings: combo.warnings || [],
      do_not_use_with: combo.do_not_use_with || [],
      usage_frequency: combo.usage_frequency || '',
      total_active_percent: combo.total_active_percent || 0,
      active_breakdown: combo.active_breakdown || {}
    });
    setShowDialog(true);
  };

  // State for delete confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [comboToDelete, setComboToDelete] = useState(null);

  const handleDelete = (comboId) => {
    setComboToDelete(comboId);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!comboToDelete) return;
    
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.delete(`${API}/admin/combo-offers/${comboToDelete}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Combo deleted');
      fetchData();
    } catch (err) {
      toast.error('Failed to delete combo');
    } finally {
      setShowDeleteConfirm(false);
      setComboToDelete(null);
    }
  };

  const resetForm = () => {
    setEditingCombo(null);
    setSelectedProducts([]);
    setComboData({
      name: '',
      tagline: '',
      description: '',
      discount_percent: 15,
      discount_type: 'percent',
      fixed_price: 0,
      is_active: true,
      popup_enabled: true,
      popup_headline: '',
      popup_message: '',
      image: '',
      results_timeline: [],
      skin_concerns: [],
      usage_order: [],
      comparison_table: [],
      warnings: [],
      do_not_use_with: [],
      usage_frequency: '',
      total_active_percent: 0,
      active_breakdown: {}
    });
  };

  const prices = calculatePrices();
  const activeLoad = calculateActiveLoad();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Combo Offers</h1>
          <p className="text-gray-500">Create product bundles with AI-generated benefits</p>
        </div>
        <Button
          onClick={() => { resetForm(); setShowDialog(true); }}
          className="bg-gradient-to-r from-purple-600 to-pink-500"
          data-testid="create-combo-btn"
        >
          <Plus className="h-4 w-4 mr-2" />
          Create Combo
        </Button>
      </div>

      {/* Existing Combos */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {combos.length === 0 ? (
          <Card className="col-span-full">
            <CardContent className="p-8 text-center">
              <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-700">No combo offers yet</h3>
              <p className="text-gray-500 mb-4">Create your first combo to boost sales</p>
              <Button onClick={() => setShowDialog(true)} variant="outline">
                <Plus className="h-4 w-4 mr-2" />
                Create First Combo
              </Button>
            </CardContent>
          </Card>
        ) : (
          combos.map(combo => (
            <Card key={combo.id} className={`overflow-hidden ${!combo.is_active ? 'opacity-60' : ''}`}>
              <div className="bg-gradient-to-r from-purple-600 to-pink-500 p-3 text-white">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold">{combo.name}</h3>
                    <p className="text-xs text-purple-100">{combo.product_ids?.length || 0} products</p>
                  </div>
                  <div className="flex flex-col gap-1 items-end">
                    {/* Active Status Badge */}
                    <Badge 
                      className={`cursor-pointer ${combo.is_active ? 'bg-green-500 hover:bg-green-600' : 'bg-gray-500 hover:bg-gray-600'}`}
                      onClick={() => handleToggleActive(combo)}
                    >
                      {combo.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                    {/* Active Concentration */}
                    {combo.total_active_percent > 0 && (
                      <Badge className="bg-amber-500 text-xs">
                        <Beaker className="h-3 w-3 mr-1" />
                        {combo.total_active_percent}% Actives
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
              <CardContent className="p-4">
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">{combo.tagline}</p>
                
                {/* Engine Breakdown - Show key actives from active_breakdown */}
                {combo.active_breakdown && Object.keys(combo.active_breakdown).length > 0 && (
                  <div className="mb-3 p-2 bg-purple-50 rounded-lg">
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(combo.active_breakdown).map(([productId, data], idx) => (
                        <Badge 
                          key={productId}
                          className={`text-xs ${idx === 0 ? 'bg-purple-200 text-purple-800' : 'bg-pink-200 text-pink-800'}`}
                        >
                          {data.type === 'engine' || idx === 0 ? '🔥' : '🛡️'} {data.label || 'Product'}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Pricing */}
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="text-lg font-bold text-purple-600">${combo.combo_price?.toFixed(2)}</span>
                    <span className="text-sm text-gray-400 line-through ml-2">${combo.original_price?.toFixed(2)}</span>
                  </div>
                  <Badge variant="outline" className="text-green-600 border-green-300">
                    {combo.discount_percent}% OFF
                  </Badge>
                </div>

                {/* Popup Toggle - Green/Red */}
                <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg mb-3">
                  <div className="flex items-center gap-2">
                    <Power className={`h-4 w-4 ${combo.popup_enabled !== false ? 'text-green-500' : 'text-red-500'}`} />
                    <span className="text-sm font-medium">Upsell Popup</span>
                  </div>
                  <button
                    onClick={() => handleTogglePopup(combo)}
                    disabled={togglingPopup === combo.id}
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      combo.popup_enabled !== false 
                        ? 'bg-green-500' 
                        : 'bg-red-500'
                    } ${togglingPopup === combo.id ? 'opacity-50' : ''}`}
                    data-testid={`popup-toggle-${combo.id}`}
                  >
                    <span 
                      className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                        combo.popup_enabled !== false ? 'translate-x-6' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
                
                {/* Action Buttons */}
                <div className="flex gap-2">
                  <Button 
                    size="sm" 
                    variant="outline" 
                    className="flex-1" 
                    onClick={() => handleEdit(combo)}
                    data-testid={`edit-combo-${combo.id}`}
                  >
                    <Edit className="h-3 w-3 mr-1" /> Edit
                  </Button>
                  <Button 
                    size="sm" 
                    variant="outline" 
                    className="text-red-500 hover:bg-red-50" 
                    onClick={() => handleDelete(combo.id)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package className="h-5 w-5 text-purple-500" />
              {editingCombo ? 'Edit Combo Offer' : 'Create Combo Offer'}
            </DialogTitle>
          </DialogHeader>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Left: Product Selection */}
            <div className="space-y-4">
              <Label>Select Products (2-4)</Label>
              <Select onValueChange={handleAddProduct}>
                <SelectTrigger>
                  <SelectValue placeholder="Add a product..." />
                </SelectTrigger>
                <SelectContent>
                  {products
                    .filter(p => !selectedProducts.find(sp => sp.id === p.id))
                    .map(product => (
                      <SelectItem key={product.id} value={product.id}>
                        {product.name} - ${product.price}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>

              {/* Selected Products */}
              <div className="space-y-2">
                {selectedProducts.map((product, idx) => {
                  const activeData = ACTIVE_CONCENTRATIONS[product.id];
                  // Determine engine type - from product, hardcoded data, or smart default
                  const productConcentration = product.active_concentration || activeData?.total || 0;
                  const engineType = product.engine_type || activeData?.type || (idx === 0 ? 'engine' : 'buffer');
                  const isEngine = engineType === 'engine' || engineType === 'Engine';
                  const hasSensitiveTag = (product.tags || []).includes('SENSITIVE');
                  
                  // Use SOOTH/PROTECT labels if SENSITIVE tag detected
                  const useSoothLabels = labelStyle === 'sooth_protect' || hasSensitiveTag;
                  const label1 = useSoothLabels ? '🌿 SOOTH' : '🔥 ENGINE';
                  const label2 = useSoothLabels ? '🛡️ PROTECT' : '🛡️ BUFFER';
                  
                  return (
                    <div key={product.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                        isEngine 
                          ? (useSoothLabels ? 'bg-green-500 text-white' : 'bg-purple-500 text-white')
                          : (useSoothLabels ? 'bg-teal-500 text-white' : 'bg-pink-500 text-white')
                      }`}>
                        {idx + 1}
                      </div>
                      <img 
                        src={product.images?.[0] || '/placeholder.png'} 
                        alt={product.name}
                        className="w-12 h-12 rounded object-cover"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{product.name}</p>
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="text-xs text-gray-500">${product.price}</p>
                          {/* Engine Type Badge - Dynamic based on SENSITIVE tag */}
                          <Badge className={`text-xs ${
                            isEngine 
                              ? (useSoothLabels ? 'bg-green-100 text-green-700' : 'bg-purple-100 text-purple-700')
                              : (useSoothLabels ? 'bg-teal-100 text-teal-700' : 'bg-pink-100 text-pink-700')
                          }`}>
                            {isEngine ? label1 : label2}
                          </Badge>
                          {/* Active Concentration */}
                          {productConcentration > 0 && (
                            <Badge className="bg-amber-100 text-amber-700 text-xs">
                              {productConcentration}%
                            </Badge>
                          )}
                          {/* Show product tags */}
                          {(product.tags || []).slice(0, 2).map(tag => (
                            <Badge key={tag} variant="outline" className="text-xs text-gray-500">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleRemoveProduct(product.id)}
                      >
                        <X className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  );
                })}
              </div>

              {/* Active Load Display */}
              {/* Total Active Load - Auto-calculated from selected products */}
              {selectedProducts.length > 0 && (
                <div className="p-4 bg-gradient-to-r from-amber-50 to-orange-50 rounded-lg border border-amber-200">
                  <div className="flex items-center gap-2 mb-2">
                    <Beaker className="h-5 w-5 text-amber-600" />
                    <span className="font-bold text-amber-800">Total Active Load</span>
                    <span className="text-xs text-amber-600 ml-auto">(Auto-calculated)</span>
                  </div>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-3xl font-bold text-amber-700">{activeLoad.total}%</span>
                    <div className="flex-1 h-3 bg-amber-200 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all"
                        style={{ width: `${Math.min(parseFloat(activeLoad.total), 100)}%` }}
                      />
                    </div>
                  </div>
                  
                  {/* Breakdown by product */}
                  {Object.keys(activeLoad.breakdown).length > 0 && (
                    <div className="space-y-1 mb-3 text-sm">
                      {selectedProducts.map((product, idx) => {
                        const productData = activeLoad.breakdown[product.id];
                        return (
                          <div key={product.id} className="flex items-center justify-between">
                            <span className="flex items-center gap-2">
                              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                                idx === 0 ? 'bg-purple-500 text-white' : 'bg-pink-500 text-white'
                              }`}>
                                {idx + 1}
                              </span>
                              <span className="text-amber-800">{product.name?.substring(0, 30)}...</span>
                            </span>
                            <span className="font-mono font-bold text-amber-700">
                              {productData ? `${productData.total}%` : `${product.active_concentration || 0}%`}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  
                  {parseFloat(activeLoad.total) >= 40 && (
                    <p className="text-xs text-amber-700 border-t border-amber-200 pt-2">
                      <strong>Hyper-Potency Formula:</strong> Clinical-grade concentration for accelerated results
                    </p>
                  )}
                  
                  {parseFloat(activeLoad.total) === 0 && (
                    <p className="text-xs text-orange-600">
                      ⚠️ No active concentrations set on selected products. Edit products to add active_concentration values.
                    </p>
                  )}
                  
                  {/* Combined Key Actives from all selected products */}
                  {selectedProducts.some(p => p.key_actives?.length > 0) && (
                    <div className="mt-3 pt-3 border-t border-amber-200">
                      <div className="flex items-center gap-2 mb-2">
                        <Zap className="h-4 w-4 text-purple-600" />
                        <span className="text-xs font-semibold text-purple-700 uppercase">Combined Engine Profile</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedProducts.map((product, idx) => (
                          product.key_actives?.map((active, i) => {
                            // Handle both string format and object format
                            const activeName = typeof active === 'string' ? active : `${active.name} ${active.percent ? active.percent + '%' : ''}`;
                            return (
                              <Badge 
                                key={`${product.id}-${i}`}
                                className={`text-xs ${idx === 0 ? 'bg-purple-100 text-purple-700' : 'bg-pink-100 text-pink-700'}`}
                              >
                                {activeName.trim()}
                              </Badge>
                            );
                          })
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Full Sync Button - Refresh Math + Generate Calendar Preview */}
              {selectedProducts.length >= 2 && (
                <Button
                  onClick={handleFullSync}
                  disabled={loadingCalendar}
                  variant="outline"
                  className="w-full border-amber-300 text-amber-700 hover:bg-amber-50"
                  data-testid="full-sync-btn"
                >
                  {loadingCalendar ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4 mr-2" />
                  )}
                  Refresh Math & Generate Calendar Preview
                </Button>
              )}

              {/* Calendar Preview Panel */}
              {calendarPreview && (
                <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                  <div className="flex items-center gap-2 mb-3">
                    <Calendar className="h-5 w-5 text-purple-600" />
                    <span className="font-bold text-purple-800">12-Week Calendar Preview</span>
                    <Badge className={labelStyle === 'sooth_protect' ? 'bg-green-100 text-green-700' : 'bg-purple-100 text-purple-700'}>
                      {labelStyle === 'sooth_protect' ? 'SOOTH/PROTECT' : 'ENGINE/BUFFER'}
                    </Badge>
                  </div>
                  
                  {/* Pro Tip */}
                  {calendarPreview.pro_tip && (
                    <div className="mb-3 p-2 bg-blue-50 rounded border border-blue-200 text-xs text-blue-800">
                      {calendarPreview.pro_tip}
                    </div>
                  )}
                  
                  {/* Potency Warning */}
                  {calendarPreview.potency_warning && (
                    <div className="mb-3 p-2 bg-red-50 rounded border border-red-200 text-xs text-red-700 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4" />
                      {calendarPreview.potency_warning}
                    </div>
                  )}
                  
                  {/* Tags Detected */}
                  <div className="mb-3">
                    <span className="text-xs font-semibold text-purple-700 uppercase">Tags Detected:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {calendarPreview.all_tags?.map(tag => (
                        <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
                      ))}
                    </div>
                  </div>
                  
                  {/* Milestone Preview */}
                  <div className="space-y-2">
                    <span className="text-xs font-semibold text-purple-700 uppercase">Milestones ({calendarPreview.milestones?.length || 0}):</span>
                    {calendarPreview.milestones?.length > 0 ? (
                      calendarPreview.milestones.map((milestone, idx) => (
                        <div key={idx} className="p-2 bg-white rounded border text-xs">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-semibold text-purple-800">{milestone.phase_name}</span>
                            <Badge variant="outline" className="text-xs">Days {milestone.day_start}-{milestone.day_end}</Badge>
                          </div>
                          <p className="text-gray-600">{milestone.description?.substring(0, 150)}...</p>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-gray-500 italic">No milestones matched. Add clinical tags to products.</p>
                    )}
                  </div>
                </div>
              )}

              {/* AI Generate Button */}
              {selectedProducts.length >= 2 && (
                <Button 
                  onClick={generateWithAI}
                  disabled={generating}
                  className="w-full bg-gradient-to-r from-indigo-500 to-purple-500"
                >
                  {generating ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4 mr-2" />
                  )}
                  {generating ? 'Generating...' : 'Generate with AI'}
                </Button>
              )}

              {/* Pricing Preview */}
              {selectedProducts.length >= 2 && (
                <div className="p-4 bg-green-50 rounded-lg">
                  <div className="flex justify-between mb-2">
                    <span className="text-gray-600">Original:</span>
                    <span className="line-through">${prices.original.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between mb-2">
                    <span className="text-gray-600">Discount:</span>
                    <span className="text-red-500">-{comboData.discount_percent}%</span>
                  </div>
                  <div className="flex justify-between font-bold text-lg">
                    <span>Combo Price:</span>
                    <span className="text-green-600">${prices.discounted.toFixed(2)}</span>
                  </div>
                  <p className="text-xs text-green-600 mt-1">
                    Customer saves ${prices.savings.toFixed(2)}
                  </p>
                </div>
              )}
            </div>

            {/* Right: Combo Details */}
            <div className="space-y-4">
              <div>
                <Label>Combo Name *</Label>
                <Input
                  value={comboData.name}
                  onChange={(e) => setComboData({ ...comboData, name: e.target.value })}
                  placeholder="e.g., Resurface & Rebuild Duo"
                />
              </div>

              <div>
                <Label>URL Slug (for shareable links)</Label>
                <div className="flex gap-2 items-center">
                  <span className="text-sm text-gray-500">reroots.ca/skincare-sets/</span>
                  <Input
                    value={comboData.slug || ''}
                    onChange={(e) => setComboData({ ...comboData, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-') })}
                    placeholder="pdrn-power-duo"
                    className="flex-1"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1">Leave empty to auto-generate from name. Use lowercase letters, numbers, and hyphens only.</p>
              </div>

              <div>
                <Label>Tagline</Label>
                <Input
                  value={comboData.tagline}
                  onChange={(e) => setComboData({ ...comboData, tagline: e.target.value })}
                  placeholder="e.g., The ultimate skin transformation protocol"
                />
              </div>

              <div>
                <Label>Description</Label>
                <Textarea
                  value={comboData.description}
                  onChange={(e) => setComboData({ ...comboData, description: e.target.value })}
                  placeholder="Describe the synergy between products..."
                  rows={3}
                />
              </div>

              {/* Pricing Options */}
              <div className="p-4 bg-green-50 rounded-lg border border-green-200 space-y-4">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="h-4 w-4 text-green-600" />
                  <span className="font-medium text-green-800 text-sm">Pricing Options</span>
                </div>
                
                {/* Pricing Type Selector */}
                <div className="flex gap-2">
                  <button
                    onClick={() => setComboData({ ...comboData, discount_type: 'percent' })}
                    className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
                      comboData.discount_type === 'percent' || !comboData.discount_type
                        ? 'bg-green-600 text-white'
                        : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    % Discount
                  </button>
                  <button
                    onClick={() => setComboData({ ...comboData, discount_type: 'fixed' })}
                    className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
                      comboData.discount_type === 'fixed'
                        ? 'bg-green-600 text-white'
                        : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    $ Fixed Price
                  </button>
                </div>
                
                {/* Discount Percentage Input */}
                {(comboData.discount_type === 'percent' || !comboData.discount_type) && (
                  <div>
                    <Label className="text-green-700">Discount Percentage (%)</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <Input
                        type="number"
                        min="0"
                        max="50"
                        value={comboData.discount_percent}
                        onChange={(e) => setComboData({ ...comboData, discount_percent: parseInt(e.target.value) || 0 })}
                        className="max-w-[120px]"
                      />
                      <span className="text-green-600 font-medium">% OFF</span>
                    </div>
                  </div>
                )}
                
                {/* Fixed Price Input */}
                {comboData.discount_type === 'fixed' && (
                  <div>
                    <Label className="text-green-700">Fixed Combo Price ($)</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-green-600 font-medium">$</span>
                      <Input
                        type="number"
                        min="0"
                        step="0.01"
                        value={comboData.fixed_price || ''}
                        onChange={(e) => {
                          const fixedPrice = parseFloat(e.target.value) || 0;
                          // Auto-calculate discount percent from fixed price
                          let calculatedDiscount = 0;
                          if (prices?.originalPrice && fixedPrice > 0) {
                            calculatedDiscount = Math.round(((prices.originalPrice - fixedPrice) / prices.originalPrice) * 100);
                          }
                          setComboData({ 
                            ...comboData, 
                            fixed_price: fixedPrice,
                            discount_percent: calculatedDiscount > 0 ? calculatedDiscount : comboData.discount_percent
                          });
                        }}
                        placeholder="Enter combo price"
                        className="max-w-[150px]"
                      />
                      <span className="text-gray-500 text-sm">CAD</span>
                    </div>
                    {prices?.originalPrice && comboData.fixed_price > 0 && (
                      <p className="text-xs text-gray-500 mt-1">
                        Original total: ${prices.originalPrice.toFixed(2)} • 
                        You save customer: ${(prices.originalPrice - comboData.fixed_price).toFixed(2)} 
                        <span className="text-green-600 font-semibold ml-1">
                          ({Math.round(((prices.originalPrice - comboData.fixed_price) / prices.originalPrice) * 100)}% OFF)
                        </span>
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Toggle Switches */}
              <div className="space-y-3 p-4 bg-gray-50 rounded-lg">
                {/* Combo Active Toggle */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Eye className="h-4 w-4 text-gray-600" />
                    <span className="text-sm font-medium">Combo Visible on Store</span>
                  </div>
                  <button
                    onClick={() => setComboData({ ...comboData, is_active: !comboData.is_active })}
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      comboData.is_active 
                        ? 'bg-green-500' 
                        : 'bg-red-500'
                    }`}
                  >
                    <span 
                      className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                        comboData.is_active ? 'translate-x-6' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                {/* Popup Enabled Toggle */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Power className={`h-4 w-4 ${comboData.popup_enabled ? 'text-green-500' : 'text-red-500'}`} />
                    <span className="text-sm font-medium">Upsell Popup Enabled</span>
                  </div>
                  <button
                    onClick={() => setComboData({ ...comboData, popup_enabled: !comboData.popup_enabled })}
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      comboData.popup_enabled 
                        ? 'bg-green-500' 
                        : 'bg-red-500'
                    }`}
                    data-testid="popup-enabled-toggle"
                  >
                    <span 
                      className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                        comboData.popup_enabled ? 'translate-x-6' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                {/* Custom Popup Content - Only show when popup is enabled */}
                {comboData.popup_enabled && (
                  <div className="p-4 bg-purple-50 rounded-lg border border-purple-200 space-y-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Sparkles className="h-4 w-4 text-purple-600" />
                      <span className="font-medium text-purple-800 text-sm">Customize Popup Content</span>
                    </div>
                    
                    <div>
                      <Label className="text-xs text-purple-700">Custom Headline (optional)</Label>
                      <Input
                        value={comboData.popup_headline || ''}
                        onChange={(e) => setComboData({ ...comboData, popup_headline: e.target.value })}
                        placeholder="e.g., Complete Your Clinical Protocol!"
                        className="mt-1"
                        data-testid="popup-headline-input"
                      />
                      <p className="text-xs text-gray-500 mt-1">Leave empty for auto-generated headline</p>
                    </div>
                    
                    <div>
                      <Label className="text-xs text-purple-700">Custom Message (optional)</Label>
                      <Textarea
                        value={comboData.popup_message || ''}
                        onChange={(e) => setComboData({ ...comboData, popup_message: e.target.value })}
                        placeholder="e.g., Step 1 requires Step 2 to lock in results. Without the Buffer, the Engine's acids can cause sensitivity."
                        className="mt-1"
                        rows={3}
                        data-testid="popup-message-input"
                      />
                      <p className="text-xs text-gray-500 mt-1">Leave empty for AI-generated message based on products</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Safety Warnings */}
              {(comboData.warnings?.length > 0 || comboData.do_not_use_with?.length > 0) && (
                <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span className="font-medium text-amber-800 text-sm">Safety Information</span>
                  </div>
                  {comboData.warnings?.length > 0 && (
                    <ul className="text-xs text-amber-700 space-y-1 mb-2">
                      {comboData.warnings.map((w, i) => (
                        <li key={i}>• {w}</li>
                      ))}
                    </ul>
                  )}
                  {comboData.do_not_use_with?.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {comboData.do_not_use_with.map((item, i) => (
                        <Badge key={i} variant="outline" className="text-xs text-red-600 border-red-300">
                          {item}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleSave}
              className="bg-gradient-to-r from-purple-600 to-pink-500"
              data-testid="save-combo-btn"
            >
              <Save className="h-4 w-4 mr-2" />
              {editingCombo ? 'Update Combo' : 'Create Combo'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <Trash2 className="h-5 w-5" />
              Delete Combo Offer
            </DialogTitle>
          </DialogHeader>
          <p className="text-gray-600 py-4">
            Are you sure you want to delete this combo offer? This action cannot be undone.
          </p>
          <div className="flex gap-3 justify-end">
            <Button 
              variant="outline" 
              onClick={() => {
                setShowDeleteConfirm(false);
                setComboToDelete(null);
              }}
            >
              No, Cancel
            </Button>
            <Button 
              variant="destructive"
              onClick={confirmDelete}
            >
              Yes, Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ComboOffersManager;
