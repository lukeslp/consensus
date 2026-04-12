"""
Consensus — Multi-model research debate engine.
Ask a question, watch language models argue and vote on the answer.
"""

import os
import sys
import json
import re
import time
import uuid
import queue
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeoutError

from flask import Flask, Response, request, jsonify, send_from_directory

# llm_providers is a shared library in the broader geepers ecosystem. Allow the
# path to be overridden via env var so this project isn't tied to a single dev
# machine layout.
_LLM_PROVIDERS_PATH = os.environ.get('LLM_PROVIDERS_PATH', '/home/coolhand/shared')
if _LLM_PROVIDERS_PATH and os.path.isdir(_LLM_PROVIDERS_PATH) and _LLM_PROVIDERS_PATH not in sys.path:
    sys.path.insert(0, _LLM_PROVIDERS_PATH)

from llm_providers import ProviderFactory  # noqa: E402

logger = logging.getLogger('consensus')
logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO'),
                    format='%(asctime)s %(name)s %(levelname)s %(message)s')

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 5063))

# ── Model Hierarchy ──────────────────────────────────────────────

PROVIDERS = {
    'anthropic': {
        'rank': 'queen',
        'weight': 3,
        'label': 'Anthropic',
        'color': '#C9A84C',
        'models': [
            {'id': 'claude-sonnet-4-5-20250514', 'label': 'Sonnet 4.5'},
            {'id': 'claude-haiku-4-5-20251001', 'label': 'Haiku 4.5'},
        ]
    },
    'gemini': {
        'rank': 'king',
        'weight': 3,
        'label': 'Gemini',
        'color': '#C9A84C',
        'models': [
            {'id': 'gemini-2.5-flash', 'label': 'Flash 2.5'},
            {'id': 'gemini-2.0-flash', 'label': 'Flash 2.0'},
        ]
    },
    'openai': {
        'rank': 'lord',
        'weight': 2,
        'label': 'OpenAI',
        'color': '#8B95A2',
        'models': [
            {'id': 'gpt-4o', 'label': 'GPT-4o'},
            {'id': 'gpt-4o-mini', 'label': 'GPT-4o Mini'},
        ]
    },
    'xai': {
        'rank': 'lord',
        'weight': 2,
        'label': 'xAI',
        'color': '#8B95A2',
        'models': [
            {'id': 'grok-3-mini-fast', 'label': 'Grok 3 Mini'},
        ]
    },
    'mistral': {
        'rank': 'knight',
        'weight': 1,
        'label': 'Mistral',
        'color': '#B87333',
        'models': [
            {'id': 'mistral-small-latest', 'label': 'Mistral Small'},
        ]
    },
    'cohere': {
        'rank': 'knight',
        'weight': 1,
        'label': 'Cohere',
        'color': '#B87333',
        'models': [
            {'id': 'command-r-plus', 'label': 'Command R+'},
        ]
    },
    'groq': {
        'rank': 'knight',
        'weight': 1,
        'label': 'Groq',
        'color': '#B87333',
        'models': [
            {'id': 'llama-3.3-70b-versatile', 'label': 'Llama 3.3 70B'},
            {'id': 'deepseek-r1-distill-llama-70b', 'label': 'DeepSeek R1'},
        ]
    },
    'perplexity': {
        'rank': 'knight',
        'weight': 1,
        'label': 'Perplexity',
        'color': '#B87333',
        'models': [
            {'id': 'sonar', 'label': 'Sonar'},
        ]
    },
}

# ── Session registry ─────────────────────────────────────────────
# Each session holds a blocking Queue the debate worker pushes events into and
# the SSE stream drains. The lock guards the dict itself; the Queues are
# thread-safe.

_sessions: dict = {}
_sessions_lock = threading.Lock()

SESSION_TTL = 600            # seconds — stream will self-terminate after this
STREAM_HEARTBEAT = 15        # seconds between heartbeat comments
MODEL_TIMEOUT = 90           # seconds per provider.chat call (informational)
DEBATE_TIMEOUT = 180         # seconds total before we cut losses
MAX_QUESTION_LEN = 4000


def _create_session(session_id: str, question: str) -> None:
    with _sessions_lock:
        _sessions[session_id] = {
            'queue': queue.Queue(),
            'question': question,
            'started': time.time(),
        }


def _get_session(session_id: str):
    with _sessions_lock:
        return _sessions.get(session_id)


def _drop_session(session_id: str) -> None:
    with _sessions_lock:
        _sessions.pop(session_id, None)


def _reap_stale_sessions() -> None:
    now = time.time()
    with _sessions_lock:
        stale = [sid for sid, s in _sessions.items() if now - s['started'] > SESSION_TTL]
        for sid in stale:
            _sessions.pop(sid, None)
    if stale:
        logger.info('reaped %d stale session(s)', len(stale))


def emit_event(session_id: str, event_type: str, data) -> None:
    """Push an event to a session's queue. No-op if session is gone."""
    session = _get_session(session_id)
    if session is not None:
        session['queue'].put({'type': event_type, 'data': data, 'ts': time.time()})


# ── Tree construction ────────────────────────────────────────────

def build_tree_data():
    """Build the D3-compatible tree structure from PROVIDERS config."""
    children = []
    for key, p in PROVIDERS.items():
        model_children = [
            {'name': m['label'], 'id': f"{key}/{m['id']}", 'status': 'idle', 'vote': None, 'response': ''}
            for m in p['models']
        ]
        children.append({
            'name': p['label'],
            'id': key,
            'rank': p['rank'],
            'weight': p['weight'],
            'color': p['color'],
            'status': 'idle',
            'vote': None,
            'children': model_children,
        })
    return {'name': 'Question', 'id': 'root', 'children': children}


# ── Prompt & response parsing ────────────────────────────────────

DEBATE_SYSTEM = """You are participating in a multi-model research debate. Your role: independently research the user's question and provide your honest assessment.

Rules:
1. Be concise but thorough (2-4 paragraphs max)
2. State your confidence level (low/medium/high/very high)
3. If you disagree with common assumptions, say so
4. End with a clear VOTE line in this exact format:
   VOTE: [AGREE|DISAGREE|PARTIAL] — [one sentence summary of your position]

The question to research and vote on:"""


# \bVOTE ... DISAGREE ordered before AGREE so the alternation doesn't misfire.
_VOTE_RE = re.compile(
    r'\bVOTE\s*[:\-—]?\s*\**\s*(DISAGREE|AGREE|PARTIAL)\b',
    re.IGNORECASE,
)

# Match either "confidence: high" / "confidence level is high" or the reverse
# phrasing "high confidence". Order matters inside the alternation: very high
# first so "high" doesn't swallow it.
_CONFIDENCE_RE = re.compile(
    r'(?:\bconfidence(?:\s+level)?\s*(?:is|:|=|-|–|—)?\s*\**\s*(very\s+high|high|medium|low)\b'
    r'|\b(very\s+high|high|medium|low)\s+confidence\b)',
    re.IGNORECASE,
)

_CONFIDENCE_MAP = {
    'low': 0.40,
    'medium': 0.65,
    'high': 0.85,
    'very high': 0.98,
}


def parse_vote(text: str) -> dict:
    """Extract VOTE stance, summary, and confidence from a model response."""
    text = text or ''
    vote_match = _VOTE_RE.search(text)
    if not vote_match:
        return {'stance': 'UNCLEAR', 'summary': 'No explicit vote found', 'confidence': 0.5}

    stance = vote_match.group(1).upper()

    # Grab the rest of the line after the stance token.
    tail = text[vote_match.end():]
    first_line = tail.split('\n', 1)[0]
    summary = first_line.lstrip(' —–-:*').strip() or f'Voted {stance}'
    if len(summary) > 240:
        summary = summary[:237] + '…'

    # Confidence: default to 0.7 when the model didn't name one.
    confidence = 0.7
    conf_match = _CONFIDENCE_RE.search(text)
    if conf_match:
        raw = conf_match.group(1) or conf_match.group(2) or ''
        key = re.sub(r'\s+', ' ', raw.lower()).strip()
        confidence = _CONFIDENCE_MAP.get(key, 0.7)

    return {'stance': stance, 'summary': summary, 'confidence': confidence}


def _extract_text(chunk) -> str:
    """Normalize chat/stream chunks from heterogeneous providers into str."""
    if chunk is None:
        return ''
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        return chunk.get('content') or chunk.get('text') or ''
    return str(chunk) if chunk else ''


def _stream_or_complete(provider, messages, model_info, model_id, session_id) -> str:
    """Prefer streaming; fall back to a blocking chat call if unsupported."""
    full = ''
    streamed_any = False

    stream_fn = getattr(provider, 'stream_chat', None)
    if callable(stream_fn):
        try:
            for chunk in stream_fn(messages, model=model_info['id']):
                text = _extract_text(chunk)
                if text:
                    streamed_any = True
                    full += text
                    emit_event(session_id, 'model_chunk', {'model': model_id, 'text': text})
        except Exception as stream_err:
            # Mid-stream failure after partial output: propagate; we have a
            # best-effort response but the model clearly broke. Pre-stream
            # failure (no chunks seen): fall through to the blocking path.
            if streamed_any:
                logger.warning('stream failed mid-output for %s: %s', model_id, stream_err)
                return full
            logger.info('stream_chat unavailable for %s (%s), falling back', model_id, stream_err)

    if not streamed_any:
        result = provider.chat(messages, model=model_info['id'])
        full = _extract_text(result) or (str(result) if result else '')
        if full:
            emit_event(session_id, 'model_chunk', {'model': model_id, 'text': full})

    return full


def query_model(provider_key, model_info, question, session_id):
    """Query a single model end-to-end, streaming events as it goes."""
    model_id = f"{provider_key}/{model_info['id']}"
    emit_event(session_id, 'model_start', {'model': model_id})

    try:
        provider = ProviderFactory.get_provider(provider_key)
        messages = [
            {'role': 'system', 'content': DEBATE_SYSTEM},
            {'role': 'user', 'content': question},
        ]
        full_response = _stream_or_complete(provider, messages, model_info, model_id, session_id)
        vote = parse_vote(full_response)

        emit_event(session_id, 'model_done', {
            'model': model_id,
            'response': full_response,
            'vote': vote,
        })
        return {'model': model_id, 'response': full_response, 'vote': vote}

    except Exception as e:
        msg = str(e)[:200]
        logger.warning('query_model %s failed: %s', model_id, msg)
        emit_event(session_id, 'model_error', {'model': model_id, 'error': msg})
        return {
            'model': model_id,
            'response': '',
            'vote': {'stance': 'ERROR', 'summary': msg, 'confidence': 0.0},
        }


# ── Voting / consensus ───────────────────────────────────────────

def _majority_stance(results: list) -> str:
    stances = [r['vote']['stance'] for r in results
               if r['vote']['stance'] in ('AGREE', 'DISAGREE', 'PARTIAL')]
    if not stances:
        return 'UNCLEAR'
    return max(set(stances), key=stances.count)


def tally_votes(results):
    """Weighted tally across all providers/sub-models."""
    totals = {'AGREE': 0, 'DISAGREE': 0, 'PARTIAL': 0, 'ERROR': 0, 'UNCLEAR': 0}
    details = []

    for provider_key, provider_results in results.items():
        weight = PROVIDERS[provider_key]['weight']
        for r in provider_results:
            stance = r['vote'].get('stance', 'UNCLEAR')
            totals[stance] = totals.get(stance, 0) + weight
            details.append({
                'model': r['model'],
                'stance': stance,
                'summary': r['vote'].get('summary', ''),
                'confidence': r['vote'].get('confidence', 0),
                'weight': weight,
            })

    valid = totals['AGREE'] + totals['DISAGREE'] + totals['PARTIAL']
    if valid == 0:
        consensus = 'NO_QUORUM'
        confidence = 0
    else:
        max_stance = max(['AGREE', 'DISAGREE', 'PARTIAL'], key=lambda s: totals[s])
        consensus = max_stance
        confidence = round(totals[max_stance] / valid * 100)

    return {
        'consensus': consensus,
        'confidence': confidence,
        'totals': totals,
        'details': details,
    }


def _emit_provider_done(session_id, pkey, provider_results):
    emit_event(session_id, 'provider_done', {
        'provider': pkey,
        'stance': _majority_stance(provider_results),
        'models': len(provider_results),
    })


def run_debate(session_id, question, selected_providers=None):
    """Run the full debate across providers and their sub-models in parallel."""
    providers_to_use = [p for p in (selected_providers or list(PROVIDERS.keys())) if p in PROVIDERS]
    results = {p: [] for p in providers_to_use}

    emit_event(session_id, 'debate_start', {
        'question': question,
        'providers': providers_to_use,
        'tree': build_tree_data(),
    })

    tasks = [(pkey, m) for pkey in providers_to_use for m in PROVIDERS[pkey]['models']]
    if not tasks:
        emit_event(session_id, 'debate_end', tally_votes(results))
        return

    expected = {pkey: len(PROVIDERS[pkey]['models']) for pkey in providers_to_use}
    max_workers = min(16, len(tasks))
    pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='consensus-debate')

    try:
        future_to_task = {
            pool.submit(query_model, pkey, m, question, session_id): (pkey, m)
            for pkey, m in tasks
        }
        try:
            for future in as_completed(future_to_task, timeout=DEBATE_TIMEOUT):
                pkey, m = future_to_task[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = {
                        'model': f"{pkey}/{m['id']}",
                        'response': '',
                        'vote': {'stance': 'ERROR', 'summary': str(e)[:200], 'confidence': 0.0},
                    }
                    emit_event(session_id, 'model_error',
                               {'model': result['model'], 'error': result['vote']['summary']})

                results[pkey].append(result)
                if len(results[pkey]) == expected[pkey]:
                    _emit_provider_done(session_id, pkey, results[pkey])
        except FutureTimeoutError:
            logger.warning('debate %s timed out after %ds', session_id, DEBATE_TIMEOUT)

        # Finalize any provider whose sub-models didn't all report back.
        for pkey in providers_to_use:
            if len(results[pkey]) >= expected[pkey]:
                continue
            seen = {r['model'] for r in results[pkey]}
            for m in PROVIDERS[pkey]['models']:
                model_id = f"{pkey}/{m['id']}"
                if model_id in seen:
                    continue
                emit_event(session_id, 'model_error', {'model': model_id, 'error': 'Timed out'})
                results[pkey].append({
                    'model': model_id,
                    'response': '',
                    'vote': {'stance': 'ERROR', 'summary': 'Timed out', 'confidence': 0.0},
                })
            _emit_provider_done(session_id, pkey, results[pkey])
    finally:
        # Don't block on hung provider threads; let them finish in the background.
        # cancel_futures stops unstarted work (Python 3.9+).
        pool.shutdown(wait=False, cancel_futures=True)

    emit_event(session_id, 'debate_end', tally_votes(results))


# ── Routes ───────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/health')
def health():
    with _sessions_lock:
        active = len(_sessions)
    return jsonify({'status': 'ok', 'service': 'consensus', 'port': PORT, 'sessions': active})


@app.route('/api/providers')
def get_providers():
    """Return the provider hierarchy for the tree visualization."""
    return jsonify(build_tree_data())


@app.route('/api/debate', methods=['POST'])
def start_debate():
    """Start a new debate. Returns a session_id for SSE streaming."""
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    if len(question) > MAX_QUESTION_LEN:
        return jsonify({'error': f'Question too long (max {MAX_QUESTION_LEN} chars)'}), 400

    selected = data.get('providers')
    _reap_stale_sessions()

    session_id = uuid.uuid4().hex[:12]
    _create_session(session_id, question)

    threading.Thread(
        target=run_debate,
        args=(session_id, question, selected),
        daemon=True,
        name=f'debate-{session_id}',
    ).start()

    return jsonify({'session_id': session_id})


@app.route('/api/stream/<session_id>')
def stream_events(session_id):
    """SSE stream for a debate session. Blocks on the session's event queue."""
    session = _get_session(session_id)
    if session is None:
        return jsonify({'error': 'Session not found'}), 404

    q = session['queue']

    def generate():
        # Open the SSE channel with a comment; keeps proxies from buffering.
        yield ': connected\n\n'
        try:
            while True:
                try:
                    evt = q.get(timeout=STREAM_HEARTBEAT)
                except queue.Empty:
                    yield ': heartbeat\n\n'
                    s = _get_session(session_id)
                    if s is None or (time.time() - s['started']) > SESSION_TTL:
                        break
                    continue

                yield f"data: {json.dumps(evt)}\n\n"
                if evt['type'] == 'debate_end':
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break
        finally:
            _drop_session(session_id)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


if __name__ == '__main__':
    logger.info('Consensus listening on port %d', PORT)
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
