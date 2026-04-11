import os
import re
import difflib
import threading
from flask import Flask, jsonify, render_template, send_from_directory, abort


def _normalize(s):
    """Lowercase and strip non-alphanumeric characters for fuzzy comparison."""
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _build_awakening_index(awk_dir):
    """
    Scan awakeningImages/ and return a list of (normalized_stem, filename) pairs.
    Stem is extracted from filenames like T_GlassCannon-512x512.png → 'glasscannon'.
    """
    index = []
    for fname in os.listdir(awk_dir):
        if not fname.lower().endswith('.png'):
            continue
        stem = fname[:-4]                       # strip .png
        if stem.startswith('T_'):
            stem = stem[2:]                     # strip T_ prefix
        stem = stem.split('-')[0]               # strip -512x512 and anything after
        index.append((_normalize(stem), fname))
    return index


def fuzzy_find_awakening(name, index, threshold=0.5):
    """
    Return the best-matching filename for the given external awakening name,
    or None if no match exceeds the threshold.
    """
    normalized = _normalize(name)
    best_ratio = 0
    best_file = None
    for key, fname in index:
        ratio = difflib.SequenceMatcher(None, normalized, key).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_file = fname
    if best_ratio >= threshold:
        return best_file
    return None


class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = {"players": None, "game_count": 0}

    def update(self, players: list):
        with self._lock:
            self._state["players"] = players
            self._state["game_count"] += 1

    def get(self) -> dict:
        with self._lock:
            return dict(self._state)


def create_app(shared_state):
    app = Flask(__name__, template_folder='templates', static_folder='static')

    base_dir = os.path.dirname(os.path.abspath(__file__))
    char_dir = os.path.join(base_dir, 'characterImages')
    awk_dir  = os.path.join(base_dir, 'awakeningImages')

    # Build awakening fuzzy index once at startup
    awk_index = _build_awakening_index(awk_dir)

    # Cache resolved awakening lookups so fuzzy matching only runs once per name
    awk_cache = {}

    @app.route('/')
    def overlay():
        return render_template('overlay.html')

    @app.route('/api/state')
    def api_state():
        return jsonify(shared_state.get())

    @app.route('/img/char/<path:name>')
    def serve_character(name):
        fname = name + '.png'
        full  = os.path.join(char_dir, fname)
        if not os.path.isfile(full):
            fname = 'T_CharacterCloseUpMissing.png'
        return send_from_directory(char_dir, fname)

    @app.route('/img/awk/<path:name>')
    def serve_awakening(name):
        if name not in awk_cache:
            awk_cache[name] = fuzzy_find_awakening(name, awk_index)
        filename = awk_cache[name]
        if not filename:
            abort(404)
        return send_from_directory(awk_dir, filename)

    return app


def start_flask_server(shared_state, port):
    app = create_app(shared_state)
    t = threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False),
        daemon=True,
        name='FlaskThread'
    )
    t.start()
    print(f"Overlay ready at http://127.0.0.1:{port}")
    print("Add this URL as a Browser Source in OBS (enable 'Allow transparency').")
