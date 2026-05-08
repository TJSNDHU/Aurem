/**
 * Pretext.js integration for ORA Chat
 * Zero-reflow text height measurement for virtual message scrolling.
 * Uses pure arithmetic — no DOM reads, no layout thrashing.
 */

import { prepare, layout } from '@chenglou/pretext';

// Cache prepared text measurements (keyed by content hash)
const prepareCache = new Map();

/**
 * Measure a chat message height without DOM access.
 * @param {string} text - Message content
 * @param {number} containerWidth - Available width in pixels (minus padding)
 * @param {object} options - Font and line height options
 * @returns {Promise<{height: number, lineCount: number}>}
 */
export async function measureMessageHeight(text, containerWidth, options = {}) {
  const {
    font = '14px Jost',
    lineHeight = 22,
    paddingY = 32, // top + bottom padding on bubble
  } = options;

  if (!text || containerWidth <= 0) {
    return { height: paddingY + lineHeight, lineCount: 1 };
  }

  // Prepare (cached per unique text + font combo)
  const cacheKey = `${text.slice(0, 100)}_${text.length}_${font}`;
  let prepared = prepareCache.get(cacheKey);
  if (!prepared) {
    try {
      prepared = await prepare(text, font);
      prepareCache.set(cacheKey, prepared);
      // Limit cache size
      if (prepareCache.size > 500) {
        const firstKey = prepareCache.keys().next().value;
        prepareCache.delete(firstKey);
      }
    } catch {
      // Fallback: estimate based on character count
      const charsPerLine = Math.floor(containerWidth / 8);
      const lineCount = Math.ceil(text.length / charsPerLine);
      return { height: paddingY + lineCount * lineHeight, lineCount };
    }
  }

  // Layout — pure math, call freely
  try {
    const result = layout(prepared, containerWidth, lineHeight);
    return {
      height: paddingY + (result.height || result.lineCount * lineHeight),
      lineCount: result.lineCount || 1,
    };
  } catch {
    const charsPerLine = Math.floor(containerWidth / 8);
    const lineCount = Math.ceil(text.length / charsPerLine);
    return { height: paddingY + lineCount * lineHeight, lineCount };
  }
}

/**
 * Batch-measure multiple messages for virtual list rendering.
 * @param {Array<{content: string, role: string}>} messages
 * @param {number} containerWidth
 * @returns {Promise<Array<{height: number, lineCount: number, offset: number}>>}
 */
export async function measureMessages(messages, containerWidth) {
  const measurements = [];
  let offset = 0;

  for (const msg of messages) {
    const width = msg.role === 'user'
      ? containerWidth * 0.8 - 32  // user bubble: 80% max width, minus padding
      : containerWidth * 0.8 - 32; // assistant bubble: same

    const { height, lineCount } = await measureMessageHeight(
      msg.content || '',
      width,
      { font: msg.role === 'user' ? '14px Jost' : '14px Jost' }
    );

    // Add extra height for metadata (assistant messages have feedback buttons, freshness, etc.)
    const metaHeight = msg.role === 'assistant' ? 40 : 0;
    const totalHeight = height + metaHeight + 16; // 16px gap between messages

    measurements.push({ height: totalHeight, lineCount, offset });
    offset += totalHeight;
  }

  return measurements;
}

/**
 * Get total scroll height for all messages.
 * @param {Array} measurements - Output from measureMessages
 * @returns {number}
 */
export function getTotalHeight(measurements) {
  if (!measurements.length) return 0;
  const last = measurements[measurements.length - 1];
  return last.offset + last.height;
}

/**
 * Get visible message indices for a given scroll position.
 * @param {Array} measurements
 * @param {number} scrollTop
 * @param {number} viewportHeight
 * @returns {{start: number, end: number}}
 */
export function getVisibleRange(measurements, scrollTop, viewportHeight) {
  if (!measurements.length) return { start: 0, end: 0 };

  let start = 0;
  let end = measurements.length;

  // Binary search for start
  let lo = 0, hi = measurements.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (measurements[mid].offset + measurements[mid].height < scrollTop) {
      lo = mid + 1;
    } else {
      start = mid;
      hi = mid - 1;
    }
  }

  // Linear scan for end (usually close to start)
  const bottomEdge = scrollTop + viewportHeight;
  for (let i = start; i < measurements.length; i++) {
    if (measurements[i].offset > bottomEdge) {
      end = i;
      break;
    }
  }

  // Overscan by 3 items in each direction for smooth scrolling
  return {
    start: Math.max(0, start - 3),
    end: Math.min(measurements.length, end + 3),
  };
}
