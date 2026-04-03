import React, { useState, useEffect } from "react";
import axios from "axios";
import { Loader2, Globe, Truck, Clock, ChevronDown, ChevronUp, Package, Shield, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// API URL - same logic as main App.js
const getBackendUrl = () => {
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    return window.location.origin;
  }
  return window.location.origin;
};
const API = `${getBackendUrl()}/api`;

const GlobalShippingPolicyPage = () => {
  const [policy, setPolicy] = useState(null);
  const [shippingInfo, setShippingInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedRegion, setExpandedRegion] = useState(null);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/shipping-policy`),
      axios.get(`${API}/international-shipping-info`)
    ])
      .then(([policyRes, shippingRes]) => {
        setPolicy(policyRes.data);
        setShippingInfo(shippingRes.data);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  const regions = shippingInfo?.regions || [
    { code: "NA", name: "North America", countries: ["Canada", "United States", "Mexico"], delivery: "3-7 days", shipping: "Free over $75" },
    { code: "EU", name: "Europe", countries: ["UK", "France", "Germany", "Italy", "Spain"], delivery: "7-14 days", shipping: "Flat $15" },
    { code: "ASIA", name: "Asia Pacific", countries: ["Japan", "South Korea", "Australia", "Singapore"], delivery: "10-21 days", shipping: "Flat $20" },
    { code: "OTHER", name: "Rest of World", countries: ["UAE", "India", "Brazil"], delivery: "14-30 days", shipping: "Calculated at checkout" }
  ];

  return (
    <div className="min-h-screen bg-[#FAF8F5]">
      {/* Hero */}
      <section className="bg-gradient-to-r from-[#2D2A2E] to-[#1a1819] py-16">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <div className="inline-flex items-center gap-2 bg-white/10 px-4 py-2 rounded-full mb-6">
            <Globe className="h-4 w-4 text-[#F8A5B8]" />
            <span className="text-white text-sm">Global Delivery</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
            {policy?.title || "Shipping & Returns Policy"}
          </h1>
          <p className="text-gray-300 text-lg max-w-2xl mx-auto">
            {policy?.subtitle || "We ship worldwide with care. Learn about our delivery times, shipping costs, and hassle-free returns."}
          </p>
        </div>
      </section>

      {/* Shipping Highlights */}
      <section className="py-12 border-b">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-6">
            <div className="text-center p-6 bg-white rounded-xl shadow-sm">
              <Truck className="h-8 w-8 text-[#F8A5B8] mx-auto mb-3" />
              <h3 className="font-bold text-[#2D2A2E]">{shippingInfo?.free_shipping_threshold ? `Free Over $${shippingInfo.free_shipping_threshold}` : "Free Over $75"}</h3>
              <p className="text-sm text-[#5A5A5A]">Canada & USA</p>
            </div>
            <div className="text-center p-6 bg-white rounded-xl shadow-sm">
              <Clock className="h-8 w-8 text-[#F8A5B8] mx-auto mb-3" />
              <h3 className="font-bold text-[#2D2A2E]">{shippingInfo?.processing_time || "1-2 Business Days"}</h3>
              <p className="text-sm text-[#5A5A5A]">Processing Time</p>
            </div>
            <div className="text-center p-6 bg-white rounded-xl shadow-sm">
              <Package className="h-8 w-8 text-[#F8A5B8] mx-auto mb-3" />
              <h3 className="font-bold text-[#2D2A2E]">{shippingInfo?.tracking ? "Real-time Tracking" : "Order Tracking"}</h3>
              <p className="text-sm text-[#5A5A5A]">On All Orders</p>
            </div>
            <div className="text-center p-6 bg-white rounded-xl shadow-sm">
              <Shield className="h-8 w-8 text-[#F8A5B8] mx-auto mb-3" />
              <h3 className="font-bold text-[#2D2A2E]">{policy?.return_period || 30}-Day Returns</h3>
              <p className="text-sm text-[#5A5A5A]">Easy & Free</p>
            </div>
          </div>
        </div>
      </section>

      {/* International Shipping */}
      <section className="py-16">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-[#2D2A2E] mb-8 text-center">
            <Globe className="inline-block h-6 w-6 mr-2 text-[#F8A5B8]" />
            International Shipping Zones
          </h2>
          
          <div className="space-y-4">
            {regions.map((region, idx) => (
              <Card key={idx} className="overflow-hidden">
                <CardHeader 
                  className="cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => setExpandedRegion(expandedRegion === region.code ? null : region.code)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-[#F8A5B8]/20 rounded-full flex items-center justify-center">
                        <MapPin className="h-6 w-6 text-[#F8A5B8]" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">{region.name}</CardTitle>
                        <p className="text-sm text-[#5A5A5A]">{region.countries.slice(0, 3).join(", ")}{region.countries.length > 3 ? ` +${region.countries.length - 3} more` : ""}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">{region.delivery}</Badge>
                        <p className="text-sm text-[#5A5A5A] mt-1">{region.shipping}</p>
                      </div>
                      {expandedRegion === region.code ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                    </div>
                  </div>
                </CardHeader>
                {expandedRegion === region.code && (
                  <CardContent className="bg-gray-50 border-t">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 py-4">
                      {region.countries.map((country, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm text-[#5A5A5A]">
                          <span className="w-2 h-2 rounded-full bg-[#F8A5B8]"></span>
                          {country}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Returns Policy */}
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-[#2D2A2E] mb-8 text-center">Returns & Refunds</h2>
          
          <div className="prose prose-lg max-w-none">
            <div className="bg-[#FDF9F9] rounded-xl p-8 mb-8">
              <h3 className="text-xl font-bold text-[#2D2A2E] mb-4">Our Promise</h3>
              <p className="text-[#5A5A5A]">
                {policy?.return_policy || "We stand behind our products. If you're not completely satisfied with your purchase, you may return unopened items within 30 days for a full refund. Opened products may be eligible for exchange or store credit."}
              </p>
            </div>
            
            <div className="grid md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg text-green-600">✓ Eligible for Return</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm text-[#5A5A5A]">
                    <li>• Unopened, sealed products</li>
                    <li>• Items in original packaging</li>
                    <li>• Within {policy?.return_period || 30} days of delivery</li>
                    <li>• Defective or damaged items</li>
                  </ul>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg text-red-600">✗ Non-Returnable</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm text-[#5A5A5A]">
                    <li>• Opened skincare products (hygiene)</li>
                    <li>• Items marked "Final Sale"</li>
                    <li>• Gift cards</li>
                    <li>• Items beyond return window</li>
                  </ul>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </section>

      {/* Contact */}
      <section className="py-16 bg-gradient-to-r from-[#F8A5B8]/20 to-[#FDF9F9]">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <h2 className="text-2xl font-bold text-[#2D2A2E] mb-4">Need Help?</h2>
          <p className="text-[#5A5A5A] mb-6">Our customer service team is here to assist you with any shipping or return questions.</p>
          <Button className="bg-[#2D2A2E] hover:bg-[#1a1819] text-white">
            Contact Support
          </Button>
        </div>
      </section>
    </div>
  );
};

export default GlobalShippingPolicyPage;
