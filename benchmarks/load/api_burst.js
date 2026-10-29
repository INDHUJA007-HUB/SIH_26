import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Custom metrics matching Section 11.3 & 13.4 qualification requirements
export const errorRate = new Rate('error_rate');
export const apiDuration = new Trend('api_latency_ms', true);
export const burstRequests = new Counter('burst_requests_total');

export const options = {
  scenarios: {
    // 25 req/s sustained, bursting to 75 req/s, 200 concurrent users
    burst_ramp: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 200,
      stages: [
        { duration: '30s', target: 25 }, // Ramp up to sustained 25 req/s
        { duration: '1m', target: 25 },  // Sustain 25 req/s
        { duration: '30s', target: 75 }, // Spike burst to 75 req/s
        { duration: '30s', target: 25 }, // Recover back to 25 req/s
        { duration: '30s', target: 0 },  // Cool down
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'], // < 1% errors
    http_req_duration: ['p(95)<500'], // 95% of requests under 500ms
    api_latency_ms: ['p(95)<500'],
  },
};

const BASE_URL = __ENV.WB_API_URL || 'http://127.0.0.1:8000';

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer qualification-load-token',
  };

  // Health / Readiness probe
  const resHealth = http.get(`${BASE_URL}/healthz`, { headers });
  burstRequests.add(1);
  const okHealth = check(resHealth, {
    'health status is 200': (r) => r.status === 200,
  });
  errorRate.add(!okHealth);
  apiDuration.add(resHealth.timings.duration);

  // Read applications endpoint
  const resList = http.get(`${BASE_URL}/api/v1/applications?limit=10`, { headers });
  burstRequests.add(1);
  const okList = check(resList, {
    'list status is 200 or 401': (r) => r.status === 200 || r.status === 401,
  });
  errorRate.add(!okList);
  apiDuration.add(resList.timings.duration);

  sleep(0.1);
}
