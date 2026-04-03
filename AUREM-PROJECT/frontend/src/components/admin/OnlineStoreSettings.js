import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Store, Palette, Type, Image, Layout, Navigation, FileText,
  Bell, Globe, Shield, Save, Eye, Smartphone, Monitor,
  Upload, Link, ExternalLink, Settings, ChevronRight, Search,
  Share2, Code, CheckCircle, AlertCircle, Copy, Star, ShoppingCart, Mail
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { useAdminBrand } from './useAdminBrand';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Brand-specific default settings
const BRAND_DEFAULTS = {
  reroots: {
    primaryColor: '#F8A5B8',
    secondaryColor: '#2D2A2E',
    backgroundColor: '#FDF9F9',
    announcementBgColor: '#F8A5B8',
    footerAbout: 'ReRoots Skincare Canada - Premium biotech skincare for skin longevity.',
    siteTitle: 'ReRoots Skincare Canada',
    siteDescription: 'Premium biotech skincare featuring PDRN technology for anti-aging and skin rejuvenation.',
    metaKeywords: 'skincare, PDRN, anti-aging, biotech, Canada',
    heroTitle: 'The Future of Skin Longevity',
    heroSubtitle: 'Experience the restorative power of Biotech PDRN',
  },
  lavela: {
    primaryColor: '#0D4D4D',
    secondaryColor: '#D4A574',
    backgroundColor: '#FDF8F5',
    announcementBgColor: '#0D4D4D',
    footerAbout: 'LA VELA BIANCA - Luxury teen skincare. Clean light for your skin.',
    siteTitle: 'LA VELA BIANCA | Luxury Teen Skincare',
    siteDescription: 'Premium pediatric-safe skincare for teens aged 8-18. ORO ROSA serum with PDRN, Glutathione, Hyaluronic Acid.',
    metaKeywords: 'teen skincare, pediatric safe, luxury teen skincare, Canada, La Vela Bianca, ORO ROSA',
    heroTitle: 'Unveil Your Inner Radiance',
    heroSubtitle: 'Luxury skincare designed for young, radiant skin',
  }
};

const OnlineStoreSettings = () => {
  const { activeBrand } = useAdminBrand();
  const brandDefaults = BRAND_DEFAULTS[activeBrand] || BRAND_DEFAULTS.reroots;
  
  const [settings, setSettings] = useState({
    // Theme - use brand defaults
    primaryColor: brandDefaults.primaryColor,
    secondaryColor: brandDefaults.secondaryColor,
    backgroundColor: brandDefaults.backgroundColor,
    fontFamily: 'Manrope',
    
    // Header
    logoUrl: '',
    faviconUrl: '',
    showAnnouncementBar: true,
    announcementText: 'Free shipping on orders over $75!',
    announcementLink: '/shop',
    announcementBgColor: brandDefaults.announcementBgColor,
    
    // Homepage
    heroTitle: brandDefaults.heroTitle,
    heroSubtitle: brandDefaults.heroSubtitle,
    heroButtonText: 'Shop Now',
    heroButtonLink: '/shop',
    heroImage: '',
    showFeaturedProducts: true,
    featuredProductsCount: 4,
    
    // Navigation
    menuItems: [
      { label: 'Shop', link: '/shop' },
      { label: 'Skincare', link: '/category/skincare' },
      { label: 'About', link: '/about' }
    ],
    
    // Footer
    footerAbout: brandDefaults.footerAbout,
    socialLinks: {
      instagram: activeBrand === 'lavela' ? 'https://instagram.com/La_Vela_Bianca' : 'https://instagram.com/reroots',
      facebook: '',
      tiktok: ''
    },
    
    // SEO
    siteTitle: brandDefaults.siteTitle,
    siteDescription: brandDefaults.siteDescription,
    metaKeywords: brandDefaults.metaKeywords,
    
    // Open Graph
    ogImage: '',
    ogType: 'website',
    twitterHandle: '',
    
    // Policies
    shippingPolicy: '',
    returnPolicy: '',
    privacyPolicy: '',
    
    // Analytics
    googleAnalyticsId: '',
    facebookPixelId: '',
    googleSearchConsoleId: '',
    
    // Notifications
    reviewNotificationsEnabled: true,
    reviewThankYouEnabled: true,
    thankYouDiscountCode: 'THANKYOU10',
    adminEmail: 'admin@reroots.ca'
  });

  const [activeTab, setActiveTab] = useState('theme');
  const [saving, setSaving] = useState(false);
  const [loadingPolicies, setLoadingPolicies] = useState(true);

  // Load settings from localStorage (for non-policy settings)
  // Reset settings when brand changes
  useEffect(() => {
    const newDefaults = BRAND_DEFAULTS[activeBrand] || BRAND_DEFAULTS.reroots;
    setSettings(prev => ({
      ...prev,
      primaryColor: newDefaults.primaryColor,
      secondaryColor: newDefaults.secondaryColor,
      backgroundColor: newDefaults.backgroundColor,
      announcementBgColor: newDefaults.announcementBgColor,
      footerAbout: newDefaults.footerAbout,
      siteTitle: newDefaults.siteTitle,
      siteDescription: newDefaults.siteDescription,
      metaKeywords: newDefaults.metaKeywords,
      heroTitle: newDefaults.heroTitle,
      heroSubtitle: newDefaults.heroSubtitle,
      socialLinks: {
        ...prev.socialLinks,
        instagram: activeBrand === 'lavela' ? 'https://instagram.com/La_Vela_Bianca' : 'https://instagram.com/reroots',
      }
    }));
  }, [activeBrand]);

  useEffect(() => {
    const saved = localStorage.getItem(`${activeBrand}_store_settings`);
    if (saved) {
      const parsed = JSON.parse(saved);
      // Don't override policies from localStorage - they come from DB
      const { shippingPolicy, returnPolicy, privacyPolicy, ...otherSettings } = parsed;
      setSettings(prev => ({ ...prev, ...otherSettings }));
    }
  }, [activeBrand]);

  // Load policies from backend database
  useEffect(() => {
    const loadPolicies = async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        const response = await axios.get(`${API}/api/site-content/policies`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSettings(prev => ({
          ...prev,
          shippingPolicy: response.data.shipping_policy || '',
          returnPolicy: response.data.return_policy || '',
          privacyPolicy: response.data.privacy_policy || ''
        }));
      } catch (error) {
        console.error('Failed to load policies:', error);
      } finally {
        setLoadingPolicies(false);
      }
    };
    loadPolicies();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Save policies to backend database
      const token = localStorage.getItem('reroots_token');
      await axios.put(`${API}/api/site-content/policies`, {
        shipping_policy: settings.shippingPolicy,
        return_policy: settings.returnPolicy,
        privacy_policy: settings.privacyPolicy
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      // Save non-policy settings to localStorage (theme, SEO, etc.)
      const { shippingPolicy, returnPolicy, privacyPolicy, ...otherSettings } = settings;
      localStorage.setItem('reroots_store_settings', JSON.stringify(otherSettings));
      
      toast.success('Settings saved!');
    } catch (error) {
      console.error('Failed to save policies:', error);
      toast.error('Failed to save policies. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const SettingSection = ({ title, description, children }) => (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">
        {children}
      </CardContent>
    </Card>
  );

  const ChecklistItem = ({ label, checked }) => (
    <div className="flex items-center gap-3">
      <div className={`w-5 h-5 rounded-full flex items-center justify-center ${checked ? 'bg-green-500' : 'bg-gray-200'}`}>
        {checked && <CheckCircle className="h-4 w-4 text-white" />}
      </div>
      <span className={checked ? 'text-[#2D2A2E]' : 'text-[#5A5A5A]'}>{label}</span>
      {checked && <Badge className="bg-green-100 text-green-700 text-xs">Done</Badge>}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#2D2A2E]">Online Store</h1>
          <p className="text-[#5A5A5A]">Customize your storefront appearance and settings</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="gap-2" onClick={() => window.open('/', '_blank')}>
            <Eye className="h-4 w-4" />
            View Store
          </Button>
          <Button onClick={handleSave} disabled={saving} className="bg-[#F8A5B8] hover:bg-[#E88DA0] text-white gap-2">
            <Save className="h-4 w-4" />
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>

      {/* Settings Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="bg-white border">
          <TabsTrigger value="theme" className="gap-2">
            <Palette className="h-4 w-4" />
            Theme
          </TabsTrigger>
          <TabsTrigger value="homepage" className="gap-2">
            <Layout className="h-4 w-4" />
            Homepage
          </TabsTrigger>
          <TabsTrigger value="navigation" className="gap-2">
            <Navigation className="h-4 w-4" />
            Navigation
          </TabsTrigger>
          <TabsTrigger value="seo" className="gap-2">
            <Globe className="h-4 w-4" />
            SEO
          </TabsTrigger>
          <TabsTrigger value="notifications" className="gap-2">
            <Bell className="h-4 w-4" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="policies" className="gap-2">
            <FileText className="h-4 w-4" />
            Policies
          </TabsTrigger>
        </TabsList>

        {/* Theme Settings */}
        <TabsContent value="theme">
          <SettingSection title="Brand Colors" description="Customize your store's color scheme">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label>Primary Color</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    type="color"
                    value={settings.primaryColor}
                    onChange={(e) => updateSetting('primaryColor', e.target.value)}
                    className="w-12 h-10 p-1 cursor-pointer"
                  />
                  <Input
                    value={settings.primaryColor}
                    onChange={(e) => updateSetting('primaryColor', e.target.value)}
                    className="flex-1 font-mono"
                  />
                </div>
              </div>
              <div>
                <Label>Secondary Color</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    type="color"
                    value={settings.secondaryColor}
                    onChange={(e) => updateSetting('secondaryColor', e.target.value)}
                    className="w-12 h-10 p-1 cursor-pointer"
                  />
                  <Input
                    value={settings.secondaryColor}
                    onChange={(e) => updateSetting('secondaryColor', e.target.value)}
                    className="flex-1 font-mono"
                  />
                </div>
              </div>
              <div>
                <Label>Background Color</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    type="color"
                    value={settings.backgroundColor}
                    onChange={(e) => updateSetting('backgroundColor', e.target.value)}
                    className="w-12 h-10 p-1 cursor-pointer"
                  />
                  <Input
                    value={settings.backgroundColor}
                    onChange={(e) => updateSetting('backgroundColor', e.target.value)}
                    className="flex-1 font-mono"
                  />
                </div>
              </div>
            </div>
          </SettingSection>

          <SettingSection title="Logo & Favicon" description="Upload your brand assets">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Logo URL</Label>
                <Input
                  value={settings.logoUrl}
                  onChange={(e) => updateSetting('logoUrl', e.target.value)}
                  placeholder="https://your-logo-url.png"
                />
              </div>
              <div>
                <Label>Favicon URL</Label>
                <Input
                  value={settings.faviconUrl}
                  onChange={(e) => updateSetting('faviconUrl', e.target.value)}
                  placeholder="https://your-favicon-url.ico"
                />
              </div>
            </div>
          </SettingSection>

          <SettingSection title="Announcement Bar" description="Display promotional messages at the top of your store">
            <div className="flex items-center gap-2 mb-4">
              <Switch
                checked={settings.showAnnouncementBar}
                onCheckedChange={(checked) => updateSetting('showAnnouncementBar', checked)}
              />
              <Label>Show Announcement Bar</Label>
            </div>
            {settings.showAnnouncementBar && (
              <div className="space-y-4">
                <div>
                  <Label>Announcement Text</Label>
                  <Input
                    value={settings.announcementText}
                    onChange={(e) => updateSetting('announcementText', e.target.value)}
                    placeholder="Free shipping on orders over $75!"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Link (optional)</Label>
                    <Input
                      value={settings.announcementLink}
                      onChange={(e) => updateSetting('announcementLink', e.target.value)}
                      placeholder="/shop"
                    />
                  </div>
                  <div>
                    <Label>Background Color</Label>
                    <div className="flex gap-2">
                      <Input
                        type="color"
                        value={settings.announcementBgColor}
                        onChange={(e) => updateSetting('announcementBgColor', e.target.value)}
                        className="w-12 h-10 p-1 cursor-pointer"
                      />
                      <Input
                        value={settings.announcementBgColor}
                        onChange={(e) => updateSetting('announcementBgColor', e.target.value)}
                        className="flex-1 font-mono"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </SettingSection>
        </TabsContent>

        {/* Homepage Settings */}
        <TabsContent value="homepage">
          <SettingSection title="Hero Section" description="Customize your homepage hero banner">
            <div className="space-y-4">
              <div>
                <Label>Hero Title</Label>
                <Input
                  value={settings.heroTitle}
                  onChange={(e) => updateSetting('heroTitle', e.target.value)}
                  placeholder="The Future of Skin Longevity"
                />
              </div>
              <div>
                <Label>Hero Subtitle</Label>
                <Textarea
                  value={settings.heroSubtitle}
                  onChange={(e) => updateSetting('heroSubtitle', e.target.value)}
                  placeholder="Experience the restorative power..."
                  rows={2}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Button Text</Label>
                  <Input
                    value={settings.heroButtonText}
                    onChange={(e) => updateSetting('heroButtonText', e.target.value)}
                    placeholder="Shop Now"
                  />
                </div>
                <div>
                  <Label>Button Link</Label>
                  <Input
                    value={settings.heroButtonLink}
                    onChange={(e) => updateSetting('heroButtonLink', e.target.value)}
                    placeholder="/shop"
                  />
                </div>
              </div>
              <div>
                <Label>Hero Background Image URL</Label>
                <Input
                  value={settings.heroImage}
                  onChange={(e) => updateSetting('heroImage', e.target.value)}
                  placeholder="https://your-hero-image-url.jpg"
                />
              </div>
            </div>
          </SettingSection>

          <SettingSection title="Featured Products" description="Show products on homepage">
            <div className="flex items-center gap-2 mb-4">
              <Switch
                checked={settings.showFeaturedProducts}
                onCheckedChange={(checked) => updateSetting('showFeaturedProducts', checked)}
              />
              <Label>Show Featured Products</Label>
            </div>
            {settings.showFeaturedProducts && (
              <div>
                <Label>Number of Products to Show</Label>
                <Input
                  type="number"
                  value={settings.featuredProductsCount}
                  onChange={(e) => updateSetting('featuredProductsCount', parseInt(e.target.value) || 4)}
                  min={1}
                  max={12}
                  className="w-24"
                />
              </div>
            )}
          </SettingSection>
        </TabsContent>

        {/* Navigation Settings */}
        <TabsContent value="navigation">
          <SettingSection title="Header Menu" description="Edit your main navigation links">
            <div className="space-y-3">
              {settings.menuItems.map((item, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input
                    value={item.label}
                    onChange={(e) => {
                      const newItems = [...settings.menuItems];
                      newItems[index] = { ...item, label: e.target.value };
                      updateSetting('menuItems', newItems);
                    }}
                    placeholder="Label"
                    className="flex-1"
                  />
                  <Input
                    value={item.link}
                    onChange={(e) => {
                      const newItems = [...settings.menuItems];
                      newItems[index] = { ...item, link: e.target.value };
                      updateSetting('menuItems', newItems);
                    }}
                    placeholder="/link"
                    className="flex-1"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => {
                      const newItems = settings.menuItems.filter((_, i) => i !== index);
                      updateSetting('menuItems', newItems);
                    }}
                  >
                    ×
                  </Button>
                </div>
              ))}
              <Button
                variant="outline"
                onClick={() => {
                  updateSetting('menuItems', [...settings.menuItems, { label: '', link: '' }]);
                }}
                className="w-full"
              >
                + Add Menu Item
              </Button>
            </div>
          </SettingSection>

          <SettingSection title="Social Links" description="Connect your social media profiles">
            <div className="space-y-4">
              <div>
                <Label>Instagram</Label>
                <Input
                  value={settings.socialLinks.instagram}
                  onChange={(e) => updateSetting('socialLinks', { ...settings.socialLinks, instagram: e.target.value })}
                  placeholder="https://instagram.com/yourstore"
                />
              </div>
              <div>
                <Label>Facebook</Label>
                <Input
                  value={settings.socialLinks.facebook}
                  onChange={(e) => updateSetting('socialLinks', { ...settings.socialLinks, facebook: e.target.value })}
                  placeholder="https://facebook.com/yourstore"
                />
              </div>
              <div>
                <Label>TikTok</Label>
                <Input
                  value={settings.socialLinks.tiktok}
                  onChange={(e) => updateSetting('socialLinks', { ...settings.socialLinks, tiktok: e.target.value })}
                  placeholder="https://tiktok.com/@yourstore"
                />
              </div>
            </div>
          </SettingSection>
        </TabsContent>

        {/* SEO Settings */}
        <TabsContent value="seo">
          {/* SEO Health Status */}
          <Card className="mb-6 bg-gradient-to-r from-green-50 to-blue-50 border-green-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="h-6 w-6 text-green-600" />
                <div>
                  <p className="font-medium text-green-800">SEO Infrastructure Active</p>
                  <p className="text-sm text-green-600">Sitemap and robots.txt are automatically generated</p>
                </div>
                <div className="ml-auto flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => window.open(`${API}/api/sitemap.xml`, '_blank')}
                    className="gap-1"
                  >
                    <ExternalLink className="h-3 w-3" />
                    Sitemap
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => window.open(`${API}/api/robots.txt`, '_blank')}
                    className="gap-1"
                  >
                    <ExternalLink className="h-3 w-3" />
                    Robots.txt
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <SettingSection title="Meta Tags" description="Optimize your store for search engines">
            <div className="space-y-4">
              <div>
                <Label>Site Title</Label>
                <Input
                  value={settings.siteTitle}
                  onChange={(e) => updateSetting('siteTitle', e.target.value)}
                  placeholder="Your Store Name"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">
                  <span className={settings.siteTitle.length > 60 ? 'text-red-500' : 'text-green-600'}>
                    {settings.siteTitle.length}/60 characters
                  </span>
                  {settings.siteTitle.length > 60 && ' (Too long for search results)'}
                </p>
              </div>
              <div>
                <Label>Meta Description</Label>
                <Textarea
                  value={settings.siteDescription}
                  onChange={(e) => updateSetting('siteDescription', e.target.value)}
                  placeholder="Describe your store..."
                  rows={3}
                />
                <p className="text-xs mt-1">
                  <span className={settings.siteDescription.length > 160 ? 'text-red-500' : settings.siteDescription.length < 120 ? 'text-amber-500' : 'text-green-600'}>
                    {settings.siteDescription.length}/160 characters
                  </span>
                  {settings.siteDescription.length < 120 && ' (Add more details for better SEO)'}
                </p>
              </div>
              <div>
                <Label>Keywords</Label>
                <Input
                  value={settings.metaKeywords}
                  onChange={(e) => updateSetting('metaKeywords', e.target.value)}
                  placeholder="keyword1, keyword2, keyword3"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">Separate with commas • Focus on 5-10 primary keywords</p>
              </div>
            </div>
          </SettingSection>

          {/* Google Search Preview */}
          <SettingSection title="Google Search Preview" description="How your site appears in search results">
            <div className="bg-white border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center">
                  <span className="text-xs font-bold text-[#F8A5B8]">R</span>
                </div>
                <div>
                  <p className="text-sm text-[#5A5A5A]">reroots.ca</p>
                </div>
              </div>
              <p className="text-xl text-blue-700 hover:underline cursor-pointer mb-1">
                {settings.siteTitle || 'Your Site Title'}
              </p>
              <p className="text-sm text-[#5A5A5A] line-clamp-2">
                {settings.siteDescription || 'Your meta description will appear here...'}
              </p>
            </div>
          </SettingSection>

          {/* Open Graph / Social Sharing */}
          <SettingSection title="Social Sharing (Open Graph)" description="Control how your site looks when shared on social media">
            <div className="space-y-4">
              <div>
                <Label>Default Share Image URL</Label>
                <Input
                  value={settings.ogImage || ''}
                  onChange={(e) => updateSetting('ogImage', e.target.value)}
                  placeholder="https://reroots.ca/images/og-image.jpg"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">Recommended: 1200x630 pixels for best results</p>
              </div>
              <div>
                <Label>Twitter/X Handle</Label>
                <Input
                  value={settings.twitterHandle || ''}
                  onChange={(e) => updateSetting('twitterHandle', e.target.value)}
                  placeholder="@yourhandle"
                />
              </div>
              
              {/* Social Preview */}
              <div className="mt-4">
                <Label className="mb-2 block">Social Share Preview</Label>
                <div className="border rounded-lg overflow-hidden max-w-md">
                  <div className="h-40 bg-gradient-to-br from-[#F8A5B8]/20 to-[#F8A5B8]/5 flex items-center justify-center">
                    {settings.ogImage ? (
                      <img src={settings.ogImage} alt="OG Preview" className="w-full h-full object-cover" />
                    ) : (
                      <div className="text-center text-[#5A5A5A]">
                        <Image className="h-8 w-8 mx-auto mb-2" />
                        <p className="text-sm">Share image preview</p>
                      </div>
                    )}
                  </div>
                  <div className="p-3 bg-gray-50">
                    <p className="text-xs text-[#5A5A5A] uppercase">reroots.ca</p>
                    <p className="font-semibold text-[#2D2A2E] truncate">{settings.siteTitle || 'Site Title'}</p>
                    <p className="text-sm text-[#5A5A5A] line-clamp-2">{settings.siteDescription || 'Description...'}</p>
                  </div>
                </div>
              </div>
            </div>
          </SettingSection>

          {/* Schema Markup Info */}
          <SettingSection title="Structured Data (Schema.org)" description="Rich snippets for enhanced search results">
            <Card className="bg-blue-50 border-blue-200">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <Code className="h-5 w-5 text-blue-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-blue-800">Auto-Generated Schema Markup</p>
                    <p className="text-sm text-blue-600 mt-1">
                      Product pages automatically include JSON-LD structured data with:
                    </p>
                    <ul className="text-sm text-blue-600 mt-2 space-y-1">
                      <li>• Product name, description, images</li>
                      <li>• Price and availability</li>
                      <li>• Review ratings and count</li>
                      <li>• Brand information (ReRoots)</li>
                    </ul>
                    <p className="text-xs text-blue-500 mt-3">
                      This helps Google show rich snippets with star ratings and prices in search results.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </SettingSection>

          <SettingSection title="Analytics & Tracking" description="Track your store performance">
            <div className="space-y-4">
              <div>
                <Label>Google Analytics ID</Label>
                <Input
                  value={settings.googleAnalyticsId}
                  onChange={(e) => updateSetting('googleAnalyticsId', e.target.value)}
                  placeholder="G-XXXXXXXXXX"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">Measurement ID from Google Analytics 4</p>
              </div>
              <div>
                <Label>Google Search Console Verification</Label>
                <Input
                  value={settings.googleSearchConsoleId || ''}
                  onChange={(e) => updateSetting('googleSearchConsoleId', e.target.value)}
                  placeholder="google-site-verification=XXXXXXXXXX"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">Meta tag content for Search Console verification</p>
              </div>
              <div>
                <Label>Facebook Pixel ID</Label>
                <Input
                  value={settings.facebookPixelId}
                  onChange={(e) => updateSetting('facebookPixelId', e.target.value)}
                  placeholder="XXXXXXXXXXXXXXX"
                />
              </div>
            </div>
          </SettingSection>

          {/* SEO Checklist */}
          <SettingSection title="SEO Checklist" description="Quick health check for your store's SEO">
            <div className="space-y-3">
              <ChecklistItem 
                label="Site title set" 
                checked={settings.siteTitle?.length > 0} 
              />
              <ChecklistItem 
                label="Meta description (120-160 chars)" 
                checked={settings.siteDescription?.length >= 120 && settings.siteDescription?.length <= 160} 
              />
              <ChecklistItem 
                label="Keywords defined" 
                checked={settings.metaKeywords?.length > 0} 
              />
              <ChecklistItem 
                label="Social share image set" 
                checked={settings.ogImage?.length > 0} 
              />
              <ChecklistItem 
                label="Google Analytics connected" 
                checked={settings.googleAnalyticsId?.length > 0} 
              />
              <ChecklistItem 
                label="Search Console verified" 
                checked={settings.googleSearchConsoleId?.length > 0} 
              />
            </div>
          </SettingSection>
        </TabsContent>

        {/* Notifications Settings */}
        <TabsContent value="notifications">
          <SettingSection title="Review Notifications" description="Get notified when customers submit reviews">
            <div className="space-y-6">
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-[#F8A5B8]/20 rounded-lg">
                    <Star className="h-5 w-5 text-[#F8A5B8]" />
                  </div>
                  <div>
                    <p className="font-medium text-[#2D2A2E]">Email Alerts for New Reviews</p>
                    <p className="text-sm text-[#5A5A5A]">Receive an email when customers submit reviews</p>
                  </div>
                </div>
                <Switch
                  checked={settings.reviewNotificationsEnabled}
                  onCheckedChange={(checked) => updateSetting('reviewNotificationsEnabled', checked)}
                />
              </div>
              
              <div>
                <Label>Admin Email Address</Label>
                <Input
                  type="email"
                  value={settings.adminEmail}
                  onChange={(e) => updateSetting('adminEmail', e.target.value)}
                  placeholder="admin@reroots.ca"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">Review notifications will be sent to this address</p>
              </div>
              
              <Card className="bg-blue-50 border-blue-200">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div className="text-sm">
                      <p className="font-medium text-blue-800">Smart Priority Alerts (Hybrid System)</p>
                      <ul className="text-blue-600 mt-2 space-y-1">
                        <li>• <strong>Low ratings (1-3 stars)</strong> - Instant alert with "Contact Customer" button</li>
                        <li>• <strong>High ratings (4-5 stars)</strong> - Queued for daily digest summary</li>
                        <li>• <strong>Photo reviews</strong> - Highlighted as high-value content</li>
                      </ul>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </SettingSection>

          <SettingSection title="Customer Thank You Emails" description="Auto-send thank you emails when reviews are approved">
            <div className="space-y-6">
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <Mail className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="font-medium text-[#2D2A2E]">Thank You Email on Approval</p>
                    <p className="text-sm text-[#5A5A5A]">Send customers a thank you email with a discount code</p>
                  </div>
                </div>
                <Switch
                  checked={settings.reviewThankYouEnabled}
                  onCheckedChange={(checked) => updateSetting('reviewThankYouEnabled', checked)}
                />
              </div>
              
              <div>
                <Label>Thank You Discount Code</Label>
                <Input
                  value={settings.thankYouDiscountCode}
                  onChange={(e) => updateSetting('thankYouDiscountCode', e.target.value)}
                  placeholder="THANKYOU10"
                />
                <p className="text-xs text-[#5A5A5A] mt-1">This code will be included in thank you emails (10% off by default)</p>
              </div>
              
              <Card className="bg-green-50 border-green-200">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                    <div className="text-sm">
                      <p className="font-medium text-green-800">What customers receive:</p>
                      <ul className="text-green-600 mt-2 space-y-1">
                        <li>• Personalized thank you message</li>
                        <li>• Confirmation their review is live</li>
                        <li>• Special photo mention (if they included photos)</li>
                        <li>• 10% discount code for next purchase</li>
                      </ul>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </SettingSection>

          <SettingSection title="Order Notifications" description="Email alerts for order events">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg opacity-50">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <ShoppingCart className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="font-medium text-[#2D2A2E]">New Order Alerts</p>
                    <p className="text-sm text-[#5A5A5A]">Get notified when new orders are placed</p>
                  </div>
                </div>
                <Badge variant="outline">Coming Soon</Badge>
              </div>
              
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg opacity-50">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-orange-100 rounded-lg">
                    <AlertCircle className="h-5 w-5 text-orange-600" />
                  </div>
                  <div>
                    <p className="font-medium text-[#2D2A2E]">Low Stock Alerts</p>
                    <p className="text-sm text-[#5A5A5A]">Get notified when inventory runs low</p>
                  </div>
                </div>
                <Badge variant="outline">Coming Soon</Badge>
              </div>
            </div>
          </SettingSection>
        </TabsContent>

        {/* Policies Settings */}
        <TabsContent value="policies">
          {loadingPolicies ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#F8A5B8]"></div>
              <span className="ml-3 text-[#5A5A5A]">Loading policies...</span>
            </div>
          ) : (
            <>
              <SettingSection title="Shipping Policy" description="Explain your shipping terms">
                <Textarea
                  value={settings.shippingPolicy}
                  onChange={(e) => updateSetting('shippingPolicy', e.target.value)}
                  placeholder="Describe your shipping policy..."
                  rows={6}
                />
              </SettingSection>

              <SettingSection title="Return Policy" description="Explain your return/refund terms">
                <Textarea
                  value={settings.returnPolicy}
                  onChange={(e) => updateSetting('returnPolicy', e.target.value)}
                  placeholder="Describe your return policy..."
                  rows={6}
                />
              </SettingSection>

              <SettingSection title="Privacy Policy" description="Your data privacy policy">
                <Textarea
                  value={settings.privacyPolicy}
                  onChange={(e) => updateSetting('privacyPolicy', e.target.value)}
                  placeholder="Describe your privacy policy..."
                  rows={6}
                />
              </SettingSection>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default OnlineStoreSettings;
