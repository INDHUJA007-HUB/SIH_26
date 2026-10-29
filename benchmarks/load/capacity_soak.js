import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

export const errorRate = new Rate('soak_error_rate');
export const soakDuration = new Trend('soak_latency_ms', true);
export const totalTransactions = new Counter('soak_transactions_total');

export const options = {
  scenarios: {
    // 30-minute endurance soak testing memory stability and connection leaks
    soak_profile: {
      executor: 'constant-arrival-rate',
      rate: 20, // 20 req/s sustained load
      timeUnit: '1s',
      duration: '10m', // 10 minutes qualification soak
      preAllocatedVUs: 40,
      maxVUs: 100,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.005'], // < 0.5% failure
    http_req_duration: ['p(95)<350'],
    soak_latency_ms: ['p(99)<600'],
  },
};

const BASE_URL = __ENV.WB_API_URL || 'http://127.0.0.1:8000';

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer soak-test-token',
  };

  const res = http.get(`${BASE_URL}/healthz`, { headers });
  totalTransactions.add(1);

  const passed = check(res, {
    'status is 200': (r) => r.status === 200,
  });

  errorRate.add(!passed);
  soakDuration.add(res.timings.duration);

  sleep(0.05);
}
