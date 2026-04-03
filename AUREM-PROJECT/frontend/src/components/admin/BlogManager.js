import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { 
  Plus, Edit, Trash2, Eye, EyeOff, Search, Loader2, Save, 
  FileText, Calendar, Tag, Image as ImageIcon, ExternalLink,
  Globe, TrendingUp, Clock, CheckCircle, XCircle, AlertCircle,
  ShoppingBag, Link2, BookOpen, Quote, Beaker, FlaskConical, Zap
} from 'lucide-react';
import { useAdminBrand } from './useAdminBrand';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Shoppable Product Card Component - For embedding in articles
const ShoppableProductCard = ({ product, onRemove }) => {
  if (!product) return null;
  
  return (
    <div className="border rounded-xl p-4 bg-gradient-to-r from-[#FDF9F9] to-white flex items-center gap-4 my-4">
      <div className="w-20 h-20 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0">
        {product.images?.[0] ? (
          <img src={product.images[0]} alt={product.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <ShoppingBag className="w-8 h-8 text-gray-300" />
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-[#2D2A2E] truncate">{product.name}</p>
        <p className="text-lg font-bold text-[#F8A5B8]">${product.price?.toFixed(2)}</p>
        {product.compare_price && product.compare_price > product.price && (
          <p className="text-sm text-gray-400 line-through">${product.compare_price.toFixed(2)}</p>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <Badge className="bg-[#F8A5B8]/20 text-[#F8A5B8]">Featured Product</Badge>
        {onRemove && (
          <Button size="sm" variant="ghost" onClick={onRemove} className="text-red-500">
            <Trash2 className="w-3 h-3" />
          </Button>
        )}
      </div>
    </div>
  );
};

// Reference/Citation Component
const ReferenceItem = ({ reference, index, onRemove, onEdit }) => (
  <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg group">
    <span className="w-6 h-6 bg-[#2D2A2E] text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
      {index + 1}
    </span>
    <div className="flex-1 min-w-0">
      <p className="text-sm font-medium text-[#2D2A2E] truncate">{reference.title}</p>
      <p className="text-xs text-[#5A5A5A] truncate">{reference.source}</p>
      {reference.url && (
        <a href={reference.url} target="_blank" rel="noopener noreferrer" className="text-xs text-[#F8A5B8] hover:underline">
          View Source →
        </a>
      )}
    </div>
    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
      <Button size="sm" variant="ghost" onClick={() => onEdit(index)}>
        <Edit className="w-3 h-3" />
      </Button>
      <Button size="sm" variant="ghost" className="text-red-500" onClick={() => onRemove(index)}>
        <Trash2 className="w-3 h-3" />
      </Button>
    </div>
  </div>
);

const BlogManager = () => {
  const { name: brandName } = useAdminBrand();
  const teamName = `${brandName} Team`;
  
  const [posts, setPosts] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPost, setEditingPost] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categories, setCategories] = useState({});
  const [productSearchOpen, setProductSearchOpen] = useState(false);
  const [productSearch, setProductSearch] = useState('');
  const [referenceDialogOpen, setReferenceDialogOpen] = useState(false);
  const [editingReferenceIndex, setEditingReferenceIndex] = useState(null);
  const [newReference, setNewReference] = useState({ title: '', source: '', url: '', year: '' });
  
  // Form state - Enhanced with shoppable products and references
  const [formData, setFormData] = useState({
    title: '',
    slug: '',
    content: '',
    excerpt: '',
    featured_image: '',
    category: 'General',
    tags: '',
    status: 'draft',
    meta_title: '',
    meta_description: '',
    author_name: teamName,
    focus_keyword: '',
    featured_products: [],
    references: [],
    schema_type: 'Article',
    embedded_cta: 'none'  // 'none', 'quiz', 'bio_scan', 'both'
  });

  // CTA Embed options for conversion
  const ctaEmbedOptions = [
    { value: 'none', label: 'No CTA Widget', description: 'Standard article' },
    { value: 'quiz', label: 'Skin Quiz Widget', description: '87.5% conversion rate' },
    { value: 'bio_scan', label: 'Bio-Age Scan Widget', description: 'Capture emails + concerns' },
    { value: 'both', label: 'Both Widgets', description: 'Maximum conversion potential' }
  ];

  const categoryOptions = [
    'General',
    'Skincare Tips',
    'Product Guides',
    'Ingredient Science',
    'Clinical Studies',
    'Beauty Routines',
    'Wellness',
    'News & Updates'
  ];

  const schemaTypes = [
    { value: 'Article', label: 'Standard Article' },
    { value: 'BlogPosting', label: 'Blog Post' },
    { value: 'NewsArticle', label: 'News Article' },
    { value: 'TechArticle', label: 'Technical Article' },
    { value: 'ScholarlyArticle', label: 'Scholarly/Research Article' }
  ];

  // Fetch posts and products
  const fetchData = useCallback(async () => {
    try {
      const token = localStorage.getItem('reroots_token');
      const [postsRes, productsRes] = await Promise.all([
        axios.get(`${API}/admin/blog/posts`, {
          params: { status: statusFilter !== 'all' ? statusFilter : undefined },
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/products`)
      ]);
      setPosts(postsRes.data.posts || []);
      setCategories(postsRes.data.categories || {});
      setProducts(productsRes.data || []);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Generate slug from title
  const generateSlug = (title) => {
    return title
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/[\s_]+/g, '-')
      .replace(/-+/g, '-')
      .trim();
  };

  // Handle title change and auto-generate slug
  const handleTitleChange = (value) => {
    setFormData(prev => ({
      ...prev,
      title: value,
      slug: prev.slug || generateSlug(value)
    }));
  };

  // Add product to featured products
  const addFeaturedProduct = (product) => {
    if (formData.featured_products.find(p => p.id === product.id)) {
      toast.error('Product already added');
      return;
    }
    setFormData(prev => ({
      ...prev,
      featured_products: [...prev.featured_products, product]
    }));
    setProductSearchOpen(false);
    setProductSearch('');
    toast.success('Product added to article');
  };

  // Remove featured product
  const removeFeaturedProduct = (productId) => {
    setFormData(prev => ({
      ...prev,
      featured_products: prev.featured_products.filter(p => p.id !== productId)
    }));
  };

  // Add/Edit reference
  const saveReference = () => {
    if (!newReference.title) {
      toast.error('Reference title is required');
      return;
    }
    
    if (editingReferenceIndex !== null) {
      // Edit existing
      const updated = [...formData.references];
      updated[editingReferenceIndex] = newReference;
      setFormData(prev => ({ ...prev, references: updated }));
    } else {
      // Add new
      setFormData(prev => ({
        ...prev,
        references: [...prev.references, newReference]
      }));
    }
    
    setReferenceDialogOpen(false);
    setEditingReferenceIndex(null);
    setNewReference({ title: '', source: '', url: '', year: '' });
  };

  // Remove reference
  const removeReference = (index) => {
    setFormData(prev => ({
      ...prev,
      references: prev.references.filter((_, i) => i !== index)
    }));
  };

  // Edit reference
  const editReference = (index) => {
    setNewReference(formData.references[index]);
    setEditingReferenceIndex(index);
    setReferenceDialogOpen(true);
  };

  // Open create dialog
  const openCreateDialog = () => {
    setEditingPost(null);
    setFormData({
      title: '',
      slug: '',
      content: '',
      excerpt: '',
      featured_image: '',
      category: 'General',
      tags: '',
      status: 'draft',
      meta_title: '',
      meta_description: '',
      author_name: teamName,
      focus_keyword: '',
      featured_products: [],
      references: [],
      schema_type: 'Article',
      embedded_cta: 'none'
    });
    setDialogOpen(true);
  };

  // Open edit dialog
  const openEditDialog = (post) => {
    setEditingPost(post);
    setFormData({
      title: post.title || '',
      slug: post.slug || '',
      content: post.content || '',
      excerpt: post.excerpt || '',
      featured_image: post.featured_image || '',
      category: post.category || 'General',
      tags: (post.tags || []).join(', '),
      status: post.status || 'draft',
      meta_title: post.meta_title || '',
      meta_description: post.meta_description || '',
      author_name: post.author_name || teamName,
      focus_keyword: post.focus_keyword || '',
      featured_products: post.featured_products || [],
      references: post.references || [],
      schema_type: post.schema_type || 'Article',
      embedded_cta: post.embedded_cta || 'none'
    });
    setDialogOpen(true);
  };

  // Save post (create or update)
  const handleSavePost = async () => {
    if (!formData.title.trim()) {
      toast.error('Title is required');
      return;
    }
    if (!formData.content.trim()) {
      toast.error('Content is required');
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const payload = {
        ...formData,
        tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean),
        featured_products: formData.featured_products.map(p => ({
          id: p.id,
          name: p.name,
          price: p.price,
          images: p.images,
          slug: p.slug
        }))
      };

      if (editingPost) {
        await axios.put(`${API}/admin/blog/posts/${editingPost.id}`, payload, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Blog post updated!');
      } else {
        await axios.post(`${API}/admin/blog/posts`, payload, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Blog post created!');
      }

      setDialogOpen(false);
      fetchData();
    } catch (error) {
      console.error('Failed to save blog post:', error);
      toast.error(error.response?.data?.detail || 'Failed to save blog post');
    } finally {
      setSaving(false);
    }
  };

  // Delete post
  const handleDeletePost = async (postId) => {
    if (!window.confirm('Are you sure you want to delete this blog post?')) return;

    try {
      const token = localStorage.getItem('reroots_token');
      await axios.delete(`${API}/admin/blog/posts/${postId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Blog post deleted!');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete blog post');
    }
  };

  // Quick publish/unpublish
  const togglePublishStatus = async (post) => {
    const newStatus = post.status === 'published' ? 'draft' : 'published';
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.put(`${API}/admin/blog/posts/${post.id}`, 
        { status: newStatus },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(newStatus === 'published' ? 'Post published!' : 'Post unpublished');
      fetchData();
    } catch (error) {
      toast.error('Failed to update post status');
    }
  };

  // Filter posts by search
  const filteredPosts = posts.filter(post => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      post.title?.toLowerCase().includes(query) ||
      post.excerpt?.toLowerCase().includes(query) ||
      post.category?.toLowerCase().includes(query)
    );
  });

  // Filter products by search
  const filteredProducts = products.filter(p => 
    p.name?.toLowerCase().includes(productSearch.toLowerCase())
  );

  // Get status badge
  const getStatusBadge = (status) => {
    switch (status) {
      case 'published':
        return <Badge className="bg-green-100 text-green-700"><CheckCircle className="w-3 h-3 mr-1" />Published</Badge>;
      case 'draft':
        return <Badge className="bg-yellow-100 text-yellow-700"><AlertCircle className="w-3 h-3 mr-1" />Draft</Badge>;
      case 'scheduled':
        return <Badge className="bg-blue-100 text-blue-700"><Clock className="w-3 h-3 mr-1" />Scheduled</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  // Calculate SEO score
  const calculateSEOScore = () => {
    let score = 0;
    if (formData.title.length >= 30 && formData.title.length <= 60) score += 20;
    if (formData.meta_description.length >= 120 && formData.meta_description.length <= 160) score += 20;
    if (formData.focus_keyword && formData.title.toLowerCase().includes(formData.focus_keyword.toLowerCase())) score += 20;
    if (formData.content.length >= 1000) score += 20;
    if (formData.featured_image) score += 10;
    if (formData.references.length > 0) score += 10;
    return score;
  };

  const seoScore = calculateSEOScore();

  return (
    <div className="space-y-6" data-testid="blog-manager">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[#2D2A2E] flex items-center gap-2">
            <FileText className="w-6 h-6 text-[#F8A5B8]" />
            Blog Manager
          </h2>
          <p className="text-[#5A5A5A] mt-1">Create SEO-optimized, shoppable content for organic traffic</p>
        </div>
        <Button 
          onClick={openCreateDialog}
          className="bg-[#F8A5B8] hover:bg-[#E89AAB] text-white"
          data-testid="create-post-btn"
        >
          <Plus className="w-4 h-4 mr-2" />
          New Blog Post
        </Button>
      </div>

      {/* SEO Tips Card - Enhanced */}
      <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-blue-200">
        <CardContent className="py-4">
          <div className="flex items-start gap-3">
            <FlaskConical className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <h3 className="font-semibold text-blue-800">Biotech Content Strategy</h3>
              <p className="text-sm text-blue-700 mt-1">
                Your blog is now a <strong>conversion engine</strong>. Each article can embed "Shoppable" product cards 
                and cite clinical studies for E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) - 
                critical for Google's ranking of health-related content.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-[#5A5A5A]">Total Posts</p>
            <p className="text-2xl font-bold text-[#2D2A2E]">{posts.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-[#5A5A5A]">Published</p>
            <p className="text-2xl font-bold text-green-600">
              {posts.filter(p => p.status === 'published').length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-[#5A5A5A]">Drafts</p>
            <p className="text-2xl font-bold text-yellow-600">
              {posts.filter(p => p.status === 'draft').length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-[#5A5A5A]">Total Views</p>
            <p className="text-2xl font-bold text-blue-600">
              {posts.reduce((sum, p) => sum + (p.views || 0), 0)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <Input
            placeholder="Search posts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
            data-testid="search-posts-input"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="published">Published</SelectItem>
            <SelectItem value="draft">Drafts</SelectItem>
            <SelectItem value="scheduled">Scheduled</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Posts List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-[#F8A5B8]" />
        </div>
      ) : filteredPosts.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-[#2D2A2E] mb-2">No blog posts yet</h3>
            <p className="text-[#5A5A5A] mb-4">Start creating shoppable content to boost organic traffic</p>
            <Button onClick={openCreateDialog} className="bg-[#F8A5B8] hover:bg-[#E89AAB]">
              <Plus className="w-4 h-4 mr-2" />
              Create Your First Post
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredPosts.map((post) => (
            <Card key={post.id} className="hover:shadow-md transition-shadow" data-testid={`post-card-${post.id}`}>
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  {/* Featured Image */}
                  <div className="w-24 h-24 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0">
                    {post.featured_image ? (
                      <img 
                        src={post.featured_image} 
                        alt={post.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <ImageIcon className="w-8 h-8 text-gray-300" />
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="font-semibold text-[#2D2A2E] truncate">{post.title}</h3>
                        <p className="text-sm text-[#5A5A5A] line-clamp-2 mt-1">{post.excerpt}</p>
                      </div>
                      {getStatusBadge(post.status)}
                    </div>

                    <div className="flex flex-wrap items-center gap-3 mt-3 text-xs text-[#5A5A5A]">
                      <span className="flex items-center gap-1">
                        <Tag className="w-3 h-3" />
                        {post.category}
                      </span>
                      <span className="flex items-center gap-1">
                        <Eye className="w-3 h-3" />
                        {post.views || 0} views
                      </span>
                      {post.featured_products?.length > 0 && (
                        <span className="flex items-center gap-1 text-[#F8A5B8]">
                          <ShoppingBag className="w-3 h-3" />
                          {post.featured_products.length} products
                        </span>
                      )}
                      {post.references?.length > 0 && (
                        <span className="flex items-center gap-1 text-purple-600">
                          <BookOpen className="w-3 h-3" />
                          {post.references.length} citations
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {post.published_at 
                          ? new Date(post.published_at).toLocaleDateString()
                          : 'Not published'
                        }
                      </span>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 mt-3">
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={() => openEditDialog(post)}
                        data-testid={`edit-post-${post.id}`}
                      >
                        <Edit className="w-3 h-3 mr-1" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => togglePublishStatus(post)}
                        data-testid={`toggle-status-${post.id}`}
                      >
                        {post.status === 'published' ? (
                          <><EyeOff className="w-3 h-3 mr-1" />Unpublish</>
                        ) : (
                          <><Eye className="w-3 h-3 mr-1" />Publish</>
                        )}
                      </Button>
                      {post.status === 'published' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => window.open(`/blog/${post.slug}`, '_blank')}
                        >
                          <ExternalLink className="w-3 h-3 mr-1" />
                          View
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-red-500 hover:text-red-700 hover:bg-red-50"
                        onClick={() => handleDeletePost(post.id)}
                        data-testid={`delete-post-${post.id}`}
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Dialog - Enhanced with Shoppable & References */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Beaker className="w-5 h-5 text-[#F8A5B8]" />
              {editingPost ? 'Edit Blog Post' : 'Create New Blog Post'}
            </DialogTitle>
            <DialogDescription>
              Build SEO-optimized, shoppable content with clinical citations
            </DialogDescription>
          </DialogHeader>

          {/* SEO Score Indicator */}
          <div className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
            <div className="flex-1">
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium">SEO Score</span>
                <span className={seoScore >= 70 ? 'text-green-600' : seoScore >= 40 ? 'text-yellow-600' : 'text-red-600'}>
                  {seoScore}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full transition-all ${
                    seoScore >= 70 ? 'bg-green-500' : seoScore >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${seoScore}%` }}
                />
              </div>
            </div>
          </div>

          <Tabs defaultValue="content" className="mt-4">
            <TabsList className="grid grid-cols-5 w-full">
              <TabsTrigger value="content">Content</TabsTrigger>
              <TabsTrigger value="media">Media</TabsTrigger>
              <TabsTrigger value="products">Products</TabsTrigger>
              <TabsTrigger value="references">Citations</TabsTrigger>
              <TabsTrigger value="seo">SEO</TabsTrigger>
            </TabsList>

            {/* Content Tab */}
            <TabsContent value="content" className="space-y-4 mt-4">
              <div>
                <Label>Title *</Label>
                <Input
                  value={formData.title}
                  onChange={(e) => handleTitleChange(e.target.value)}
                  placeholder="e.g., The Science of PDRN: How Salmon DNA Repairs Skin"
                  data-testid="post-title-input"
                />
              </div>

              <div>
                <Label>URL Slug</Label>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-[#5A5A5A]">/blog/</span>
                  <Input
                    value={formData.slug}
                    onChange={(e) => setFormData(prev => ({ ...prev, slug: e.target.value }))}
                    placeholder="science-of-pdrn-salmon-dna"
                    className="flex-1"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Category</Label>
                  <Select 
                    value={formData.category} 
                    onValueChange={(v) => setFormData(prev => ({ ...prev, category: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                    <SelectContent>
                      {categoryOptions.map(cat => (
                        <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Status</Label>
                  <Select 
                    value={formData.status} 
                    onValueChange={(v) => setFormData(prev => ({ ...prev, status: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="published">Published</SelectItem>
                      <SelectItem value="scheduled">Scheduled</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label>Excerpt (Summary)</Label>
                <Textarea
                  value={formData.excerpt}
                  onChange={(e) => setFormData(prev => ({ ...prev, excerpt: e.target.value }))}
                  placeholder="Brief summary for search results and social sharing..."
                  rows={2}
                />
                <p className="text-xs text-[#5A5A5A] mt-1">
                  {formData.excerpt.length}/160 characters (recommended for SEO)
                </p>
              </div>

              <div>
                <Label>Content *</Label>
                <Textarea
                  value={formData.content}
                  onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
                  placeholder="Write your blog post content here. Use HTML for formatting. 

Tip: Use [PRODUCT:product-id] to insert shoppable product cards.
Example: [PRODUCT:prod-aura-gen]"
                  rows={12}
                  data-testid="post-content-input"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">
                  Use headings (h2, h3), bullet points, and [PRODUCT:id] tags for shoppable content.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Tags (comma-separated)</Label>
                  <Input
                    value={formData.tags}
                    onChange={(e) => setFormData(prev => ({ ...prev, tags: e.target.value }))}
                    placeholder="PDRN, anti-aging, biotech, clinical"
                  />
                </div>
                <div>
                  <Label>Author Name</Label>
                  <Input
                    value={formData.author_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, author_name: e.target.value }))}
                    placeholder={teamName}
                  />
                </div>
              </div>
            </TabsContent>

            {/* Media Tab */}
            <TabsContent value="media" className="space-y-4 mt-4">
              <div>
                <Label>Featured Image URL</Label>
                <Input
                  value={formData.featured_image}
                  onChange={(e) => setFormData(prev => ({ ...prev, featured_image: e.target.value }))}
                  placeholder="https://example.com/image.jpg"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">
                  Recommended size: 1200x630px for social sharing
                </p>
              </div>

              {formData.featured_image && (
                <div className="border rounded-lg p-4">
                  <p className="text-sm font-medium mb-2">Preview:</p>
                  <img 
                    src={formData.featured_image} 
                    alt="Featured preview"
                    className="max-h-48 rounded-lg object-cover"
                    onError={(e) => {
                      e.target.style.display = 'none';
                      toast.error('Invalid image URL');
                    }}
                  />
                </div>
              )}
            </TabsContent>

            {/* Shoppable Products Tab */}
            <TabsContent value="products" className="space-y-4 mt-4">
              <Card className="bg-gradient-to-r from-pink-50 to-rose-50 border-pink-200">
                <CardContent className="py-3">
                  <div className="flex items-start gap-2">
                    <ShoppingBag className="w-4 h-4 text-pink-600 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-pink-800">Shoppable Articles</p>
                      <p className="text-xs text-pink-700">
                        Add products that will appear as "Buy Now" cards within your article.
                        Perfect for converting readers who are researching ingredients.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div>
                <Label>Featured Products in this Article</Label>
                {formData.featured_products.length === 0 ? (
                  <div className="border-2 border-dashed rounded-lg p-8 text-center mt-2">
                    <ShoppingBag className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-[#5A5A5A]">No products added yet</p>
                  </div>
                ) : (
                  <div className="space-y-2 mt-2">
                    {formData.featured_products.map(product => (
                      <ShoppableProductCard 
                        key={product.id} 
                        product={product}
                        onRemove={() => removeFeaturedProduct(product.id)}
                      />
                    ))}
                  </div>
                )}
              </div>

              <div>
                <Button 
                  variant="outline" 
                  onClick={() => setProductSearchOpen(true)}
                  className="w-full"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add Product to Article
                </Button>
              </div>

              {/* Product Search Dropdown */}
              {productSearchOpen && (
                <Card className="border-2 border-[#F8A5B8]">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <Label>Search Products</Label>
                      <Button size="sm" variant="ghost" onClick={() => setProductSearchOpen(false)}>
                        <XCircle className="w-4 h-4" />
                      </Button>
                    </div>
                    <Input
                      placeholder="Search by product name..."
                      value={productSearch}
                      onChange={(e) => setProductSearch(e.target.value)}
                      className="mb-3"
                    />
                    <div className="max-h-60 overflow-y-auto space-y-2">
                      {filteredProducts.slice(0, 10).map(product => (
                        <div 
                          key={product.id}
                          className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded-lg cursor-pointer"
                          onClick={() => addFeaturedProduct(product)}
                        >
                          <div className="w-10 h-10 bg-gray-100 rounded overflow-hidden">
                            {product.images?.[0] ? (
                              <img src={product.images[0]} alt="" className="w-full h-full object-cover" />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center">
                                <ShoppingBag className="w-4 h-4 text-gray-300" />
                              </div>
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{product.name}</p>
                            <p className="text-xs text-[#F8A5B8]">${product.price?.toFixed(2)}</p>
                          </div>
                          <Plus className="w-4 h-4 text-[#F8A5B8]" />
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Citations/References Tab */}
            <TabsContent value="references" className="space-y-4 mt-4">
              <Card className="bg-gradient-to-r from-purple-50 to-indigo-50 border-purple-200">
                <CardContent className="py-3">
                  <div className="flex items-start gap-2">
                    <BookOpen className="w-4 h-4 text-purple-600 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-purple-800">Biotech Citations (E-E-A-T)</p>
                      <p className="text-xs text-purple-700">
                        Citing clinical studies and research papers boosts your article's credibility 
                        with Google's E-E-A-T algorithm. Essential for health/skincare content.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div>
                <Label>References & Citations</Label>
                {formData.references.length === 0 ? (
                  <div className="border-2 border-dashed rounded-lg p-8 text-center mt-2">
                    <Quote className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-[#5A5A5A]">No citations added yet</p>
                    <p className="text-xs text-gray-400 mt-1">Add clinical studies to build authority</p>
                  </div>
                ) : (
                  <div className="space-y-2 mt-2">
                    {formData.references.map((ref, index) => (
                      <ReferenceItem 
                        key={index}
                        reference={ref}
                        index={index}
                        onRemove={removeReference}
                        onEdit={editReference}
                      />
                    ))}
                  </div>
                )}
              </div>

              <Button 
                variant="outline" 
                onClick={() => {
                  setNewReference({ title: '', source: '', url: '', year: '' });
                  setEditingReferenceIndex(null);
                  setReferenceDialogOpen(true);
                }}
                className="w-full"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Citation
              </Button>
            </TabsContent>

            {/* SEO Tab - Enhanced */}
            <TabsContent value="seo" className="space-y-4 mt-4">
              <Card className="bg-green-50 border-green-200">
                <CardContent className="py-3">
                  <div className="flex items-start gap-2">
                    <Globe className="w-4 h-4 text-green-600 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-green-800">Google Search Preview</p>
                      <div className="mt-2 p-3 bg-white rounded border">
                        <p className="text-blue-600 text-lg hover:underline cursor-pointer">
                          {formData.meta_title || formData.title || 'Your Page Title'}
                        </p>
                        <p className="text-green-700 text-sm">
                          reroots.ca/blog/{formData.slug || 'your-post-slug'}
                        </p>
                        <p className="text-gray-600 text-sm mt-1">
                          {formData.meta_description || formData.excerpt || 'Your meta description will appear here...'}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div>
                <Label>Focus Keyword</Label>
                <Input
                  value={formData.focus_keyword}
                  onChange={(e) => setFormData(prev => ({ ...prev, focus_keyword: e.target.value }))}
                  placeholder="e.g., PDRN serum benefits"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">
                  The main keyword this article should rank for. Include it in the title.
                </p>
              </div>

              <div>
                <Label>Meta Title (for SEO)</Label>
                <Input
                  value={formData.meta_title}
                  onChange={(e) => setFormData(prev => ({ ...prev, meta_title: e.target.value }))}
                  placeholder="Leave empty to use post title"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">
                  {(formData.meta_title || formData.title).length}/60 characters (recommended)
                </p>
              </div>

              <div>
                <Label>Meta Description (for SEO)</Label>
                <Textarea
                  value={formData.meta_description}
                  onChange={(e) => setFormData(prev => ({ ...prev, meta_description: e.target.value }))}
                  placeholder="Leave empty to use excerpt"
                  rows={3}
                />
                <p className="text-xs text-[#5A5A5A] mt-1">
                  {(formData.meta_description || formData.excerpt).length}/160 characters (recommended)
                </p>
              </div>

              <div>
                <Label>Schema.org Article Type</Label>
                <Select 
                  value={formData.schema_type} 
                  onValueChange={(v) => setFormData(prev => ({ ...prev, schema_type: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select schema type" />
                  </SelectTrigger>
                  <SelectContent>
                    {schemaTypes.map(type => (
                      <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-[#5A5A5A] mt-1">
                  Schema markup helps Google understand your content type for rich snippets.
                </p>
              </div>

              {/* CTA Widget Embed Selection */}
              <div className="space-y-2 pt-4 border-t">
                <Label className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-[#F8A5B8]" />
                  Conversion Widget
                  <Badge className="bg-green-100 text-green-700 text-xs">Recommended</Badge>
                </Label>
                <Select
                  value={formData.embedded_cta} 
                  onValueChange={(v) => setFormData(prev => ({ ...prev, embedded_cta: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select CTA widget" />
                  </SelectTrigger>
                  <SelectContent>
                    {ctaEmbedOptions.map(option => (
                      <SelectItem key={option.value} value={option.value}>
                        <div className="flex items-center gap-2">
                          <span>{option.label}</span>
                          <span className="text-xs text-gray-500">• {option.description}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-[#5A5A5A] mt-1">
                  Embed high-converting widgets at the end of your article to capture leads.
                </p>
              </div>
            </TabsContent>
          </Tabs>

          <DialogFooter className="mt-6">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleSavePost} 
              disabled={saving}
              className="bg-[#F8A5B8] hover:bg-[#E89AAB]"
              data-testid="save-post-btn"
            >
              {saving ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving...</>
              ) : (
                <><Save className="w-4 h-4 mr-2" />{editingPost ? 'Update Post' : 'Create Post'}</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reference Dialog */}
      <Dialog open={referenceDialogOpen} onOpenChange={setReferenceDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingReferenceIndex !== null ? 'Edit Citation' : 'Add Citation'}
            </DialogTitle>
            <DialogDescription>
              Link to clinical studies, research papers, or authoritative sources
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div>
              <Label>Study/Article Title *</Label>
              <Input
                value={newReference.title}
                onChange={(e) => setNewReference(prev => ({ ...prev, title: e.target.value }))}
                placeholder="e.g., PDRN promotes skin regeneration in clinical trial"
              />
            </div>
            <div>
              <Label>Source/Journal</Label>
              <Input
                value={newReference.source}
                onChange={(e) => setNewReference(prev => ({ ...prev, source: e.target.value }))}
                placeholder="e.g., Journal of Dermatological Science, 2023"
              />
            </div>
            <div>
              <Label>URL (optional)</Label>
              <Input
                value={newReference.url}
                onChange={(e) => setNewReference(prev => ({ ...prev, url: e.target.value }))}
                placeholder="https://pubmed.ncbi.nlm.nih.gov/..."
              />
            </div>
            <div>
              <Label>Year (optional)</Label>
              <Input
                value={newReference.year}
                onChange={(e) => setNewReference(prev => ({ ...prev, year: e.target.value }))}
                placeholder="2023"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setReferenceDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveReference} className="bg-[#F8A5B8] hover:bg-[#E89AAB]">
              {editingReferenceIndex !== null ? 'Update Citation' : 'Add Citation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BlogManager;
