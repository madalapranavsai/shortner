import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 20 },  // Ramp up to 20 virtual users
    { duration: '30s', target: 50 },  // Stay at 50 VUs (sustained load)
    { duration: '10s', target: 0 },   // Ramp down to 0
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],    // Error rate should be less than 1%
    http_req_duration: ['p(95)<100'],  // 95% of requests should be below 100ms
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export function setup() {
  // 1. Create an API Key for the load test client with a very high rate limit capacity
  const resKey = http.post(`${BASE_URL}/keys`, JSON.stringify({
    client_name: 'k6-load-tester',
    rate_limit_capacity: 100000,          // Massive capacity to avoid being throttled
    rate_limit_refill_rate: 10000.0        // High refill rate
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  
  const keyData = resKey.json();
  const apiKey = keyData.key;
  
  // 2. Pre-generate some short URLs to query during the load test (for cache read testing)
  const codes = [];
  for (let i = 0; i < 100; i++) {
    const resShorten = http.post(`${BASE_URL}/shorten`, JSON.stringify({
      url: `https://github.com/google/page-${i}-${Math.random()}`
    }), {
      headers: { 
        'Content-Type': 'application/json',
        'X-API-Key': apiKey
      },
    });
    if (resShorten.status === 201) {
      codes.push(resShorten.json().short_code);
    }
  }
  
  console.log(`Setup complete. Created API Key: ${apiKey} and pre-populated ${codes.length} short codes.`);
  return { apiKey, codes };
}

export default function (data) {
  const { apiKey, codes } = data;
  const rand = Math.random();
  
  if (rand < 0.20) {
    // Scenario A: Write path (20% of traffic)
    // Generates a new short URL
    const payload = JSON.stringify({
      url: `https://github.com/google/repo-${Math.floor(Math.random() * 1000000)}`
    });
    const params = {
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
    };
    const res = http.post(`${BASE_URL}/shorten`, payload, params);
    check(res, {
      'shorten success': (r) => r.status === 201,
    });
  } else if (rand < 0.90) {
    // Scenario B: Read/Redirect path (70% of traffic)
    // Fetches and follows redirect (hits Redis cache on hit)
    if (codes.length > 0) {
      const code = codes[Math.floor(Math.random() * codes.length)];
      const res = http.get(`${BASE_URL}/${code}`, {
        redirects: 0, // Do NOT follow redirect location (we measure redirect server performance)
        headers: { 'X-API-Key': apiKey }
      });
      check(res, {
        'redirect success (302)': (r) => r.status === 302,
      });
    }
  } else {
    // Scenario C: Stats lookup path (10% of traffic)
    if (codes.length > 0) {
      const code = codes[Math.floor(Math.random() * codes.length)];
      const res = http.get(`${BASE_URL}/stats/${code}`, {
        headers: { 'X-API-Key': apiKey }
      });
      check(res, {
        'stats lookup success': (r) => r.status === 200,
      });
    }
  }
  
  sleep(0.05); // Sleep 50ms to control req rate
}
