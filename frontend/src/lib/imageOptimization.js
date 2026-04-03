/**
 * Image Optimization Utility for 2026 Performance Standards
 * Supports: Cloudinary CDN (primary), Unsplash, Pexels, and other CDNs
 */

// Cloudinary configuration
const CLOUDINARY_CLOUD_NAME = 'ddpphzqdg';

/**
 * Optimize image URL using Cloudinary fetch (works with any URL)
 * @param {string} url - Original image URL
 * @param {number} width - Target width
 * @param {number} quality - Quality (1-100 or 'auto')
 * @param {string} format - Output format ('auto', 'webp', 'avif')
 * @returns {string} - Cloudinary optimized URL
 */
export const optimizeWithCloudinary = (url, width = 800, quality = 'auto', format = 'auto') => {
  if (!url || !CLOUDINARY_CLOUD_NAME) return url;
  
  try {
    // Skip if already a Cloudinary URL
    if (url.includes('cloudinary.com')) {
      return url;
    }
    
    // Skip data URLs and blob URLs
    if (url.startsWith('data:') || url.startsWith('blob:')) {
      return url;
    }
    
    // Build transformation string
    const transforms = [`w_${width}`, `q_${quality}`, `f_${format}`, 'c_fill'];
    const transformStr = transforms.join(',');
    
    // Use Cloudinary fetch to optimize any external URL
    const encodedUrl = encodeURIComponent(url);
    return `https://res.cloudinary.com/${CLOUDINARY_CLOUD_NAME}/image/fetch/${transformStr}/${encodedUrl}`;
  } catch (e) {
    console.warn('Cloudinary optimization failed:', e);
    return url;
  }
};

/**
 * Optimize image URL with size parameters where supported
 * Uses Cloudinary for external URLs, native params for CDNs
 * @param {string} url - Original image URL
 * @param {number} width - Target width
 * @param {number} quality - Quality (1-100)
 * @returns {string} - Optimized image URL
 */
export const optimizeImageUrl = (url, width = 800, quality = 80) => {
  if (!url) return url;
  
  try {
    // Skip data URLs and blob URLs
    if (url.startsWith('data:') || url.startsWith('blob:')) {
      return url;
    }
    
    const urlObj = new URL(url);
    const hostname = urlObj.hostname;
    
    // Already a Cloudinary URL - add/update transforms
    if (hostname.includes('cloudinary.com')) {
      // If it's a fetch URL, it already has transforms
      if (url.includes('/fetch/')) {
        return url;
      }
      // For uploaded images, add transforms
      const parts = url.split('/upload/');
      if (parts.length === 2) {
        return `${parts[0]}/upload/w_${width},q_auto,f_auto,c_fill/${parts[1]}`;
      }
      return url;
    }
    
    // Unsplash - use native params (faster than Cloudinary fetch)
    if (hostname.includes('unsplash.com')) {
      urlObj.searchParams.set('w', width.toString());
      urlObj.searchParams.set('q', quality.toString());
      urlObj.searchParams.set('auto', 'format');
      urlObj.searchParams.set('fit', 'crop');
      urlObj.searchParams.set('fm', 'webp');
      return urlObj.toString();
    }
    
    // Pexels - use native params
    if (hostname.includes('images.pexels.com')) {
      urlObj.searchParams.set('auto', 'compress');
      urlObj.searchParams.set('cs', 'tinysrgb');
      urlObj.searchParams.set('w', width.toString());
      urlObj.searchParams.set('fm', 'webp');
      return urlObj.toString();
    }
    
    // ImageKit - use native params
    if (hostname.includes('imagekit.io') || hostname.includes('ik.imagekit.io')) {
      urlObj.searchParams.set('tr', `w-${width},q-${quality},f-auto`);
      return urlObj.toString();
    }
    
    // For all other sources, use Cloudinary fetch for optimization
    return optimizeWithCloudinary(url, width, 'auto', 'auto');
  } catch (e) {
    // If URL parsing fails, try Cloudinary fetch anyway
    return optimizeWithCloudinary(url, width, 'auto', 'auto');
  }
};

/**
 * Get WebP version of image URL using Cloudinary
 * @param {string} url - Original image URL
 * @param {number} width - Target width
 * @returns {string} - WebP optimized URL
 */
export const getWebPUrl = (url, width = 800) => {
  if (!url) return url;
  
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname;
    
    // Cloudinary URL
    if (hostname.includes('cloudinary.com')) {
      const parts = url.split('/upload/');
      if (parts.length === 2) {
        return `${parts[0]}/upload/w_${width},f_webp,q_auto/${parts[1]}`;
      }
    }
    
    // Unsplash
    if (hostname.includes('unsplash.com')) {
      urlObj.searchParams.set('w', width.toString());
      urlObj.searchParams.set('fm', 'webp');
      urlObj.searchParams.set('q', '80');
      return urlObj.toString();
    }
    
    // Use Cloudinary fetch for other URLs
    return optimizeWithCloudinary(url, width, 'auto', 'webp');
  } catch (e) {
    return optimizeWithCloudinary(url, width, 'auto', 'webp');
  }
};

/**
 * Get AVIF version of image URL using Cloudinary
 * @param {string} url - Original image URL
 * @param {number} width - Target width
 * @returns {string} - AVIF optimized URL (with WebP fallback handled by f_auto)
 */
export const getAVIFUrl = (url, width = 800) => {
  if (!url) return url;
  return optimizeWithCloudinary(url, width, 'auto', 'avif');
};

/**
 * Get responsive image srcSet for different screen sizes
 * @param {string} url - Original image URL
 * @returns {string} - srcSet string
 */
export const getResponsiveSrcSet = (url) => {
  if (!url) return '';
  
  const sizes = [320, 480, 640, 800, 1024];
  const srcSet = sizes.map(size => {
    const optimized = optimizeImageUrl(url, size, 80);
    return `${optimized} ${size}w`;
  }).join(', ');
  
  return srcSet;
};

/**
 * Get placeholder blur data URL (tiny base64 image)
 * @returns {string} - Base64 placeholder
 */
export const getPlaceholderBlur = () => {
  return 'data:image/gif;base64,R0lGODlhAQABAIAAAMLCwgAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==';
};

/**
 * Check if browser supports WebP
 * @returns {boolean}
 */
export const supportsWebP = () => {
  if (typeof window === 'undefined') return false;
  
  const canvas = document.createElement('canvas');
  if (canvas.getContext && canvas.getContext('2d')) {
    return canvas.toDataURL('image/webp').indexOf('data:image/webp') === 0;
  }
  return false;
};

/**
 * Check if browser supports AVIF
 * @returns {Promise<boolean>}
 */
export const supportsAVIF = async () => {
  if (typeof window === 'undefined') return false;
  
  return new Promise((resolve) => {
    const avifImage = new Image();
    avifImage.onload = () => resolve(true);
    avifImage.onerror = () => resolve(false);
    avifImage.src = 'data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAAB0AAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAIAAAACAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQ0MAAAAABNjb2xybmNseAACAAIAAYAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAACVtZGF0EgAKBzgADlAgIGkyCR/wAABAAACvcA==';
  });
};

/**
 * Upload image to Cloudinary via backend
 * @param {File} file - File to upload
 * @param {string} folder - Cloudinary folder
 * @returns {Promise<object>} - Upload result with URLs
 */
export const uploadToCloudinary = async (file, folder = 'reroots/products') => {
  const API_URL = typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') 
    ? 'https://reroots.ca' 
    : (process.env.REACT_APP_BACKEND_URL || window.location.origin);
  
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(`${API_URL}/api/cloudinary/upload?folder=${encodeURIComponent(folder)}`, {
    method: 'POST',
    body: formData
  });
  
  if (!response.ok) {
    throw new Error('Upload failed');
  }
  
  return response.json();
};

export default {
  optimizeImageUrl,
  optimizeWithCloudinary,
  getWebPUrl,
  getAVIFUrl,
  getResponsiveSrcSet,
  getPlaceholderBlur,
  supportsWebP,
  supportsAVIF,
  uploadToCloudinary
};
