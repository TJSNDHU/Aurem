import React, { useState, lazy, Suspense } from 'react';
import { cn } from '../../lib/utils';
import { Loader2, ExternalLink } from 'lucide-react';
import { useAdminBrand } from './useAdminBrand';

// Loading fallback for lazy-loaded components
const LoadingSpinner = () => (
  <div className="flex items-center justify-center py-12">
    <Loader2 className="h-8 w-8 animate-spin text-[#F8A5B8]" />
  </div>
);

// Get brand-aware tab labels
const getTabLabels = (activeBrand) => {
  const isLaVela = activeBrand === 'lavela';
  const pointsName = isLaVela ? 'Glow Points' : 'Roots';
  
  return {
    'orders': 'Orders',
    'order-flow': 'Order Flow',
    'products': 'Products',
    'collections': 'Collections',
    'combos': 'Combo Offers',
    'inventory': 'Inventory',
    'customers': 'Customers',
    'partners': 'Partners',
    'founders': 'Founders',
    'waitlist': 'Waitlist',
    'offers': 'Discounts',
    'loyalty-points': 'Loyalty',
    'redemption': 'Redemption',
    'reviews': 'Reviews',
    'gift-tracking': `Gift ${pointsName}`,
    'birthday-bonus': 'Birthday',
    'referral-bonus': 'Referral',
    'templates': 'Templates',
    '28-day-cycle': '28-Day Cycle',
    'ai-intelligence': 'AI Intelligence',
    'sales-intelligence': 'Sales Intelligence',
    'analytics': 'Analytics',
    'marketing-lab': 'Marketing Lab',
    'settings': 'Store Settings',
    'security': 'Security',
    'team': 'Team',
    'partner-portal': 'Partner Portal',
    'store': 'Online Store',
    'view-store': 'View Store',
  };
};

// Lazy load components
const VirtualizedOrdersTable = lazy(() => import('./VirtualizedOrdersTable'));
const OrderFlowDashboard = lazy(() => import('./OrderFlowDashboard'));
const VirtualizedProductsTable = lazy(() => import('./VirtualizedProductsTable'));
const CollectionsManager = lazy(() => import('./CollectionsManager'));
const ComboOffersManager = lazy(() => import('./ComboOffersManager'));
const InventoryManager = lazy(() => import('./InventoryManager'));
const VirtualizedCustomersTable = lazy(() => import('./VirtualizedCustomersTable'));
const DataHub = lazy(() => import('./DataHub'));
const OffersManager = lazy(() => import('./OffersManager'));
const LoyaltyPointsManager = lazy(() => import('./LoyaltyPointsManager'));
const ReviewsManager = lazy(() => import('./ReviewsManager'));
const GiftTrackingDashboard = lazy(() => import('./GiftTrackingDashboard'));
const WhatsAppCRMActions = lazy(() => import('./WhatsAppCRMActions'));
const AIIntelligenceHub = lazy(() => import('./AIIntelligenceHub'));
const SalesIntelligence = lazy(() => import('./SalesIntelligence'));
const AnalyticsDashboard = lazy(() => import('./AnalyticsDashboard'));
const MarketingLab = lazy(() => import('./MarketingLab'));
const StoreSettingsEditor = lazy(() => import('./StoreSettingsEditor'));
const SecuritySettings = lazy(() => import('./SecuritySettings'));
const OnlineStoreSettings = lazy(() => import('./OnlineStoreSettings'));

/**
 * TabbedSection - Renders multiple sections as tabs
 * @param {string[]} tabs - Array of tab IDs to show
 * @param {string} title - Optional title above tabs
 * @param {object} props - Additional props passed to child components
 */
const TabbedSection = ({ tabs = [], title, ...props }) => {
  const [activeTab, setActiveTab] = useState(tabs[0] || '');
  const { activeBrand } = useAdminBrand();
  const TAB_LABELS = getTabLabels(activeBrand);
  
  // Handle "View Store" special case - opens in new tab
  const handleTabClick = (tabId) => {
    if (tabId === 'view-store') {
      window.open('/', '_blank');
      return;
    }
    setActiveTab(tabId);
  };
  
  // Render content based on active tab
  const renderTabContent = () => {
    switch (activeTab) {
      case 'orders':
        return <VirtualizedOrdersTable orders={props.orders || []} loading={props.loading} maxHeight={600} onRefresh={props.onRefresh} />;
      case 'order-flow':
        return <OrderFlowDashboard />;
      case 'products':
        return <VirtualizedProductsTable products={props.products || []} loading={props.loading} onAdd={props.onAdd} onEdit={props.onEdit} onDelete={props.onDelete} />;
      case 'collections':
        return <CollectionsManager />;
      case 'combos':
        return <ComboOffersManager />;
      case 'inventory':
        return <InventoryManager />;
      case 'customers':
        return <VirtualizedCustomersTable customers={props.customers || []} loading={props.loading} />;
      case 'partners':
        return <DataHub initialTab="partners" />;
      case 'founders':
        return <DataHub initialTab="founding" />;
      case 'waitlist':
        return <DataHub initialTab="waitlist" />;
      case 'offers':
        return <OffersManager />;
      case 'loyalty-points':
      case 'redemption':
      case 'birthday-bonus':
      case 'referral-bonus':
        return <LoyaltyPointsManager />;
      case 'reviews':
        return <ReviewsManager />;
      case 'gift-tracking':
        return <GiftTrackingDashboard />;
      case 'templates':
      case '28-day-cycle':
        return <WhatsAppCRMActions />;
      case 'ai-intelligence':
        return <AIIntelligenceHub products={props.products || []} />;
      case 'sales-intelligence':
        return <SalesIntelligence />;
      case 'analytics':
        return <AnalyticsDashboard />;
      case 'marketing-lab':
        return <MarketingLab />;
      case 'settings':
        return <StoreSettingsEditor />;
      case 'security':
        return <SecuritySettings />;
      case 'store':
        return <OnlineStoreSettings />;
      case 'team':
        return <DataHub initialTab="team" />;
      case 'partner-portal':
        return <DataHub initialTab="partners" />;
      default:
        return <div className="text-gray-500 py-8 text-center">Content not available for "{activeTab}"</div>;
    }
  };
  
  if (!tabs || tabs.length === 0) {
    return <div className="text-gray-500">No tabs configured</div>;
  }
  
  return (
    <div className="space-y-4">
      {title && (
        <h1 className="text-2xl font-bold text-[#2D2A2E]" style={{ fontFamily: "'Manrope', sans-serif" }}>
          {title}
        </h1>
      )}
      
      {/* Tab Navigation */}
      <div className="flex gap-1 border-b border-gray-200 pb-px">
        {tabs.map((tabId) => (
          <button
            key={tabId}
            onClick={() => handleTabClick(tabId)}
            className={cn(
              "px-4 py-2 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-1",
              activeTab === tabId
                ? "bg-[#F8A5B8]/20 text-[#2D2A2E] border-b-2 border-[#F8A5B8]"
                : "text-gray-500 hover:text-[#2D2A2E] hover:bg-gray-50"
            )}
            data-testid={`tab-${tabId}`}
          >
            {TAB_LABELS[tabId] || tabId}
            {tabId === 'view-store' && (
              <ExternalLink className="h-3 w-3" />
            )}
          </button>
        ))}
      </div>
      
      {/* Tab Content */}
      <div className="pt-2">
        <Suspense fallback={<LoadingSpinner />}>
          {renderTabContent()}
        </Suspense>
      </div>
    </div>
  );
};

export default TabbedSection;
