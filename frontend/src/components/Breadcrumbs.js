import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';
import { Helmet } from 'react-helmet-async';

// Route to breadcrumb name mapping
const routeNames = {
  '': 'Home',
  'shop': 'Shop',
  'products': 'Products',
  'cart': 'Shopping Cart',
  'checkout': 'Checkout',
  'about': 'About Us',
  'science': 'The Science',
  'science-of-pdrn': 'Science of PDRN',
  'waitlist': 'Join Waitlist',
  'founding-member': 'Founding Member',
  'mission-control': 'Mission Control',
  'contact': 'Contact Us',
  'login': 'Login',
  'register': 'Create Account',
  'account': 'My Account',
  'wishlist': 'Wishlist',
  'return-policy': 'Return Policy',
  'shipping-policy': 'Shipping Policy',
  'shipping': 'Shipping',
  'global-shipping': 'Global Shipping',
  'privacy': 'Privacy Policy',
  'terms': 'Terms of Service',
  'become-partner': 'Partner Program',
  'partner-program': 'Partner Program',
  'influencer': 'Influencer Program',
  'partner-login': 'Partner Login',
  'influencer-login': 'Influencer Login',
};

// Generate breadcrumb items from pathname
const generateBreadcrumbs = (pathname, productName = null) => {
  const paths = pathname.split('/').filter(Boolean);
  const breadcrumbs = [{ name: 'Home', path: '/' }];
  
  let currentPath = '';
  paths.forEach((segment, index) => {
    currentPath += `/${segment}`;
    
    // Handle product detail pages
    if (paths[index - 1] === 'products' && !routeNames[segment]) {
      breadcrumbs.push({
        name: productName || 'Product Details',
        path: currentPath,
        isCurrentPage: index === paths.length - 1
      });
    } else if (routeNames[segment]) {
      breadcrumbs.push({
        name: routeNames[segment],
        path: currentPath,
        isCurrentPage: index === paths.length - 1
      });
    }
  });
  
  return breadcrumbs;
};

// Generate JSON-LD structured data for breadcrumbs
const generateBreadcrumbSchema = (breadcrumbs, baseUrl = 'https://reroots.ca') => {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": breadcrumbs.map((crumb, index) => ({
      "@type": "ListItem",
      "position": index + 1,
      "name": crumb.name,
      "item": `${baseUrl}${crumb.path}`
    }))
  };
};

// Visual Breadcrumb Component
export const Breadcrumbs = ({ productName = null, className = '' }) => {
  const location = useLocation();
  const breadcrumbs = generateBreadcrumbs(location.pathname, productName);
  const schema = generateBreadcrumbSchema(breadcrumbs);
  
  // Don't show breadcrumbs on home page
  if (location.pathname === '/') return null;
  
  return (
    <>
      {/* JSON-LD Schema */}
      <Helmet>
        <script type="application/ld+json">
          {JSON.stringify(schema)}
        </script>
      </Helmet>
      
      {/* Visual Breadcrumbs */}
      <nav 
        aria-label="Breadcrumb" 
        className={`py-3 px-4 md:px-6 ${className}`}
      >
        <ol 
          className="flex flex-wrap items-center gap-1 text-sm"
          itemScope 
          itemType="https://schema.org/BreadcrumbList"
        >
          {breadcrumbs.map((crumb, index) => (
            <li 
              key={crumb.path}
              className="flex items-center"
              itemScope
              itemProp="itemListElement"
              itemType="https://schema.org/ListItem"
            >
              {index > 0 && (
                <ChevronRight className="w-4 h-4 mx-1 text-[#888888]" />
              )}
              
              {crumb.isCurrentPage ? (
                <span 
                  className="text-[#5A5A5A] font-medium"
                  itemProp="name"
                >
                  {crumb.name}
                </span>
              ) : (
                <Link
                  to={crumb.path}
                  className="text-[#888888] hover:text-[#D4AF37] transition-colors flex items-center gap-1"
                  itemProp="item"
                >
                  {index === 0 && <Home className="w-3.5 h-3.5" />}
                  <span itemProp="name">{crumb.name}</span>
                </Link>
              )}
              <meta itemProp="position" content={String(index + 1)} />
            </li>
          ))}
        </ol>
      </nav>
    </>
  );
};

// Compact breadcrumb for mobile
export const BreadcrumbsCompact = ({ productName = null }) => {
  const location = useLocation();
  const breadcrumbs = generateBreadcrumbs(location.pathname, productName);
  const schema = generateBreadcrumbSchema(breadcrumbs);
  
  if (location.pathname === '/' || breadcrumbs.length <= 1) return null;
  
  const parentCrumb = breadcrumbs[breadcrumbs.length - 2];
  
  return (
    <>
      <Helmet>
        <script type="application/ld+json">
          {JSON.stringify(schema)}
        </script>
      </Helmet>
      
      <nav aria-label="Breadcrumb" className="py-2 px-4">
        <Link 
          to={parentCrumb.path}
          className="inline-flex items-center gap-1 text-sm text-[#888888] hover:text-[#D4AF37] transition-colors"
        >
          <ChevronRight className="w-4 h-4 rotate-180" />
          <span>Back to {parentCrumb.name}</span>
        </Link>
      </nav>
    </>
  );
};

// Hook to get breadcrumb data
export const useBreadcrumbs = (productName = null) => {
  const location = useLocation();
  return generateBreadcrumbs(location.pathname, productName);
};

export default Breadcrumbs;
