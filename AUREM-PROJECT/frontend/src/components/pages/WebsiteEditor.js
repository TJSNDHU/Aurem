import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

// UI Components
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Switch } from '../ui/switch';

// Icons
import { Loader2, Save, Image, Type, Layout, Settings } from 'lucide-react';

// Contexts
import { useSiteContent } from '../../contexts';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const WebsiteEditor = () => {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeSection, setActiveSection] = useState("hero");
  const { refreshContent } = useSiteContent();
  
  const token = localStorage.getItem("reroots_token");
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    axios.get(`${API}/site-content`)
      .then(res => setContent(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const saveSection = async (section, data) => {
    setSaving(true);
    try {
      await axios.put(`${API}/site-content/${section}`, data, { headers });
      toast.success(`${section.charAt(0).toUpperCase() + section.slice(1)} section saved!`);
      refreshContent();
    } catch (error) {
      toast.error("Failed to save changes");
    }
    setSaving(false);
  };

  const updateContent = (section, field, value) => {
    setContent(prev => ({
      ...prev,
      [section]: {
        ...prev?.[section],
        [field]: value
      }
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-2xl font-bold text-[#2D2A2E]">Website Editor</h2>
        <Button 
          onClick={() => saveSection(activeSection, content?.[activeSection])}
          disabled={saving}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
          Save Changes
        </Button>
      </div>

      <Tabs value={activeSection} onValueChange={setActiveSection}>
        <TabsList className="mb-4">
          <TabsTrigger value="hero">
            <Layout className="h-4 w-4 mr-2" />
            Hero
          </TabsTrigger>
          <TabsTrigger value="about">
            <Type className="h-4 w-4 mr-2" />
            About
          </TabsTrigger>
          <TabsTrigger value="images">
            <Image className="h-4 w-4 mr-2" />
            Images
          </TabsTrigger>
          <TabsTrigger value="settings">
            <Settings className="h-4 w-4 mr-2" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* Hero Section Editor */}
        <TabsContent value="hero">
          <Card>
            <CardHeader>
              <CardTitle>Hero Section</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Headline</Label>
                <Input 
                  value={content?.hero?.headline || ""}
                  onChange={(e) => updateContent('hero', 'headline', e.target.value)}
                  placeholder="Main headline text"
                />
              </div>
              <div>
                <Label>Subheadline</Label>
                <Textarea 
                  value={content?.hero?.subheadline || ""}
                  onChange={(e) => updateContent('hero', 'subheadline', e.target.value)}
                  placeholder="Supporting text"
                  rows={3}
                />
              </div>
              <div>
                <Label>CTA Button Text</Label>
                <Input 
                  value={content?.hero?.cta_text || ""}
                  onChange={(e) => updateContent('hero', 'cta_text', e.target.value)}
                  placeholder="Button text"
                />
              </div>
              <div>
                <Label>CTA Button Link</Label>
                <Input 
                  value={content?.hero?.cta_link || ""}
                  onChange={(e) => updateContent('hero', 'cta_link', e.target.value)}
                  placeholder="/shop"
                />
              </div>
              <div>
                <Label>Background Image URL</Label>
                <Input 
                  value={content?.hero?.background_image || ""}
                  onChange={(e) => updateContent('hero', 'background_image', e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* About Section Editor */}
        <TabsContent value="about">
          <Card>
            <CardHeader>
              <CardTitle>About Section</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Title</Label>
                <Input 
                  value={content?.about?.title || ""}
                  onChange={(e) => updateContent('about', 'title', e.target.value)}
                  placeholder="About section title"
                />
              </div>
              <div>
                <Label>Description</Label>
                <Textarea 
                  value={content?.about?.description || ""}
                  onChange={(e) => updateContent('about', 'description', e.target.value)}
                  placeholder="About text"
                  rows={5}
                />
              </div>
              <div>
                <Label>Image URL</Label>
                <Input 
                  value={content?.about?.image || ""}
                  onChange={(e) => updateContent('about', 'image', e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Images Editor */}
        <TabsContent value="images">
          <Card>
            <CardHeader>
              <CardTitle>Site Images</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Logo URL</Label>
                <Input 
                  value={content?.images?.logo || ""}
                  onChange={(e) => updateContent('images', 'logo', e.target.value)}
                  placeholder="https://..."
                />
              </div>
              <div>
                <Label>Favicon URL</Label>
                <Input 
                  value={content?.images?.favicon || ""}
                  onChange={(e) => updateContent('images', 'favicon', e.target.value)}
                  placeholder="https://..."
                />
              </div>
              <div>
                <Label>Default Product Image</Label>
                <Input 
                  value={content?.images?.default_product || ""}
                  onChange={(e) => updateContent('images', 'default_product', e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Editor */}
        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle>Site Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Maintenance Mode</Label>
                  <p className="text-sm text-[#5A5A5A]">Show maintenance page to visitors</p>
                </div>
                <Switch 
                  checked={content?.settings?.maintenance_mode || false}
                  onCheckedChange={(checked) => updateContent('settings', 'maintenance_mode', checked)}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>Show Announcement Bar</Label>
                  <p className="text-sm text-[#5A5A5A]">Display promotional banner at top</p>
                </div>
                <Switch 
                  checked={content?.settings?.show_announcement || false}
                  onCheckedChange={(checked) => updateContent('settings', 'show_announcement', checked)}
                />
              </div>
              <div>
                <Label>Announcement Text</Label>
                <Input 
                  value={content?.settings?.announcement_text || ""}
                  onChange={(e) => updateContent('settings', 'announcement_text', e.target.value)}
                  placeholder="Free shipping on orders over $75!"
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default WebsiteEditor;
