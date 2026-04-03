import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  FileText, Plus, Search, Send, Trash2, Edit, Package,
  User, Mail, Phone, DollarSign, Clock, CheckCircle, XCircle,
  ShoppingCart, Copy, ExternalLink
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const OrderDraftsManager = () => {
  const [drafts, setDrafts] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingDraft, setEditingDraft] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [selectedProducts, setSelectedProducts] = useState([]);
  const [productSearch, setProductSearch] = useState('');

  // Load drafts from localStorage
  useEffect(() => {
    const savedDrafts = localStorage.getItem('reroots_order_drafts');
    if (savedDrafts) {
      setDrafts(JSON.parse(savedDrafts));
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

  const saveDrafts = (newDrafts) => {
    setDrafts(newDrafts);
    localStorage.setItem('reroots_order_drafts', JSON.stringify(newDrafts));
  };

  const calculateTotal = (items) => {
    return items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  };

  const handleCreateDraft = () => {
    setEditingDraft({
      id: `DRAFT-${Date.now()}`,
      customer: {
        name: '',
        email: '',
        phone: ''
      },
      items: [],
      discount: 0,
      discountType: 'percent', // percent or fixed
      notes: '',
      status: 'draft', // draft, sent, paid, expired
      createdAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString() // 7 days
    });
    setSelectedProducts([]);
    setIsCreating(true);
  };

  const handleEditDraft = (draft) => {
    setEditingDraft({ ...draft });
    setSelectedProducts(draft.items || []);
    setIsCreating(false);
  };

  const handleSaveDraft = () => {
    if (!editingDraft.customer.name && !editingDraft.customer.email) {
      toast.error('Please enter customer name or email');
      return;
    }
    if (selectedProducts.length === 0) {
      toast.error('Please add at least one product');
      return;
    }

    const updatedDraft = {
      ...editingDraft,
      items: selectedProducts
    };

    let newDrafts;
    if (isCreating) {
      newDrafts = [updatedDraft, ...drafts];
      toast.success('Draft order created!');
    } else {
      newDrafts = drafts.map(d => d.id === updatedDraft.id ? updatedDraft : d);
      toast.success('Draft updated!');
    }

    saveDrafts(newDrafts);
    setEditingDraft(null);
    setSelectedProducts([]);
  };

  const handleDeleteDraft = (draftId) => {
    if (!window.confirm('Delete this draft order?')) return;
    const newDrafts = drafts.filter(d => d.id !== draftId);
    saveDrafts(newDrafts);
    toast.success('Draft deleted');
  };

  const handleSendInvoice = (draft) => {
    // Generate payment link
    const paymentLink = `${window.location.origin}/checkout?draft=${draft.id}`;
    
    // Update draft status
    const newDrafts = drafts.map(d => 
      d.id === draft.id ? { ...d, status: 'sent', sentAt: new Date().toISOString() } : d
    );
    saveDrafts(newDrafts);
    
    // Copy link to clipboard
    navigator.clipboard.writeText(paymentLink);
    toast.success('Payment link copied! Send it to the customer via email or WhatsApp.');
  };

  const handleMarkPaid = (draftId) => {
    const newDrafts = drafts.map(d => 
      d.id === draftId ? { ...d, status: 'paid', paidAt: new Date().toISOString() } : d
    );
    saveDrafts(newDrafts);
    toast.success('Marked as paid!');
  };

  const addProductToDraft = (product) => {
    const existing = selectedProducts.find(p => p.id === product.id);
    if (existing) {
      setSelectedProducts(selectedProducts.map(p => 
        p.id === product.id ? { ...p, quantity: p.quantity + 1 } : p
      ));
    } else {
      setSelectedProducts([...selectedProducts, {
        id: product.id,
        name: product.name,
        price: product.price,
        image: product.images?.[0] || '',
        quantity: 1
      }]);
    }
  };

  const updateProductQuantity = (productId, quantity) => {
    if (quantity <= 0) {
      setSelectedProducts(selectedProducts.filter(p => p.id !== productId));
    } else {
      setSelectedProducts(selectedProducts.map(p => 
        p.id === productId ? { ...p, quantity } : p
      ));
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'draft':
        return <Badge className="bg-gray-500 text-white">Draft</Badge>;
      case 'sent':
        return <Badge className="bg-blue-500 text-white">Invoice Sent</Badge>;
      case 'paid':
        return <Badge className="bg-green-500 text-white">Paid</Badge>;
      case 'expired':
        return <Badge className="bg-red-500 text-white">Expired</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const filteredDrafts = drafts.filter(d => 
    d.customer?.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.customer?.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.id.toLowerCase().includes(searchQuery.toLowerCase())
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
          <h1 className="text-2xl font-bold text-[#2D2A2E]">Order Drafts</h1>
          <p className="text-[#5A5A5A]">Create manual orders for phone/VIP customers</p>
        </div>
        <Button onClick={handleCreateDraft} className="bg-[#F8A5B8] hover:bg-[#E88DA0] text-white gap-2">
          <Plus className="h-4 w-4" />
          Create Draft Order
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold text-[#2D2A2E]">{drafts.length}</p>
            <p className="text-sm text-[#5A5A5A]">Total Drafts</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold text-blue-600">{drafts.filter(d => d.status === 'sent').length}</p>
            <p className="text-sm text-[#5A5A5A]">Invoices Sent</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold text-green-600">{drafts.filter(d => d.status === 'paid').length}</p>
            <p className="text-sm text-[#5A5A5A]">Paid</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-2xl font-bold text-orange-600">
              ${drafts.filter(d => d.status === 'sent').reduce((sum, d) => sum + calculateTotal(d.items || []), 0).toFixed(2)}
            </p>
            <p className="text-sm text-[#5A5A5A]">Pending Payment</p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#5A5A5A]" />
        <Input
          placeholder="Search by customer or draft ID..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Drafts List */}
      <div className="space-y-4">
        {filteredDrafts.map((draft) => (
          <Card key={draft.id} className="overflow-hidden">
            <CardContent className="p-4">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                {/* Draft Info */}
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-mono text-sm text-[#5A5A5A]">{draft.id}</span>
                    {getStatusBadge(draft.status)}
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="flex items-center gap-1">
                      <User className="h-4 w-4 text-[#5A5A5A]" />
                      {draft.customer?.name || 'No name'}
                    </span>
                    {draft.customer?.email && (
                      <span className="flex items-center gap-1">
                        <Mail className="h-4 w-4 text-[#5A5A5A]" />
                        {draft.customer.email}
                      </span>
                    )}
                    {draft.customer?.phone && (
                      <span className="flex items-center gap-1">
                        <Phone className="h-4 w-4 text-[#5A5A5A]" />
                        {draft.customer.phone}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-sm text-[#5A5A5A]">
                    <span className="flex items-center gap-1">
                      <ShoppingCart className="h-4 w-4" />
                      {draft.items?.length || 0} items
                    </span>
                    <span className="flex items-center gap-1">
                      <DollarSign className="h-4 w-4" />
                      ${calculateTotal(draft.items || []).toFixed(2)}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-4 w-4" />
                      {new Date(draft.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  {draft.status === 'draft' && (
                    <Button
                      size="sm"
                      onClick={() => handleSendInvoice(draft)}
                      className="bg-blue-500 hover:bg-blue-600 text-white gap-1"
                    >
                      <Send className="h-4 w-4" />
                      Send Invoice
                    </Button>
                  )}
                  {draft.status === 'sent' && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          navigator.clipboard.writeText(`${window.location.origin}/checkout?draft=${draft.id}`);
                          toast.success('Link copied!');
                        }}
                        className="gap-1"
                      >
                        <Copy className="h-4 w-4" />
                        Copy Link
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => handleMarkPaid(draft.id)}
                        className="bg-green-500 hover:bg-green-600 text-white gap-1"
                      >
                        <CheckCircle className="h-4 w-4" />
                        Mark Paid
                      </Button>
                    </>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleEditDraft(draft)}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDeleteDraft(draft.id)}
                    className="text-red-500 hover:text-red-600"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {filteredDrafts.length === 0 && (
          <Card className="p-8 text-center">
            <FileText className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-[#5A5A5A]">No draft orders yet</p>
            <Button onClick={handleCreateDraft} variant="link" className="text-[#F8A5B8]">
              Create your first draft order
            </Button>
          </Card>
        )}
      </div>

      {/* Create/Edit Draft Dialog */}
      <Dialog open={!!editingDraft} onOpenChange={() => setEditingDraft(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{isCreating ? 'Create Draft Order' : 'Edit Draft Order'}</DialogTitle>
          </DialogHeader>
          {editingDraft && (
            <div className="space-y-6 py-4">
              {/* Customer Info */}
              <div className="space-y-4">
                <h3 className="font-semibold text-[#2D2A2E]">Customer Information</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <Label>Name</Label>
                    <Input
                      value={editingDraft.customer?.name || ''}
                      onChange={(e) => setEditingDraft({
                        ...editingDraft,
                        customer: { ...editingDraft.customer, name: e.target.value }
                      })}
                      placeholder="Customer name"
                    />
                  </div>
                  <div>
                    <Label>Email</Label>
                    <Input
                      type="email"
                      value={editingDraft.customer?.email || ''}
                      onChange={(e) => setEditingDraft({
                        ...editingDraft,
                        customer: { ...editingDraft.customer, email: e.target.value }
                      })}
                      placeholder="email@example.com"
                    />
                  </div>
                  <div>
                    <Label>Phone</Label>
                    <Input
                      value={editingDraft.customer?.phone || ''}
                      onChange={(e) => setEditingDraft({
                        ...editingDraft,
                        customer: { ...editingDraft.customer, phone: e.target.value }
                      })}
                      placeholder="+1 (555) 000-0000"
                    />
                  </div>
                </div>
              </div>

              {/* Products */}
              <div className="space-y-4">
                <h3 className="font-semibold text-[#2D2A2E]">Products</h3>
                
                {/* Search Products */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#5A5A5A]" />
                  <Input
                    placeholder="Search products to add..."
                    value={productSearch}
                    onChange={(e) => setProductSearch(e.target.value)}
                    className="pl-10"
                  />
                </div>

                {/* Product Search Results */}
                {productSearch && (
                  <div className="max-h-40 overflow-y-auto border rounded-lg divide-y">
                    {filteredProducts.slice(0, 5).map((product) => (
                      <div
                        key={product.id}
                        className="flex items-center gap-3 p-2 cursor-pointer hover:bg-gray-50"
                        onClick={() => {
                          addProductToDraft(product);
                          setProductSearch('');
                        }}
                      >
                        {product.images?.[0] ? (
                          <img src={product.images[0]} alt={product.name} className="w-8 h-8 rounded object-cover" />
                        ) : (
                          <div className="w-8 h-8 rounded bg-gray-100 flex items-center justify-center">
                            <Package className="h-4 w-4 text-gray-400" />
                          </div>
                        )}
                        <span className="flex-1 text-sm">{product.name}</span>
                        <span className="text-sm text-[#5A5A5A]">${product.price?.toFixed(2)}</span>
                        <Plus className="h-4 w-4 text-[#F8A5B8]" />
                      </div>
                    ))}
                  </div>
                )}

                {/* Selected Products */}
                <div className="border rounded-lg divide-y">
                  {selectedProducts.length === 0 ? (
                    <div className="p-4 text-center text-[#5A5A5A]">
                      No products added yet
                    </div>
                  ) : (
                    selectedProducts.map((item) => (
                      <div key={item.id} className="flex items-center gap-3 p-3">
                        {item.image ? (
                          <img src={item.image} alt={item.name} className="w-12 h-12 rounded object-cover" />
                        ) : (
                          <div className="w-12 h-12 rounded bg-gray-100 flex items-center justify-center">
                            <Package className="h-6 w-6 text-gray-400" />
                          </div>
                        )}
                        <div className="flex-1">
                          <p className="font-medium text-[#2D2A2E]">{item.name}</p>
                          <p className="text-sm text-[#5A5A5A]">${item.price?.toFixed(2)} each</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            size="icon"
                            variant="outline"
                            className="h-8 w-8"
                            onClick={() => updateProductQuantity(item.id, item.quantity - 1)}
                          >
                            -
                          </Button>
                          <span className="w-8 text-center">{item.quantity}</span>
                          <Button
                            size="icon"
                            variant="outline"
                            className="h-8 w-8"
                            onClick={() => updateProductQuantity(item.id, item.quantity + 1)}
                          >
                            +
                          </Button>
                        </div>
                        <p className="font-medium w-20 text-right">
                          ${(item.price * item.quantity).toFixed(2)}
                        </p>
                      </div>
                    ))
                  )}
                </div>

                {/* Totals */}
                {selectedProducts.length > 0 && (
                  <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                    <div className="flex justify-between">
                      <span>Subtotal</span>
                      <span>${calculateTotal(selectedProducts).toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span>Discount</span>
                      <div className="flex items-center gap-2">
                        <Input
                          type="number"
                          value={editingDraft.discount || 0}
                          onChange={(e) => setEditingDraft({ ...editingDraft, discount: parseFloat(e.target.value) || 0 })}
                          className="w-20 text-right"
                        />
                        <Select
                          value={editingDraft.discountType || 'percent'}
                          onValueChange={(value) => setEditingDraft({ ...editingDraft, discountType: value })}
                        >
                          <SelectTrigger className="w-24">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="percent">%</SelectItem>
                            <SelectItem value="fixed">$</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="flex justify-between font-bold text-lg border-t pt-2">
                      <span>Total</span>
                      <span>
                        ${(() => {
                          const subtotal = calculateTotal(selectedProducts);
                          const discount = editingDraft.discountType === 'percent' 
                            ? subtotal * (editingDraft.discount || 0) / 100
                            : (editingDraft.discount || 0);
                          return Math.max(0, subtotal - discount).toFixed(2);
                        })()}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Notes */}
              <div>
                <Label>Internal Notes</Label>
                <Textarea
                  value={editingDraft.notes || ''}
                  onChange={(e) => setEditingDraft({ ...editingDraft, notes: e.target.value })}
                  placeholder="Add any notes about this order..."
                  rows={2}
                />
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setEditingDraft(null)}>
                  Cancel
                </Button>
                <Button onClick={handleSaveDraft} className="bg-[#F8A5B8] hover:bg-[#E88DA0] text-white">
                  {isCreating ? 'Create Draft' : 'Save Changes'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default OrderDraftsManager;
