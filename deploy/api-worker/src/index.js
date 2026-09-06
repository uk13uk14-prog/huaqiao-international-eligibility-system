const ALLOWED = new Set([
  'https://app.guoqiaoplan.com',
  'https://admin.guoqiaoplan.com',
  'https://huaqiao-international-eligibility-system.rambolluk.workers.dev',
]);

/** Public API hostname expected by named tunnel ingress */
const PUBLIC_API_HOST = 'api.guoqiaoplan.com';

function corsHeaders(origin) {
  const o = ALLOWED.has(origin) ? origin : '';
  const h = {
    'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization,Content-Type',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  };
  if (o) {
    h['Access-Control-Allow-Origin'] = o;
    h['Access-Control-Allow-Credentials'] = 'true';
  }
  return h;
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }
    if (!env.BACKEND_ORIGIN) {
      return new Response('BACKEND_ORIGIN not configured', {
        status: 502,
        headers: { 'Content-Type': 'text/plain', ...corsHeaders(origin) },
      });
    }
    const url = new URL(request.url);
    const backend = new URL(env.BACKEND_ORIGIN);
    const target = new URL(url.pathname + url.search, env.BACKEND_ORIGIN);
    const headers = new Headers(request.headers);
    headers.delete('host');
    // Named tunnel ingress matches hostname api.guoqiaoplan.com only.
    if (backend.hostname.endsWith('.cfargotunnel.com')) {
      headers.set('Host', PUBLIC_API_HOST);
    }
    const init = {
      method: request.method,
      headers,
      redirect: 'manual',
    };
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      init.body = await request.arrayBuffer();
    }
    const upstream = await fetch(target, init);
    const outHeaders = new Headers(upstream.headers);
    const cors = corsHeaders(origin);
    for (const [k, v] of Object.entries(cors)) outHeaders.set(k, v);
    return new Response(upstream.body, { status: upstream.status, headers: outHeaders });
  },
};
