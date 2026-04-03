import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, FileText, ShoppingCart, CreditCard, Truck, RotateCcw, AlertTriangle, Scale } from 'lucide-react';

const TermsOfServicePage = () => {
  return (
    <div className="min-h-screen bg-[#FDF9F9]">
      {/* Header */}
      <div className="bg-gradient-to-r from-[#2D2A2E] to-[#1a1819] text-white py-16">
        <div className="max-w-4xl mx-auto px-4">
          <Link to="/" className="inline-flex items-center text-[#F8A5B8] hover:text-white mb-6 transition-colors">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Home
          </Link>
          <div className="flex items-center gap-4 mb-4">
            <div className="p-3 bg-[#F8A5B8]/20 rounded-xl">
              <FileText className="w-8 h-8 text-[#F8A5B8]" />
            </div>
            <h1 className="text-4xl font-bold">Terms of Service</h1>
          </div>
          <p className="text-white/70">Last updated: February 2026</p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="prose prose-lg max-w-none">
          
          {/* Introduction */}
          <section className="mb-12">
            <p className="text-lg text-[#5A5A5A] leading-relaxed">
              Welcome to ReRoots Biotech Skincare. These Terms of Service ("Terms") govern your use of our website 
              reroots.ca and the purchase of products from our online store. By accessing our website or placing 
              an order, you agree to be bound by these Terms. Please read them carefully.
            </p>
          </section>

          {/* Section 1 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">1. Acceptance of Terms</h2>
            <div className="text-[#5A5A5A]">
              <p>By using this website, you confirm that:</p>
              <ul className="list-disc pl-6 mt-4 space-y-2">
                <li>You are at least 16 years of age</li>
                <li>You have the legal capacity to enter into a binding agreement</li>
                <li>You will use the website in compliance with these Terms and all applicable laws</li>
                <li>All information you provide is accurate and complete</li>
              </ul>
            </div>
          </section>

          {/* Section 2 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <ShoppingCart className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">2. Products and Orders</h2>
            </div>
            <div className="text-[#5A5A5A] space-y-4">
              <div>
                <h3 className="font-semibold text-[#2D2A2E] mb-2">Product Information</h3>
                <ul className="list-disc pl-6 space-y-2">
                  <li>We strive to display product colors and images accurately, but cannot guarantee exact representation on all devices</li>
                  <li>Product descriptions are for informational purposes and do not constitute medical advice</li>
                  <li>All products are cosmetic in nature and are not intended to diagnose, treat, cure, or prevent any disease</li>
                </ul>
              </div>
              <div>
                <h3 className="font-semibold text-[#2D2A2E] mb-2">Order Acceptance</h3>
                <ul className="list-disc pl-6 space-y-2">
                  <li>All orders are subject to acceptance and availability</li>
                  <li>We reserve the right to refuse or cancel any order for any reason</li>
                  <li>Prices are subject to change without notice</li>
                  <li>We are not responsible for typographical errors in pricing</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Section 3 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <CreditCard className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">3. Payment Terms</h2>
            </div>
            <div className="text-[#5A5A5A]">
              <ul className="list-disc pl-6 space-y-2">
                <li>All prices are displayed in the currency selected (CAD, USD, or other supported currencies)</li>
                <li>Payment is required at the time of purchase</li>
                <li>We accept major credit cards, debit cards, and other payment methods as displayed at checkout</li>
                <li>All payments are processed securely through our PCI-compliant payment processors</li>
                <li>You agree to provide accurate and complete payment information</li>
                <li>Additional duties, taxes, or customs fees may apply for international orders</li>
              </ul>
            </div>
          </section>

          {/* Section 4 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <Truck className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">4. Shipping and Delivery</h2>
            </div>
            <div className="text-[#5A5A5A]">
              <ul className="list-disc pl-6 space-y-2">
                <li>Shipping times are estimates and not guaranteed</li>
                <li>Risk of loss and title for products pass to you upon delivery to the carrier</li>
                <li>We are not responsible for delays caused by customs, weather, or carrier issues</li>
                <li>It is your responsibility to provide accurate shipping information</li>
                <li>For detailed shipping information, please see our <Link to="/shipping-policy" className="text-[#F8A5B8] hover:underline">Shipping Policy</Link></li>
              </ul>
            </div>
          </section>

          {/* Section 5 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <RotateCcw className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">5. Returns and Refunds</h2>
            </div>
            <div className="text-[#5A5A5A]">
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Unopened Products:</strong> May be returned within 30 days of delivery for a full refund</li>
                <li><strong>Opened Products:</strong> Due to hygiene and safety regulations, opened skincare products cannot be returned</li>
                <li><strong>Damaged Items:</strong> Contact us within 48 hours of delivery for damaged or defective products</li>
                <li>Refunds will be processed to the original payment method within 5-10 business days</li>
                <li>Shipping costs are non-refundable unless the return is due to our error</li>
                <li>For complete details, see our <Link to="/return-policy" className="text-[#F8A5B8] hover:underline">Return Policy</Link></li>
              </ul>
            </div>
          </section>

          {/* Section 6 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">6. Intellectual Property</h2>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">All content on this website is the property of ReRoots Biotech Skincare and is protected by copyright and trademark laws:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>You may not copy, reproduce, or distribute any content without written permission</li>
                <li>The ReRoots name, logo, and brand elements are trademarks of ReRoots</li>
                <li>Product images and descriptions may not be used for commercial purposes</li>
                <li>User-generated content (reviews, photos) grants us a license to use such content</li>
              </ul>
            </div>
          </section>

          {/* Section 7 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">7. User Accounts</h2>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">If you create an account with us:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>You are responsible for maintaining the confidentiality of your account credentials</li>
                <li>You are responsible for all activities that occur under your account</li>
                <li>You must notify us immediately of any unauthorized use</li>
                <li>We reserve the right to terminate accounts that violate these Terms</li>
                <li>You may delete your account at any time by contacting us</li>
              </ul>
            </div>
          </section>

          {/* Section 8 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">8. Prohibited Activities</h2>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">You agree not to:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Use the website for any unlawful purpose</li>
                <li>Attempt to gain unauthorized access to our systems</li>
                <li>Interfere with the proper functioning of the website</li>
                <li>Submit false or misleading information</li>
                <li>Engage in fraudulent transactions</li>
                <li>Resell products without authorization</li>
                <li>Scrape or collect data from our website without permission</li>
              </ul>
            </div>
          </section>

          {/* Section 9 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">9. Disclaimers</h2>
            </div>
            <div className="text-[#5A5A5A]">
              <ul className="list-disc pl-6 space-y-2">
                <li>Our products are cosmetic in nature and are not drugs or medical devices</li>
                <li>Results may vary from person to person</li>
                <li>We do not claim to diagnose, treat, cure, or prevent any disease</li>
                <li>Consult a healthcare professional before using if you have sensitive skin or medical conditions</li>
                <li>The website is provided "as is" without warranties of any kind</li>
                <li>We do not guarantee uninterrupted or error-free website operation</li>
              </ul>
            </div>
          </section>

          {/* Section 10 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <Scale className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">10. Limitation of Liability</h2>
            </div>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">To the fullest extent permitted by law:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>ReRoots shall not be liable for any indirect, incidental, special, or consequential damages</li>
                <li>Our total liability shall not exceed the amount you paid for the product(s) in question</li>
                <li>We are not liable for any harm resulting from your use of our products contrary to instructions</li>
                <li>Some jurisdictions do not allow limitations of liability, so these may not apply to you</li>
              </ul>
            </div>
          </section>

          {/* Section 11 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">11. Governing Law</h2>
            <div className="text-[#5A5A5A]">
              <p>These Terms shall be governed by and construed in accordance with the laws of the Province of Ontario and the federal laws of Canada applicable therein, without regard to conflict of law principles. Any disputes arising from these Terms shall be resolved in the courts of Ontario, Canada.</p>
            </div>
          </section>

          {/* Section 12 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">12. Changes to Terms</h2>
            <div className="text-[#5A5A5A]">
              <p>We reserve the right to modify these Terms at any time. Changes will be effective immediately upon posting to the website. Your continued use of the website after changes are posted constitutes acceptance of the modified Terms. We encourage you to review these Terms periodically.</p>
            </div>
          </section>

          {/* Contact */}
          <section className="mb-10 p-6 bg-gradient-to-r from-[#F8A5B8]/10 to-[#E88DA0]/10 rounded-xl border border-[#F8A5B8]/30">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">13. Contact Information</h2>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">If you have any questions about these Terms of Service, please contact us:</p>
              <div className="space-y-2">
                <p><strong>Email:</strong> <a href="mailto:legal@reroots.ca" className="text-[#F8A5B8] hover:underline">legal@reroots.ca</a></p>
                <p><strong>General Support:</strong> <a href="mailto:support@reroots.ca" className="text-[#F8A5B8] hover:underline">support@reroots.ca</a></p>
                <p><strong>Address:</strong> ReRoots Biotech Skincare, Toronto, Ontario, Canada</p>
              </div>
            </div>
          </section>

          {/* Agreement */}
          <section className="text-center py-8 border-t border-[#F8A5B8]/20">
            <p className="text-[#5A5A5A]">
              By using our website or making a purchase, you acknowledge that you have read, understood, and agree to be bound by these Terms of Service.
            </p>
          </section>

        </div>
      </div>
    </div>
  );
};

export default TermsOfServicePage;
