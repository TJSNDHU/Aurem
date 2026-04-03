import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Shield, Lock, Eye, Database, Mail, Globe } from 'lucide-react';

const PrivacyPolicyPage = () => {
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
              <Shield className="w-8 h-8 text-[#F8A5B8]" />
            </div>
            <h1 className="text-4xl font-bold">Privacy Policy</h1>
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
              At ReRoots Biotech Skincare ("ReRoots," "we," "us," or "our"), we are committed to protecting your privacy 
              and ensuring the security of your personal information. This Privacy Policy explains how we collect, use, 
              disclose, and safeguard your information when you visit our website reroots.ca and use our services.
            </p>
          </section>

          {/* Section 1 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <Database className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">1. Information We Collect</h2>
            </div>
            <div className="space-y-4 text-[#5A5A5A]">
              <div>
                <h3 className="font-semibold text-[#2D2A2E] mb-2">Personal Information</h3>
                <p>When you make a purchase, create an account, or contact us, we may collect:</p>
                <ul className="list-disc pl-6 mt-2 space-y-1">
                  <li>Name and contact information (email address, phone number, shipping address)</li>
                  <li>Payment information (processed securely through our payment providers)</li>
                  <li>Account credentials (email and encrypted password)</li>
                  <li>Order history and preferences</li>
                  <li>Skin quiz responses and skincare preferences</li>
                </ul>
              </div>
              <div>
                <h3 className="font-semibold text-[#2D2A2E] mb-2">Automatically Collected Information</h3>
                <p>When you visit our website, we automatically collect:</p>
                <ul className="list-disc pl-6 mt-2 space-y-1">
                  <li>Device information (browser type, operating system)</li>
                  <li>IP address and general location</li>
                  <li>Pages visited and time spent on our site</li>
                  <li>Referring website or source</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Section 2 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <Eye className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">2. How We Use Your Information</h2>
            </div>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">We use the information we collect to:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Process and fulfill your orders</li>
                <li>Communicate with you about your orders, products, and promotions</li>
                <li>Personalize your shopping experience and product recommendations</li>
                <li>Improve our website, products, and services</li>
                <li>Prevent fraud and maintain security</li>
                <li>Comply with legal obligations</li>
                <li>Send marketing communications (with your consent)</li>
              </ul>
            </div>
          </section>

          {/* Section 3 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <Globe className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">3. Information Sharing</h2>
            </div>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">We do not sell your personal information. We may share your information with:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Service Providers:</strong> Third parties who help us operate our business (payment processors, shipping carriers, email service providers)</li>
                <li><strong>Legal Requirements:</strong> When required by law or to protect our rights</li>
                <li><strong>Business Transfers:</strong> In connection with a merger, acquisition, or sale of assets</li>
              </ul>
            </div>
          </section>

          {/* Section 4 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <div className="flex items-center gap-3 mb-4">
              <Lock className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">4. Data Security</h2>
            </div>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">We implement appropriate security measures to protect your information:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>SSL encryption for all data transmission</li>
                <li>Secure payment processing through PCI-compliant providers</li>
                <li>Regular security audits and updates</li>
                <li>Limited employee access to personal information</li>
                <li>Secure data storage with industry-standard encryption</li>
              </ul>
            </div>
          </section>

          {/* Section 5 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">5. Your Rights and Choices</h2>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">You have the right to:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Access:</strong> Request a copy of your personal information</li>
                <li><strong>Correction:</strong> Update or correct inaccurate information</li>
                <li><strong>Deletion:</strong> Request deletion of your personal information</li>
                <li><strong>Opt-out:</strong> Unsubscribe from marketing communications at any time</li>
                <li><strong>Data Portability:</strong> Request your data in a portable format</li>
              </ul>
              <p className="mt-4">To exercise these rights, please contact us at <a href="mailto:privacy@reroots.ca" className="text-[#F8A5B8] hover:underline">privacy@reroots.ca</a></p>
            </div>
          </section>

          {/* Section 6 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">6. Cookies and Tracking</h2>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">We use cookies and similar technologies to:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Remember your preferences and cart items</li>
                <li>Analyze website traffic and usage patterns</li>
                <li>Personalize your experience</li>
                <li>Measure advertising effectiveness</li>
              </ul>
              <p className="mt-4">You can manage cookie preferences through your browser settings.</p>
            </div>
          </section>

          {/* Section 7 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">7. Children's Privacy</h2>
            <div className="text-[#5A5A5A]">
              <p>Our website is not intended for children under 16 years of age. We do not knowingly collect personal information from children. If you believe we have collected information from a child, please contact us immediately.</p>
            </div>
          </section>

          {/* Section 8 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">8. International Transfers</h2>
            <div className="text-[#5A5A5A]">
              <p>ReRoots is based in Canada. If you are accessing our website from outside Canada, please be aware that your information may be transferred to, stored, and processed in Canada where our servers are located and our central database is operated.</p>
            </div>
          </section>

          {/* Section 9 */}
          <section className="mb-10 p-6 bg-white rounded-xl border border-[#F8A5B8]/20">
            <h2 className="text-xl font-bold text-[#2D2A2E] mb-4">9. Changes to This Policy</h2>
            <div className="text-[#5A5A5A]">
              <p>We may update this Privacy Policy from time to time. We will notify you of any material changes by posting the new policy on this page and updating the "Last updated" date. We encourage you to review this policy periodically.</p>
            </div>
          </section>

          {/* Contact */}
          <section className="mb-10 p-6 bg-gradient-to-r from-[#F8A5B8]/10 to-[#E88DA0]/10 rounded-xl border border-[#F8A5B8]/30">
            <div className="flex items-center gap-3 mb-4">
              <Mail className="w-6 h-6 text-[#F8A5B8]" />
              <h2 className="text-xl font-bold text-[#2D2A2E] m-0">10. Contact Us</h2>
            </div>
            <div className="text-[#5A5A5A]">
              <p className="mb-4">If you have any questions about this Privacy Policy or our privacy practices, please contact us:</p>
              <div className="space-y-2">
                <p><strong>Email:</strong> <a href="mailto:privacy@reroots.ca" className="text-[#F8A5B8] hover:underline">privacy@reroots.ca</a></p>
                <p><strong>General Support:</strong> <a href="mailto:support@reroots.ca" className="text-[#F8A5B8] hover:underline">support@reroots.ca</a></p>
                <p><strong>Address:</strong> ReRoots Biotech Skincare, Toronto, Ontario, Canada</p>
              </div>
            </div>
          </section>

        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicyPage;
