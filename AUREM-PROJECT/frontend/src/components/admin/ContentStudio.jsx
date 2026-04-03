/**
 * ContentStudio.jsx
 * AI-powered content creation dashboard for marketing
 * 6 content types with input forms, AI generation, and content library
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles,
  Instagram,
  MessageSquare,
  FileText,
  Mail,
  Send,
  Copy,
  Save,
  Search,
  Loader2,
  RefreshCw,
  Clock,
  CheckCircle,
  BookOpen,
  Layers,
  Hash,
  PenTool
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Content type configurations
const CONTENT_CONFIG = {
  instagram_caption: {
    icon: Instagram,
    color: 'bg-gradient-to-br from-purple-500 to-pink-500',
    lightColor: 'bg-purple-50 border-purple-200',
    inputs: [
      { key: 'product_name', label: 'Product Name', placeholder: 'AURA-GEN TXA + PDRN Serum' },
      { key: 'skin_concern', label: 'Skin Concern', placeholder: 'dryness, uneven tone, fine lines' },
      { key: 'tone', label: 'Tone', placeholder: 'educational, promotional, or testimonial' }
    ]
  },
  instagram_story: {
    icon: Layers,
    color: 'bg-gradient-to-br from-orange-500 to-pink-500',
    lightColor: 'bg-orange-50 border-orange-200',
    inputs: [
      { key: 'topic', label: 'Story Topic', placeholder: 'morning skincare routine' },
      { key: 'product_focus', label: 'Product Focus', placeholder: 'AURA-GEN System' }
    ]
  },
  product_description: {
    icon: FileText,
    color: 'bg-gradient-to-br from-blue-500 to-cyan-500',
    lightColor: 'bg-blue-50 border-blue-200',
    inputs: [
      { key: 'product_name', label: 'Product Name', placeholder: 'AURA-GEN TXA + PDRN Serum' },
      { key: 'ingredients', label: 'Key Ingredients', placeholder: 'PDRN, Tranexamic Acid, Argireline' },
      { key: 'target_concern', label: 'Target Concern', placeholder: 'hyperpigmentation and texture' }
    ]
  },
  whatsapp_broadcast: {
    icon: MessageSquare,
    color: 'bg-gradient-to-br from-green-500 to-emerald-500',
    lightColor: 'bg-green-50 border-green-200',
    inputs: [
      { key: 'campaign_goal', label: 'Campaign Goal', placeholder: 'new product launch, restock alert' },
      { key: 'offer_details', label: 'Offer Details (optional)', placeholder: '15% off this weekend' }
    ]
  },
  blog_outline: {
    icon: BookOpen,
    color: 'bg-gradient-to-br from-indigo-500 to-purple-500',
    lightColor: 'bg-indigo-50 border-indigo-200',
    inputs: [
      { key: 'topic', label: 'Blog Topic', placeholder: 'How PDRN transforms aging skin' },
      { key: 'target_keywords', label: 'Target Keywords', placeholder: 'PDRN benefits, skin renewal, clinical skincare' }
    ]
  },
  email_subjects: {
    icon: Mail,
    color: 'bg-gradient-to-br from-rose-500 to-red-500',
    lightColor: 'bg-rose-50 border-rose-200',
    inputs: [
      { key: 'email_goal', label: 'Email Goal', placeholder: 'drive purchases, re-engage inactive' },
      { key: 'target_audience', label: 'Target Audience', placeholder: 'new subscribers, repeat customers' }
    ]
  }
};

// Content type button
const ContentTypeButton = ({ type, config, apiConfig, isSelected, onClick }) => {
  const Icon = config.icon;
  
  return (
    <button
      onClick={onClick}
      className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
        isSelected 
          ? `${config.lightColor} shadow-md` 
          : 'bg-white border-gray-100 hover:border-gray-200'
      }`}
      data-testid={`content-type-${type}`}
    >
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${config.color}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div>
          <h4 className="font-medium text-gray-900">{apiConfig?.name || type}</h4>
          <p className="text-xs text-gray-500 mt-0.5">{apiConfig?.output_format}</p>
        </div>
      </div>
    </button>
  );
};

// Input form component
const InputForm = ({ contentType, config, inputs, setInputs, onGenerate, generating }) => {
  const uiConfig = CONTENT_CONFIG[contentType] || CONTENT_CONFIG.instagram_caption;
  
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
        <PenTool className="h-4 w-4" />
        Input Details
      </h3>
      
      <div className="space-y-3">
        {uiConfig.inputs.map(input => (
          <div key={input.key}>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              {input.label}
            </label>
            <Input
              value={inputs[input.key] || ''}
              onChange={(e) => setInputs(prev => ({ ...prev, [input.key]: e.target.value }))}
              placeholder={input.placeholder}
              className="w-full"
            />
          </div>
        ))}
      </div>
      
      <Button
        onClick={onGenerate}
        disabled={generating}
        className={`w-full ${uiConfig.color} text-white border-0`}
        data-testid="generate-content-btn"
      >
        {generating ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Generating...
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4 mr-2" />
            Generate with AI
          </>
        )}
      </Button>
    </div>
  );
};

// Output panel component
const OutputPanel = ({ output, onCopy, onSave, saving }) => {
  if (!output) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center p-6">
        <Sparkles className="h-12 w-12 text-gray-300 mb-4" />
        <p className="text-gray-500 font-medium">AI-generated content will appear here</p>
        <p className="text-xs text-gray-400 mt-1">Select a content type and fill in the inputs</p>
      </div>
    );
  }
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
          <CheckCircle className="h-4 w-4 text-green-600" />
          Generated Content
        </h3>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onCopy}>
            <Copy className="h-4 w-4 mr-1" />
            Copy
          </Button>
          <Button 
            size="sm" 
            onClick={onSave}
            disabled={saving}
            className="bg-green-600 hover:bg-green-700"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Save className="h-4 w-4 mr-1" />
                Save
              </>
            )}
          </Button>
        </div>
      </div>
      
      <div className="p-4 bg-white border rounded-xl">
        <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans leading-relaxed">
          {output}
        </pre>
      </div>
    </div>
  );
};

// Saved content card
const SavedContentCard = ({ content }) => {
  const config = CONTENT_CONFIG[content.content_type] || CONTENT_CONFIG.instagram_caption;
  const Icon = config.icon;
  
  const handleCopy = () => {
    navigator.clipboard.writeText(content.output);
    toast.success('Content copied!');
  };
  
  return (
    <div className="p-4 bg-white border rounded-xl">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-1.5 rounded-lg ${config.color}`}>
            <Icon className="h-4 w-4 text-white" />
          </div>
          <div>
            <Badge variant="outline" className="text-xs">
              {content.content_type?.replace(/_/g, ' ')}
            </Badge>
            <p className="text-xs text-gray-400 mt-1">
              {new Date(content.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={handleCopy}>
          <Copy className="h-4 w-4" />
        </Button>
      </div>
      <p className="text-sm text-gray-600 mt-3 line-clamp-3">
        {content.output?.substring(0, 150)}...
      </p>
    </div>
  );
};

export default function ContentStudio() {
  const [contentTypes, setContentTypes] = useState({});
  const [selectedType, setSelectedType] = useState('instagram_caption');
  const [inputs, setInputs] = useState({});
  const [output, setOutput] = useState(null);
  const [savedContent, setSavedContent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Fetch content types and history
  const fetchData = useCallback(async () => {
    const token = localStorage.getItem('reroots_token');
    if (!token) return;
    
    try {
      const [typesRes, historyRes] = await Promise.all([
        fetch(`${API}/api/content/types`),
        fetch(`${API}/api/content/history?limit=10`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);
      
      if (typesRes.ok) {
        const data = await typesRes.json();
        setContentTypes(data.types || {});
      }
      
      if (historyRes.ok) {
        const data = await historyRes.json();
        setSavedContent(data.history || []);
      }
    } catch (error) {
      console.error('Failed to fetch content data:', error);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  // Reset inputs when type changes
  useEffect(() => {
    setInputs({});
    setOutput(null);
  }, [selectedType]);
  
  // Generate content
  const handleGenerate = async () => {
    setGenerating(true);
    
    const token = localStorage.getItem('reroots_token');
    try {
      const res = await fetch(`${API}/api/content/generate`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content_type: selectedType,
          inputs: inputs
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setOutput(data.output);
        toast.success('Content generated!');
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to generate content');
      }
    } catch (error) {
      toast.error('Error generating content');
    } finally {
      setGenerating(false);
    }
  };
  
  // Copy content
  const handleCopy = () => {
    if (output) {
      navigator.clipboard.writeText(output);
      toast.success('Content copied to clipboard!');
    }
  };
  
  // Save content
  const handleSave = async () => {
    if (!output) return;
    
    setSaving(true);
    const token = localStorage.getItem('reroots_token');
    
    try {
      const res = await fetch(`${API}/api/content/save`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content_type: selectedType,
          inputs: inputs,
          output: output
        })
      });
      
      if (res.ok) {
        toast.success('Content saved to library!');
        fetchData(); // Refresh history
      } else {
        toast.error('Failed to save content');
      }
    } catch (error) {
      toast.error('Error saving content');
    } finally {
      setSaving(false);
    }
  };
  
  // Search content
  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      fetchData();
      return;
    }
    
    const token = localStorage.getItem('reroots_token');
    try {
      const res = await fetch(`${API}/api/content/search?q=${encodeURIComponent(searchQuery)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        const data = await res.json();
        setSavedContent(data.results || []);
      }
    } catch (error) {
      console.error('Search failed:', error);
    }
  };
  
  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6" data-testid="content-studio">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600">
            <Sparkles className="h-6 w-6 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Content Studio</h2>
            <p className="text-sm text-gray-500">AI-powered marketing content</p>
          </div>
        </div>
        
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>
      
      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left panel - Content types */}
        <div className="lg:col-span-3 space-y-3">
          <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Hash className="h-4 w-4" />
            Content Types
          </h3>
          <div className="space-y-2">
            {Object.entries(contentTypes).map(([type, config]) => (
              <ContentTypeButton
                key={type}
                type={type}
                config={CONTENT_CONFIG[type] || CONTENT_CONFIG.instagram_caption}
                apiConfig={config}
                isSelected={selectedType === type}
                onClick={() => setSelectedType(type)}
              />
            ))}
          </div>
        </div>
        
        {/* Middle panel - Input form */}
        <div className="lg:col-span-4">
          <div className="bg-gray-50 rounded-xl border p-4">
            <InputForm
              contentType={selectedType}
              config={contentTypes[selectedType]}
              inputs={inputs}
              setInputs={setInputs}
              onGenerate={handleGenerate}
              generating={generating}
            />
          </div>
        </div>
        
        {/* Right panel - Output */}
        <div className="lg:col-span-5">
          <div className="bg-gray-50 rounded-xl border p-4 min-h-[300px]">
            <OutputPanel
              output={output}
              onCopy={handleCopy}
              onSave={handleSave}
              saving={saving}
            />
          </div>
        </div>
      </div>
      
      {/* Saved content library */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Content Library
            <Badge variant="secondary" className="text-xs">
              {savedContent.length}
            </Badge>
          </h3>
          
          <div className="flex items-center gap-2">
            <Input
              placeholder="Search saved content..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-64 h-9"
            />
            <Button variant="outline" size="sm" onClick={handleSearch}>
              <Search className="h-4 w-4" />
            </Button>
          </div>
        </div>
        
        {savedContent.length === 0 ? (
          <div className="p-8 text-center bg-gray-50 rounded-xl border border-dashed border-gray-200">
            <BookOpen className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No saved content yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Generate and save content to build your library
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {savedContent.map((content, idx) => (
              <SavedContentCard key={idx} content={content} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
