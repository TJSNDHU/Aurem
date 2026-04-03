import React, { useState, Suspense, lazy } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Mail, MapPin, Clock, Send, Check, Loader2, Instagram, Facebook, Bot } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

// Dynamic API URL for custom domains
const getBackendUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname.includes('localhost') || hostname.includes('127.0.0.1')) {
      return 'http://localhost:8001';
    }
    if (!hostname.includes('preview.emergentagent.com') && !hostname.includes('emergent.host')) {
      return window.location.origin;
    }
    if (process.env.REACT_APP_BACKEND_URL) {
      return process.env.REACT_APP_BACKEND_URL;
    }
    return window.location.origin;
  }
  return process.env.REACT_APP_BACKEND_URL || '';
};

const API = getBackendUrl();

// Lazy load VoiceAIChat
const VoiceAIChatLazy = lazy(() => import('../VoiceAIChat'));
const AnimatePresence = lazy(() => import('framer-motion').then(mod => ({ default: mod.AnimatePresence })));

const ContactPage = () => {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    subject: "",
    message: ""
  });
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [showVoiceChat, setShowVoiceChat] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSending(true);
    
    try {
      // Save contact message to database
      await axios.post(`${API}/api/contact`, formData);
      setSent(true);
      toast.success("Message sent! We'll get back to you soon.");
      setFormData({ name: "", email: "", phone: "", subject: "", message: "" });
    } catch (error) {
      toast.error("Failed to send message. Please try again.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="min-h-screen pt-24 bg-[#FDF9F9]">
      {/* Voice AI Chat Modal */}
      <Suspense fallback={null}>
        <AnimatePresence>
          {showVoiceChat && <VoiceAIChatLazy onClose={() => setShowVoiceChat(false)} />}
        </AnimatePresence>
      </Suspense>

      {/* Hero */}
      <section className="py-16 bg-[#2D2A2E] text-white">
        <div className="max-w-4xl mx-auto px-6 md:px-12 text-center">
          <Badge className="bg-[#F8A5B8]/20 text-[#F8A5B8] mb-4">GET IN TOUCH</Badge>
          <h1 className="font-display text-4xl md:text-5xl font-bold mb-6">Contact Us</h1>
          <p className="text-xl text-white/70">
            We&apos;d love to hear from you. Reach out with any questions or feedback.
          </p>
        </div>
      </section>

      {/* Contact Form & Info */}
      <section className="py-24">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
            {/* Contact Info */}
            <div className="space-y-8">
              <div>
                <h2 className="font-display text-3xl font-bold text-[#2D2A2E] mb-6">Let&apos;s Connect</h2>
                <p className="text-[#5A5A5A] text-lg">
                  Have a question about our products? Need help with an order? We&apos;re here to help!
                </p>
              </div>

              <div className="space-y-6">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-[#F8A5B8]/20 rounded-full flex items-center justify-center flex-shrink-0">
                    <Mail className="h-5 w-5 text-[#F8A5B8]" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[#2D2A2E] mb-1">Email</h3>
                    <a href="mailto:support@reroots.ca" className="text-[#5A5A5A] hover:text-[#F8A5B8] transition-colors">
                      support@reroots.ca
                    </a>
                  </div>
                </div>

                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-[#F8A5B8]/20 rounded-full flex items-center justify-center flex-shrink-0">
                    <Bot className="h-5 w-5 text-[#F8A5B8]" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[#2D2A2E] mb-1">AI Voice Support</h3>
                    <p className="text-[#5A5A5A] text-sm mb-2">
                      24/7 AI-powered voice assistance
                    </p>
                    <Button
                      onClick={() => setShowVoiceChat(true)}
                      className="bg-[#F8A5B8] hover:bg-[#E991A5] text-white"
                    >
                      <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1 1.93c-3.94-.49-7-3.85-7-7.93h2c0 3.31 2.69 6 6 6s6-2.69 6-6h2c0 4.08-3.06 7.44-7 7.93V20h4v2H8v-2h4v-4.07z"/>
                      </svg>
                      Talk to AI Support
                    </Button>
                  </div>
                </div>

                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-[#F8A5B8]/20 rounded-full flex items-center justify-center flex-shrink-0">
                    <MapPin className="h-5 w-5 text-[#F8A5B8]" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[#2D2A2E] mb-1">Location</h3>
                    <p className="text-[#5A5A5A]">
                      Toronto, Ontario<br />
                      Canada
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-[#F8A5B8]/20 rounded-full flex items-center justify-center flex-shrink-0">
                    <Clock className="h-5 w-5 text-[#F8A5B8]" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[#2D2A2E] mb-1">Business Hours</h3>
                    <p className="text-[#5A5A5A]">
                      Monday - Friday: 9am - 6pm EST<br />
                      Saturday: 10am - 4pm EST<br />
                      Sunday: Closed
                    </p>
                  </div>
                </div>
              </div>

              {/* Social Links */}
              <div>
                <h3 className="font-semibold text-[#2D2A2E] mb-4">Follow Us</h3>
                <div className="flex gap-4">
                  <a href="https://instagram.com/reroots.ca" target="_blank" rel="noopener noreferrer" 
                     className="w-10 h-10 bg-[#2D2A2E] rounded-full flex items-center justify-center hover:bg-[#F8A5B8] transition-colors">
                    <Instagram className="h-5 w-5 text-white" />
                  </a>
                  <a href="https://facebook.com" target="_blank" rel="noopener noreferrer"
                     className="w-10 h-10 bg-[#2D2A2E] rounded-full flex items-center justify-center hover:bg-[#F8A5B8] transition-colors">
                    <Facebook className="h-5 w-5 text-white" />
                  </a>
                </div>
              </div>
            </div>

            {/* Contact Form */}
            <Card className="shadow-xl border-0">
              <CardHeader>
                <CardTitle className="text-2xl text-[#2D2A2E]">Send us a Message</CardTitle>
                <CardDescription>Fill out the form below and we&apos;ll get back to you within 24 hours.</CardDescription>
              </CardHeader>
              <CardContent>
                {sent ? (
                  <div className="text-center py-8">
                    <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                      <Check className="h-8 w-8 text-green-600" />
                    </div>
                    <h3 className="text-xl font-semibold text-[#2D2A2E] mb-2">Message Sent!</h3>
                    <p className="text-[#5A5A5A] mb-4">Thank you for reaching out. We&apos;ll respond shortly.</p>
                    <Button onClick={() => setSent(false)} variant="outline">Send Another Message</Button>
                  </div>
                ) : (
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="name">Name *</Label>
                        <Input 
                          id="name"
                          required
                          value={formData.name}
                          onChange={(e) => setFormData({...formData, name: e.target.value})}
                          placeholder="Your name"
                        />
                      </div>
                      <div>
                        <Label htmlFor="email">Email *</Label>
                        <Input 
                          id="email"
                          type="email"
                          required
                          value={formData.email}
                          onChange={(e) => setFormData({...formData, email: e.target.value})}
                          placeholder="your@email.com"
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="phone">Phone</Label>
                        <Input 
                          id="phone"
                          value={formData.phone}
                          onChange={(e) => setFormData({...formData, phone: e.target.value})}
                          placeholder="+1 (xxx) xxx-xxxx"
                        />
                      </div>
                      <div>
                        <Label htmlFor="subject">Subject *</Label>
                        <Select value={formData.subject} onValueChange={(v) => setFormData({...formData, subject: v})}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select a topic" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="product">Product Question</SelectItem>
                            <SelectItem value="order">Order Inquiry</SelectItem>
                            <SelectItem value="shipping">Shipping &amp; Delivery</SelectItem>
                            <SelectItem value="returns">Returns &amp; Refunds</SelectItem>
                            <SelectItem value="feedback">Feedback</SelectItem>
                            <SelectItem value="partnership">Business Partnership</SelectItem>
                            <SelectItem value="other">Other</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div>
                      <Label htmlFor="message">Message *</Label>
                      <Textarea 
                        id="message"
                        required
                        rows={5}
                        value={formData.message}
                        onChange={(e) => setFormData({...formData, message: e.target.value})}
                        placeholder="How can we help you?"
                      />
                    </div>
                    <Button 
                      type="submit" 
                      className="w-full bg-[#F8A5B8] text-[#2D2A2E] hover:bg-[#2D2A2E] hover:text-white"
                      disabled={sending}
                    >
                      {sending ? (
                        <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Sending...</>
                      ) : (
                        <><Send className="h-4 w-4 mr-2" /> Send Message</>
                      )}
                    </Button>
                  </form>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-24 bg-white">
        <div className="max-w-4xl mx-auto px-6 md:px-12">
          <h2 className="font-display text-3xl font-bold text-[#2D2A2E] text-center mb-12">Frequently Asked Questions</h2>
          <div className="space-y-4">
            {[
              { q: "What is your return policy?", a: "We offer a 30-day money-back guarantee on all products. If you're not satisfied, simply contact us for a full refund." },
              { q: "How long does shipping take?", a: "Standard shipping within Canada takes 5-7 business days. Express shipping (2-3 days) is available at checkout." },
              { q: "Are your products cruelty-free?", a: "Yes! All ReRoots products are 100% cruelty-free and never tested on animals." },
              { q: "Can I track my order?", a: "Yes, you'll receive a tracking number via email once your order ships." }
            ].map((faq, i) => (
              <div key={i} className="border border-gray-100 rounded-lg p-6 hover:border-[#F8A5B8] transition-colors">
                <h3 className="font-semibold text-[#2D2A2E] mb-2">{faq.q}</h3>
                <p className="text-[#5A5A5A]">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};

export default ContactPage;
