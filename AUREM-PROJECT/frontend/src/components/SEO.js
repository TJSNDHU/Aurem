import React, { useEffect } from 'react';
import { Helmet } from 'react-helmet-async';
import { useLocation } from 'react-router-dom';

const SEO = ({ title, description, keywords, image, url, type = "website", product = null, brand = "reroots", reviews = [] }) => {
  const location = useLocation();
  const baseUrl = "https://reroots.ca";
  
  // Force update canonical on client-side after render
  useEffect(() => {
    const canonicalUrl = url ? `${baseUrl}${url}` : `${baseUrl}${location.pathname}`;
    const existingCanonical = document.querySelector('link[rel="canonical"]');
    if (existingCanonical) {
      existingCanonical.href = canonicalUrl;
    } else {
      const link = document.createElement('link');
      link.rel = 'canonical';
      link.href = canonicalUrl;
      document.head.appendChild(link);
    }
  }, [url, location.pathname]);
  
  // Brand-specific configurations for Open Graph and Schema
  const BRAND_SEO_CONFIG = {
    reroots: {
      siteName: "Reroots Aesthetics Inc. | Canadian Biotech Skincare",
      brandName: "Reroots Aesthetics Inc.",
      defaultImage: "https://customer-assets.emergentagent.com/job_mission-control-84/artifacts/a4671ebm_1767158945864.jpg",
      twitterHandle: "@rerootscanada",
      locale: "en_CA",
      themeColor: "#D4AF37",
      description: "Reroots Aesthetics Inc. presents Aura-Gen: Canada's leading PDRN serum. A 17% Active Recovery Complex with TXA and Argireline for skin longevity. Made in Toronto. 93% visible improvement.",
      keywords: "Reroots Aesthetics Inc, PDRN skincare Canada, Aura-Gen serum, 17% active complex, TXA serum, Argireline Canada, biotech skincare Toronto, anti-aging serum, pigmentation treatment, milia-safe, hormonal skin support"
    },
    oroe: {
      siteName: "OROÉ | Luxury Cellular Skincare",
      brandName: "OROÉ",
      defaultImage: "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=1200",
      twitterHandle: "@oroe_skincare",
      locale: "en_CA",
      themeColor: "#D4AF37",
      description: "OROÉ - Ultra-luxury cellular rejuvenation with EGF & PDRN. Artisan-crafted in Canada for discerning skin. Limited batch releases for VIP members.",
      keywords: "OROÉ, luxury skincare, EGF serum, PDRN Canada, anti-aging, cellular rejuvenation, premium skincare"
    },
    lavela: {
      siteName: "LA VELA BIANCA | Teen Skincare",
      brandName: "LA VELA BIANCA",
      defaultImage: "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=1200",
      twitterHandle: "@La_Vela_Bianca",
      locale: "en_CA",
      themeColor: "#0D4D4D",
      description: "LA VELA BIANCA - Premium pediatric-safe skincare for teens 8-18. Centella Asiatica formulas designed for young, developing skin. Canadian-Italian technology. Milia-safe, hormonal skin support.",
      keywords: "teen skincare, pediatric safe, LA VELA BIANCA, Centella Asiatica, Gen Alpha skincare, safe teen beauty, milia-safe, hormonal skin support"
    }
  };
  
  const brandConfig = BRAND_SEO_CONFIG[brand] || BRAND_SEO_CONFIG.reroots;
  const defaultImage = brandConfig.defaultImage;
  
  const seoTitle = title ? `${title} | ${brandConfig.siteName}` : brandConfig.siteName;
  const seoDescription = description || brandConfig.description;
  const seoKeywords = keywords || brandConfig.keywords;
  const seoImage = image || defaultImage;
  // Use provided URL or fallback to current location pathname
  const canonicalUrl = url ? `${baseUrl}${url}` : `${baseUrl}${location.pathname}`;
  
  // Generate product-specific schema (enhanced with all required fields)
  // Special handling for AURA-GEN products - use full technical title for SEO
  const getProductName = (prod) => {
    if (!prod) return '';
    // If it's an AURA-GEN product, use the full technical title for SEO
    if (prod.slug?.includes('aura-gen') || prod.name?.toLowerCase().includes('aura-gen')) {
      return 'AURA-GEN PDRN + TXA + ARGIRELINE 17.0% Active Recovery Complex';
    }
    return prod.name;
  };
  
  const productSchema = product ? {
    "@context": "https://schema.org/",
    "@type": "Product",
    "name": getProductName(product),
    "image": Array.isArray(product.images) && product.images.length > 0 
      ? product.images 
      : [product.image || seoImage],
    "description": product.description || `${product.name} - Premium skincare product from ${brandConfig.brandName}`,
    "sku": product.id || product.slug,
    "mpn": product.mpn || product.id || product.slug,
    "brand": {
      "@type": "Brand",
      "name": product.brand || brandConfig.brandName
    },
    "offers": {
      "@type": "Offer",
      "url": canonicalUrl,
      "priceCurrency": "CAD",
      "price": typeof product.price === 'number' ? product.price.toFixed(2) : String(product.price || 0),
      "availability": product.stock > 0 || product.allow_preorder 
        ? "https://schema.org/InStock" 
        : "https://schema.org/OutOfStock",
      "itemCondition": "https://schema.org/NewCondition",
      "seller": {
        "@type": "Organization",
        "name": brandConfig.brandName
      },
      "priceValidUntil": "2026-12-31"
    },
    // Add aggregate rating if product has reviews
    ...(product.rating && product.review_count > 0 ? {
      "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": String(product.rating.toFixed ? product.rating.toFixed(1) : product.rating),
        "reviewCount": String(product.review_count),
        "bestRating": "5",
        "worstRating": "1"
      }
    } : {})
  } : null;
  
  // Organization schema
  const organizationSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": brandConfig.siteName,
    "url": baseUrl,
    "logo": seoImage,
    "sameAs": [
      "https://www.instagram.com/rerootscanada",
      "https://www.tiktok.com/@rerootscanada"
    ]
  };
  
  // Website schema with search action
  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": brandConfig.siteName,
    "url": baseUrl,
    "potentialAction": {
      "@type": "SearchAction",
      "target": `${baseUrl}/search?q={search_term_string}`,
      "query-input": "required name=search_term_string"
    }
  };

  // BreadcrumbList schema for product pages
  const breadcrumbSchema = product ? {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {
        "@type": "ListItem",
        "position": 1,
        "name": "Home",
        "item": baseUrl
      },
      {
        "@type": "ListItem",
        "position": 2,
        "name": "Products",
        "item": `${baseUrl}/products`
      },
      {
        "@type": "ListItem",
        "position": 3,
        "name": product.name,
        "item": canonicalUrl
      }
    ]
  } : null;

  // VideoObject schema for AURA-GEN product (Google Video SEO)
  // Exact format for Google Rich Results Video Snippet
  const isAuraGen = product?.slug?.includes('aura-gen') || product?.name?.toLowerCase().includes('aura-gen');
  const videoSchema = isAuraGen ? {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    "name": "Aura-Gen 17.0% Active Recovery Complex Unboxing",
    "description": "A close-up look at the premium packaging and reveal of the Aura-Gen PDRN + TXA + ARGIRELINE 17.0% Active Recovery Complex.",
    "thumbnailUrl": [
      product?.images?.[0] || "https://reroots.ca/images/aura-gen-video-thumb.jpg"
    ],
    "uploadDate": "2026-01-31T21:00:00-05:00",
    "duration": "PT0M07S",
    "contentUrl": "https://reroots.ca/videos/aura-gen-unboxing.mp4",
    "embedUrl": "https://reroots.ca/products/prod-aura-gen",
    "potentialAction": {
      "@type": "SeekAction",
      "target": "https://reroots.ca/products/prod-aura-gen?t={seek_to_second_number}",
      "startOffset-input": "required name=seek_to_second_number"
    }
  } : null;

  return (
    <Helmet>
      {/* Primary Meta Tags */}
      <title>{seoTitle}</title>
      <meta name="title" content={seoTitle} />
      <meta name="description" content={seoDescription} />
      <meta name="keywords" content={seoKeywords} />
      <meta name="author" content={brandConfig.siteName} />
      <meta name="robots" content="index, follow" />
      <meta name="theme-color" content={brandConfig.themeColor} />
      <link rel="canonical" href={canonicalUrl} />
      
      {/* Open Graph / Facebook */}
      <meta property="og:type" content={type === "product" ? "product" : type} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:title" content={seoTitle} />
      <meta property="og:description" content={seoDescription} />
      <meta property="og:image" content={seoImage} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:site_name" content={brandConfig.siteName} />
      <meta property="og:locale" content={brandConfig.locale} />
      
      {/* Product-specific Open Graph tags */}
      {product && (
        <>
          <meta property="product:price:amount" content={product.price} />
          <meta property="product:price:currency" content="CAD" />
          <meta property="product:availability" content={product.stock > 0 ? "in stock" : "out of stock"} />
          <meta property="product:brand" content={product.brand || brandConfig.brandName} />
          <meta property="product:category" content={product.category || "Skincare"} />
        </>
      )}
      
      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content={brandConfig.twitterHandle} />
      <meta name="twitter:url" content={canonicalUrl} />
      <meta name="twitter:title" content={seoTitle} />
      <meta name="twitter:description" content={seoDescription} />
      <meta name="twitter:image" content={seoImage} />
      {product && <meta name="twitter:label1" content="Price" />}
      {product && <meta name="twitter:data1" content={`$${product.price} CAD`} />}
      
      {/* Structured Data - Organization */}
      <script type="application/ld+json">
        {JSON.stringify(organizationSchema)}
      </script>
      
      {/* Structured Data - Website */}
      <script type="application/ld+json">
        {JSON.stringify(websiteSchema)}
      </script>
      
      {/* Structured Data - Product (with full schema) */}
      {productSchema && (
        <script type="application/ld+json">
          {JSON.stringify(productSchema)}
        </script>
      )}
      
      {/* Structured Data - Breadcrumb */}
      {breadcrumbSchema && (
        <script type="application/ld+json">
          {JSON.stringify(breadcrumbSchema)}
        </script>
      )}
      
      {/* Structured Data - VideoObject (AURA-GEN only) */}
      {videoSchema && (
        <script type="application/ld+json">
          {JSON.stringify(videoSchema)}
        </script>
      )}
    </Helmet>
  );
};

export default SEO;
