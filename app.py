"""
Consensus — Multi-model research debate engine.
Ask a question, watch language models argue and vote on the answer.
"""

import sys
import os
import json
import time
import uuid
import threading
from flask import Flask, Response, request, jsonify, send_from_directory

sys.path.insert(0, '/home/coolhand/shared')
from llm_providers import ProviderFactory

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

# Active sessions
sessions = {}


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


DEBATE_SYSTEM = """You are participating in a multi-model research debate. Your role: independently research the user's question and provide your honest assessment.

Rules:
1. Be concise but thorough (2-4 paragraphs max)
2. State your confidence level (low/medium/high/very high)
3. If you disagree with common assumptions, say so
4. End with a clear VOTE line in this exact format:
   VOTE: [AGREE|DISAGREE|PARTIAL] — [one sentence summary of your position]

The question to research and vote on:"""


def query_model(provider_key, model_info, question, session_id):
    """Query a single model and stream events."""
    model_id = f"{provider_key}/{model_info['id']}"

    # Signal: model starting
    emit_event(session_id, 'model_start', {'model': model_id})

    try:
        provider = ProviderFactory.get_provider(provider_key)
        messages = [
            {'role': 'system', 'content': DEBATE_SYSTEM},
            {'role': 'user', 'content': question},
        ]

        full_response = ''
        # Try streaming first
        try:
            for chunk in provider.stream_chat(messages, model=model_info['id']):
                if isinstance(chunk, dict):
                    text = chunk.get('content', chunk.get('text', ''))
                elif isinstance(chunk, str):
                    text = chunk
                else:
                    text = str(chunk)
                if text:
                    full_response += text
                    emit_event(session_id, 'model_chunk', {'model': model_id, 'text': text})
        except (AttributeError, TypeError):
            # Fallback to non-streaming
            result = provider.chat(messages, model=model_info['id'])
            if isinstance(result, dict):
                full_response = result.get('content', result.get('text', str(result)))
            else:
                full_response = str(result)
            emit_event(session_id, 'model_chunk', {'model': model_id, 'text': full_response})

        # Parse vote
        vote = parse_vote(full_response)
        emit_event(session_id, 'model_done', {
            'model': model_id,
            'response': full_response,
            'vote': vote,
        })
        return {'model': model_id, 'response': full_response, 'vote': vote}

    except Exception as e:
        emit_event(session_id, 'model_error', {'model': model_id, 'error': str(e)})
        return {'model': model_id, 'response': '', 'vote': {'stance': 'ERROR', 'summary': str(e)}}


def parse_vote(text):
    """Extract VOTE: line from model response."""
    for line in text.strip().split('\n'):
        line = line.strip()
        if line.upper().startswith('VOTE:'):
            rest = line[5:].strip()
            # Parse stance
            stance = 'PARTIAL'
            for s in ['AGREE', 'DISAGREE', 'PARTIAL']:
                if s in rest.upper():
                    stance = s
                    break
            # Extract summary after the dash
            summary = rest
            for sep in [' — ', ' - ', '—', '-']:
                if sep in rest:
                    summary = rest.split(sep, 1)[1].strip()
                    break
            return {'stance': stance, 'summary': summary}
    return {'stance': 'UNCLEAR', 'summary': 'No explicit vote found'}


def tally_votes(results):
    """Weighted vote tally across all models."""
    totals = {'AGREE': 0, 'DISAGREE': 0, 'PARTIAL': 0, 'ERROR': 0, 'UNCLEAR': 0}
    details = []

    for provider_key, provider_results in results.items():
        weight = PROVIDERS[provider_key]['weight']
        for r in provider_results:
            stance = r['vote']['stance']
            totals[stance] = totals.get(stance, 0) + weight
            details.append({
                'model': r['model'],
                'stance': stance,
                'summary': r['vote']['summary'],
                'weight': weight,
            })

    # Determine consensus
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


# ── SSE Event System ─────────────────────────────────────────────

def emit_event(session_id, event_type, data):
    """Push an event to a session's event queue."""
    if session_id in sessions:
        sessions[session_id]['events'].append({
            'type': event_type,
            'data': data,
            'ts': time.time(),
        })


def run_debate(session_id, question, selected_providers=None):
    """Run the full debate across all providers in parallel."""
    providers_to_use = selected_providers or list(PROVIDERS.keys())
    results = {}
    threads = []

    emit_event(session_id, 'debate_start', {
        'question': question,
        'providers': providers_to_use,
        'tree': build_tree_data(),
    })

    def run_provider(pkey):
        provider_results = []
        for model_info in PROVIDERS[pkey]['models']:
            result = query_model(pkey, model_info, question, session_id)
            provider_results.append(result)
        results[pkey] = provider_results

        # Emit provider-level vote (aggregate of sub-models)
        stances = [r['vote']['stance'] for r in provider_results]
        provider_stance = max(set(stances), key=stances.count) if stances else 'UNCLEAR'
        emit_event(session_id, 'provider_done', {
            'provider': pkey,
            'stance': provider_stance,
            'models': len(provider_results),
        })

    for pkey in providers_to_use:
        t = threading.Thread(target=run_provider, args=(pkey,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=60)

    # Final tally
    tally = tally_votes(results)
    emit_event(session_id, 'debate_end', tally)


# ── Routes ───────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'consensus', 'port': PORT})


@app.route('/api/providers')
def get_providers():
    """Return the provider hierarchy for the tree visualization."""
    return jsonify(build_tree_data())


@app.route('/api/debate', methods=['POST'])
def start_debate():
    """Start a new debate. Returns a session_id for SSE streaming."""
    data = request.get_json()
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'error': 'No question provided'}), 400

    selected = data.get('providers')  # optional subset
    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {'events': [], 'question': question, 'cursor': 0}

    # Run debate in background thread
    threading.Thread(
        target=run_debate,
        args=(session_id, question, selected),
        daemon=True,
    ).start()

    return jsonify({'session_id': session_id})


@app.route('/api/stream/<session_id>')
def stream_events(session_id):
    """SSE stream for a debate session."""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    def generate():
        cursor = 0
        stale_count = 0
        while True:
            session = sessions.get(session_id)
            if not session:
                break

            events = session['events']
            if cursor < len(events):
                for evt in events[cursor:]:
                    yield f"data: {json.dumps(evt)}\n\n"
                cursor = len(events)
                stale_count = 0

                # Check if debate ended
                if events and events[-1]['type'] == 'debate_end':
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break
            else:
                stale_count += 1
                if stale_count > 300:  # 5 min timeout
                    break
                time.sleep(0.1)

        # Cleanup
        sessions.pop(session_id, None)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


if __name__ == '__main__':
    print(f"Consensus listening on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
