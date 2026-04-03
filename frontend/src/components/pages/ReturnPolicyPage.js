import React from "react";
import { Helmet } from "react-helmet-async";
import { Link } from "react-router-dom";
import { ArrowLeft, ShieldCheck, Package, AlertCircle, Mail, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const ReturnPolicyPage = () => {
  return (
    <div className="min-h-screen bg-[#FDF9F9] pt-24 pb-16">
      <Helmet>
        <title>Return Policy | ReRoots Skincare</title>
        <meta name="description" content="ReRoots return policy for defective products. Learn about our quality guarantee and return process." />
        <link rel="canonical" href="https://www.reroots.ca/return-policy" />
      </Helmet>
      
      <div className="max-w-4xl mx-auto px-6 md:px-12">
        {/* Back Button */}
        <Link to="/">
          <Button variant="ghost" className="mb-8 text-[#5A5A5A] hover:text-[#2D2A2E]">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Button>
        </Link>
        
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="font-luxury text-4xl md:text-5xl font-medium text-[#2D2A2E] mb-4">
            Return Policy
          </h1>
          <p className="text-[#5A5A5A] text-lg">
            Our commitment to quality and your satisfaction
          </p>
          <p className="text-sm text-[#888] mt-2">
            Last updated: January 12, 2025
          </p>
        </div>
        
        {/* Quick Summary Cards */}
        <div className="grid md:grid-cols-3 gap-4 mb-12">
          <Card className="border-green-200 bg-green-50">
            <CardContent className="p-6 text-center">
              <ShieldCheck className="w-8 h-8 text-green-600 mx-auto mb-3" />
              <h3 className="font-semibold text-green-800">Defective Products</h3>
              <p className="text-sm text-green-700 mt-1">Full refund guaranteed</p>
            </CardContent>
          </Card>
          
          <Card className="border-amber-200 bg-amber-50">
            <CardContent className="p-6 text-center">
              <Clock className="w-8 h-8 text-amber-600 mx-auto mb-3" />
              <h3 className="font-semibold text-amber-800">30-Day Window</h3>
              <p className="text-sm text-amber-700 mt-1">From delivery date</p>
            </CardContent>
          </Card>
          
          <Card className="border-red-200 bg-red-50">
            <CardContent className="p-6 text-center">
              <AlertCircle className="w-8 h-8 text-red-600 mx-auto mb-3" />
              <h3 className="font-semibold text-red-800">No Exchanges</h3>
              <p className="text-sm text-red-700 mt-1">Refunds only</p>
            </CardContent>
          </Card>
        </div>
        
        {/* Policy Content */}
        <div className="prose prose-lg max-w-none">
          <Card className="mb-8">
            <CardContent className="p-8">
              <h2 className="text-2xl font-luxury font-medium text-[#2D2A2E] mb-4 flex items-center gap-3">
                <Package className="w-6 h-6 text-[#D4AF37]" />
                Defective Product Returns
              </h2>
              
              <p className="text-[#5A5A5A] mb-4">
                At ReRoots, we take pride in the quality of our biotech skincare products. If you receive a defective product, we will provide a <strong>full refund</strong> within 30 days of delivery.
              </p>
              
              <h3 className="text-lg font-semibold text-[#2D2A2E] mt-6 mb-3">What qualifies as defective?</h3>
              <ul className="list-disc pl-6 text-[#5A5A5A] space-y-2">
                <li>Damaged or broken packaging upon arrival</li>
                <li>Product seal broken or tampered with</li>
                <li>Product leakage or contamination</li>
                <li>Incorrect product received</li>
                <li>Product expired before the stated date</li>
                <li>Visible manufacturing defects</li>
              </ul>
              
              <h3 className="text-lg font-semibold text-[#2D2A2E] mt-6 mb-3">How to request a return</h3>
              <ol className="list-decimal pl-6 text-[#5A5A5A] space-y-2">
                <li>Contact us at <a href="mailto:support@reroots.ca" className="text-[#D4AF37] hover:underline">support@reroots.ca</a> within 30 days of receiving your order</li>
                <li>Include your order number and a description of the defect</li>
                <li>Attach clear photos showing the defect</li>
                <li>Our team will review your request within 2-3 business days</li>
                <li>If approved, you'll receive a prepaid return shipping label</li>
                <li>Once we receive the returned item, your refund will be processed within 5-7 business days</li>
              </ol>
            </CardContent>
          </Card>
          
          <Card className="mb-8">
            <CardContent className="p-8">
              <h2 className="text-2xl font-luxury font-medium text-[#2D2A2E] mb-4 flex items-center gap-3">
                <AlertCircle className="w-6 h-6 text-red-500" />
                No Exchange Policy
              </h2>
              
              <p className="text-[#5A5A5A] mb-4">
                Please note that we do <strong>not offer exchanges</strong> on any products. If you wish to try a different product, please request a refund for the defective item and place a new order.
              </p>
              
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mt-4">
                <p className="text-amber-800 text-sm">
                  <strong>Why no exchanges?</strong> Our products are made in small batches to ensure freshness and potency. This policy allows us to maintain the highest quality standards for every customer.
                </p>
              </div>
            </CardContent>
          </Card>
          
          <Card className="mb-8">
            <CardContent className="p-8">
              <h2 className="text-2xl font-luxury font-medium text-[#2D2A2E] mb-4">
                Non-Returnable Items
              </h2>
              
              <p className="text-[#5A5A5A] mb-4">
                The following items cannot be returned:
              </p>
              
              <ul className="list-disc pl-6 text-[#5A5A5A] space-y-2">
                <li>Products that have been opened or used (unless defective)</li>
                <li>Products returned after the 30-day window</li>
                <li>Products purchased during final sale promotions</li>
                <li>Gift cards</li>
                <li>Free samples or promotional items</li>
              </ul>
            </CardContent>
          </Card>
          
          <Card className="mb-8">
            <CardContent className="p-8">
              <h2 className="text-2xl font-luxury font-medium text-[#2D2A2E] mb-4">
                Refund Processing
              </h2>
              
              <p className="text-[#5A5A5A] mb-4">
                Refunds will be issued to the original payment method:
              </p>
              
              <ul className="list-disc pl-6 text-[#5A5A5A] space-y-2">
                <li><strong>Credit/Debit Cards:</strong> 5-7 business days after we receive the returned item</li>
                <li><strong>PayPal:</strong> 3-5 business days</li>
                <li><strong>Other payment methods:</strong> Up to 10 business days</li>
              </ul>
              
              <p className="text-[#5A5A5A] mt-4">
                Original shipping costs are non-refundable unless the return is due to our error or a defective product.
              </p>
            </CardContent>
          </Card>
          
          {/* Contact Section */}
          <Card className="bg-[#2D2A2E] text-white">
            <CardContent className="p-8 text-center">
              <Mail className="w-10 h-10 text-[#D4AF37] mx-auto mb-4" />
              <h2 className="text-2xl font-luxury font-medium mb-2">
                Need Help?
              </h2>
              <p className="text-white/70 mb-4">
                Our customer support team is here to assist you with any return-related questions.
              </p>
              <a 
                href="mailto:support@reroots.ca"
                className="inline-block bg-[#D4AF37] text-[#2D2A2E] px-8 py-3 rounded-full font-semibold hover:bg-[#B8960F] transition-colors"
              >
                Contact Support
              </a>
              <p className="text-white/50 text-sm mt-4">
                support@reroots.ca • Response within 24 hours
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
      
      <style>{`
        .font-luxury { font-family: 'Playfair Display', Georgia, serif; }
      `}</style>
    </div>
  );
};

export default ReturnPolicyPage;
