import React from "react";
import {
  Plus,
  RefreshCw,
  Loader2,
  Package,
  Users,
  X,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Upload,
  Globe,
  TrendingUp,
  DollarSign,
  MapPin,
  Crown,
  Pencil
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

/**
 * OROÉ Global Command Center - Luxury Brand Administration
 * Extracted from App.js for better code organization and faster builds
 */
const OroeCommandCenter = ({
  // Data
  oroeProducts,
  oroeWaitlist,
  oroeStats,
  oroeLoading,
  
  // Form state
  oroeProductForm,
  setOroeProductForm,
  oroeProductFormOpen,
  setOroeProductFormOpen,
  translating,
  editingProduct,
  setEditingProduct,
  
  // Filters
  oroeMarketFilter,
  oroeStatusFilter,
  oroeHighValueOnly,
  
  // Actions
  fetchOroeData,
  createOroeProduct,
  deleteOroeProduct,
  updateOroeProduct,
  translateDescription,
  handleMarketFilterChange,
  handleStatusFilterChange,
  toggleHighValueFilter,
  approveWaitlistApplication,
  blacklistApplication,
  updateOroeStatus,
  updateSampleStatus,
  updateFeedbackNotes,
  
  // External
  API,
  headers
}) => {
  // Handle edit product - populate form with existing data
  const handleEditProduct = (product) => {
    setOroeProductForm({
      name: product.name || '',
      price_usd: product.price_usd || 0,
      limited_edition_quantity: product.limited_edition_quantity || 500,
      batch_signature: product.batch_signature || '',
      ritual_link: product.ritual_link || product.qr_destination || '',
      inventory_type: product.inventory_type || 'serialized',
      availability: product.availability || 'waitlist',
      descriptions: {
        en: product.descriptions?.en || product.description_en || '',
        fr: product.descriptions?.fr || product.description_fr || '',
        ar: product.descriptions?.ar || product.description_ar || ''
      },
      hero_image_url: product.hero_image_url || '',
      image_urls: product.image_urls || [],
      video_url: product.video_url || '',
      payment_methods: product.payment_methods || ['stripe', 'crypto'],
      redirect_to_ritual: product.redirect_to_ritual ?? true
    });
    setEditingProduct(product);
    setOroeProductFormOpen(true);
  };
  
  // Market region mapping for display
  const marketRegions = {
    middle_east: { label: "Middle East", icon: "🇦🇪", countries: ["UAE", "Saudi Arabia", "Qatar", "Kuwait"] },
    canada: { label: "Canada", icon: "🇨🇦", countries: ["Canada"] },
    europe: { label: "Europe", icon: "🇪🇺", countries: ["UK", "France", "Germany", "Italy"] },
    asia: { label: "Asia Pacific", icon: "🌏", countries: ["Singapore", "Hong Kong", "Japan"] }
  };

  // Format currency
  const formatCurrency = (amount, currency = "USD") => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 0
    }).format(amount);
  };

  return (
    <div className="space-y-6">
      {/* OROÉ Header */}
      <div className="bg-gradient-to-r from-[#0A0A0A] to-[#1A1A1A] rounded-lg p-6 border border-[#D4AF37]/30">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-2xl font-display text-[#D4AF37]">OROÉ Management</h2>
            <p className="text-[#D4AF37]/60 text-sm mt-1">Luxury Brand Administration</p>
          </div>
          <div className="flex gap-3">
            <Button 
              onClick={() => fetchOroeData()}
              variant="outline"
              className="border-[#D4AF37]/30 text-[#D4AF37] hover:bg-[#D4AF37]/10"
              disabled={oroeLoading}
              data-testid="oroe-refresh-btn"
            >
              {oroeLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
              Refresh
            </Button>
            <Button 
              onClick={() => window.open('/oroe', '_blank')}
              className="bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-[#0A0A0A] hover:opacity-90"
            >
              View OROÉ Site →
            </Button>
          </div>
        </div>
      </div>

      {/* OROÉ Sub-tabs */}
      <Tabs defaultValue="products" className="w-full">
        <div className="overflow-x-auto pb-2" style={{ WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none' }}>
          <TabsList className="mb-4 bg-[#0A0A0A] p-1 rounded-lg border border-[#D4AF37]/20 inline-flex min-w-max">
            <TabsTrigger 
              value="products" 
              className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-[#D4AF37] data-[state=active]:to-[#B8860B] data-[state=active]:text-[#0A0A0A] text-[#D4AF37]/70 rounded-md px-4 whitespace-nowrap"
            >
              <Package className="h-4 w-4 mr-2" /> Products
            </TabsTrigger>
            <TabsTrigger 
              value="waitlist" 
              className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-[#D4AF37] data-[state=active]:to-[#B8860B] data-[state=active]:text-[#0A0A0A] text-[#D4AF37]/70 rounded-md px-4 whitespace-nowrap"
            >
              <Users className="h-4 w-4 mr-2" /> VIP Waitlist
            {oroeWaitlist.filter(w => w.status === 'pending').length > 0 && (
              <Badge className="ml-2 bg-red-500 text-white text-xs">
                {oroeWaitlist.filter(w => w.status === 'pending').length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger 
            value="analytics" 
            className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-[#D4AF37] data-[state=active]:to-[#B8860B] data-[state=active]:text-[#0A0A0A] text-[#D4AF37]/70 rounded-md px-4 whitespace-nowrap"
          >
            <TrendingUp className="h-4 w-4 mr-2" /> Analytics
          </TabsTrigger>
          </TabsList>
        </div>

        {/* Products Tab */}
        <TabsContent value="products">
          <Card className="bg-white border-[#D4AF37]/20">
            <CardHeader className="border-b border-[#D4AF37]/20">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <CardTitle className="text-lg">OROÉ Luxury Product Creator</CardTitle>
                  <CardDescription>Create limited edition, serialized luxury products</CardDescription>
                </div>
                <Dialog open={oroeProductFormOpen} onOpenChange={(open) => {
                  setOroeProductFormOpen(open);
                  if (!open) setEditingProduct(null);
                }}>
                  <DialogTrigger asChild>
                    <Button 
                      className="bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-[#0A0A0A] hover:opacity-90"
                      data-testid="add-oroe-product-btn"
                    >
                      <Plus className="h-4 w-4 mr-2" /> Add Luxury Product
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                      <DialogTitle className="text-xl bg-gradient-to-r from-[#D4AF37] to-[#B8860B] bg-clip-text text-transparent">
                        {editingProduct ? 'Edit OROÉ Luxury Listing' : 'Create OROÉ Luxury Listing'}
                      </DialogTitle>
                      <DialogDescription>
                        {editingProduct 
                          ? `Editing: ${editingProduct.name}`
                          : 'Add a new limited edition product to the OROÉ collection'}
                      </DialogDescription>
                    </DialogHeader>
                    <ProductCreatorForm 
                      form={oroeProductForm}
                      setForm={setOroeProductForm}
                      onSubmit={editingProduct ? () => updateOroeProduct(editingProduct._id) : createOroeProduct}
                      onCancel={() => {
                        setOroeProductFormOpen(false);
                        setEditingProduct(null);
                      }}
                      translating={translating}
                      onTranslate={translateDescription}
                      isEditing={!!editingProduct}
                    />
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent className="p-6">
              {/* Products List */}
              {oroeLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin text-[#D4AF37]" />
                </div>
              ) : oroeProducts.length === 0 ? (
                <div className="text-center py-12 text-[#5A5A5A]">
                  <Package className="h-12 w-12 mx-auto text-[#D4AF37]/30 mb-4" />
                  <p className="mb-2">No luxury products yet</p>
                  <p className="text-sm">Create your first OROÉ product to get started</p>
                </div>
              ) : (
                <div className="grid gap-4">
                  {oroeProducts.map((product) => (
                    <ProductCard 
                      key={product._id} 
                      product={product} 
                      onDelete={deleteOroeProduct}
                      onEdit={handleEditProduct}
                      formatCurrency={formatCurrency}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Waitlist Tab */}
        <TabsContent value="waitlist">
          <WaitlistManager
            waitlist={oroeWaitlist}
            stats={oroeStats}
            loading={oroeLoading}
            marketFilter={oroeMarketFilter}
            statusFilter={oroeStatusFilter}
            highValueOnly={oroeHighValueOnly}
            onMarketFilterChange={handleMarketFilterChange}
            onStatusFilterChange={handleStatusFilterChange}
            onHighValueToggle={toggleHighValueFilter}
            onApprove={approveWaitlistApplication}
            onBlacklist={blacklistApplication}
            onUpdateStatus={updateOroeStatus}
            onUpdateSampleStatus={updateSampleStatus}
            onUpdateFeedbackNotes={updateFeedbackNotes}
            formatCurrency={formatCurrency}
            marketRegions={marketRegions}
          />
        </TabsContent>

        {/* Analytics Tab */}
        <TabsContent value="analytics">
          <AnalyticsDashboard 
            stats={oroeStats} 
            products={oroeProducts}
            waitlist={oroeWaitlist}
            formatCurrency={formatCurrency}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};

/**
 * Product Creator Form - Multi-image upload, translations, etc.
 */
const ProductCreatorForm = ({ form, setForm, onSubmit, onCancel, translating, onTranslate, isEditing }) => {
  return (
    <div className="space-y-6 py-4">
      {/* Product Name */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Product Name</Label>
        <Input 
          placeholder="OROÉ Luminous Elixir (Batch 01)" 
          className="border-[#D4AF37]/30 focus:border-[#D4AF37]"
          value={form.name}
          onChange={(e) => setForm({...form, name: e.target.value})}
          data-testid="oroe-product-name"
        />
      </div>
      
      {/* Price & Inventory Row */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label className="text-sm font-medium">Base Price (USD)</Label>
          <Input 
            type="number" 
            placeholder="155" 
            value={form.price_usd}
            onChange={(e) => setForm({...form, price_usd: parseFloat(e.target.value) || 0})}
            className="border-[#D4AF37]/30 focus:border-[#D4AF37]"
            data-testid="oroe-product-price"
          />
          <p className="text-xs text-[#5A5A5A]">Auto-converts to CAD/EUR/AED/GBP</p>
        </div>
        <div className="space-y-2">
          <Label className="text-sm font-medium">Limited Edition Quantity</Label>
          <Input 
            type="number" 
            placeholder="500"
            value={form.limited_edition_quantity}
            onChange={(e) => setForm({...form, limited_edition_quantity: parseInt(e.target.value) || 0})}
            className="border-[#D4AF37]/30 focus:border-[#D4AF37]"
            data-testid="oroe-product-quantity"
          />
          <p className="text-xs text-[#5A5A5A]">Serialized: Bottle 1 of {form.limited_edition_quantity}</p>
        </div>
      </div>

      {/* Batch Signature */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Batch Signature</Label>
        <Input 
          placeholder="Batch 01 - May 2025" 
          value={form.batch_signature}
          onChange={(e) => setForm({...form, batch_signature: e.target.value})}
          className="border-[#D4AF37]/30 focus:border-[#D4AF37]"
          data-testid="oroe-product-batch"
        />
        <p className="text-xs text-[#5A5A5A]">Unique identifier for this production batch</p>
      </div>

      {/* Ritual Link (QR Destination) */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Ritual Link (Certificate QR Code)</Label>
        <Input 
          placeholder="https://reroots.ca/oroe/ritual?bottle=001" 
          value={form.qr_destination}
          onChange={(e) => setForm({...form, qr_destination: e.target.value})}
          className="border-[#D4AF37]/30 focus:border-[#D4AF37]"
          data-testid="oroe-product-qr"
        />
        <p className="text-xs text-[#5A5A5A]">
          🔗 This URL is printed as a QR code on each bottle's Certificate of Authenticity. 
          Customers scan it to access "The Ritual" - your exclusive application masterclass.
        </p>
        <p className="text-xs text-[#D4AF37]/70 mt-1">
          💡 Tip: Use <code className="bg-[#D4AF37]/10 px-1 rounded">/oroe/ritual?bottle=001</code> to personalize each certificate
        </p>
      </div>

      {/* Inventory Type */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Inventory Type</Label>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input 
              type="radio" 
              name="inventory" 
              value="serialized" 
              checked={form.inventory_type === 'serialized'}
              onChange={() => setForm({...form, inventory_type: 'serialized'})}
              className="accent-[#D4AF37]" 
            />
            <span className="text-sm">Serialized (Numbered Bottles)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input 
              type="radio" 
              name="inventory" 
              value="standard"
              checked={form.inventory_type === 'standard'}
              onChange={() => setForm({...form, inventory_type: 'standard'})}
              className="accent-[#D4AF37]" 
            />
            <span className="text-sm">Standard</span>
          </label>
        </div>
      </div>

      {/* Availability */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Availability</Label>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input 
              type="radio" 
              name="availability" 
              value="waitlist"
              checked={form.availability === 'waitlist'}
              onChange={() => setForm({...form, availability: 'waitlist'})}
              className="accent-[#D4AF37]" 
            />
            <span className="text-sm">Waitlist Only (VIP Approval Required)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input 
              type="radio" 
              name="availability" 
              value="public"
              checked={form.availability === 'public'}
              onChange={() => setForm({...form, availability: 'public'})}
              className="accent-[#D4AF37]" 
            />
            <span className="text-sm">Public Sale</span>
          </label>
        </div>
      </div>

      <Separator className="bg-[#D4AF37]/20" />

      {/* Multilingual Descriptions with Auto-Translate */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">Product Descriptions (Multilingual)</Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onTranslate}
            disabled={translating || !form.descriptions.en?.trim()}
            className="border-[#D4AF37]/30 hover:bg-[#D4AF37]/10 text-xs"
            data-testid="translate-btn"
          >
            {translating ? (
              <>
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Translating...
              </>
            ) : (
              <>
                <Globe className="h-3 w-3 mr-1" />
                Auto-Translate to FR & AR
              </>
            )}
          </Button>
        </div>
        <p className="text-xs text-[#5A5A5A] -mt-2">
          💡 Write English description first, then click "Auto-Translate" for luxury-quality French & Arabic
        </p>
        <div className="space-y-3">
          <div>
            <Label className="text-xs text-[#5A5A5A]">English 🇬🇧 (Primary)</Label>
            <Textarea 
              placeholder="The Golden Elixir - A revolutionary fusion of 24K gold particles and advanced peptides that targets the appearance of fine lines..."
              className="border-[#D4AF37]/30 focus:border-[#D4AF37] mt-1"
              rows={3}
              value={form.descriptions.en}
              onChange={(e) => setForm({
                ...form, 
                descriptions: {...form.descriptions, en: e.target.value}
              })}
              data-testid="oroe-desc-en"
            />
          </div>
          <div>
            <Label className="text-xs text-[#5A5A5A]">Français 🇫🇷</Label>
            <Textarea 
              placeholder="L'Élixir Doré - Une fusion révolutionnaire de particules d'or 24K..."
              className="border-[#D4AF37]/30 focus:border-[#D4AF37] mt-1"
              rows={2}
              value={form.descriptions.fr}
              onChange={(e) => setForm({
                ...form, 
                descriptions: {...form.descriptions, fr: e.target.value}
              })}
              data-testid="oroe-desc-fr"
            />
          </div>
          <div>
            <Label className="text-xs text-[#5A5A5A]">العربية 🇦🇪 (RTL)</Label>
            <Textarea 
              placeholder="الإكسير الذهبي - مزيج ثوري من جزيئات الذهب عيار 24..."
              className="border-[#D4AF37]/30 focus:border-[#D4AF37] mt-1 text-right"
              dir="rtl"
              rows={2}
              value={form.descriptions.ar}
              onChange={(e) => setForm({
                ...form, 
                descriptions: {...form.descriptions, ar: e.target.value}
              })}
              data-testid="oroe-desc-ar"
            />
          </div>
        </div>
      </div>

      <Separator className="bg-[#D4AF37]/20" />

      {/* Payment Options */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Payment Options</Label>
        <div className="space-y-2">
          <label className="flex items-center gap-3 p-3 border border-[#D4AF37]/20 rounded-lg cursor-pointer hover:bg-[#D4AF37]/5">
            <input 
              type="checkbox" 
              checked={form.payment_methods.includes('stripe')}
              onChange={(e) => {
                const methods = e.target.checked 
                  ? [...form.payment_methods, 'stripe']
                  : form.payment_methods.filter(m => m !== 'stripe');
                setForm({...form, payment_methods: methods});
              }}
              className="accent-[#D4AF37] w-4 h-4" 
            />
            <span className="text-sm">💳 Credit Card (Stripe)</span>
          </label>
          <label className="flex items-center gap-3 p-3 border border-[#D4AF37]/20 rounded-lg cursor-pointer hover:bg-[#D4AF37]/5">
            <input 
              type="checkbox" 
              checked={form.payment_methods.includes('crypto')}
              onChange={(e) => {
                const methods = e.target.checked 
                  ? [...form.payment_methods, 'crypto']
                  : form.payment_methods.filter(m => m !== 'crypto');
                setForm({...form, payment_methods: methods});
              }}
              className="accent-[#D4AF37] w-4 h-4" 
            />
            <span className="text-sm">₿ Cryptocurrency (BTC, ETH, USDC)</span>
          </label>
          <label className="flex items-center gap-3 p-3 border border-[#D4AF37]/20 rounded-lg cursor-pointer hover:bg-[#D4AF37]/5">
            <input 
              type="checkbox" 
              checked={form.payment_methods.includes('paypal')}
              onChange={(e) => {
                const methods = e.target.checked 
                  ? [...form.payment_methods, 'paypal']
                  : form.payment_methods.filter(m => m !== 'paypal');
                setForm({...form, payment_methods: methods});
              }}
              className="accent-[#D4AF37] w-4 h-4" 
            />
            <span className="text-sm">🅿️ PayPal</span>
          </label>
        </div>
      </div>

      {/* Post-Purchase Redirect */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Post-Purchase Experience</Label>
        <div className="flex items-center gap-3 p-3 bg-gradient-to-r from-[#D4AF37]/5 to-transparent border border-[#D4AF37]/20 rounded-lg">
          <input 
            type="checkbox" 
            checked={form.redirect_to_ritual}
            onChange={(e) => setForm({...form, redirect_to_ritual: e.target.checked})}
            className="accent-[#D4AF37] w-4 h-4" 
          />
          <div>
            <span className="text-sm font-medium">Redirect to "The Ritual" ✨</span>
            <p className="text-xs text-[#5A5A5A]">VIPs see the secret application masterclass after purchase</p>
          </div>
        </div>
      </div>

      {/* Product Images Gallery - Multiple Upload */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Product Images Gallery</Label>
        <p className="text-xs text-[#5A5A5A] -mt-1">
          Upload multiple images for a complete product showcase
        </p>
        
        {/* Image Type Guide */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="p-2 bg-[#D4AF37]/5 rounded border border-[#D4AF37]/20">
            <span className="font-medium">📸 Hero Shot</span>
            <p className="text-[#5A5A5A]">Transparent background</p>
          </div>
          <div className="p-2 bg-[#D4AF37]/5 rounded border border-[#D4AF37]/20">
            <span className="font-medium">🔬 Texture Shot</span>
            <p className="text-[#5A5A5A]">Macro gold mica view</p>
          </div>
          <div className="p-2 bg-[#D4AF37]/5 rounded border border-[#D4AF37]/20">
            <span className="font-medium">🛁 Lifestyle Shot</span>
            <p className="text-[#5A5A5A]">Luxury spa setting</p>
          </div>
          <div className="p-2 bg-[#D4AF37]/5 rounded border border-[#D4AF37]/20">
            <span className="font-medium">🧬 Science Graphic</span>
            <p className="text-[#5A5A5A]">PDRN visualization</p>
          </div>
        </div>

        {/* Current Images Preview */}
        {(form.hero_image_url || form.image_urls?.length > 0) && (
          <div className="grid grid-cols-4 gap-2">
            {/* Hero Image (Primary) */}
            {form.hero_image_url && (
              <div className="relative aspect-square rounded-lg border-2 border-[#D4AF37] overflow-hidden bg-gradient-to-br from-[#D4AF37]/10 to-transparent">
                <img 
                  src={form.hero_image_url} 
                  alt="Hero" 
                  className="w-full h-full object-cover"
                />
                <div className="absolute top-1 left-1 bg-[#D4AF37] text-[#0A0A0A] text-[10px] px-1.5 py-0.5 rounded font-medium">
                  HERO
                </div>
                <button
                  type="button"
                  onClick={() => setForm({...form, hero_image_url: ''})}
                  className="absolute top-1 right-1 p-1 rounded-full bg-red-500 text-white hover:bg-red-600"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
            {/* Gallery Images */}
            {form.image_urls?.map((url, idx) => (
              <div key={idx} className="relative aspect-square rounded-lg border border-[#D4AF37]/30 overflow-hidden bg-gradient-to-br from-[#D4AF37]/5 to-transparent">
                <img 
                  src={url} 
                  alt={`Gallery ${idx + 1}`} 
                  className="w-full h-full object-cover"
                />
                <div className="absolute top-1 left-1 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded">
                  {idx + 1}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const newUrls = form.image_urls.filter((_, i) => i !== idx);
                    setForm({...form, image_urls: newUrls});
                  }}
                  className="absolute top-1 right-1 p-1 rounded-full bg-red-500 text-white hover:bg-red-600"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Multi-File Upload Area */}
        <div 
          className="border-2 border-dashed border-[#D4AF37]/30 rounded-lg p-6 text-center hover:border-[#D4AF37]/50 transition-colors cursor-pointer"
          onClick={() => document.getElementById('oroe-multi-image-upload-modal')?.click()}
        >
          <input
            id="oroe-multi-image-upload-modal"
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            data-testid="oroe-image-upload"
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              files.forEach((file, index) => {
                const reader = new FileReader();
                reader.onload = (ev) => {
                  setForm(prev => {
                    // First image goes to hero_image_url if empty
                    if (index === 0 && !prev.hero_image_url) {
                      return {...prev, hero_image_url: ev.target.result};
                    }
                    // Rest go to image_urls array
                    return {
                      ...prev, 
                      image_urls: [...(prev.image_urls || []), ev.target.result]
                    };
                  });
                };
                reader.readAsDataURL(file);
              });
              e.target.value = ''; // Reset input
            }}
          />
          <Upload className="h-8 w-8 mx-auto text-[#D4AF37]/50 mb-2" />
          <p className="text-sm text-[#D4AF37]/70 font-medium">Click to upload images</p>
          <p className="text-xs text-[#5A5A5A] mt-1">Select multiple files • First image = Hero Shot</p>
          <p className="text-xs text-[#5A5A5A]">PNG, JPG, WebP • Recommended: 1000×1000px</p>
        </div>
      </div>

      {/* Form Actions */}
      <div className="flex flex-col sm:flex-row justify-end gap-3 pt-4 border-t">
        <Button variant="outline" onClick={onCancel} className="order-2 sm:order-1">
          Cancel
        </Button>
        <Button 
          className="bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-[#0A0A0A] hover:opacity-90 order-1 sm:order-2"
          onClick={onSubmit}
          data-testid={isEditing ? "update-oroe-product-btn" : "create-oroe-product-btn"}
        >
          {isEditing ? (
            <>
              <Pencil className="h-4 w-4 mr-2" />
              Update Product
            </>
          ) : (
            <>
              <Plus className="h-4 w-4 mr-2" />
              Create Luxury Listing
            </>
          )}
        </Button>
      </div>
    </div>
  );
};

/**
 * Product Card - Displays a single OROÉ product
 */
const ProductCard = ({ product, onDelete, onEdit, formatCurrency }) => {
  return (
    <div className="flex items-center gap-4 p-4 border border-[#D4AF37]/20 rounded-lg hover:border-[#D4AF37]/40 transition-colors">
      {/* Image */}
      <div className="w-20 h-20 rounded-lg overflow-hidden bg-gradient-to-br from-[#D4AF37]/10 to-transparent flex-shrink-0">
        {product.hero_image_url ? (
          <img src={product.hero_image_url} alt={product.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package className="h-8 w-8 text-[#D4AF37]/30" />
          </div>
        )}
      </div>
      
      {/* Info */}
      <div className="flex-1 min-w-0">
        <h4 className="font-medium truncate">{product.name}</h4>
        <p className="text-sm text-[#5A5A5A]">
          {formatCurrency(product.price_usd)} • {product.sold_count || 0}/{product.limited_edition_quantity} sold
        </p>
        <div className="flex items-center gap-2 mt-1">
          <Badge variant="outline" className="text-xs border-[#D4AF37]/30 text-[#D4AF37]">
            {product.batch_signature || "No Batch"}
          </Badge>
          <Badge variant={product.availability === 'public' ? 'default' : 'secondary'} className="text-xs">
            {product.availability === 'public' ? 'Public' : 'Waitlist'}
          </Badge>
          {product.image_urls?.length > 0 && (
            <Badge variant="outline" className="text-xs">
              {product.image_urls.length + 1} images
            </Badge>
          )}
        </div>
      </div>
      
      {/* Actions */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="border-[#D4AF37]/50 text-[#D4AF37] hover:bg-[#D4AF37]/10"
          onClick={() => onEdit(product)}
          data-testid={`edit-oroe-product-${product._id}`}
        >
          <Pencil className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="border-red-300 text-red-600 hover:bg-red-50"
          onClick={() => onDelete(product._id)}
          data-testid={`delete-oroe-product-${product._id}`}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};

/**
 * Waitlist Manager - VIP application management
 */
const WaitlistManager = ({
  waitlist,
  stats,
  loading,
  marketFilter,
  statusFilter,
  highValueOnly,
  onMarketFilterChange,
  onStatusFilterChange,
  onHighValueToggle,
  onApprove,
  onBlacklist,
  onUpdateStatus,
  onUpdateSampleStatus,
  onUpdateFeedbackNotes,
  formatCurrency,
  marketRegions
}) => {
  const pendingCount = waitlist.filter(w => w.status === 'pending').length;
  const approvedCount = waitlist.filter(w => w.status === 'approved').length;
  
  return (
    <Card className="bg-white border-[#D4AF37]/20">
      <CardHeader className="border-b border-[#D4AF37]/20">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <CardTitle className="text-lg">VIP Waitlist Management</CardTitle>
            <CardDescription>{waitlist.length} total applications • {pendingCount} pending review</CardDescription>
          </div>
        </div>
        
        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
          <div className="p-4 bg-gradient-to-br from-[#D4AF37]/10 to-transparent rounded-lg border border-[#D4AF37]/20">
            <div className="flex items-center gap-2 text-[#D4AF37]">
              <Users className="h-4 w-4" />
              <span className="text-xs font-medium">Global Demand</span>
            </div>
            <p className="text-2xl font-bold mt-1">{stats.total_applications || 0}</p>
          </div>
          <div className="p-4 bg-gradient-to-br from-green-500/10 to-transparent rounded-lg border border-green-500/20">
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle className="h-4 w-4" />
              <span className="text-xs font-medium">Approved VIPs</span>
            </div>
            <p className="text-2xl font-bold mt-1">{approvedCount}</p>
          </div>
          <div className="p-4 bg-gradient-to-br from-purple-500/10 to-transparent rounded-lg border border-purple-500/20">
            <div className="flex items-center gap-2 text-purple-600">
              <Crown className="h-4 w-4" />
              <span className="text-xs font-medium">High-Value</span>
            </div>
            <p className="text-2xl font-bold mt-1">{stats.high_value_count || 0}</p>
          </div>
          <div className="p-4 bg-gradient-to-br from-blue-500/10 to-transparent rounded-lg border border-blue-500/20">
            <div className="flex items-center gap-2 text-blue-600">
              <DollarSign className="h-4 w-4" />
              <span className="text-xs font-medium">Revenue Forecast</span>
            </div>
            <p className="text-2xl font-bold mt-1">{formatCurrency(stats.revenue_forecast || 0)}</p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mt-4">
          <select 
            className="px-3 py-1.5 border border-[#D4AF37]/30 rounded-md text-sm bg-white"
            value={marketFilter}
            onChange={(e) => onMarketFilterChange(e.target.value)}
          >
            <option value="all">All Regions</option>
            <option value="middle_east">🇦🇪 Middle East</option>
            <option value="canada">🇨🇦 Canada</option>
            <option value="europe">🇪🇺 Europe</option>
          </select>
          <select 
            className="px-3 py-1.5 border border-[#D4AF37]/30 rounded-md text-sm bg-white"
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value)}
          >
            <option value="all">All Status</option>
            <option value="pending">⏳ Pending</option>
            <option value="approved">✅ Approved</option>
            <option value="blacklisted">❌ Blacklisted</option>
          </select>
          <Button
            variant={highValueOnly ? "default" : "outline"}
            size="sm"
            onClick={onHighValueToggle}
            className={highValueOnly ? "bg-[#D4AF37] text-[#0A0A0A]" : "border-[#D4AF37]/30"}
          >
            <Crown className="h-3 w-3 mr-1" />
            High-Value Only
          </Button>
        </div>
      </CardHeader>
      
      <CardContent className="p-6">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-[#D4AF37]" />
          </div>
        ) : waitlist.length === 0 ? (
          <div className="text-center py-12 text-[#5A5A5A]">
            <Users className="h-12 w-12 mx-auto text-[#D4AF37]/30 mb-4" />
            <p className="mb-2">No applications match your filters</p>
          </div>
        ) : (
          <div className="space-y-3">
            {waitlist.map((app) => (
              <WaitlistCard
                key={app._id}
                application={app}
                onApprove={onApprove}
                onBlacklist={onBlacklist}
                onUpdateStatus={onUpdateStatus}
                onUpdateSampleStatus={onUpdateSampleStatus}
                onUpdateFeedbackNotes={onUpdateFeedbackNotes}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

/**
 * Single Waitlist Application Card with CRM Features
 */
const WaitlistCard = ({ application, onApprove, onBlacklist, onUpdateStatus, onUpdateSampleStatus, onUpdateFeedbackNotes }) => {
  const isHighValue = application.is_high_value || application.prequalification_score >= 4;
  
  const handleFeedbackClick = () => {
    const notes = prompt('Enter feedback notes:', application.feedbackNotes || '');
    if (notes !== null && onUpdateFeedbackNotes) {
      onUpdateFeedbackNotes(application._id, notes);
    }
  };
  
  return (
    <div className={`p-4 border rounded-lg ${isHighValue ? 'border-[#D4AF37] bg-gradient-to-r from-[#D4AF37]/5 to-transparent' : 'border-gray-200'}`}>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="font-medium">{application.firstName} {application.lastName}</h4>
            {isHighValue && (
              <Badge className="bg-gradient-to-r from-[#D4AF37] to-[#B8860B] text-[#0A0A0A] text-xs">
                <Crown className="h-3 w-3 mr-1" /> VIP
              </Badge>
            )}
            <Badge variant={
              application.status === 'approved' ? 'default' : 
              application.status === 'blacklisted' ? 'destructive' : 'secondary'
            } className="text-xs">
              {application.status}
            </Badge>
          </div>
          <p className="text-sm text-[#5A5A5A] truncate">{application.email}</p>
          <div className="flex items-center gap-3 mt-2 text-xs text-[#5A5A5A] flex-wrap">
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {application.country || "Unknown"}
            </span>
            <span>Units: {application.unitsRequested || 1}</span>
            <span>Payment: {application.paymentPreference || "traditional"}</span>
            {application.referredBy && (
              <span className="text-[#D4AF37]">Ref: {application.referredBy}</span>
            )}
          </div>
          
          {/* CRM: Sample Status & Feedback Notes - Only show for approved applications */}
          {application.status === 'approved' && (
            <div className="flex items-center gap-3 mt-3 flex-wrap">
              <select
                className="px-2 py-1 text-xs border border-gray-200 rounded bg-white"
                value={application.sampleStatus || 'not_sent'}
                onChange={(e) => onUpdateSampleStatus && onUpdateSampleStatus(application._id, e.target.value)}
              >
                <option value="not_sent">📦 Not Sent</option>
                <option value="sent">🚚 Sent</option>
                <option value="delivered">✅ Delivered</option>
                <option value="feedback_pending">⏳ Awaiting Feedback</option>
                <option value="feedback_received">💬 Feedback Received</option>
              </select>
              <button
                onClick={handleFeedbackClick}
                className="text-xs px-2 py-1 border border-gray-200 rounded hover:bg-gray-50 truncate max-w-[150px]"
                title={application.feedbackNotes || 'Click to add notes'}
              >
                {application.feedbackNotes ? application.feedbackNotes.substring(0, 20) + '...' : '+ Add notes'}
              </button>
            </div>
          )}
          
          {/* Access Code Display for Approved */}
          {application.status === 'approved' && application.access_code && (
            <div className="mt-2 p-2 bg-green-50 rounded text-xs">
              <span className="text-green-700">Access Code: </span>
              <span className="font-mono font-bold text-green-800">{application.access_code}</span>
              <span className="text-green-600 ml-2">• Bottle #{application.bottle_number}</span>
            </div>
          )}
        </div>
        
        {/* Action Buttons */}
        <div className="flex gap-2 flex-shrink-0">
          {application.status === 'pending' && (
            <>
              <Button
                size="sm"
                className="bg-green-600 hover:bg-green-700 text-white"
                onClick={() => onApprove(application._id)}
              >
                <CheckCircle className="h-4 w-4 mr-1" />
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-red-300 text-red-600 hover:bg-red-50"
                onClick={() => onBlacklist(application._id)}
              >
                <XCircle className="h-4 w-4" />
              </Button>
            </>
          )}
          {application.status === 'approved' && onUpdateStatus && (
            <Button
              size="sm"
              variant="outline"
              className="border-gray-300 text-gray-600 hover:bg-gray-50"
              onClick={() => onUpdateStatus(application._id, 'pending')}
            >
              Reset
            </Button>
          )}
          {application.status === 'blacklisted' && onUpdateStatus && (
            <Button
              size="sm"
              variant="outline"
              className="border-gray-300 text-gray-600 hover:bg-gray-50"
              onClick={() => onUpdateStatus(application._id, 'pending')}
            >
              Unblock
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Analytics Dashboard
 */
const AnalyticsDashboard = ({ stats, products, waitlist, formatCurrency }) => {
  const totalRevenuePotential = products.reduce((sum, p) => 
    sum + (p.price_usd * (p.limited_edition_quantity - (p.sold_count || 0))), 0
  );
  
  return (
    <Card className="bg-white border-[#D4AF37]/20">
      <CardHeader>
        <CardTitle className="text-lg">OROÉ Analytics Dashboard</CardTitle>
        <CardDescription>Performance metrics and forecasts</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-6 bg-gradient-to-br from-[#D4AF37]/10 to-transparent rounded-lg border border-[#D4AF37]/20 text-center">
            <DollarSign className="h-8 w-8 mx-auto text-[#D4AF37] mb-2" />
            <p className="text-sm text-[#5A5A5A]">Total Revenue Potential</p>
            <p className="text-3xl font-bold text-[#D4AF37]">{formatCurrency(totalRevenuePotential)}</p>
          </div>
          <div className="p-6 bg-gradient-to-br from-purple-500/10 to-transparent rounded-lg border border-purple-500/20 text-center">
            <Package className="h-8 w-8 mx-auto text-purple-600 mb-2" />
            <p className="text-sm text-[#5A5A5A]">Active Products</p>
            <p className="text-3xl font-bold text-purple-600">{products.length}</p>
          </div>
          <div className="p-6 bg-gradient-to-br from-blue-500/10 to-transparent rounded-lg border border-blue-500/20 text-center">
            <Users className="h-8 w-8 mx-auto text-blue-600 mb-2" />
            <p className="text-sm text-[#5A5A5A]">Conversion Rate</p>
            <p className="text-3xl font-bold text-blue-600">
              {waitlist.length > 0 ? 
                Math.round((waitlist.filter(w => w.status === 'approved').length / waitlist.length) * 100) : 0}%
            </p>
          </div>
        </div>
        
        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <h4 className="font-medium mb-3">Regional Distribution</h4>
          <div className="space-y-2">
            {['Canada', 'UAE', 'UK', 'USA'].map(region => {
              const count = waitlist.filter(w => w.country === region).length;
              const percentage = waitlist.length > 0 ? (count / waitlist.length) * 100 : 0;
              return (
                <div key={region} className="flex items-center gap-3">
                  <span className="w-20 text-sm">{region}</span>
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-gradient-to-r from-[#D4AF37] to-[#B8860B] h-2 rounded-full" 
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <span className="text-sm text-[#5A5A5A] w-12">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default OroeCommandCenter;
