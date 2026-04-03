import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { Sparkles, X, Package, Shield, Sun, AlertTriangle, CheckCircle2, Zap, TrendingUp, Clock } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Speed advantage data for different concerns
const CONCERN_BENEFITS = [
  { concern: 'Hyperpigmentation', speed: '60%', icon: '✨' },
  { concern: 'Fine Lines', speed: '50%', icon: '🌟' },
  { concern: 'Acne Recovery', speed: '45%', icon: '💧' },
];

const ComboUpsellPopup = ({ productId, productName, isOpen, onClose, onAddCombo }) => {
  const [matchingCombo, setMatchingCombo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hasChecked, setHasChecked] = useState(false);

  useEffect(() => {
    if (isOpen && productId) {
      checkForMatchingCombo();
    }
    // Reset state when popup closes
    if (!isOpen) {
      setHasChecked(false);
      setMatchingCombo(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, productId]);

  const checkForMatchingCombo = async () => {
    setLoading(true);
    setHasChecked(false);
    try {
      console.log('[ComboUpsellPopup] Checking for combos with productId:', productId);
      const res = await axios.get(`${API}/combo-offers`);
      const combos = res.data || [];
      
      // Find a combo that contains this product AND has popup enabled
      const match = combos.find(combo => 
        combo.product_ids?.includes(productId) && 
        combo.is_active && 
        combo.popup_enabled !== false  // Default to enabled if not set
      );
      
      console.log('[ComboUpsellPopup] Match found:', match ? match.name : 'none', 'popup_enabled:', match?.popup_enabled);
      
      if (match) {
        // Fetch full combo details
        const detailRes = await axios.get(`${API}/combo-offers/${match.id}`);
        setMatchingCombo(detailRes.data);
      } else {
        setMatchingCombo(null);
      }
    } catch (err) {
      console.error('Failed to check combos:', err);
      setMatchingCombo(null);
    } finally {
      setLoading(false);
      setHasChecked(true);
    }
  };

  // Determine which product is selected and which is "missing"
  const { selectedProduct, missingProduct, dynamicContent } = useMemo(() => {
    if (!matchingCombo?.products || matchingCombo.products.length < 2) {
      return { selectedProduct: null, missingProduct: null, dynamicContent: null };
    }

    const selected = matchingCombo.products.find(p => p.id === productId);
    const missing = matchingCombo.products.find(p => p.id !== productId);

    // Intelligent messaging based on which product is selected
    // Detect product types based on ingredients
    const selectedIngredients = (selected?.ingredients || '').toLowerCase();
    const missingIngredients = (missing?.ingredients || '').toLowerCase();
    
    const isSelectedAcid = selectedIngredients.includes('mandelic') || 
                           selectedIngredients.includes('glycolic') || 
                           selectedIngredients.includes('salicylic') ||
                           selectedIngredients.includes('tranexamic');
    
    const isMissingRecovery = missingIngredients.includes('squalane') || 
                              missingIngredients.includes('ceramide') ||
                              missingIngredients.includes('peptide') ||
                              missingIngredients.includes('copper');

    let headline, body, benefits;

    if (isSelectedAcid && isMissingRecovery) {
      // User selected an acid/active product, missing recovery
      headline = "Don't just Resurface. Rebuild.";
      body = `You've selected the high-intensity ${selected?.name?.split(' ').slice(0, 2).join(' ')}. To prevent dryness and maximize results, our clinical protocol recommends the ${missing?.name} as Step 2. It floods the skin with active recovery ingredients to seal the barrier while the actives work their magic.`;
      benefits = [
        { icon: Zap, text: "Synergy: Active acids prepare the pathway, Recovery Complex fills the skin" },
        { icon: Shield, text: "Safety: Dramatically reduces the risk of irritation or peeling" },
        { icon: Sparkles, text: `Value: Unlock ${matchingCombo.discount_percent}% Discount ($${(matchingCombo.original_price - matchingCombo.combo_price).toFixed(2)} Savings)` }
      ];
    } else if (isMissingRecovery && !isSelectedAcid) {
      // User selected recovery, missing active
      headline = "Ready for a Total Transformation?";
      body = `The ${selected?.name} is half the story. To see real results on fine lines and dark spots, pair it with the ${missing?.name}. Using them together allows the Recovery Complex to penetrate deeper, rebuilding your skin from the inside out.`;
      benefits = [
        { icon: Zap, text: "Synergy: Actives open cellular pathways for deeper penetration" },
        { icon: CheckCircle2, text: "Results: See visible transformation in as little as 4 weeks" },
        { icon: Sparkles, text: `Value: Save ${matchingCombo.discount_percent}% when purchased together` }
      ];
    } else {
      // Default intelligent messaging
      headline = "Complete Your Protocol";
      body = `Great choice! The ${selected?.name?.split(' ').slice(0, 3).join(' ')} works even better with its partner product. Together, they form a complete clinical system designed for optimal results.`;
      benefits = [
        { icon: Zap, text: "Synergy: Products designed to work together" },
        { icon: Shield, text: "Safety: Clinical protocol for best results" },
        { icon: Sparkles, text: `Value: ${matchingCombo.discount_percent}% off when purchased as a duo` }
      ];
    }

    return { 
      selectedProduct: selected, 
      missingProduct: missing, 
      dynamicContent: { headline, body, benefits } 
    };
  }, [matchingCombo, productId]);

  const handleAddCombo = () => {
    if (matchingCombo && onAddCombo) {
      onAddCombo(matchingCombo);
    }
    onClose();
  };

  // Don't show if no matching combo (but only after we've checked)
  if (!matchingCombo && hasChecked && !loading) {
    if (isOpen) {
      console.log('[ComboUpsellPopup] No combo found, closing popup');
      setTimeout(onClose, 100);
    }
    return null;
  }

  // Show loading state while checking
  if (loading || (!hasChecked && isOpen)) {
    return (
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="max-w-lg p-8 flex items-center justify-center">
          <VisuallyHidden>
            <DialogTitle>Checking for special offers</DialogTitle>
          </VisuallyHidden>
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-gray-600">Checking for special offers...</p>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  // Check for safety warnings based on ingredients
  const hasAcids = matchingCombo?.products?.some(p => 
    (p.ingredients || '').toLowerCase().match(/mandelic|glycolic|salicylic|retino|tranexamic/)
  );

  return (
    <Dialog open={isOpen && matchingCombo} onOpenChange={onClose}>
      <DialogContent 
        className="max-w-lg p-0 overflow-hidden max-h-[85vh] overflow-y-auto"
        style={{ overscrollBehavior: 'contain' }}
        data-testid="combo-upsell-popup"
      >
        <VisuallyHidden>
          <DialogTitle>Complete Your Skincare Protocol</DialogTitle>
        </VisuallyHidden>
        
        {/* Prominent X Close Button - Fixed position */}
        <button 
          onClick={onClose}
          className="absolute top-3 right-3 z-50 w-8 h-8 rounded-full bg-white/90 hover:bg-white shadow-lg flex items-center justify-center text-gray-600 hover:text-black transition-all"
          aria-label="Close"
          data-testid="upsell-close-btn"
        >
          <X className="h-5 w-5" />
        </button>
        
        {/* Header with Dynamic Headline */}
        <div className="bg-gradient-to-r from-purple-600 to-pink-500 p-4 pt-12 text-white relative">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="h-5 w-5" />
            <span className="font-semibold">
              {matchingCombo?.popup_headline || dynamicContent?.headline || "Complete the Protocol!"}
            </span>
          </div>
          <p className="text-sm text-purple-100">
            Clinical protocol for optimal results
          </p>
        </div>

        {matchingCombo && (
          <div className="p-5">
            {/* Dynamic Upsell Message */}
            <div className="mb-4 p-4 bg-purple-50 rounded-lg border-l-4 border-purple-500">
              <p className="text-gray-700 text-sm leading-relaxed">
                {matchingCombo?.popup_message || dynamicContent?.body}
              </p>
            </div>

            {/* Step-by-Step Protocol */}
            <div className="mb-4">
              <h3 className="font-bold text-lg text-gray-900 mb-3">{matchingCombo.name}</h3>
              
              {/* Products with Step Numbers - Both show "Included" */}
              <div className="space-y-3 mb-4">
                {matchingCombo.products?.map((product, idx) => (
                  <div 
                    key={product.id} 
                    className={`flex items-center gap-3 p-3 rounded-lg border-2 transition-all ${
                      product.id === productId 
                        ? 'bg-purple-50 border-purple-300' 
                        : 'bg-green-50 border-green-200'
                    }`}
                  >
                    {/* Step Number */}
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm ${
                      idx === 0 ? 'bg-purple-500' : 'bg-pink-500'
                    }`}>
                      {idx + 1}
                    </div>
                    
                    {/* Product Image */}
                    <div className="w-12 h-12 rounded-lg overflow-hidden border border-gray-200 bg-white">
                      <img 
                        src={product.images?.[0] || '/placeholder.png'}
                        alt={product.name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    
                    {/* Product Info */}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 text-sm truncate">{product.name}</p>
                      <p className="text-xs text-gray-500">
                        {idx === 0 ? 'Apply first on cleansed skin' : 'Apply after Step 1 to seal'}
                      </p>
                    </div>
                    
                    {/* Both products show "Included" with checkmark */}
                    <div className="flex items-center gap-1">
                      <CheckCircle2 className={`h-4 w-4 ${product.id === productId ? 'text-purple-600' : 'text-green-600'}`} />
                      <Badge className={`text-xs ${
                        product.id === productId 
                          ? 'bg-purple-100 text-purple-700' 
                          : 'bg-green-100 text-green-700'
                      }`}>
                        {product.id === productId ? 'Selected' : 'Included'}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>

              {/* Synergy Note */}
              {matchingCombo.synergy_note && (
                <div className="p-3 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg text-sm mb-4">
                  <div className="flex items-start gap-2">
                    <Zap className="h-4 w-4 text-purple-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <span className="font-semibold text-purple-700">The Science: </span>
                      <span className="text-gray-700">{matchingCombo.synergy_note}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Benefits List */}
              {dynamicContent?.benefits && (
                <div className="space-y-2 mb-4">
                  {dynamicContent.benefits.map((benefit, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-sm">
                      <benefit.icon className="h-4 w-4 text-purple-500 flex-shrink-0" />
                      <span className="text-gray-700">{benefit.text}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Safety Warning for Products with Acids/Retinoids */}
            {hasAcids && (
              <div className="mb-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
                  <div className="text-xs text-amber-800">
                    <p className="font-semibold mb-1">Clinical Protocol Notice:</p>
                    <ul className="space-y-0.5">
                      <li className="flex items-center gap-1">
                        <Sun className="h-3 w-3" /> SPF 30+ required daily when using this protocol
                      </li>
                      <li>• Best applied in PM routine for optimal absorption</li>
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* Benefit by Concern - Speed Advantages */}
            <div className="mb-4 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="h-4 w-4 text-blue-600" />
                <span className="font-semibold text-blue-800 text-sm">Targeted Results, Double the Speed</span>
              </div>
              <p className="text-xs text-gray-600 mb-3">
                Why wait 12 weeks? The duo targets your primary concerns with clinical-grade percentages:
              </p>
              <div className="grid grid-cols-3 gap-2">
                {CONCERN_BENEFITS.map((item, idx) => (
                  <div key={idx} className="text-center p-2 bg-white rounded-lg">
                    <span className="text-lg">{item.icon}</span>
                    <p className="text-xs font-medium text-gray-700">{item.concern}</p>
                    <p className="text-xs font-bold text-green-600">{item.speed} Faster</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Pricing with Enhanced Savings Display */}
            <div className="flex items-center justify-between mb-4 p-4 bg-gradient-to-r from-emerald-50 to-green-50 rounded-lg border border-green-200">
              <div>
                <p className="text-xs text-gray-500 mb-1">Complete Protocol Price</p>
                <div className="flex items-center gap-2">
                  <span className="text-2xl font-bold text-gray-900">${matchingCombo.combo_price?.toFixed(2)}</span>
                  <span className="text-gray-400 line-through text-lg">${matchingCombo.original_price?.toFixed(2)}</span>
                </div>
              </div>
              <div className="text-right">
                <Badge className="bg-gradient-to-r from-emerald-500 to-green-500 text-white px-3 py-1.5 text-sm font-semibold">
                  Save ${(matchingCombo.original_price - matchingCombo.combo_price).toFixed(2)}
                </Badge>
                <p className="text-xs text-emerald-600 mt-1">{matchingCombo.discount_percent}% off today</p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-3">
              <Button 
                variant="outline" 
                className="flex-1 py-6"
                onClick={onClose}
                data-testid="upsell-decline-btn"
              >
                Just Add Single Product
              </Button>
              <Button 
                className="flex-1 py-6 bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-700 hover:to-pink-600 text-white font-semibold"
                onClick={handleAddCombo}
                data-testid="upsell-accept-btn"
              >
                <Package className="h-4 w-4 mr-2" />
                Add Combo - Save {Number(matchingCombo.discount_percent).toFixed(0)}%
              </Button>
            </div>
            
            {/* Clinical Authority Note */}
            <p className="text-center text-xs text-gray-400 mt-3">
              Recommended by our clinical skincare experts
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ComboUpsellPopup;
