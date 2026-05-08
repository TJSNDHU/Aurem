/**
 * ORA Web Pixel — AUREM Shopify Tracking Sandbox
 * Runs in Shopify's secure Web Pixel sandbox.
 * Captures: page_viewed, product_viewed, add_to_cart, checkout_started, checkout_completed
 * Batches events and sends to AUREM backend every 5 seconds.
 */

const AUREM_ENDPOINT = '{{settings.aurem_backend_url}}/api/shopify-app/pixel/events';
const BATCH_INTERVAL = 5000;
const MAX_BATCH = 20;

let eventQueue = [];
let batchTimer = null;

function flushEvents() {
  if (eventQueue.length === 0) return;
  const batch = eventQueue.splice(0, MAX_BATCH);
  
  fetch(AUREM_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ events: batch }),
    keepalive: true
  }).catch(() => {
    // Re-queue on failure (max 1 retry)
    eventQueue.unshift(...batch.slice(0, 5));
  });
}

function queueEvent(eventType, data) {
  eventQueue.push({
    event_type: eventType,
    shop_domain: self.shopify?.shop?.domain || '',
    customer_id: data.customer_id || null,
    product_id: data.product_id || null,
    product_title: data.product_title || null,
    variant_id: data.variant_id || null,
    collection_id: data.collection_id || null,
    search_query: data.search_query || null,
    cart_value: data.cart_value || null,
    currency: data.currency || 'CAD',
    page_url: data.page_url || null,
    referrer: data.referrer || null,
    metadata: data.metadata || {}
  });
  
  if (eventQueue.length >= MAX_BATCH) {
    flushEvents();
  }
}

// Start batch timer
batchTimer = setInterval(flushEvents, BATCH_INTERVAL);

// ─── Event Subscriptions ─────────────────────────────────────

analytics.subscribe('page_viewed', (event) => {
  queueEvent('page_viewed', {
    page_url: event.context?.document?.location?.href,
    referrer: event.context?.document?.referrer
  });
});

analytics.subscribe('product_viewed', (event) => {
  const product = event.data?.productVariant?.product;
  queueEvent('product_viewed', {
    product_id: product?.id,
    product_title: product?.title,
    variant_id: event.data?.productVariant?.id,
    page_url: event.context?.document?.location?.href
  });
});

analytics.subscribe('product_added_to_cart', (event) => {
  const line = event.data?.cartLine;
  queueEvent('add_to_cart', {
    product_id: line?.merchandise?.product?.id,
    product_title: line?.merchandise?.product?.title,
    variant_id: line?.merchandise?.id,
    cart_value: parseFloat(line?.cost?.totalAmount?.amount || 0),
    currency: line?.cost?.totalAmount?.currencyCode
  });
});

analytics.subscribe('checkout_started', (event) => {
  const checkout = event.data?.checkout;
  queueEvent('checkout_started', {
    cart_value: parseFloat(checkout?.totalPrice?.amount || 0),
    currency: checkout?.totalPrice?.currencyCode,
    metadata: { line_items: checkout?.lineItems?.length || 0 }
  });
});

analytics.subscribe('checkout_completed', (event) => {
  const checkout = event.data?.checkout;
  queueEvent('checkout_completed', {
    cart_value: parseFloat(checkout?.totalPrice?.amount || 0),
    currency: checkout?.totalPrice?.currencyCode,
    customer_id: checkout?.email || null,
    metadata: {
      order_id: checkout?.order?.id,
      line_items: checkout?.lineItems?.length || 0
    }
  });
  // Flush immediately on checkout
  flushEvents();
});

analytics.subscribe('collection_viewed', (event) => {
  const collection = event.data?.collection;
  queueEvent('collection_viewed', {
    collection_id: collection?.id,
    product_title: collection?.title,
    page_url: event.context?.document?.location?.href
  });
});

analytics.subscribe('search_submitted', (event) => {
  queueEvent('search_submitted', {
    search_query: event.data?.searchResult?.query,
    page_url: event.context?.document?.location?.href
  });
});
