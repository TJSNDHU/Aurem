// k6 load test — iter 282ak (Prompt 8, Task D).
//
// Ramp 10→50 users across 2min, tests 5 critical health endpoints
// thresholds: p95<5s, fail<5%.
//
// Run: k6 run tests/k6/load_test.js \
//        --env BASE_URL=https://aurem.live \
//        --env ADMIN_TOKEN=<token>

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m',  target: 50 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'],
    http_req_failed:   ['rate<0.05'],
  },
};

const BASE  = __ENV.BASE_URL  || 'https://aurem.live';
const TOKEN = __ENV.ADMIN_TOKEN || '';

export default function () {
  const h = { headers: { Authorization: `Bearer ${TOKEN}` } };

  check(http.get(`${BASE}/health`),
    { 'health 200': r => r.status === 200 });

  check(http.get(`${BASE}/api/admin/composer/health`, h), {
    'composer up':      r => r.status === 200,
    'composer not red': r => {
      try { return JSON.parse(r.body).status !== 'red'; }
      catch (_) { return false; }
    },
  });

  check(http.get(`${BASE}/api/admin/webclaw/health`, h),
    { 'webclaw up': r => r.status === 200 });

  check(http.get(`${BASE}/api/admin/skills/health`, h),
    { 'skills router up': r => r.status === 200 });

  check(http.get(`${BASE}/api/linkedin/status`, h),
    { 'linkedin up': r => r.status === 200 });

  sleep(1);
}
