import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Sparkles, Clock, CheckCircle2, Droplets, 
  ChevronRight, Loader2, Target, Zap
} from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const ComboBenefits = ({ products, onAddToCart }) => {
  const [benefits, setBenefits] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('timeline');

  useEffect(() => {
    if (products && products.length >= 2) {
      generateBenefits();
    }
  }, [products]);

  const generateBenefits = async () => {
    setLoading(true);
    setError(null);
    try {
      const productData = products.map(p => ({
        name: p.name,
        ingredients: p.ingredients || p.short_description || '',
        short_description: p.short_description
      }));
      
      const res = await axios.post(`${API}/generate-combo-benefits`, {
        products: productData
      }, { timeout: 60000 });
      
      if (res.data?.success) {
        setBenefits(res.data.benefits);
      }
    } catch (err) {
      console.error('Failed to generate combo benefits:', err);
      setError('Unable to load combo benefits');
    } finally {
      setLoading(false);
    }
  };

  if (!products || products.length < 2) return null;

  // Calculate combo price
  const originalTotal = products.reduce((sum, p) => sum + (p.compare_price || p.price || 0), 0);
  const comboTotal = products.reduce((sum, p) => sum + (p.price || 0), 0);
  const savings = originalTotal - comboTotal;
  const savingsPercent = originalTotal > 0 ? Math.round((savings / originalTotal) * 100) : 0;

  if (loading) {
    return (
      <Card className="border-2 border-purple-200 bg-gradient-to-br from-purple-50 to-pink-50">
        <CardContent className="p-8 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-purple-500 mx-auto mb-3" />
          <p className="text-purple-600 font-medium">Analyzing combo benefits...</p>
          <p className="text-sm text-purple-400">AI is calculating your skincare synergy</p>
        </CardContent>
      </Card>
    );
  }

  if (error || !benefits) {
    return null;
  }

  return (
    <Card className="border-2 border-purple-200 bg-gradient-to-br from-purple-50 via-white to-pink-50 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-pink-500 p-4 text-white">
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className="h-5 w-5" />
          <span className="font-semibold text-lg">{benefits.combo_name || 'Complete Skincare Routine'}</span>
        </div>
        <p className="text-purple-100 text-sm">{benefits.tagline}</p>
      </div>

      <CardContent className="p-0">
        {/* Tab Navigation */}
        <div className="flex border-b">
          <button
            onClick={() => setActiveTab('timeline')}
            className={`flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors ${
              activeTab === 'timeline' 
                ? 'text-purple-600 border-b-2 border-purple-500 bg-purple-50' 
                : 'text-gray-500 hover:text-purple-500'
            }`}
          >
            <Clock className="h-4 w-4" />
            Results Timeline
          </button>
          <button
            onClick={() => setActiveTab('concerns')}
            className={`flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors ${
              activeTab === 'concerns' 
                ? 'text-purple-600 border-b-2 border-purple-500 bg-purple-50' 
                : 'text-gray-500 hover:text-purple-500'
            }`}
          >
            <Target className="h-4 w-4" />
            Skin Concerns
          </button>
          <button
            onClick={() => setActiveTab('routine')}
            className={`flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center gap-2 transition-colors ${
              activeTab === 'routine' 
                ? 'text-purple-600 border-b-2 border-purple-500 bg-purple-50' 
                : 'text-gray-500 hover:text-purple-500'
            }`}
          >
            <Droplets className="h-4 w-4" />
            How to Use
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-4">
          {/* Results Timeline Tab */}
          {activeTab === 'timeline' && benefits.results_timeline && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600 mb-4">{benefits.synergy_description}</p>
              <div className="relative">
                {/* Timeline line */}
                <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gradient-to-b from-purple-400 via-pink-400 to-purple-300" />
                
                {benefits.results_timeline.map((phase, idx) => (
                  <div key={idx} className="relative pl-10 pb-6 last:pb-0">
                    {/* Timeline dot */}
                    <div className={`absolute left-2 w-5 h-5 rounded-full border-2 border-white shadow-md ${
                      idx === 0 ? 'bg-purple-500' : 
                      idx === 1 ? 'bg-pink-500' : 
                      idx === 2 ? 'bg-rose-500' : 'bg-amber-500'
                    }`}>
                      <Zap className="h-3 w-3 text-white absolute top-0.5 left-0.5" />
                    </div>
                    
                    <div className="bg-white rounded-lg p-3 shadow-sm border border-gray-100">
                      <div className="font-semibold text-gray-800 mb-2 flex items-center gap-2">
                        <Clock className="h-4 w-4 text-purple-500" />
                        {phase.period}
                      </div>
                      <ul className="space-y-1">
                        {phase.results.map((result, rIdx) => (
                          <li key={rIdx} className="flex items-start gap-2 text-sm text-gray-600">
                            <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                            {result}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Skin Concerns Tab */}
          {activeTab === 'concerns' && benefits.skin_concerns_addressed && (
            <div className="space-y-3">
              {benefits.skin_concerns_addressed.map((item, idx) => (
                <div key={idx} className="bg-white rounded-lg p-4 border border-gray-100 shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                      <span className="font-semibold text-gray-800">{item.concern}</span>
                    </div>
                    <Badge variant="outline" className="bg-purple-50 text-purple-600 border-purple-200">
                      {item.resolution_time}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {item.addressed_by.map((product, pIdx) => (
                      <Badge key={pIdx} variant="secondary" className="text-xs bg-gray-100">
                        {product}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
              
              {/* Best for skin types */}
              {benefits.best_for_skin_types && (
                <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                  <p className="text-sm font-medium text-blue-700 mb-2">Best for skin types:</p>
                  <div className="flex flex-wrap gap-2">
                    {benefits.best_for_skin_types.map((type, idx) => (
                      <Badge key={idx} className="bg-blue-100 text-blue-700 border-blue-200">
                        {type}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Routine/How to Use Tab */}
          {activeTab === 'routine' && benefits.usage_order && (
            <div className="space-y-3">
              {benefits.usage_order.map((step, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 bg-white rounded-lg border border-gray-100">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
                    {step.step}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-gray-800">{step.product}</span>
                      <Badge variant="outline" className="text-xs">
                        {step.when}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-600">{step.instruction}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pricing & CTA */}
        <div className="p-4 bg-gradient-to-r from-purple-100 to-pink-100 border-t">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-gray-900">${comboTotal.toFixed(2)}</span>
                {savings > 0 && (
                  <span className="text-lg text-gray-400 line-through">${originalTotal.toFixed(2)}</span>
                )}
              </div>
              {savingsPercent > 0 && (
                <p className="text-green-600 font-medium text-sm">
                  Save {savingsPercent}% with this combo!
                </p>
              )}
            </div>
            {onAddToCart && (
              <Button 
                onClick={() => onAddToCart(products)}
                className="bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-700 hover:to-pink-600 text-white px-6"
              >
                Add Combo to Bag
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ComboBenefits;
