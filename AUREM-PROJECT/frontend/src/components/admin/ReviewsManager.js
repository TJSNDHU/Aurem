import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Star, MessageSquare, Check, X, Trash2, Search, Filter,
  User, Calendar, Image as ImageIcon, ThumbsUp, ThumbsDown,
  RefreshCw, Eye, EyeOff, AlertCircle
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const ReviewsManager = () => {
  const [reviews, setReviews] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('all'); // all, pending, approved
  const [selectedReview, setSelectedReview] = useState(null);

  const fetchReviews = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = { Authorization: `Bearer ${token}` };
      
      const [reviewsRes, productsRes] = await Promise.all([
        axios.get(`${API}/admin/reviews`, { headers }),
        axios.get(`${API}/products`, { headers })
      ]);
      
      // Handle both array and object responses
      const reviewsData = reviewsRes.data?.reviews || reviewsRes.data || [];
      setReviews(Array.isArray(reviewsData) ? reviewsData : []);
      setProducts(productsRes.data || []);
    } catch (error) {
      console.error('Failed to fetch reviews:', error);
      toast.error('Failed to load reviews');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  const getProductName = (productId) => {
    const product = products.find(p => p.id === productId);
    return product?.name || 'Unknown Product';
  };

  const handleApprove = async (reviewId) => {
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.put(`${API}/admin/reviews/${reviewId}/approve`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setReviews(reviews.map(r => 
        r.id === reviewId ? { ...r, is_approved: true } : r
      ));
      toast.success('Review approved and published!');
    } catch (error) {
      toast.error('Failed to approve review');
    }
  };

  const handleDelete = async (reviewId) => {
    if (!window.confirm('Are you sure you want to delete this review?')) return;
    
    try {
      const token = localStorage.getItem('reroots_token');
      await axios.delete(`${API}/admin/reviews/${reviewId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setReviews(reviews.filter(r => r.id !== reviewId));
      setSelectedReview(null);
      toast.success('Review deleted');
    } catch (error) {
      toast.error('Failed to delete review');
    }
  };

  const filteredReviews = reviews.filter(review => {
    const matchesSearch = 
      review.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      review.comment?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      review.user_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      getProductName(review.product_id).toLowerCase().includes(searchQuery.toLowerCase());
    
    if (filter === 'pending') return matchesSearch && !review.is_approved;
    if (filter === 'approved') return matchesSearch && review.is_approved;
    return matchesSearch;
  });

  const stats = {
    total: reviews.length,
    pending: reviews.filter(r => !r.is_approved).length,
    approved: reviews.filter(r => r.is_approved).length,
    avgRating: reviews.length > 0 
      ? (reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length).toFixed(1) 
      : '0.0'
  };

  const renderStars = (rating) => (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={`h-4 w-4 ${star <= rating ? 'text-yellow-500 fill-yellow-500' : 'text-gray-300'}`}
        />
      ))}
    </div>
  );

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
          <h1 className="text-2xl font-bold text-[#2D2A2E]">Customer Reviews</h1>
          <p className="text-[#5A5A5A]">Manage and moderate product reviews</p>
        </div>
        <Button onClick={fetchReviews} variant="outline" className="gap-2">
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
                <MessageSquare className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[#2D2A2E]">{stats.total}</p>
                <p className="text-sm text-[#5A5A5A]">Total Reviews</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setFilter('pending')}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-orange-100">
                <AlertCircle className="h-5 w-5 text-orange-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-orange-600">{stats.pending}</p>
                <p className="text-sm text-[#5A5A5A]">Pending Approval</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setFilter('approved')}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-100">
                <Check className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600">{stats.approved}</p>
                <p className="text-sm text-[#5A5A5A]">Published</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-yellow-100">
                <Star className="h-5 w-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-yellow-600">{stats.avgRating}</p>
                <p className="text-sm text-[#5A5A5A]">Average Rating</p>
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
            placeholder="Search reviews..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex gap-2">
          {['all', 'pending', 'approved'].map((f) => (
            <Button
              key={f}
              variant={filter === f ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilter(f)}
              className={filter === f ? 'bg-[#F8A5B8] hover:bg-[#E88DA0]' : ''}
            >
              {f === 'all' ? 'All' : f === 'pending' ? 'Pending' : 'Approved'}
            </Button>
          ))}
        </div>
      </div>

      {/* Reviews List */}
      <div className="space-y-4">
        {filteredReviews.length === 0 ? (
          <Card className="p-8 text-center">
            <MessageSquare className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-[#5A5A5A]">
              {filter === 'pending' 
                ? 'No pending reviews to moderate' 
                : filter === 'approved' 
                ? 'No approved reviews yet'
                : 'No reviews found'}
            </p>
          </Card>
        ) : (
          filteredReviews.map((review) => (
            <Card key={review.id} className={`overflow-hidden ${!review.is_approved ? 'border-l-4 border-l-orange-500' : ''}`}>
              <CardContent className="p-4">
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                  {/* Review Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      {renderStars(review.rating)}
                      <Badge variant={review.is_approved ? 'default' : 'secondary'} className={review.is_approved ? 'bg-green-500' : 'bg-orange-500'}>
                        {review.is_approved ? 'Published' : 'Pending'}
                      </Badge>
                    </div>
                    
                    <h3 className="font-semibold text-[#2D2A2E] mb-1">{review.title || 'No title'}</h3>
                    <p className="text-sm text-[#5A5A5A] mb-3 line-clamp-2">{review.comment}</p>
                    
                    <div className="flex flex-wrap items-center gap-4 text-xs text-[#5A5A5A]">
                      <span className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        {review.user_name || 'Anonymous'}
                      </span>
                      <span className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded">
                        {getProductName(review.product_id)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {new Date(review.created_at).toLocaleDateString()}
                      </span>
                      {review.images?.length > 0 && (
                        <span className="flex items-center gap-1">
                          <ImageIcon className="h-3 w-3" />
                          {review.images.length} photo(s)
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    {!review.is_approved && (
                      <Button
                        size="sm"
                        onClick={() => handleApprove(review.id)}
                        className="bg-green-500 hover:bg-green-600 text-white gap-1"
                      >
                        <Check className="h-4 w-4" />
                        Approve
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setSelectedReview(review)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDelete(review.id)}
                      className="text-red-500 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Review Detail Dialog */}
      <Dialog open={!!selectedReview} onOpenChange={() => setSelectedReview(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Review Details</DialogTitle>
          </DialogHeader>
          {selectedReview && (
            <div className="space-y-4 py-4">
              {/* Rating */}
              <div className="flex items-center gap-3">
                {renderStars(selectedReview.rating)}
                <span className="text-lg font-bold">{selectedReview.rating}/5</span>
                <Badge variant={selectedReview.is_approved ? 'default' : 'secondary'} className={selectedReview.is_approved ? 'bg-green-500' : 'bg-orange-500'}>
                  {selectedReview.is_approved ? 'Published' : 'Pending'}
                </Badge>
              </div>

              {/* Product */}
              <div className="p-3 bg-gray-50 rounded-lg">
                <p className="text-sm text-[#5A5A5A]">Product</p>
                <p className="font-medium">{getProductName(selectedReview.product_id)}</p>
              </div>

              {/* Title & Comment */}
              <div>
                <h3 className="font-semibold text-lg text-[#2D2A2E] mb-2">{selectedReview.title || 'No title'}</h3>
                <p className="text-[#5A5A5A] whitespace-pre-wrap">{selectedReview.comment}</p>
              </div>

              {/* Images */}
              {selectedReview.images?.length > 0 && (
                <div>
                  <p className="text-sm text-[#5A5A5A] mb-2">Customer Photos</p>
                  <div className="flex gap-2 flex-wrap">
                    {selectedReview.images.map((img, idx) => (
                      <img 
                        key={idx} 
                        src={img} 
                        alt={`Review ${idx + 1}`}
                        className="w-20 h-20 rounded-lg object-cover cursor-pointer hover:opacity-80"
                        onClick={() => window.open(img, '_blank')}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Meta */}
              <div className="flex items-center gap-4 text-sm text-[#5A5A5A] pt-2 border-t">
                <span className="flex items-center gap-1">
                  <User className="h-4 w-4" />
                  {selectedReview.user_name || 'Anonymous'}
                </span>
                <span className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  {new Date(selectedReview.created_at).toLocaleDateString()}
                </span>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-4">
                {!selectedReview.is_approved && (
                  <Button
                    onClick={() => {
                      handleApprove(selectedReview.id);
                      setSelectedReview({ ...selectedReview, is_approved: true });
                    }}
                    className="bg-green-500 hover:bg-green-600 text-white gap-2"
                  >
                    <Check className="h-4 w-4" />
                    Approve & Publish
                  </Button>
                )}
                <Button
                  variant="outline"
                  onClick={() => handleDelete(selectedReview.id)}
                  className="text-red-500 hover:text-red-600 gap-2"
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ReviewsManager;
