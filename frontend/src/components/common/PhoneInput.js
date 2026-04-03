import React, { useState, useEffect } from 'react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { ChevronDown, Phone } from 'lucide-react';

// Country/region configuration with phone codes
export const COUNTRY_CODES = [
  { code: 'CA', name: 'Canada', phoneCode: '+1', flag: '🇨🇦' },
  { code: 'US', name: 'USA', phoneCode: '+1', flag: '🇺🇸' },
  { code: 'GB', name: 'UK', phoneCode: '+44', flag: '🇬🇧' },
  { code: 'FR', name: 'France', phoneCode: '+33', flag: '🇫🇷' },
  { code: 'DE', name: 'Germany', phoneCode: '+49', flag: '🇩🇪' },
  { code: 'IT', name: 'Italy', phoneCode: '+39', flag: '🇮🇹' },
  { code: 'ES', name: 'Spain', phoneCode: '+34', flag: '🇪🇸' },
  { code: 'AU', name: 'Australia', phoneCode: '+61', flag: '🇦🇺' },
  { code: 'NZ', name: 'New Zealand', phoneCode: '+64', flag: '🇳🇿' },
  { code: 'IN', name: 'India', phoneCode: '+91', flag: '🇮🇳' },
  { code: 'PK', name: 'Pakistan', phoneCode: '+92', flag: '🇵🇰' },
  { code: 'AE', name: 'UAE', phoneCode: '+971', flag: '🇦🇪' },
  { code: 'SA', name: 'Saudi Arabia', phoneCode: '+966', flag: '🇸🇦' },
  { code: 'SG', name: 'Singapore', phoneCode: '+65', flag: '🇸🇬' },
  { code: 'MY', name: 'Malaysia', phoneCode: '+60', flag: '🇲🇾' },
  { code: 'PH', name: 'Philippines', phoneCode: '+63', flag: '🇵🇭' },
  { code: 'MX', name: 'Mexico', phoneCode: '+52', flag: '🇲🇽' },
  { code: 'BR', name: 'Brazil', phoneCode: '+55', flag: '🇧🇷' },
  { code: 'JP', name: 'Japan', phoneCode: '+81', flag: '🇯🇵' },
  { code: 'KR', name: 'South Korea', phoneCode: '+82', flag: '🇰🇷' },
  { code: 'CN', name: 'China', phoneCode: '+86', flag: '🇨🇳' },
  { code: 'HK', name: 'Hong Kong', phoneCode: '+852', flag: '🇭🇰' },
  { code: 'TW', name: 'Taiwan', phoneCode: '+886', flag: '🇹🇼' },
  { code: 'TH', name: 'Thailand', phoneCode: '+66', flag: '🇹🇭' },
  { code: 'VN', name: 'Vietnam', phoneCode: '+84', flag: '🇻🇳' },
  { code: 'ID', name: 'Indonesia', phoneCode: '+62', flag: '🇮🇩' },
  { code: 'ZA', name: 'South Africa', phoneCode: '+27', flag: '🇿🇦' },
  { code: 'NG', name: 'Nigeria', phoneCode: '+234', flag: '🇳🇬' },
  { code: 'EG', name: 'Egypt', phoneCode: '+20', flag: '🇪🇬' },
  { code: 'TR', name: 'Turkey', phoneCode: '+90', flag: '🇹🇷' },
  { code: 'RU', name: 'Russia', phoneCode: '+7', flag: '🇷🇺' },
  { code: 'NL', name: 'Netherlands', phoneCode: '+31', flag: '🇳🇱' },
  { code: 'BE', name: 'Belgium', phoneCode: '+32', flag: '🇧🇪' },
  { code: 'SE', name: 'Sweden', phoneCode: '+46', flag: '🇸🇪' },
  { code: 'NO', name: 'Norway', phoneCode: '+47', flag: '🇳🇴' },
  { code: 'DK', name: 'Denmark', phoneCode: '+45', flag: '🇩🇰' },
  { code: 'FI', name: 'Finland', phoneCode: '+358', flag: '🇫🇮' },
  { code: 'PL', name: 'Poland', phoneCode: '+48', flag: '🇵🇱' },
  { code: 'IE', name: 'Ireland', phoneCode: '+353', flag: '🇮🇪' },
  { code: 'PT', name: 'Portugal', phoneCode: '+351', flag: '🇵🇹' },
  { code: 'GR', name: 'Greece', phoneCode: '+30', flag: '🇬🇷' },
  { code: 'IL', name: 'Israel', phoneCode: '+972', flag: '🇮🇱' },
  { code: 'AR', name: 'Argentina', phoneCode: '+54', flag: '🇦🇷' },
  { code: 'CL', name: 'Chile', phoneCode: '+56', flag: '🇨🇱' },
  { code: 'CO', name: 'Colombia', phoneCode: '+57', flag: '🇨🇴' },
  { code: 'PE', name: 'Peru', phoneCode: '+51', flag: '🇵🇪' },
];

// Detect country from browser timezone/locale
export const detectUserCountry = () => {
  try {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    const locale = navigator.language || 'en-CA';
    
    // Timezone-based detection
    if (timezone.includes('America/Toronto') || timezone.includes('America/Vancouver') || timezone.includes('Canada')) return 'CA';
    if (timezone.includes('America/New_York') || timezone.includes('America/Los_Angeles') || timezone.includes('America/Chicago')) return 'US';
    if (timezone.includes('Europe/London')) return 'GB';
    if (timezone.includes('Europe/Paris')) return 'FR';
    if (timezone.includes('Europe/Berlin')) return 'DE';
    if (timezone.includes('Europe/Rome')) return 'IT';
    if (timezone.includes('Europe/Madrid')) return 'ES';
    if (timezone.includes('Australia')) return 'AU';
    if (timezone.includes('Pacific/Auckland')) return 'NZ';
    if (timezone.includes('Asia/Kolkata') || timezone.includes('Asia/Mumbai')) return 'IN';
    if (timezone.includes('Asia/Karachi')) return 'PK';
    if (timezone.includes('Asia/Dubai')) return 'AE';
    if (timezone.includes('Asia/Singapore')) return 'SG';
    if (timezone.includes('Asia/Manila')) return 'PH';
    if (timezone.includes('America/Mexico')) return 'MX';
    if (timezone.includes('Asia/Tokyo')) return 'JP';
    if (timezone.includes('Asia/Seoul')) return 'KR';
    if (timezone.includes('Asia/Shanghai') || timezone.includes('Asia/Beijing')) return 'CN';
    if (timezone.includes('Asia/Hong_Kong')) return 'HK';
    
    // Fallback to locale
    const localeLower = locale.toLowerCase();
    if (localeLower.startsWith('en-ca')) return 'CA';
    if (localeLower.startsWith('en-us')) return 'US';
    if (localeLower.startsWith('en-gb')) return 'GB';
    if (localeLower.startsWith('en-au')) return 'AU';
    if (localeLower.startsWith('en-in') || localeLower.startsWith('hi')) return 'IN';
    if (localeLower.startsWith('fr-ca')) return 'CA';
    if (localeLower.startsWith('fr')) return 'FR';
    if (localeLower.startsWith('de')) return 'DE';
    if (localeLower.startsWith('es-mx')) return 'MX';
    if (localeLower.startsWith('es')) return 'ES';
    if (localeLower.startsWith('pt-br')) return 'BR';
    if (localeLower.startsWith('pt')) return 'PT';
    if (localeLower.startsWith('ja')) return 'JP';
    if (localeLower.startsWith('ko')) return 'KR';
    if (localeLower.startsWith('zh')) return 'CN';
    
    return 'CA'; // Default to Canada
  } catch (e) {
    return 'CA';
  }
};

// Get country config by code
export const getCountryByCode = (code) => {
  return COUNTRY_CODES.find(c => c.code === code) || COUNTRY_CODES[0];
};

// Get country config by phone code
export const getCountryByPhoneCode = (phoneCode) => {
  return COUNTRY_CODES.find(c => c.phoneCode === phoneCode) || COUNTRY_CODES[0];
};

// Format full phone number
export const formatFullPhone = (countryCode, phone) => {
  if (!phone) return '';
  const cleanPhone = phone.replace(/^0+/, '').replace(/\D/g, '');
  return `${countryCode}${cleanPhone}`;
};

/**
 * PhoneInput Component
 * Reusable phone input with country code dropdown and auto-detection
 */
const PhoneInput = ({ 
  value, 
  onChange, 
  countryCode, 
  onCountryCodeChange,
  placeholder = "Phone number",
  required = false,
  className = "",
  inputClassName = "",
  darkMode = false,
  disabled = false,
  testId = "phone-input"
}) => {
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCountry, setSelectedCountry] = useState(null);

  // Auto-detect country on mount
  useEffect(() => {
    if (!countryCode) {
      const detectedCode = detectUserCountry();
      const country = getCountryByCode(detectedCode);
      setSelectedCountry(country);
      onCountryCodeChange?.(country.phoneCode);
    } else {
      const country = getCountryByPhoneCode(countryCode);
      setSelectedCountry(country);
    }
  }, []);

  // Update selected country when countryCode prop changes
  useEffect(() => {
    if (countryCode) {
      const country = getCountryByPhoneCode(countryCode);
      setSelectedCountry(country);
    }
  }, [countryCode]);

  const filteredCountries = COUNTRY_CODES.filter(c => 
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.phoneCode.includes(searchQuery) ||
    c.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCountrySelect = (country) => {
    setSelectedCountry(country);
    onCountryCodeChange?.(country.phoneCode);
    setShowDropdown(false);
    setSearchQuery('');
  };

  const baseStyles = darkMode 
    ? "bg-white/5 border-white/10 text-white placeholder:text-white/50" 
    : "bg-white border-gray-200 text-gray-900";
  
  const dropdownStyles = darkMode
    ? "bg-[#1a1a2e] border-white/20"
    : "bg-white border-gray-200 shadow-lg";

  return (
    <div className={`relative ${className}`}>
      <div className="flex">
        {/* Country Code Selector */}
        <Button
          type="button"
          variant="outline"
          onClick={() => !disabled && setShowDropdown(!showDropdown)}
          className={`rounded-r-none border-r-0 px-2 h-10 min-w-[90px] ${baseStyles} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          disabled={disabled}
          data-testid={`${testId}-country-selector`}
        >
          <span className="text-lg mr-1">{selectedCountry?.flag || '🌍'}</span>
          <span className="text-sm font-mono">{selectedCountry?.phoneCode || '+1'}</span>
          <ChevronDown className="h-3 w-3 ml-1 opacity-50" />
        </Button>

        {/* Phone Number Input */}
        <Input
          type="tel"
          value={value}
          onChange={(e) => onChange(e.target.value.replace(/[^\d]/g, ''))}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          className={`rounded-l-none flex-1 ${baseStyles} ${inputClassName}`}
          data-testid={testId}
        />
      </div>

      {/* Country Dropdown */}
      {showDropdown && (
        <div className={`absolute top-full left-0 right-0 mt-1 z-50 rounded-lg border max-h-64 overflow-hidden ${dropdownStyles}`}>
          {/* Search */}
          <div className="p-2 border-b border-inherit">
            <Input
              type="text"
              placeholder="Search country..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={`h-8 text-sm ${baseStyles}`}
              autoFocus
              data-testid={`${testId}-search`}
            />
          </div>
          
          {/* Country List */}
          <div className="max-h-48 overflow-y-auto">
            {filteredCountries.map((country) => (
              <button
                key={country.code}
                type="button"
                onClick={() => handleCountrySelect(country)}
                className={`w-full px-3 py-2 text-left flex items-center gap-2 hover:bg-gray-100 dark:hover:bg-white/10 transition-colors ${
                  selectedCountry?.code === country.code ? 'bg-gray-50 dark:bg-white/5' : ''
                }`}
                data-testid={`${testId}-country-${country.code}`}
              >
                <span className="text-lg">{country.flag}</span>
                <span className={`flex-1 text-sm ${darkMode ? 'text-white' : 'text-gray-900'}`}>
                  {country.name}
                </span>
                <span className={`text-sm font-mono ${darkMode ? 'text-white/60' : 'text-gray-500'}`}>
                  {country.phoneCode}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Click outside to close */}
      {showDropdown && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={() => setShowDropdown(false)}
        />
      )}
    </div>
  );
};

export default PhoneInput;
