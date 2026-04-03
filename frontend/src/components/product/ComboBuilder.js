import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Sparkles, Clock, CheckCircle2, X, ShoppingBag,
  ChevronRight, Loader2, Target, Zap, Plus, Package
} from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { toast } from 'sonner';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const ComboBuilder = ({ selectedProducts, onRemoveProduct, onClearAll, onAddToCart }) => {
  const [benefits, setBenefits] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('timeline');

  useEffect(() => {
    if (selectedProducts && selectedProducts.length >= 2) {
      generateBenefits();
    } else {
      setBenefits(null);
    }
  }, [selectedProducts]);

  const generateBenefits = async () => {
    setLoading(true);
    try {
      const productData = selectedProducts.map(p => ({
        name: p.name,
        ingredients: p.ingredients || p.short_description || '',
        short_description: p.short_description
      }));
      
      // Show loading message for long operations
      toast.loading('Analyzing product synergies with AI...', { id: 'combo-gen', duration: 90000 });
      
      const res = await axios.post(`${API}/generate-combo-benefits`, {
        products: productData
      }, { timeout: 90000 }); // Increased timeout to 90 seconds
      
      if (res.data?.success) {
        setBenefits(res.data.benefits);
        toast.success('Combo analysis complete!', { id: 'combo-gen' });
      } else {
        toast.error('Could not analyze combo. Try different products.', { id: 'combo-gen' });
      }
    } catch (err) {
      console.error('Failed to generate combo benefits:', err);
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        toast.error('Analysis taking too long. Please try again.', { id: 'combo-gen' });
      } else {
        toast.error('Failed to analyze combo. Please try again.', { id: 'combo-gen' });
      }
    } finally {
      setLoading(false);
    }
  };

  // Calculate prices
  const individualTotal = selectedProducts.reduce((sum, p) => sum + (p.price || 0), 0);
  const compareTotal = selectedProducts.reduce((sum, p) => sum + (p.compare_price || p.price || 0), 0);
  
  // Auto discount for combos: 10% for 2 products, 15% for 3, 20% for 4+
  const comboDiscount = selectedProducts.length === 2 ? 0.10 : 
                        selectedProducts.length === 3 ? 0.15 : 0.20;
  const comboPrice = individualTotal * (1 - comboDiscount);
  const savings = individualTotal - comboPrice;

  if (!selectedProducts || selectedProducts.length === 0) {
    return null;
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t-2 border-purple-300 shadow-2xl transform transition-transform duration-300">
      {/* Collapsed Bar */}
      <div className="max-w-7xl mx-auto">
        {/* Header with selected products */}
        <div className="p-4 bg-gradient-to-r from-purple-50 to-pink-50">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Package className="h-5 w-5 text-purple-600" />
              <span className="font-semibold text-purple-800">
                Build Your Routine ({selectedProducts.length} products)
              </span>
              {selectedProducts.length >= 2 && (
                <Badge className="bg-green-100 text-green-700">
                  Save {Math.round(comboDiscount * 100)}%
                </Badge>
              )}
            </div>
            <Button variant="ghost" size="sm" onClick={onClearAll} className="text-gray-500">
              Clear All <X className="h-4 w-4 ml-1" />
            </Button>
          </div>
          
          {/* Selected Products Row */}
          <div className="flex items-center gap-3 overflow-x-auto pb-2">
            {selectedProducts.map((product, idx) => (
              <div key={product.id} className="flex-shrink-0 relative group">
                <div className="w-16 h-16 rounded-lg border-2 border-purple-200 overflow-hidden bg-white">
                  <img 
                    src={product.images?.[0] || '/placeholder.png'} 
                    alt={product.name}
                    className="w-full h-full object-cover"
                  />
                </div>
                <button
                  onClick={() => onRemoveProduct(product.id)}
                  className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  ×
                </button>
                <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-purple-500 text-white rounded-full text-xs flex items-center justify-center">
                  {idx + 1}
                </div>
              </div>
            ))}
            
            {selectedProducts.length < 4 && (
              <div className="w-16 h-16 rounded-lg border-2 border-dashed border-purple-300 flex items-center justify-center text-purple-400">
                <Plus className="h-5 w-5" />
              </div>
            )}
            
            {/* Price Summary */}
            <div className="flex-shrink-0 ml-auto pl-4 border-l border-purple-200">
              <div className="text-right">
                {selectedProducts.length >= 2 ? (
                  <>
                    <div className="text-sm text-gray-500 line-through">${individualTotal.toFixed(2)}</div>
                    <div className="text-xl font-bold text-purple-600">${comboPrice.toFixed(2)}</div>
                    <div className="text-xs text-green-600">You save ${savings.toFixed(2)}</div>
                  </>
                ) : (
                  <>
                    <div className="text-xl font-bold text-gray-700">${individualTotal.toFixed(2)}</div>
                    <div className="text-xs text-purple-500">Add 1 more for 10% off</div>
                  </>
                )}
              </div>
            </div>
            
            {/* Add to Cart Button */}
            <Button 
              onClick={() => onAddToCart(selectedProducts, comboPrice)}
              disabled={selectedProducts.length < 2}
              className="flex-shrink-0 bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-700 hover:to-pink-600"
            >
              <ShoppingBag className="h-4 w-4 mr-2" />
              {selectedProducts.length >= 2 ? 'Add Combo' : 'Select 2+'}
            </Button>
          </div>
        </div>

        {/* AI Benefits Panel (expandable) */}
        {selectedProducts.length >= 2 && (
          <div className="border-t border-purple-200">
            {loading ? (
              <div className="p-6 text-center bg-purple-50">
                <Loader2 className="h-6 w-6 animate-spin text-purple-500 mx-auto mb-2" />
                <p className="text-purple-600 font-medium">AI is analyzing your routine...</p>
              </div>
            ) : benefits ? (
              <div className="bg-white">
                {/* Combo Name Header */}
                <div className="p-4 bg-gradient-to-r from-purple-600 to-pink-500 text-white">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5" />
                    <span className="font-bold">{benefits.combo_name}</span>
                  </div>
                  <p className="text-sm text-purple-100 mt-1">{benefits.tagline}</p>
                </div>
                
                {/* Tabs */}
                <div className="flex border-b">
                  {[
                    { id: 'timeline', label: 'Results Timeline', icon: Clock },
                    { id: 'concerns', label: 'Skin Concerns', icon: Target },
                    { id: 'routine', label: 'How to Use', icon: Zap }
                  ].map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex-1 px-3 py-2 text-sm font-medium flex items-center justify-center gap-1 ${
                        activeTab === tab.id 
                          ? 'text-purple-600 border-b-2 border-purple-500 bg-purple-50' 
                          : 'text-gray-500'
                      }`}
                    >
                      <tab.icon className="h-4 w-4" />
                      <span className="hidden sm:inline">{tab.label}</span>
                    </button>
                  ))}
                </div>
                
                {/* Tab Content */}
                <div className="p-4 max-h-48 overflow-y-auto">
                  {activeTab === 'timeline' && benefits.results_timeline && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {benefits.results_timeline.map((phase, idx) => (
                        <div key={idx} className="bg-gray-50 rounded-lg p-3">
                          <div className="font-semibold text-purple-600 text-sm mb-2 flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {phase.period}
                          </div>
                          <ul className="space-y-1">
                            {phase.results.slice(0, 2).map((result, rIdx) => (
                              <li key={rIdx} className="flex items-start gap-1 text-xs text-gray-600">
                                <CheckCircle2 className="h-3 w-3 text-green-500 mt-0.5 flex-shrink-0" />
                                <span className="line-clamp-2">{result}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'concerns' && benefits.skin_concerns_addressed && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {benefits.skin_concerns_addressed.map((item, idx) => (
                        <div key={idx} className="bg-gray-50 rounded-lg p-3">
                          <div className="flex items-center gap-2 mb-1">
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                            <span className="font-medium text-sm">{item.concern}</span>
                          </div>
                          <Badge variant="outline" className="text-xs bg-purple-50 text-purple-600">
                            {item.resolution_time}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'routine' && benefits.usage_order && (
                    <div className="flex gap-3 overflow-x-auto">
                      {benefits.usage_order.map((step, idx) => (
                        <div key={idx} className="flex-shrink-0 w-48 bg-gray-50 rounded-lg p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <div className="w-6 h-6 rounded-full bg-purple-500 text-white text-xs flex items-center justify-center">
                              {step.step}
                            </div>
                            <Badge variant="outline" className="text-xs">{step.when}</Badge>
                          </div>
                          <div className="font-medium text-sm mb-1">{step.product}</div>
                          <p className="text-xs text-gray-500 line-clamp-2">{step.instruction}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};

export default ComboBuilder;
