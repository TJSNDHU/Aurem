# 🤖 AUREM Widget - FULLY AUTOMATED Theme Detection

## ✨ What Makes It "Fully Automated"

Your widget is now **INTELLIGENT** - it automatically adapts to ANY website without manual configuration!

---

## 🎨 AUTOMATIC THEME DETECTION

### **What It Auto-Detects:**

1. **✅ Dark/Light Mode**
   - Analyzes website background color
   - Detects if site uses dark or light theme
   - Adjusts widget colors accordingly

2. **✅ Primary Brand Color**
   - Scans CSS variables (`--primary-color`, `--brand-color`, `--theme-color`)
   - Analyzes button colors
   - Checks link colors
   - Reads header/nav colors
   - **Automatically matches your brand!**

3. **✅ Accent Colors**
   - Auto-generates complementary accent shade
   - Creates harmonious color palette
   - Ensures proper contrast

4. **✅ Text Colors**
   - Auto-calculates readable text colors
   - Ensures accessibility (WCAG compliant)
   - Adapts to light/dark backgrounds

5. **✅ Responsive Width & Height**
   - **Mobile (< 480px):** Full width (100vw)
   - **Small Tablet (480-768px):** 90% width
   - **Tablet (768-1024px):** 400px fixed
   - **Desktop (> 1024px):** 420px fixed
   - **Height:** Adapts to screen size (600-650px)

6. **✅ Smart Positioning**
   - Detects if bottom-right is cluttered
   - Automatically switches to bottom-left if needed
   - Avoids overlapping with existing elements

---

## 📝 USAGE EXAMPLES

### **Minimal Integration (100% Auto)**
```html
<!-- Just API key - everything else is AUTO-DETECTED! -->
<script src="https://aurem.live/widget.js" 
        data-api-key="sk_aurem_live_xxxxx"></script>
```

**Result:**
- ✅ Auto-detects your website colors
- ✅ Auto-detects dark/light mode
- ✅ Auto-positions widget
- ✅ Auto-sizes for responsive
- ✅ Matches your brand perfectly!

---

### **Manual Override (Optional)**
```html
<!-- Override auto-detection if needed -->
<script src="https://aurem.live/widget.js" 
        data-api-key="sk_aurem_live_xxxxx"
        data-color="#FF5733"
        data-position="bottom-left"></script>
```

---

## 🎯 HOW AUTO-DETECTION WORKS

### **1. Dark/Light Mode Detection**
```javascript
// Analyzes body background
const bodyBg = window.getComputedStyle(document.body).backgroundColor;
const lightness = calculateLightness(bodyBg);

if (lightness < 50) {
  // Dark mode detected
  widgetBg = '#0A0A0A';
  textColor = '#FFFFFF';
} else {
  // Light mode detected
  widgetBg = '#FFFFFF';
  textColor = '#1A1A1A';
}
```

### **2. Brand Color Detection**
```javascript
// Priority order:
1. CSS variable: --primary-color
2. CSS variable: --brand-color
3. CSS variable: --theme-color
4. Button background colors
5. Link colors
6. Header/nav colors
7. Fallback: #D4AF37 (gold)
```

### **3. Responsive Sizing**
```javascript
Screen < 480px  → width: 100vw (full screen mobile)
Screen 480-768px → width: 90vw (tablet)
Screen 768-1024px → width: 400px (large tablet)
Screen > 1024px  → width: 420px (desktop)
```

---

## 🌈 THEME EXAMPLES

### **Example 1: Dark E-commerce Site**
**Website:** Dark background (#1A1A1A), Red buttons (#E63946)

**Widget Auto-Adapts:**
- Button: Red gradient (#E63946 → darker shade)
- Window: Dark (#0A0A0A)
- Messages: Dark gray (#1A1A1A)
- Text: White (#FFFFFF)
- **Looks native to the site!**

---

### **Example 2: Light Corporate Site**
**Website:** White background (#FFFFFF), Blue brand (#0077B6)

**Widget Auto-Adapts:**
- Button: Blue gradient (#0077B6 → darker shade)
- Window: White (#FFFFFF)
- Messages: Light gray (#F5F5F5)
- Text: Dark (#1A1A1A)
- **Matches corporate branding!**

---

### **Example 3: Purple Startup Site**
**Website:** Purple theme (#7209B7), Dark mode

**Widget Auto-Adapts:**
- Button: Purple gradient (#7209B7 → darker)
- Window: Dark (#0A0A0A)
- Messages: Dark (#1A1A1A)
- Text: White
- **On-brand automatically!**

---

## 🔍 DETECTION FALLBACKS

**If auto-detection fails:**
1. Uses sensible defaults (gold button, dark theme)
2. Logs detection results to console for debugging
3. Allows manual override via data attributes

---

## 📱 RESPONSIVE BEHAVIOR

### **Mobile Devices**
- Full-width chat window (100vw)
- Adjusts to screen height
- Touch-optimized buttons
- Smooth animations

### **Tablets**
- 90% width on small tablets
- Fixed 400px on large tablets
- Portrait & landscape support

### **Desktop**
- Fixed 420px width
- 650px height
- Hover effects
- Smooth transitions

---

## 🎨 COLOR SCIENCE

### **Contrast Calculation**
Widget automatically ensures:
- Text on buttons is readable (white or black based on lightness)
- Messages have proper contrast ratios
- WCAG AA compliance

### **Lightness Formula**
```javascript
lightness = (0.299 * R) + (0.587 * G) + (0.114 * B)

if (lightness > 128) {
  textColor = '#000000'; // Dark text on light background
} else {
  textColor = '#FFFFFF'; // Light text on dark background
}
```

---

## 🚀 TESTING THE AUTO-THEME

### **Test on Different Sites:**

1. **Dark Site:**
   ```html
   <body style="background: #1A1A1A;">
     <script src="https://aurem.live/widget.js" 
             data-api-key="sk_aurem_live_xxxxx"></script>
   </body>
   ```
   **Result:** Widget uses dark theme automatically

2. **Light Site:**
   ```html
   <body style="background: #FFFFFF;">
     <script src="https://aurem.live/widget.js" 
             data-api-key="sk_aurem_live_xxxxx"></script>
   </body>
   ```
   **Result:** Widget uses light theme automatically

3. **Branded Site:**
   ```html
   <style>
     :root {
       --primary-color: #FF6B6B;
     }
   </style>
   <script src="https://aurem.live/widget.js" 
           data-api-key="sk_aurem_live_xxxxx"></script>
   ```
   **Result:** Widget button is red (#FF6B6B)

---

## 🐛 DEBUGGING

**Check Console Logs:**
```javascript
[AUREM Widget] Auto-detected theme: {
  isDarkMode: true,
  primaryColor: "#E63946",
  backgroundColor: "rgb(26, 26, 26)",
  textColor: "#FFFFFF",
  accentColor: "#b82d3a"
}

[AUREM Widget] Final config: {
  position: "bottom-right",
  color: "#E63946",
  width: "420px",
  height: "650px"
}
```

---

## ✅ SUMMARY

**No Configuration Needed:**
- ✅ Detects dark/light mode
- ✅ Matches brand colors
- ✅ Responsive sizing
- ✅ Smart positioning
- ✅ Accessible contrast
- ✅ Beautiful animations

**One Line of Code:**
```html
<script src="https://aurem.live/widget.js" 
        data-api-key="sk_aurem_live_xxxxx"></script>
```

**Result:** Professional AI chat that looks native to ANY website! 🎉

---

## 🎯 YOUR API KEY

```
🔑 sk_aurem_live_ee4befd0f507dd05fe5a9a09d956f552
```

**Test it now on any website - it will automatically match the theme!**
