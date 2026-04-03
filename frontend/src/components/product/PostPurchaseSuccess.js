import React, { useState, useEffect } from 'react';
import { CheckCircle2, Download, Clock, Sparkles, ChevronRight, Shield, Beaker, Calendar, MessageCircle } from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';

// ReRoots WhatsApp Business Number (Canada)
const WHATSAPP_BUSINESS_NUMBER = '16475551234'; // Replace with actual number

/**
 * PostPurchaseSuccess Component
 * 
 * Displays a personalized success message after a combo purchase.
 * Dynamically pulls the specific combo name and provides clinical protocol guidance.
 * 
 * Props:
 * - order: The completed order object
 * - comboDetails: Details of the combo purchased (name, products, total_active_percent)
 */
const PostPurchaseSuccess = ({ order, comboDetails }) => {
  const [showCalendarPrompt, setShowCalendarPrompt] = useState(false);
  const [showWhatsAppPrompt, setShowWhatsAppPrompt] = useState(false);
  
  // Determine if this is a "Resurface & Rebuild" or similar high-potency combo
  const isHighPotencyCombo = comboDetails?.total_active_percent >= 40;
  const has60SecondProtocol = comboDetails?.name?.toLowerCase().includes('resurface') || 
                              comboDetails?.name?.toLowerCase().includes('rebuild') ||
                              isHighPotencyCombo;
  
  // Check if customer opted in to WhatsApp or if this is their first order
  const showWhatsAppButton = order?.whatsapp_opted_in || order?.is_first_order !== false;
  
  // Generate WhatsApp message link
  const getWhatsAppLink = () => {
    const orderId = order?.order_id || order?.order_number || 'ORDER';
    const message = encodeURIComponent(`Hi ReRoots! My order #${orderId} is confirmed. Can you confirm my details?`);
    return `https://wa.me/${WHATSAPP_BUSINESS_NUMBER}?text=${message}`;
  };
  
  useEffect(() => {
    // Show calendar prompt after 2 seconds
    const timer = setTimeout(() => setShowCalendarPrompt(true), 2000);
    // Show WhatsApp prompt after 4 seconds
    const timer2 = setTimeout(() => setShowWhatsAppPrompt(true), 4000);
    return () => {
      clearTimeout(timer);
      clearTimeout(timer2);
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Main Success Card */}
      <Card className="border-2 border-green-200 bg-gradient-to-br from-green-50 to-emerald-50 overflow-hidden">
        <CardContent className="p-6">
          {/* Success Icon & Header */}
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-gradient-to-r from-green-500 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg">
              <CheckCircle2 className="h-8 w-8 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Your Clinical Protocol is Ready!
            </h2>
            <p className="text-gray-600">
              You've made the smartest choice for your skin transformation journey.
            </p>
          </div>

          {/* Dynamic Combo Name Display */}
          {comboDetails && (
            <div className="bg-white rounded-xl p-4 mb-6 border border-green-100">
              <div className="flex items-center gap-3 mb-3">
                <Sparkles className="h-5 w-5 text-amber-500" />
                <span className="font-semibold text-gray-900">Your Protocol:</span>
              </div>
              <h3 className="text-xl font-bold text-purple-700 mb-2">
                {comboDetails.name || "The Complete Duo"}
              </h3>
              
              {/* Active Concentration Badge */}
              {comboDetails.total_active_percent && (
                <div className="flex items-center gap-2 mb-3">
                  <Badge className="bg-amber-500 text-white">
                    <Beaker className="h-3 w-3 mr-1" />
                    {comboDetails.total_active_percent}% Total Actives
                  </Badge>
                  <span className="text-xs text-gray-500">Clinical-Grade Formula</span>
                </div>
              )}

              {/* Products in combo */}
              {comboDetails.products && (
                <div className="space-y-2">
                  {comboDetails.products.map((product, idx) => (
                    <div key={product.id || idx} className="flex items-center gap-2 text-sm">
                      <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                        idx === 0 ? 'bg-purple-100 text-purple-700' : 'bg-pink-100 text-pink-700'
                      }`}>
                        {idx + 1}
                      </span>
                      <span className="text-gray-700">{product.name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 60-Second Protocol Reminder - Only for high-potency combos */}
          {has60SecondProtocol && (
            <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl p-4 mb-6 border border-amber-200">
              <div className="flex items-start gap-3">
                <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <Clock className="h-6 w-6 text-amber-600" />
                </div>
                <div>
                  <h4 className="font-bold text-amber-800 mb-1">
                    Critical Protocol: 60-Second Wait Time
                  </h4>
                  <p className="text-sm text-amber-700 mb-2">
                    For optimal results with your {comboDetails?.name || "protocol"}:
                  </p>
                  <ul className="text-sm text-amber-700 space-y-1">
                    <li className="flex items-center gap-2">
                      <span className="w-5 h-5 bg-purple-500 text-white rounded-full flex items-center justify-center text-xs">1</span>
                      Apply Step 1 (Accelerator) to clean skin
                    </li>
                    <li className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-amber-500" />
                      <strong>Wait 60 seconds</strong> — DMI "molecular taxi" clearing pathways
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="w-5 h-5 bg-pink-500 text-white rounded-full flex items-center justify-center text-xs">2</span>
                      Apply Step 2 (Recovery) while skin is still damp
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* SPF Reminder */}
          <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg border border-blue-100 mb-4">
            <Shield className="h-5 w-5 text-blue-600 flex-shrink-0" />
            <p className="text-sm text-blue-800">
              <strong>Morning Routine:</strong> Always apply SPF 30+ as the final step. 
              This protocol increases photosensitivity.
            </p>
          </div>
          
          {/* Pro-Tip for High Potency Protocols */}
          {isHighPotencyCombo && (
            <div className="flex items-start gap-3 p-3 bg-gradient-to-r from-purple-50 to-pink-50 rounded-lg border border-purple-200 mb-6">
              <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0">
                <Shield className="h-4 w-4 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-purple-800">
                  <strong className="text-purple-900">Pro-Tip:</strong> Your{' '}
                  <span className="font-semibold">{comboDetails?.total_active_percent || 55}% protocol</span> is potent. 
                  If you're using the Accelerator (Step 1) for the first time, skip every other night 
                  for Week 1 to allow your surface barrier to adapt.
                </p>
              </div>
            </div>
          )}

          {/* 12-Week Transformation Calendar CTA */}
          <div className={`bg-gradient-to-r from-purple-600 to-pink-500 rounded-xl p-5 text-white transform transition-all duration-500 ${
            showCalendarPrompt ? 'scale-100 opacity-100' : 'scale-95 opacity-0'
          }`}>
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
                <Calendar className="h-6 w-6" />
              </div>
              <div className="flex-1">
                <h4 className="font-bold text-lg mb-1">
                  Your 12-Week Transformation Calendar
                </h4>
                <p className="text-purple-100 text-sm mb-3">
                  Track your journey through all 4 phases: Adjustment → Clarity → Structural → Transformation
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button 
                    className="bg-white text-purple-700 hover:bg-purple-50"
                    onClick={() => window.open('/account?tab=transformation-calendar', '_blank')}
                    data-testid="view-calendar-btn"
                  >
                    <Calendar className="h-4 w-4 mr-2" />
                    View My Calendar
                  </Button>
                  <Button 
                    variant="ghost" 
                    className="text-white border border-white/30 hover:bg-white/10"
                    onClick={() => window.open('/api/transformation-calendar/pdf', '_blank')}
                    data-testid="download-calendar-btn"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download PDF
                  </Button>
                </div>
              </div>
            </div>
          </div>
          
          {/* WhatsApp Contact Button - Shows for opted-in customers or first orders */}
          {showWhatsAppButton && (
            <div className={`mt-4 bg-gradient-to-r from-green-500 to-emerald-500 rounded-xl p-5 text-white transform transition-all duration-500 ${
              showWhatsAppPrompt ? 'scale-100 opacity-100' : 'scale-95 opacity-0'
            }`}>
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
                  <MessageCircle className="h-6 w-6" />
                </div>
                <div className="flex-1">
                  <h4 className="font-bold text-lg mb-1">
                    Questions? Message Us on WhatsApp
                  </h4>
                  <p className="text-green-100 text-sm mb-3">
                    Get instant support for your order, skincare tips, or protocol guidance
                  </p>
                  <Button 
                    className="bg-white text-green-700 hover:bg-green-50"
                    onClick={() => window.open(getWhatsAppLink(), '_blank')}
                    data-testid="whatsapp-order-btn"
                  >
                    <MessageCircle className="h-4 w-4 mr-2" />
                    💬 Message Us on WhatsApp
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* What to Expect Timeline */}
      <Card>
        <CardContent className="p-6">
          <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-amber-500" />
            What to Expect
          </h3>
          <div className="space-y-4">
            {[
              { phase: "Week 1-2", title: "Adjustment Phase", desc: "Skin adjusts to actives. Mild tingling normal. Some may experience purging." },
              { phase: "Week 3-4", title: "Clarity Phase", desc: "Texture improves. Pores appear smaller. Tone starts evening out." },
              { phase: "Week 6-8", title: "Structural Phase", desc: "Fine lines soften. Pigmentation fades. Skin density increases." },
              { phase: "Week 10-12", title: "Transformation Phase", desc: "Full results visible. Continued improvement with consistent use." }
            ].map((item, idx) => (
              <div key={idx} className="flex items-start gap-3">
                <div className="w-16 flex-shrink-0">
                  <Badge variant="outline" className="text-xs">
                    {item.phase}
                  </Badge>
                </div>
                <div>
                  <span className="font-medium text-gray-900">{item.title}</span>
                  <p className="text-sm text-gray-600">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PostPurchaseSuccess;
