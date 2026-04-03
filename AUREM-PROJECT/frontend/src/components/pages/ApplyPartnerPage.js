import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import {
  Instagram, Play, Youtube, Users, Star, CheckCircle2, 
  Send, ArrowRight, Award, Sparkles, Beaker, Dna
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Card, CardContent } from '../ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import PhoneInput, { detectUserCountry, getCountryByCode, formatFullPhone } from '../common/PhoneInput';

const API = process.env.REACT_APP_BACKEND_URL;

const ApplyPartnerPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [step, setStep] = useState(1);
  const [phoneCountryCode, setPhoneCountryCode] = useState('+1');
  
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    full_name: '',
    email: '',
    phone: '',
    country: 'Canada',
    primary_platform: '',
    social_handle: '',
    follower_count: '',
    instagram_handle: '',
    instagram_followers: '',
    tiktok_handle: '',
    tiktok_followers: '',
    content_niche: 'skincare',
    why_partner: '',
    content_ideas: '',
    previous_brands: '',
  });

  // Auto-detect country code on mount
  useEffect(() => {
    const detectedCountry = detectUserCountry();
    const country = getCountryByCode(detectedCountry);
    setPhoneCountryCode(country.phoneCode);
  }, []);

  const handleChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Format full phone and include first/last name
      const fullPhone = formatFullPhone(phoneCountryCode, formData.phone);
      const fullName = `${formData.first_name} ${formData.last_name}`.trim();
      
      await axios.post(`${API}/api/partner-application`, {
        ...formData,
        full_name: fullName,
        phone: fullPhone,
        phone_country_code: phoneCountryCode
      });
      setSubmitted(true);
      toast.success('Application submitted successfully!');
    } catch (error) {
      const msg = error.response?.data?.detail || 'Failed to submit application';
      toast.error(msg);
    }
    setLoading(false);
  };

  const validateStep1 = () => {
    return formData.first_name && formData.last_name && formData.email && formData.phone;
  };

  const validateStep2 = () => {
    return formData.primary_platform && formData.social_handle && formData.follower_count;
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#0f0f1a] via-[#1a1a2e] to-[#16213e] flex items-center justify-center p-4">
        <div className="max-w-lg text-center">
          <div className="w-20 h-20 bg-gradient-to-br from-green-400 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-4">Application Received</h1>
          <p className="text-gray-300 mb-8">
            Thank you for applying to the ReRoots Partner Circle. Our team will review your application 
            and reach out within 48 hours via WhatsApp with your decision.
          </p>
          <div className="bg-white/5 border border-white/10 rounded-xl p-6 mb-8">
            <p className="text-sm text-gray-400 mb-2">While you wait, explore our science:</p>
            <Button onClick={() => navigate('/science-glossary')} variant="outline" className="border-[#D4AF37] text-[#D4AF37] hover:bg-[#D4AF37]/10">
              <Beaker className="w-4 h-4 mr-2" />
              PDRN Science Glossary
            </Button>
          </div>
          <Button onClick={() => navigate('/')} className="bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-black font-semibold">
            Return Home
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f0f1a] via-[#1a1a2e] to-[#16213e]">
      {/* Hero Section */}
      <div className="relative py-16 px-4">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-10 w-64 h-64 bg-[#D4AF37] rounded-full blur-[100px]" />
          <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-500 rounded-full blur-[120px]" />
        </div>
        
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 bg-[#D4AF37]/20 border border-[#D4AF37]/30 rounded-full px-4 py-2 mb-6">
            <Dna className="w-4 h-4 text-[#D4AF37]" />
            <span className="text-sm text-[#D4AF37] font-medium">Elite Science Ambassador Program</span>
          </div>
          
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Join the <span className="text-[#D4AF37]">ReRoots Partner Circle</span>
          </h1>
          <p className="text-lg text-gray-300 max-w-2xl mx-auto mb-8">
            We're building a network of science-focused creators who understand biotech skincare. 
            Not everyone gets in — but those who do get exclusive benefits.
          </p>

          {/* Benefits Grid */}
          <div className="grid md:grid-cols-3 gap-4 mb-12">
            {[
              { icon: Award, title: '10-15% Commission', desc: 'On every sale you generate' },
              { icon: Star, title: '50% Customer Discount', desc: 'Your audience saves big' },
              { icon: Sparkles, title: 'Exclusive Assets', desc: 'White papers & brand kit' },
            ].map((benefit, idx) => (
              <div key={idx} className="bg-white/5 border border-white/10 rounded-xl p-5 text-left">
                <benefit.icon className="w-8 h-8 text-[#D4AF37] mb-3" />
                <h3 className="font-semibold text-white mb-1">{benefit.title}</h3>
                <p className="text-sm text-gray-400">{benefit.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Application Form */}
      <div className="max-w-2xl mx-auto px-4 pb-20">
        <Card className="bg-white/5 border-white/10 backdrop-blur-sm">
          <CardContent className="p-8">
            {/* Progress Steps */}
            <div className="flex items-center justify-center gap-4 mb-8">
              {[1, 2, 3].map((s) => (
                <div key={s} className="flex items-center">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-all ${
                    step >= s 
                      ? 'bg-[#D4AF37] text-black' 
                      : 'bg-white/10 text-gray-500'
                  }`}>
                    {s}
                  </div>
                  {s < 3 && (
                    <div className={`w-12 h-1 mx-2 transition-all ${
                      step > s ? 'bg-[#D4AF37]' : 'bg-white/10'
                    }`} />
                  )}
                </div>
              ))}
            </div>

            <form onSubmit={handleSubmit}>
              {/* Step 1: Personal Info */}
              {step === 1 && (
                <div className="space-y-6" data-testid="step-1-personal-info">
                  <div className="text-center mb-6">
                    <h2 className="text-xl font-semibold text-white mb-2">Personal Information</h2>
                    <p className="text-sm text-gray-400">Tell us about yourself</p>
                  </div>

                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-gray-300">First Name *</Label>
                        <Input
                          data-testid="first-name-input"
                          value={formData.first_name}
                          onChange={(e) => handleChange('first_name', e.target.value)}
                          placeholder="First name"
                          className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                          required
                        />
                      </div>
                      <div>
                        <Label className="text-gray-300">Last Name *</Label>
                        <Input
                          data-testid="last-name-input"
                          value={formData.last_name}
                          onChange={(e) => handleChange('last_name', e.target.value)}
                          placeholder="Last name"
                          className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                          required
                        />
                      </div>
                    </div>

                    <div>
                      <Label className="text-gray-300">Email *</Label>
                      <Input
                        data-testid="email-input"
                        type="email"
                        value={formData.email}
                        onChange={(e) => handleChange('email', e.target.value)}
                        placeholder="your@email.com"
                        className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                        required
                      />
                    </div>

                    <div>
                      <Label className="text-gray-300">WhatsApp Number *</Label>
                      <PhoneInput
                        value={formData.phone}
                        onChange={(val) => handleChange('phone', val)}
                        countryCode={phoneCountryCode}
                        onCountryCodeChange={setPhoneCountryCode}
                        placeholder="Phone number"
                        required
                        darkMode={true}
                        inputClassName="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                        testId="partner-apply-phone"
                      />
                      <p className="text-xs text-gray-500 mt-1">We'll send your approval status here</p>
                    </div>

                    <div>
                      <Label className="text-gray-300">Country</Label>
                      <Select value={formData.country} onValueChange={(v) => handleChange('country', v)}>
                        <SelectTrigger className="bg-white/5 border-white/20 text-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Canada">Canada</SelectItem>
                          <SelectItem value="USA">United States</SelectItem>
                          <SelectItem value="UK">United Kingdom</SelectItem>
                          <SelectItem value="Australia">Australia</SelectItem>
                          <SelectItem value="Other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <Button
                    type="button"
                    data-testid="next-step-btn"
                    onClick={() => setStep(2)}
                    disabled={!validateStep1()}
                    className="w-full bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-black font-semibold py-6"
                  >
                    Continue <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              )}

              {/* Step 2: Social Media */}
              {step === 2 && (
                <div className="space-y-6" data-testid="step-2-social-media">
                  <div className="text-center mb-6">
                    <h2 className="text-xl font-semibold text-white mb-2">Social Presence</h2>
                    <p className="text-sm text-gray-400">Share your platforms and audience</p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <Label className="text-gray-300">Primary Platform *</Label>
                      <Select value={formData.primary_platform} onValueChange={(v) => handleChange('primary_platform', v)}>
                        <SelectTrigger data-testid="primary-platform-select" className="bg-white/5 border-white/20 text-white">
                          <SelectValue placeholder="Select your main platform" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="instagram">
                            <div className="flex items-center gap-2">
                              <Instagram className="w-4 h-4" /> Instagram
                            </div>
                          </SelectItem>
                          <SelectItem value="tiktok">
                            <div className="flex items-center gap-2">
                              <Play className="w-4 h-4" /> TikTok
                            </div>
                          </SelectItem>
                          <SelectItem value="youtube">
                            <div className="flex items-center gap-2">
                              <Youtube className="w-4 h-4" /> YouTube
                            </div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-gray-300">Handle/Username *</Label>
                        <Input
                          data-testid="social-handle-input"
                          value={formData.social_handle}
                          onChange={(e) => handleChange('social_handle', e.target.value)}
                          placeholder="@yourhandle"
                          className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                          required
                        />
                      </div>
                      <div>
                        <Label className="text-gray-300">Follower Count *</Label>
                        <Input
                          data-testid="follower-count-input"
                          type="number"
                          value={formData.follower_count}
                          onChange={(e) => handleChange('follower_count', e.target.value)}
                          placeholder="10000"
                          className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                          required
                        />
                      </div>
                    </div>

                    {/* Secondary Platforms */}
                    <div className="border-t border-white/10 pt-4 mt-4">
                      <p className="text-sm text-gray-400 mb-4">Additional Platforms (Optional)</p>
                      
                      <div className="grid grid-cols-2 gap-4 mb-4">
                        <div>
                          <Label className="text-gray-300 flex items-center gap-2">
                            <Instagram className="w-4 h-4" /> Instagram
                          </Label>
                          <Input
                            value={formData.instagram_handle}
                            onChange={(e) => handleChange('instagram_handle', e.target.value)}
                            placeholder="@handle"
                            className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                          />
                        </div>
                        <div>
                          <Label className="text-gray-300">Followers</Label>
                          <Input
                            type="number"
                            value={formData.instagram_followers}
                            onChange={(e) => handleChange('instagram_followers', e.target.value)}
                            placeholder="10000"
                            className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-gray-300 flex items-center gap-2">
                            <Play className="w-4 h-4" /> TikTok
                          </Label>
                          <Input
                            value={formData.tiktok_handle}
                            onChange={(e) => handleChange('tiktok_handle', e.target.value)}
                            placeholder="@handle"
                            className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                          />
                        </div>
                        <div>
                          <Label className="text-gray-300">Followers</Label>
                          <Input
                            type="number"
                            value={formData.tiktok_followers}
                            onChange={(e) => handleChange('tiktok_followers', e.target.value)}
                            placeholder="10000"
                            className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                          />
                        </div>
                      </div>
                    </div>

                    <div>
                      <Label className="text-gray-300">Content Niche</Label>
                      <Select value={formData.content_niche} onValueChange={(v) => handleChange('content_niche', v)}>
                        <SelectTrigger className="bg-white/5 border-white/20 text-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="skincare">Skincare</SelectItem>
                          <SelectItem value="beauty">Beauty</SelectItem>
                          <SelectItem value="health">Health & Wellness</SelectItem>
                          <SelectItem value="lifestyle">Lifestyle</SelectItem>
                          <SelectItem value="science">Science Education</SelectItem>
                          <SelectItem value="dermatology">Dermatology/Aesthetics</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setStep(1)}
                      className="flex-1 border-white/20 text-white hover:bg-white/5"
                    >
                      Back
                    </Button>
                    <Button
                      type="button"
                      onClick={() => setStep(3)}
                      disabled={!validateStep2()}
                      className="flex-1 bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-black font-semibold"
                    >
                      Continue <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                </div>
              )}

              {/* Step 3: Why ReRoots */}
              {step === 3 && (
                <div className="space-y-6" data-testid="step-3-why-reroots">
                  <div className="text-center mb-6">
                    <h2 className="text-xl font-semibold text-white mb-2">Why ReRoots?</h2>
                    <p className="text-sm text-gray-400">Help us understand your interest</p>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <Label className="text-gray-300">Why do you want to partner with ReRoots? *</Label>
                      <Textarea
                        data-testid="why-partner-textarea"
                        value={formData.why_partner}
                        onChange={(e) => handleChange('why_partner', e.target.value)}
                        placeholder="Tell us what excites you about biotech skincare and PDRN technology..."
                        className="bg-white/5 border-white/20 text-white placeholder:text-gray-500 min-h-[120px]"
                        required
                      />
                      <p className="text-xs text-gray-500 mt-1">Minimum 50 characters</p>
                    </div>

                    <div>
                      <Label className="text-gray-300">Content Ideas (Optional)</Label>
                      <Textarea
                        value={formData.content_ideas}
                        onChange={(e) => handleChange('content_ideas', e.target.value)}
                        placeholder="How would you feature ReRoots in your content? (Reels, tutorials, reviews, etc.)"
                        className="bg-white/5 border-white/20 text-white placeholder:text-gray-500 min-h-[100px]"
                      />
                    </div>

                    <div>
                      <Label className="text-gray-300">Previous Brand Partnerships (Optional)</Label>
                      <Input
                        value={formData.previous_brands}
                        onChange={(e) => handleChange('previous_brands', e.target.value)}
                        placeholder="e.g., The Ordinary, Glow Recipe, CeraVe..."
                        className="bg-white/5 border-white/20 text-white placeholder:text-gray-500"
                      />
                    </div>
                  </div>

                  <div className="bg-[#D4AF37]/10 border border-[#D4AF37]/30 rounded-xl p-4">
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="w-5 h-5 text-[#D4AF37] mt-0.5" />
                      <div>
                        <p className="text-sm text-white font-medium">What happens next?</p>
                        <p className="text-xs text-gray-400 mt-1">
                          Our team reviews every application personally. If approved, you'll receive a 
                          WhatsApp message with your unique partner code and dashboard access within 48 hours.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setStep(2)}
                      className="flex-1 border-white/20 text-white hover:bg-white/5"
                    >
                      Back
                    </Button>
                    <Button
                      type="submit"
                      data-testid="submit-application-btn"
                      disabled={loading || formData.why_partner.length < 50}
                      className="flex-1 bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-black font-semibold"
                    >
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                          Submitting...
                        </span>
                      ) : (
                        <span className="flex items-center gap-2">
                          <Send className="w-4 h-4" />
                          Submit Application
                        </span>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        {/* Trust Badges */}
        <div className="flex items-center justify-center gap-6 mt-8 text-gray-500 text-sm">
          <span className="flex items-center gap-2">
            <Users className="w-4 h-4" />
            50+ Active Partners
          </span>
          <span className="flex items-center gap-2">
            <Star className="w-4 h-4" />
            4.9/5 Partner Rating
          </span>
        </div>
      </div>
    </div>
  );
};

export default ApplyPartnerPage;
