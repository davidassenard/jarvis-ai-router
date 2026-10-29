import json, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from router import Router

opts = {}
try:
    with open('/data/options.json', encoding='utf-8') as f: opts = json.load(f)
except OSError: pass
for key in ('groq_api_key','groq_model','gemini_api_key','gemini_model','local_llm_url','local_llm_key','local_llm_model','search_url'):
    env = key.upper()
    if opts.get(key): os.environ[env] = str(opts[key])
if opts.get('order'): os.environ['JARVIS_ROUTER_ORDER'] = opts['order']
router = Router()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): return
    def do_GET(self):
        if self.path == '/health': self._send(200, {'ok': True, 'providers': list(router.providers)})
        elif self.path == '/v1/models':
            self._send(200, {'object': 'list', 'data': [{'id': os.getenv('LOCAL_LLM_MODEL', 'jarvis'), 'object': 'model', 'owned_by': 'jarvis'}]})
        elif self.path == '/diagnostics':
            result = {}
            for name, fn in router.providers.items():
                try:
                    text = fn([{'role': 'user', 'content': 'Réponds uniquement OK.'}])
                    result[name] = {'ok': bool(text)}
                except Exception as exc:
                    status = getattr(exc, 'status', None)
                    result[name] = {'ok': False, 'status': status, 'error': type(exc).__name__}
            self._send(200, {'providers': result})
        else: self._send(404, {'error': 'not found'})
    def do_POST(self):
        if self.path not in ('/v1/chat/completions', '/v1/responses'):
            return self._send(404, {'error':'not found'})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('content-length','0'))))
            messages = body.get('messages', [])
            if self.path == '/v1/responses':
                inp = body.get('input', '')
                if isinstance(inp, str):
                    messages = [{'role': 'user', 'content': inp}]
                elif isinstance(inp, list):
                    messages = inp
                result = router.complete(messages)
                now = int(time.time())
                self._send(200, {'id':'jarvis-response','object':'response','created_at':now,'status':'completed','model':body.get('model','local'), 'output':[{'id':'msg_jarvis','type':'message','status':'completed','role':'assistant','content':[{'type':'output_text','text':result.text,'annotations':[]}]}], 'output_text':result.text, 'parallel_tool_calls':False,'tool_choice':'auto','tools':[],'usage':{'input_tokens':0,'output_tokens':len(result.text.split()),'total_tokens':len(result.text.split())}, 'jarvis_provider':result.provider, 'jarvis_attempts':result.attempts})
            else:
                result = router.complete(messages)
                self._send(200, {'id':'jarvis-chat','object':'chat.completion','created':int(time.time()),'model':body.get('model','jarvis'), 'choices':[{'index':0,'message':{'role':'assistant','content':result.text},'finish_reason':'stop'}], 'usage':{'prompt_tokens':0,'completion_tokens':len(result.text.split()),'total_tokens':len(result.text.split())}, 'jarvis_provider':result.provider, 'jarvis_attempts':result.attempts})
        except Exception as exc:
            self._send(502, {'error': 'all providers unavailable'})
    def _send(self, code, obj):
        data = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

ThreadingHTTPServer(('0.0.0.0', 8787), Handler).serve_forever()
