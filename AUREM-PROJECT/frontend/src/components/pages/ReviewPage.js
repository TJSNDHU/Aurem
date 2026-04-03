import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Star, Leaf, Check, Loader2, ExternalLink } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const ReviewPage = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [reviewData, setReviewData] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState(null);
  
  // Form state
  const [rating, setRating] = useState(0);
  const [hoveredRating, setHoveredRating] = useState(0);
  const [headline, setHeadline] = useState('');
  const [body, setBody] = useState('');

  // Fetch review request data
  useEffect(() => {
    const fetchReviewData = async () => {
      try {
        const res = await axios.get(`${API}/review/${token}`);
        setReviewData(res.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'This review link has expired or already been used.');
      }
      setLoading(false);
    };

    if (token) {
      fetchReviewData();
    }
  }, [token]);

  // Submit review
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (rating === 0) {
      toast.error('Please select a rating');
      return;
    }
    
    if (body.trim().length < 20) {
      toast.error('Please write at least 20 characters in your review');
      return;
    }
    
    setSubmitting(true);
    
    try {
      const res = await axios.post(`${API}/reviews/submit`, {
        token,
        rating,
        headline: headline.trim(),
        body: body.trim()
      });
      
      setResult(res.data);
      setSubmitted(true);
      toast.success('Thank you for your review! +100 Roots added to your account');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit review');
    }
    
    setSubmitting(false);
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#FDF9F9] to-white flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8] mx-auto mb-4" />
          <p className="text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#FDF9F9] to-white flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-8 text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-3xl">😔</span>
          </div>
          <h1 className="text-2xl font-light text-gray-800 mb-2">Link Expired</h1>
          <p className="text-gray-500 mb-6">{error}</p>
          <Button 
            onClick={() => navigate('/')}
            className="bg-[#F8A5B8] hover:bg-[#e8959a] text-white"
          >
            Back to ReRoots
          </Button>
        </div>
      </div>
    );
  }

  // Success state
  if (submitted && result) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-[#FDF9F9] to-white flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-8 text-center">
          {/* Header */}
          <div className="mb-6">
            <h1 className="text-2xl tracking-[0.3em] text-gray-800 font-light">
              RE<span className="text-[#F8A5B8]">ROOTS</span>
            </h1>
          </div>
          
          {/* Success Icon */}
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="h-10 w-10 text-green-600" />
          </div>
          
          <h2 className="text-2xl font-light text-gray-800 mb-2">
            Thank you, {reviewData?.customer_name?.split(' ')[0] || 'there'}!
          </h2>
          <p className="text-gray-500 mb-6">
            Your review has been received and is pending approval.
          </p>
          
          {/* Roots Awarded */}
          <div className="bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-xl p-6 mb-6">
            <div className="flex items-center justify-center gap-2 mb-2">
              <Leaf className="h-5 w-5 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-700">Roots Awarded</span>
            </div>
            <p className="text-3xl font-bold text-emerald-700 mb-1">+{result.roots_awarded} Roots</p>
            <p className="text-sm text-emerald-600">
              New balance: {result.new_balance} Roots (${(result.new_balance * 0.05).toFixed(2)})
            </p>
          </div>
          
          {/* Google Review CTA */}
          {result.google_review_link && (
            <div className="border-t pt-6 mb-6">
              <p className="text-gray-600 mb-4">
                Love ReRoots? Help other Canadians discover PDRN skincare 💙
              </p>
              <a 
                href={result.google_review_link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 w-full bg-gray-900 hover:bg-gray-800 text-white font-medium py-3 px-6 rounded-lg transition-colors"
              >
                Leave a Google Review
                <ExternalLink className="h-4 w-4" />
              </a>
              <p className="text-xs text-gray-400 mt-2">
                Takes 30 seconds and means everything to our small Canadian team.
              </p>
            </div>
          )}
          
          <Button 
            onClick={() => navigate('/account')}
            variant="outline"
            className="w-full"
          >
            Back to My Account
          </Button>
        </div>
      </div>
    );
  }

  // Review Form
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#FDF9F9] to-white py-8 px-4">
      <div className="max-w-lg mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl tracking-[0.3em] text-gray-800 font-light mb-2">
            RE<span className="text-[#F8A5B8]">ROOTS</span>
          </h1>
          <p className="text-xs tracking-widest text-gray-400 uppercase">Share Your Experience</p>
        </div>
        
        {/* Review Card */}
        <div className="bg-white rounded-2xl shadow-lg p-8">
          {/* Product Info */}
          <div className="text-center mb-6">
            <h2 className="text-xl font-light text-gray-800 mb-1">
              {reviewData?.product_name || 'AURA-GEN PDRN+TXA Serum'}
            </h2>
            {reviewData?.customer_name && (
              <p className="text-sm text-gray-500">
                Hi {reviewData.customer_name.split(' ')[0]}, how was your experience?
              </p>
            )}
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Star Rating */}
            <div className="text-center">
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Overall Rating
              </label>
              <div className="flex justify-center gap-2" data-testid="star-rating">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    onMouseEnter={() => setHoveredRating(star)}
                    onMouseLeave={() => setHoveredRating(0)}
                    className="p-1 transition-transform hover:scale-110 focus:outline-none"
                  >
                    <Star 
                      className={`h-10 w-10 transition-colors ${
                        star <= (hoveredRating || rating)
                          ? 'fill-yellow-400 text-yellow-400'
                          : 'fill-gray-200 text-gray-200'
                      }`}
                    />
                  </button>
                ))}
              </div>
              {rating > 0 && (
                <p className="text-sm text-gray-500 mt-2">
                  {rating === 5 ? 'Excellent!' : rating === 4 ? 'Great!' : rating === 3 ? 'Good' : rating === 2 ? 'Fair' : 'Poor'}
                </p>
              )}
            </div>
            
            {/* Headline */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Headline <span className="text-gray-400">(optional)</span>
              </label>
              <Input
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                placeholder="Sum up your experience in a few words"
                maxLength={100}
                className="border-gray-200 focus:border-[#F8A5B8]"
                data-testid="review-headline"
              />
            </div>
            
            {/* Review Body */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Your Review <span className="text-red-400">*</span>
              </label>
              <Textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Tell us about your experience with the product. What did you notice? How has your skin changed?"
                rows={5}
                className="border-gray-200 focus:border-[#F8A5B8] resize-none"
                data-testid="review-body"
              />
              <p className="text-xs text-gray-400 mt-1">
                {body.length}/20 characters minimum
              </p>
            </div>
            
            {/* Reward Info */}
            <div className="bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-lg p-4 text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <Leaf className="h-4 w-4 text-emerald-600" />
                <span className="font-medium text-emerald-700">Earn 100 Roots</span>
              </div>
              <p className="text-sm text-emerald-600">That's $5.00 toward your next order!</p>
            </div>
            
            {/* Submit Button */}
            <Button
              type="submit"
              disabled={submitting || rating === 0}
              className="w-full bg-[#F8A5B8] hover:bg-[#e8959a] text-white font-medium py-6 text-lg"
              data-testid="submit-review-btn"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin mr-2" />
                  Submitting...
                </>
              ) : (
                <>
                  Submit Review → Earn 100 Roots
                  <Leaf className="h-5 w-5 ml-2" />
                </>
              )}
            </Button>
          </form>
          
          {/* Google Review Link */}
          {reviewData?.google_review_link && (
            <div className="border-t mt-6 pt-6 text-center">
              <p className="text-sm text-gray-500 mb-3">
                Also love it? Share on Google:
              </p>
              <a 
                href={reviewData.google_review_link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 text-gray-700 hover:text-gray-900 font-medium text-sm border border-gray-300 rounded-lg px-4 py-2 hover:bg-gray-50 transition-colors"
              >
                Leave a Google Review
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <p className="text-center text-xs text-gray-400 mt-6">
          REROOTS AESTHETICS INC. · TORONTO, CANADA
        </p>
      </div>
    </div>
  );
};

export default ReviewPage;
