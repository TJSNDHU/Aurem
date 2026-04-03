# Google Custom Search API - Setup Guide

## 🎯 Why Google Instead of DuckDuckGo?

**Google Advantages:**
- ✅ **Highest quality results** - Google's powerful search algorithm
- ✅ **100 free queries/day** - Generous free tier
- ✅ **Rich snippets** - Better formatted results with images
- ✅ **Advanced filtering** - Date, language, country filters
- ✅ **Reliable** - 99.9% uptime

**DuckDuckGo Limitations:**
- ❌ Limited data quality
- ❌ Returns JavaScript instead of JSON
- ❌ Only instant answers (no comprehensive results)
- ❌ Poor snippet quality

---

## 🚀 Setup Instructions (5 Minutes)

### Step 1: Get Google API Key

1. Go to: https://console.cloud.google.com/apis/credentials
2. Click **"Create Credentials"** → **"API Key"**
3. Copy your API key: `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX`
4. (Optional) Restrict key to "Custom Search API" for security

**Screenshot Guide:**
```
Google Cloud Console → APIs & Services → Credentials → Create API Key
```

---

### Step 2: Enable Custom Search API

1. Go to: https://console.cloud.google.com/apis/library
2. Search for **"Custom Search API"**
3. Click **"Enable"**

---

### Step 3: Create Programmable Search Engine

1. Go to: https://programmablesearchengine.google.com/
2. Click **"Add"** to create new search engine
3. **Configuration:**
   - **Name**: AUREM Search Engine
   - **What to search**: Search the entire web
   - **Search settings**: Turn ON "Search the entire web"
4. Click **"Create"**
5. Copy your **Search Engine ID (CX)**: `a1b2c3d4e5f6g7h8i9`

**Screenshot Guide:**
```
Programmable Search Engine → Create → Configure → Get Search Engine ID
```

---

### Step 4: Connect to AUREM

```bash
curl -X POST http://localhost:8001/api/connectors/connect \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "google",
    "credentials": {
      "api_key": "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX",
      "search_engine_id": "a1b2c3d4e5f6g7h8i9"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "platform": "google",
  "status": "connected"
}
```

---

## 📊 Usage Examples

### Basic Search

```bash
# Search for AI
GET /api/connectors/web/search?q=artificial+intelligence&limit=10

# Or use POST
POST /api/connectors/fetch
{
  "platform": "google",
  "query": {
    "q": "artificial intelligence",
    "limit": 10
  }
}
```

**Response:**
```json
{
  "query": "artificial intelligence",
  "engine": "google",
  "results": [
    {
      "title": "Artificial Intelligence - Wikipedia",
      "snippet": "Artificial intelligence is intelligence demonstrated by machines...",
      "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
      "displayLink": "en.wikipedia.org",
      "formattedUrl": "https://en.wikipedia.org › wiki › Artificial_intelligence"
    },
    ...
  ]
}
```

---

### Advanced Filtering

```bash
POST /api/connectors/fetch
{
  "platform": "google",
  "query": {
    "q": "machine learning",
    "limit": 10,
    "language": "en",
    "country": "us",
    "date_restrict": "d7"  // Last 7 days only
  }
}
```

**Date Restrict Options:**
- `d1` - Last 24 hours
- `d7` - Last 7 days
- `w1` - Last week
- `m1` - Last month
- `m6` - Last 6 months
- `y1` - Last year

---

### Language & Country Codes

**Languages:**
- `en` - English
- `es` - Spanish
- `fr` - French
- `de` - German
- `zh` - Chinese
- `ja` - Japanese

**Countries:**
- `us` - United States
- `uk` - United Kingdom
- `ca` - Canada
- `au` - Australia
- `in` - India

---

## 💰 Pricing

### Free Tier
- **100 queries per day** - FREE
- **$5 per 1,000 additional queries**
- No credit card required for free tier

### Quota Management
```bash
# Check quota usage
GET /api/connectors/google/quota
```

**Recommended:**
- Cache search results to reduce API calls
- Implement rate limiting (max 100/day)
- Use for important searches only

---

## 🔧 Integration in AUREM

### Store Credentials in Admin Panel

1. Go to: `/admin/mission-control`
2. Navigate to **API Keys** section
3. Add Google credentials:
   ```json
   {
     "service": "google_search",
     "api_key": "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX",
     "search_engine_id": "a1b2c3d4e5f6g7h8i9"
   }
   ```

### Auto-connect on Startup

Add to `.env`:
```env
GOOGLE_SEARCH_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX
GOOGLE_SEARCH_ENGINE_ID=a1b2c3d4e5f6g7h8i9
```

---

## ⚠️ Common Issues & Solutions

### Issue 1: "API key not found"
**Solution:** 
1. Check API key is correctly copied (no extra spaces)
2. Ensure Custom Search API is enabled
3. Wait 2-3 minutes for API activation

### Issue 2: "Quota exceeded"
**Solution:**
- Free tier: 100 queries/day
- Check usage: https://console.cloud.google.com/apis/dashboard
- Implement caching to reduce calls
- Upgrade to paid tier if needed

### Issue 3: "Search engine not found"
**Solution:**
1. Verify Search Engine ID (CX) is correct
2. Ensure "Search the entire web" is enabled
3. Check search engine is active

### Issue 4: "Empty results"
**Solution:**
- Try different search query
- Remove date restrictions
- Check language/country settings

---

## 🎯 Best Practices

### 1. Implement Caching
```python
# Cache search results for 1 hour
cache_key = f"google_search:{query}"
cached_result = await redis.get(cache_key)

if cached_result:
    return cached_result

results = await google_search(query)
await redis.set(cache_key, results, expire=3600)
```

### 2. Rate Limiting
```python
# Track daily quota
daily_count = await redis.incr("google_search_count")
await redis.expire("google_search_count", 86400)  # 24 hours

if daily_count > 95:  # Leave 5 queries buffer
    raise QuotaExceededError("Daily limit reached")
```

### 3. Fallback Strategy
```python
try:
    results = await google_search(query)
except QuotaExceeded:
    # Fallback to cached results or alternative source
    results = await get_cached_results(query)
```

---

## 📈 Performance Metrics

**Google Custom Search:**
- Response time: 200-500ms
- Accuracy: 95%+ relevant results
- Coverage: Billions of web pages
- Freshness: Real-time indexing

**vs DuckDuckGo:**
- Response time: 100-300ms (faster)
- Accuracy: 60-70% (lower quality)
- Coverage: Limited
- Freshness: Delayed

---

## 🔗 Useful Links

- API Console: https://console.cloud.google.com/apis/dashboard
- Create Search Engine: https://programmablesearchengine.google.com/
- API Documentation: https://developers.google.com/custom-search/v1/overview
- Pricing: https://developers.google.com/custom-search/v1/overview#pricing
- Quota Dashboard: https://console.cloud.google.com/apis/api/customsearch.googleapis.com/quotas

---

## ✅ Verification Checklist

Before using Google Search in production:

- [ ] API key created and copied
- [ ] Custom Search API enabled
- [ ] Search engine created (CX obtained)
- [ ] "Search entire web" enabled
- [ ] Test connection successful
- [ ] Credentials stored securely
- [ ] Rate limiting implemented
- [ ] Caching layer added
- [ ] Error handling in place
- [ ] Quota monitoring setup

---

**Setup Time:** 5 minutes  
**Difficulty:** Easy  
**Cost:** FREE (100 queries/day)  
**Recommended:** ⭐⭐⭐⭐⭐ (5/5)
