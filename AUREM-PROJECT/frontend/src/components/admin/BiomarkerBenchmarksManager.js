import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useWebSocket, useWebSocketEvent } from '@/contexts';
import { 
  GitCompare, Plus, Edit3, Trash2, Save, X, 
  ChevronDown, ChevronUp, GripVertical, Settings,
  Activity, Droplets, Sparkles, Sun, Zap, Target,
  Check, RefreshCw, Eye, EyeOff, Wifi, WifiOff, Package, ShoppingBag
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Switch } from '../ui/switch';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Checkbox } from '../ui/checkbox';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Category icon mapping
const categoryIcons = {
  skin_age: Activity,
  hydration: Droplets,
  elasticity: Sparkles,
  pigmentation: Sun,
  texture: Zap,
  inflammation: Target,
  general: Settings,
};

// Default benchmark template
const defaultBenchmark = {
  name: '',
  category: 'general',
  unit: '',
  low_threshold: 20,
  optimal_min: 40,
  optimal_max: 70,
  high_threshold: 90,
  low_label: 'Low',
  optimal_label: 'Optimal',
  high_label: 'High',
  low_advice: '',
  optimal_advice: '',
  high_advice: '',
  low_recommendations: [],
  high_recommendations: [],
  color_low: '#EF4444',
  color_optimal: '#22C55E',
  color_high: '#F59E0B',
  is_active: true,
};

// Sortable Benchmark Item Component
const SortableBenchmarkItem = ({ benchmark, onEdit, onDelete, onToggleActive, deleting, getCategoryIcon, renderBenchmarkBar, products }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: benchmark.id });
  
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1000 : 1,
  };
  
  // Get product names for recommendations
  const getLowProductNames = () => {
    if (!benchmark.low_recommendations?.length) return null;
    const productNames = benchmark.low_recommendations
      .map(id => products.find(p => p.id === id)?.name)
      .filter(Boolean);
    return productNames.length > 0 ? productNames.join(', ') : null;
  };
  
  const getHighProductNames = () => {
    if (!benchmark.high_recommendations?.length) return null;
    const productNames = benchmark.high_recommendations
      .map(id => products.find(p => p.id === id)?.name)
      .filter(Boolean);
    return productNames.length > 0 ? productNames.join(', ') : null;
  };
  
  return (
    <div 
      ref={setNodeRef}
      style={style}
      className={`border rounded-lg p-4 transition-all ${
        benchmark.is_active ? 'bg-white hover:shadow-md' : 'bg-gray-50 opacity-60'
      } ${isDragging ? 'shadow-lg ring-2 ring-purple-300' : ''}`}
      data-testid={`benchmark-${benchmark.id}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1">
          {/* Drag Handle */}
          <div 
            {...attributes} 
            {...listeners}
            className="cursor-grab active:cursor-grabbing p-1 hover:bg-gray-100 rounded mt-1"
            data-testid={`drag-handle-${benchmark.id}`}
          >
            <GripVertical className="h-5 w-5 text-gray-400" />
          </div>
          
          <div className={`p-2 rounded-lg ${benchmark.is_active ? 'bg-purple-100' : 'bg-gray-100'}`}>
            {getCategoryIcon(benchmark.category)}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-gray-900">{benchmark.name}</h4>
              {benchmark.unit && (
                <Badge variant="outline" className="text-xs">{benchmark.unit}</Badge>
              )}
              <Badge 
                variant={benchmark.is_active ? "default" : "secondary"}
                className="text-xs"
              >
                {benchmark.category}
              </Badge>
            </div>
            
            {/* Benchmark bar visualization */}
            <div className="mt-3 space-y-1">
              {renderBenchmarkBar(benchmark)}
              <div className="flex justify-between text-xs text-gray-500">
                <span style={{ color: benchmark.color_low }}>{benchmark.low_label}: &lt;{benchmark.optimal_min}</span>
                <span style={{ color: benchmark.color_optimal }}>{benchmark.optimal_label}: {benchmark.optimal_min}-{benchmark.optimal_max}</span>
                <span style={{ color: benchmark.color_high }}>{benchmark.high_label}: &gt;{benchmark.optimal_max}</span>
              </div>
            </div>
            
            {/* Product Recommendations Preview */}
            {(getLowProductNames() || getHighProductNames()) && (
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                {getLowProductNames() && (
                  <span className="flex items-center gap-1 text-red-600 bg-red-50 px-2 py-0.5 rounded">
                    <Package className="h-3 w-3" />
                    Low: {getLowProductNames()}
                  </span>
                )}
                {getHighProductNames() && (
                  <span className="flex items-center gap-1 text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
                    <Package className="h-3 w-3" />
                    High: {getHighProductNames()}
                  </span>
                )}
              </div>
            )}
            
            {/* Advice preview */}
            {benchmark.optimal_advice && (
              <p className="text-sm text-gray-500 mt-2 line-clamp-1">
                <span className="text-green-600">Optimal advice:</span> {benchmark.optimal_advice}
              </p>
            )}
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex items-center gap-2 ml-4">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onToggleActive(benchmark)}
            title={benchmark.is_active ? 'Deactivate' : 'Activate'}
          >
            {benchmark.is_active ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onEdit(benchmark)}
            data-testid={`edit-benchmark-${benchmark.id}`}
          >
            <Edit3 className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-red-500 hover:text-red-700 hover:bg-red-50"
            onClick={() => onDelete(benchmark)}
            disabled={deleting === benchmark.id}
            data-testid={`delete-benchmark-${benchmark.id}`}
          >
            {deleting === benchmark.id ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

const BiomarkerBenchmarksManager = () => {
  const [benchmarks, setBenchmarks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  
  // Dialog states
  const [showEditor, setShowEditor] = useState(false);
  const [editingBenchmark, setEditingBenchmark] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [reordering, setReordering] = useState(false);
  
  // WebSocket connection status
  const { isConnected } = useWebSocket();
  
  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );
  
  // Fetch benchmarks
  const fetchBenchmarks = useCallback(async () => {
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      
      const [benchmarksRes, categoriesRes, productsRes] = await Promise.all([
        axios.get(`${API}/api/admin/biomarker-benchmarks`, { headers }),
        axios.get(`${API}/api/admin/biomarker-benchmarks/categories`, { headers }),
        axios.get(`${API}/api/products`, { headers }),
      ]);
      
      setBenchmarks(benchmarksRes.data.benchmarks || []);
      setCategories(categoriesRes.data.categories || []);
      setProducts(productsRes.data.products || []);
    } catch (error) {
      console.error('Failed to fetch benchmarks:', error);
      toast.error('Failed to load biomarker benchmarks');
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchBenchmarks();
  }, [fetchBenchmarks]);
  
  // WebSocket event handlers for real-time updates
  const handleBiomarkerCreated = useCallback((data) => {
    toast.success(`Biomarker "${data.name}" created`);
    fetchBenchmarks();
  }, [fetchBenchmarks]);
  
  const handleBiomarkerUpdated = useCallback((data) => {
    toast.info(`Biomarker "${data.name}" updated`);
    fetchBenchmarks();
  }, [fetchBenchmarks]);
  
  const handleBiomarkerDeleted = useCallback((data) => {
    toast.info(`Biomarker "${data.name}" deleted`);
    fetchBenchmarks();
  }, [fetchBenchmarks]);
  
  useWebSocketEvent('biomarker_created', handleBiomarkerCreated);
  useWebSocketEvent('biomarker_updated', handleBiomarkerUpdated);
  useWebSocketEvent('biomarker_deleted', handleBiomarkerDeleted);
  
  // Create new benchmark
  const handleCreate = () => {
    setEditingBenchmark({ ...defaultBenchmark });
    setShowEditor(true);
  };
  
  // Edit existing benchmark
  const handleEdit = (benchmark) => {
    setEditingBenchmark({ ...benchmark });
    setShowEditor(true);
  };
  
  // Save benchmark
  const handleSave = async () => {
    if (!editingBenchmark.name.trim()) {
      toast.error('Please enter a benchmark name');
      return;
    }
    
    setSaving(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      
      if (editingBenchmark.id) {
        // Update existing
        await axios.put(
          `${API}/api/admin/biomarker-benchmarks/${editingBenchmark.id}`,
          editingBenchmark,
          { headers }
        );
        toast.success('Benchmark updated successfully');
      } else {
        // Create new
        await axios.post(
          `${API}/api/admin/biomarker-benchmarks`,
          editingBenchmark,
          { headers }
        );
        toast.success('Benchmark created successfully');
      }
      
      setShowEditor(false);
      setEditingBenchmark(null);
      fetchBenchmarks();
    } catch (error) {
      console.error('Failed to save benchmark:', error);
      toast.error('Failed to save benchmark');
    } finally {
      setSaving(false);
    }
  };
  
  // Delete benchmark
  const handleDelete = async (benchmark) => {
    setDeleting(benchmark.id);
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.delete(
        `${API}/api/admin/biomarker-benchmarks/${benchmark.id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('Benchmark deleted');
      fetchBenchmarks();
    } catch (error) {
      console.error('Failed to delete benchmark:', error);
      toast.error('Failed to delete benchmark');
    } finally {
      setDeleting(null);
    }
  };
  
  // Toggle active status
  const handleToggleActive = async (benchmark) => {
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.put(
        `${API}/api/admin/biomarker-benchmarks/${benchmark.id}`,
        { is_active: !benchmark.is_active },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(benchmark.is_active ? 'Benchmark deactivated' : 'Benchmark activated');
      fetchBenchmarks();
    } catch (error) {
      console.error('Failed to toggle status:', error);
      toast.error('Failed to update status');
    }
  };
  
  // Handle drag end for reordering
  const handleDragEnd = async (event) => {
    const { active, over } = event;
    
    if (!over || active.id === over.id) return;
    
    const oldIndex = benchmarks.findIndex(b => b.id === active.id);
    const newIndex = benchmarks.findIndex(b => b.id === over.id);
    
    // Optimistic update
    const newBenchmarks = arrayMove(benchmarks, oldIndex, newIndex);
    setBenchmarks(newBenchmarks);
    
    // Save new order to backend
    setReordering(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const order = newBenchmarks.map((b, index) => ({
        id: b.id,
        display_order: index
      }));
      
      await axios.put(
        `${API}/api/admin/biomarker-benchmarks/reorder`,
        { order },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('Order updated');
    } catch (error) {
      console.error('Failed to reorder:', error);
      toast.error('Failed to save order');
      // Revert on error
      fetchBenchmarks();
    } finally {
      setReordering(false);
    }
  };
  
  // Get category icon component
  const getCategoryIcon = (category) => {
    const Icon = categoryIcons[category] || Settings;
    return <Icon className="h-4 w-4" />;
  };
  
  // Render benchmark visualization
  const renderBenchmarkBar = (benchmark) => {
    const total = benchmark.high_threshold;
    const lowPct = (benchmark.low_threshold / total) * 100;
    const optimalMinPct = (benchmark.optimal_min / total) * 100;
    const optimalMaxPct = (benchmark.optimal_max / total) * 100;
    
    return (
      <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden">
        {/* Low range */}
        <div 
          className="absolute h-full" 
          style={{ 
            left: 0, 
            width: `${optimalMinPct}%`, 
            backgroundColor: benchmark.color_low 
          }} 
        />
        {/* Optimal range */}
        <div 
          className="absolute h-full" 
          style={{ 
            left: `${optimalMinPct}%`, 
            width: `${optimalMaxPct - optimalMinPct}%`, 
            backgroundColor: benchmark.color_optimal 
          }} 
        />
        {/* High range */}
        <div 
          className="absolute h-full" 
          style={{ 
            left: `${optimalMaxPct}%`, 
            width: `${100 - optimalMaxPct}%`, 
            backgroundColor: benchmark.color_high 
          }} 
        />
      </div>
    );
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <RefreshCw className="h-8 w-8 animate-spin text-pink-500" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6" data-testid="biomarker-benchmarks-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <GitCompare className="h-6 w-6 text-purple-600" />
            Biomarker Benchmarks
          </h2>
          <p className="text-gray-600 text-sm mt-1">
            Manage reference ranges for the comparison tool
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* WebSocket Status */}
          <div 
            className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
              isConnected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
            }`}
            title={isConnected ? 'Real-time updates active' : 'Connecting...'}
          >
            {isConnected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
            <span>{isConnected ? 'Live' : 'Offline'}</span>
          </div>
          <Button onClick={handleCreate} className="bg-purple-600 hover:bg-purple-700" data-testid="create-benchmark-btn">
            <Plus className="h-4 w-4 mr-2" />
            Add Biomarker
          </Button>
        </div>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-purple-600">{benchmarks.length}</p>
            <p className="text-sm text-gray-600">Total Biomarkers</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-green-600">{benchmarks.filter(b => b.is_active).length}</p>
            <p className="text-sm text-gray-600">Active</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-amber-600">{categories.length}</p>
            <p className="text-sm text-gray-600">Categories</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold text-blue-600">{products.length}</p>
            <p className="text-sm text-gray-600">Products</p>
          </CardContent>
        </Card>
      </div>
      
      {/* Benchmarks List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-purple-600" />
            Benchmarks
          </CardTitle>
          <CardDescription>
            Define optimal ranges and advice for each biomarker
          </CardDescription>
        </CardHeader>
        <CardContent>
          {benchmarks.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <GitCompare className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No biomarker benchmarks yet</p>
              <p className="text-sm">Create your first benchmark to get started</p>
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={benchmarks.map(b => b.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-4">
                  {reordering && (
                    <div className="text-center text-sm text-purple-600 flex items-center justify-center gap-2">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Saving order...
                    </div>
                  )}
                  {benchmarks.map((benchmark) => (
                    <SortableBenchmarkItem
                      key={benchmark.id}
                      benchmark={benchmark}
                      onEdit={handleEdit}
                      onDelete={handleDelete}
                      onToggleActive={handleToggleActive}
                      deleting={deleting}
                      getCategoryIcon={getCategoryIcon}
                      renderBenchmarkBar={renderBenchmarkBar}
                      products={products}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}
        </CardContent>
      </Card>
      
      {/* Editor Dialog */}
      <Dialog open={showEditor} onOpenChange={setShowEditor}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <GitCompare className="h-5 w-5 text-purple-600" />
              {editingBenchmark?.id ? 'Edit Biomarker' : 'New Biomarker'}
            </DialogTitle>
            <DialogDescription>
              Configure the biomarker's reference ranges and advice
            </DialogDescription>
          </DialogHeader>
          
          {editingBenchmark && (
            <Tabs defaultValue="basic" className="mt-4">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Basic Info</TabsTrigger>
                <TabsTrigger value="ranges">Ranges</TabsTrigger>
                <TabsTrigger value="advice">Advice</TabsTrigger>
                <TabsTrigger value="products">Products</TabsTrigger>
              </TabsList>
              
              <TabsContent value="basic" className="space-y-4 mt-4">
                <div>
                  <Label>Biomarker Name *</Label>
                  <Input
                    value={editingBenchmark.name}
                    onChange={(e) => setEditingBenchmark({...editingBenchmark, name: e.target.value})}
                    placeholder="e.g., Collagen Density"
                    data-testid="benchmark-name-input"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Category</Label>
                    <Select
                      value={editingBenchmark.category}
                      onValueChange={(v) => setEditingBenchmark({...editingBenchmark, category: v})}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select category" />
                      </SelectTrigger>
                      <SelectContent>
                        {categories.map(cat => (
                          <SelectItem key={cat.value} value={cat.value}>
                            {cat.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div>
                    <Label>Unit (optional)</Label>
                    <Input
                      value={editingBenchmark.unit}
                      onChange={(e) => setEditingBenchmark({...editingBenchmark, unit: e.target.value})}
                      placeholder="e.g., %, score, mg/ml"
                    />
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Active</Label>
                    <p className="text-sm text-gray-500">Show this biomarker in the comparison tool</p>
                  </div>
                  <Switch
                    checked={editingBenchmark.is_active}
                    onCheckedChange={(v) => setEditingBenchmark({...editingBenchmark, is_active: v})}
                  />
                </div>
              </TabsContent>
              
              <TabsContent value="ranges" className="space-y-4 mt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Low Threshold</Label>
                    <Input
                      type="number"
                      value={editingBenchmark.low_threshold}
                      onChange={(e) => setEditingBenchmark({...editingBenchmark, low_threshold: parseFloat(e.target.value) || 0})}
                    />
                  </div>
                  <div>
                    <Label>Low Label</Label>
                    <Input
                      value={editingBenchmark.low_label}
                      onChange={(e) => setEditingBenchmark({...editingBenchmark, low_label: e.target.value})}
                      placeholder="Low"
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Optimal Min</Label>
                    <Input
                      type="number"
                      value={editingBenchmark.optimal_min}
                      onChange={(e) => setEditingBenchmark({...editingBenchmark, optimal_min: parseFloat(e.target.value) || 0})}
                    />
                  </div>
                  <div>
                    <Label>Optimal Max</Label>
                    <Input
                      type="number"
                      value={editingBenchmark.optimal_max}
                      onChange={(e) => setEditingBenchmark({...editingBenchmark, optimal_max: parseFloat(e.target.value) || 0})}
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Optimal Label</Label>
                    <Input
                      value={editingBenchmark.optimal_label}
                      onChange={(e) => setEditingBenchmark({...editingBenchmark, optimal_label: e.target.value})}
                      placeholder="Optimal"
                    />
                  </div>
                  <div>
                    <Label>High Threshold</Label>
                    <Input
                      type="number"
                      value={editingBenchmark.high_threshold}
                      onChange={(e) => setEditingBenchmark({...editingBenchmark, high_threshold: parseFloat(e.target.value) || 0})}
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>High Label</Label>
                    <Input
                      value={editingBenchmark.high_label}
                      onChange={(e) => setEditingBenchmark({...editingBenchmark, high_label: e.target.value})}
                      placeholder="High"
                    />
                  </div>
                </div>
                
                {/* Colors */}
                <div className="space-y-2">
                  <Label>Range Colors</Label>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={editingBenchmark.color_low}
                        onChange={(e) => setEditingBenchmark({...editingBenchmark, color_low: e.target.value})}
                        className="w-8 h-8 rounded cursor-pointer"
                      />
                      <span className="text-sm">Low</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={editingBenchmark.color_optimal}
                        onChange={(e) => setEditingBenchmark({...editingBenchmark, color_optimal: e.target.value})}
                        className="w-8 h-8 rounded cursor-pointer"
                      />
                      <span className="text-sm">Optimal</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={editingBenchmark.color_high}
                        onChange={(e) => setEditingBenchmark({...editingBenchmark, color_high: e.target.value})}
                        className="w-8 h-8 rounded cursor-pointer"
                      />
                      <span className="text-sm">High</span>
                    </div>
                  </div>
                </div>
                
                {/* Preview */}
                <div className="mt-4">
                  <Label>Preview</Label>
                  <div className="mt-2">
                    {renderBenchmarkBar(editingBenchmark)}
                  </div>
                </div>
              </TabsContent>
              
              <TabsContent value="advice" className="space-y-4 mt-4">
                <div>
                  <Label>Low Range Advice</Label>
                  <Textarea
                    value={editingBenchmark.low_advice}
                    onChange={(e) => setEditingBenchmark({...editingBenchmark, low_advice: e.target.value})}
                    placeholder="What to do when this value is low..."
                    rows={3}
                  />
                </div>
                
                <div>
                  <Label>Optimal Range Advice</Label>
                  <Textarea
                    value={editingBenchmark.optimal_advice}
                    onChange={(e) => setEditingBenchmark({...editingBenchmark, optimal_advice: e.target.value})}
                    placeholder="Maintaining optimal levels..."
                    rows={3}
                  />
                </div>
                
                <div>
                  <Label>High Range Advice</Label>
                  <Textarea
                    value={editingBenchmark.high_advice}
                    onChange={(e) => setEditingBenchmark({...editingBenchmark, high_advice: e.target.value})}
                    placeholder="What to do when this value is high..."
                    rows={3}
                  />
                </div>
              </TabsContent>
              
              <TabsContent value="products" className="space-y-6 mt-4">
                <p className="text-sm text-gray-500">
                  Select products to recommend when a customer's biomarker falls in specific ranges.
                </p>
                
                {/* Low Range Recommendations */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded" style={{ backgroundColor: editingBenchmark.color_low }} />
                    <Label className="text-red-600">Products for Low Range ({editingBenchmark.low_label})</Label>
                  </div>
                  <p className="text-xs text-gray-500">
                    Recommend these products when the biomarker value is below {editingBenchmark.optimal_min}
                  </p>
                  <div className="max-h-48 overflow-y-auto border rounded-lg p-3 space-y-2">
                    {products.length === 0 ? (
                      <p className="text-sm text-gray-400 text-center py-4">No products available</p>
                    ) : (
                      products.map(product => (
                        <div 
                          key={product.id} 
                          className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded"
                        >
                          <Checkbox
                            id={`low-${product.id}`}
                            checked={(editingBenchmark.low_recommendations || []).includes(product.id)}
                            onCheckedChange={(checked) => {
                              const current = editingBenchmark.low_recommendations || [];
                              const updated = checked 
                                ? [...current, product.id]
                                : current.filter(id => id !== product.id);
                              setEditingBenchmark({...editingBenchmark, low_recommendations: updated});
                            }}
                          />
                          <label 
                            htmlFor={`low-${product.id}`}
                            className="flex items-center gap-2 flex-1 cursor-pointer"
                          >
                            {product.images?.[0] && (
                              <img 
                                src={product.images[0]} 
                                alt={product.name} 
                                className="w-8 h-8 object-cover rounded"
                              />
                            )}
                            <span className="text-sm">{product.name}</span>
                            <span className="text-xs text-gray-400 ml-auto">${product.price}</span>
                          </label>
                        </div>
                      ))
                    )}
                  </div>
                  {editingBenchmark.low_recommendations?.length > 0 && (
                    <p className="text-xs text-gray-500">
                      {editingBenchmark.low_recommendations.length} product(s) selected
                    </p>
                  )}
                </div>
                
                {/* High Range Recommendations */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded" style={{ backgroundColor: editingBenchmark.color_high }} />
                    <Label className="text-amber-600">Products for High Range ({editingBenchmark.high_label})</Label>
                  </div>
                  <p className="text-xs text-gray-500">
                    Recommend these products when the biomarker value is above {editingBenchmark.optimal_max}
                  </p>
                  <div className="max-h-48 overflow-y-auto border rounded-lg p-3 space-y-2">
                    {products.length === 0 ? (
                      <p className="text-sm text-gray-400 text-center py-4">No products available</p>
                    ) : (
                      products.map(product => (
                        <div 
                          key={product.id} 
                          className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded"
                        >
                          <Checkbox
                            id={`high-${product.id}`}
                            checked={(editingBenchmark.high_recommendations || []).includes(product.id)}
                            onCheckedChange={(checked) => {
                              const current = editingBenchmark.high_recommendations || [];
                              const updated = checked 
                                ? [...current, product.id]
                                : current.filter(id => id !== product.id);
                              setEditingBenchmark({...editingBenchmark, high_recommendations: updated});
                            }}
                          />
                          <label 
                            htmlFor={`high-${product.id}`}
                            className="flex items-center gap-2 flex-1 cursor-pointer"
                          >
                            {product.images?.[0] && (
                              <img 
                                src={product.images[0]} 
                                alt={product.name} 
                                className="w-8 h-8 object-cover rounded"
                              />
                            )}
                            <span className="text-sm">{product.name}</span>
                            <span className="text-xs text-gray-400 ml-auto">${product.price}</span>
                          </label>
                        </div>
                      ))
                    )}
                  </div>
                  {editingBenchmark.high_recommendations?.length > 0 && (
                    <p className="text-xs text-gray-500">
                      {editingBenchmark.high_recommendations.length} product(s) selected
                    </p>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          )}
          
          <DialogFooter className="mt-6">
            <Button variant="outline" onClick={() => setShowEditor(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleSave} 
              disabled={saving}
              className="bg-purple-600 hover:bg-purple-700"
              data-testid="save-benchmark-btn"
            >
              {saving ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save Benchmark
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BiomarkerBenchmarksManager;
