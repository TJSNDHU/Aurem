import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  FolderOpen, Plus, Edit, Trash2, GripVertical, Image,
  Save, X, Search, Eye, EyeOff, Star, Package
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const CollectionsManager = () => {
  const [collections, setCollections] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingCollection, setEditingCollection] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [selectedProducts, setSelectedProducts] = useState([]);
  const [productSearch, setProductSearch] = useState('');

  // Load collections from localStorage (or could be API)
  useEffect(() => {
    const savedCollections = localStorage.getItem('reroots_collections');
    if (savedCollections) {
      setCollections(JSON.parse(savedCollections));
    } else {
      // Default collections
      setCollections([
        {
          id: '1',
          name: 'Anti-Aging Protocol',
          description: 'Complete anti-aging skincare routine',
          image: '',
          products: [],
          featured: true,
          active: true,
          createdAt: new Date().toISOString()
        },
        {
          id: '2',
          name: 'Post-Treatment Care',
          description: 'Gentle products for sensitive, treated skin',
          image: '',
          products: [],
          featured: false,
          active: true,
          createdAt: new Date().toISOString()
        }
      ]);
    }
    setLoading(false);
  }, []);

  // Fetch products
  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        const response = await axios.get(`${API}/products`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setProducts(response.data || []);
      } catch (error) {
        console.error('Failed to fetch products:', error);
      }
    };
    fetchProducts();
  }, []);

  // Save collections to localStorage
  const saveCollections = (newCollections) => {
    setCollections(newCollections);
    localStorage.setItem('reroots_collections', JSON.stringify(newCollections));
  };

  const handleCreateCollection = () => {
    setEditingCollection({
      id: Date.now().toString(),
      name: '',
      description: '',
      image: '',
      products: [],
      featured: false,
      active: true,
      createdAt: new Date().toISOString()
    });
    setSelectedProducts([]);
    setIsCreating(true);
  };

  const handleEditCollection = (collection) => {
    setEditingCollection({ ...collection });
    setSelectedProducts(collection.products || []);
    setIsCreating(false);
  };

  const handleSaveCollection = () => {
    if (!editingCollection.name.trim()) {
      toast.error('Collection name is required');
      return;
    }

    const updatedCollection = {
      ...editingCollection,
      products: selectedProducts
    };

    let newCollections;
    if (isCreating) {
      newCollections = [...collections, updatedCollection];
      toast.success('Collection created!');
    } else {
      newCollections = collections.map(c => 
        c.id === updatedCollection.id ? updatedCollection : c
      );
      toast.success('Collection updated!');
    }

    saveCollections(newCollections);
    setEditingCollection(null);
    setSelectedProducts([]);
  };

  const handleDeleteCollection = (collectionId) => {
    if (!window.confirm('Delete this collection?')) return;
    
    const newCollections = collections.filter(c => c.id !== collectionId);
    saveCollections(newCollections);
    toast.success('Collection deleted');
  };

  const toggleProductInCollection = (productId) => {
    if (selectedProducts.includes(productId)) {
      setSelectedProducts(selectedProducts.filter(id => id !== productId));
    } else {
      setSelectedProducts([...selectedProducts, productId]);
    }
  };

  const toggleFeatured = (collectionId) => {
    const newCollections = collections.map(c => 
      c.id === collectionId ? { ...c, featured: !c.featured } : c
    );
    saveCollections(newCollections);
  };

  const toggleActive = (collectionId) => {
    const newCollections = collections.map(c => 
      c.id === collectionId ? { ...c, active: !c.active } : c
    );
    saveCollections(newCollections);
  };

  const filteredCollections = collections.filter(c => 
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredProducts = products.filter(p =>
    p.name?.toLowerCase().includes(productSearch.toLowerCase())
  );

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
          <h1 className="text-2xl font-bold text-[#2D2A2E]">Product Collections</h1>
          <p className="text-[#5A5A5A]">Organize products into themed collections</p>
        </div>
        <Button onClick={handleCreateCollection} className="bg-[#F8A5B8] hover:bg-[#E88DA0] text-white gap-2">
          <Plus className="h-4 w-4" />
          Create Collection
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#5A5A5A]" />
        <Input
          placeholder="Search collections..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Collections Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredCollections.map((collection) => (
          <Card key={collection.id} className={`relative overflow-hidden ${!collection.active ? 'opacity-60' : ''}`}>
            {/* Collection Image */}
            <div className="h-32 bg-gradient-to-br from-[#F8A5B8]/20 to-[#F8A5B8]/5 flex items-center justify-center">
              {collection.image ? (
                <img src={collection.image} alt={collection.name} className="w-full h-full object-cover" />
              ) : (
                <FolderOpen className="h-12 w-12 text-[#F8A5B8]" />
              )}
              {collection.featured && (
                <Badge className="absolute top-2 left-2 bg-yellow-500 text-white gap-1">
                  <Star className="h-3 w-3" />
                  Featured
                </Badge>
              )}
              {!collection.active && (
                <Badge className="absolute top-2 right-2 bg-gray-500 text-white">
                  Hidden
                </Badge>
              )}
            </div>

            <CardContent className="p-4">
              <h3 className="font-semibold text-[#2D2A2E] mb-1">{collection.name}</h3>
              <p className="text-sm text-[#5A5A5A] line-clamp-2 mb-3">
                {collection.description || 'No description'}
              </p>
              
              <div className="flex items-center justify-between">
                <Badge variant="outline" className="gap-1">
                  <Package className="h-3 w-3" />
                  {collection.products?.length || 0} products
                </Badge>
                
                <div className="flex gap-1">
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => toggleFeatured(collection.id)}
                    className={collection.featured ? 'text-yellow-500' : 'text-gray-400'}
                  >
                    <Star className="h-4 w-4" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => toggleActive(collection.id)}
                    className={collection.active ? 'text-green-500' : 'text-gray-400'}
                  >
                    {collection.active ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => handleEditCollection(collection)}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => handleDeleteCollection(collection.id)}
                    className="text-red-500 hover:text-red-600"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {filteredCollections.length === 0 && (
          <Card className="col-span-full p-8 text-center">
            <FolderOpen className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-[#5A5A5A]">No collections found</p>
            <Button onClick={handleCreateCollection} variant="link" className="text-[#F8A5B8]">
              Create your first collection
            </Button>
          </Card>
        )}
      </div>

      {/* Edit/Create Collection Dialog */}
      <Dialog open={!!editingCollection} onOpenChange={() => setEditingCollection(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{isCreating ? 'Create Collection' : 'Edit Collection'}</DialogTitle>
          </DialogHeader>
          {editingCollection && (
            <div className="space-y-4 py-4">
              <div>
                <Label>Collection Name *</Label>
                <Input
                  value={editingCollection.name}
                  onChange={(e) => setEditingCollection({ ...editingCollection, name: e.target.value })}
                  placeholder="e.g., Anti-Aging Protocol"
                />
              </div>

              <div>
                <Label>Description</Label>
                <Textarea
                  value={editingCollection.description}
                  onChange={(e) => setEditingCollection({ ...editingCollection, description: e.target.value })}
                  placeholder="Describe this collection..."
                  rows={3}
                />
              </div>

              <div>
                <Label>Image URL (optional)</Label>
                <Input
                  value={editingCollection.image}
                  onChange={(e) => setEditingCollection({ ...editingCollection, image: e.target.value })}
                  placeholder="https://..."
                />
              </div>

              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <Switch
                    checked={editingCollection.featured}
                    onCheckedChange={(checked) => setEditingCollection({ ...editingCollection, featured: checked })}
                  />
                  <Label>Featured Collection</Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={editingCollection.active}
                    onCheckedChange={(checked) => setEditingCollection({ ...editingCollection, active: checked })}
                  />
                  <Label>Visible on Store</Label>
                </div>
              </div>

              {/* Product Selection */}
              <div>
                <Label>Products in Collection ({selectedProducts.length})</Label>
                <div className="relative mt-2 mb-3">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#5A5A5A]" />
                  <Input
                    placeholder="Search products..."
                    value={productSearch}
                    onChange={(e) => setProductSearch(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <div className="max-h-60 overflow-y-auto border rounded-lg divide-y">
                  {filteredProducts.map((product) => (
                    <div
                      key={product.id}
                      className={`flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-50 ${
                        selectedProducts.includes(product.id) ? 'bg-[#F8A5B8]/10' : ''
                      }`}
                      onClick={() => toggleProductInCollection(product.id)}
                    >
                      <input
                        type="checkbox"
                        checked={selectedProducts.includes(product.id)}
                        onChange={() => {}}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      {product.images?.[0] ? (
                        <img src={product.images[0]} alt={product.name} className="w-10 h-10 rounded object-cover" />
                      ) : (
                        <div className="w-10 h-10 rounded bg-gray-100 flex items-center justify-center">
                          <Package className="h-5 w-5 text-gray-400" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-[#2D2A2E] truncate">{product.name}</p>
                        <p className="text-sm text-[#5A5A5A]">${product.price?.toFixed(2)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setEditingCollection(null)}>
                  Cancel
                </Button>
                <Button onClick={handleSaveCollection} className="bg-[#F8A5B8] hover:bg-[#E88DA0] text-white gap-2">
                  <Save className="h-4 w-4" />
                  {isCreating ? 'Create Collection' : 'Save Changes'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CollectionsManager;
