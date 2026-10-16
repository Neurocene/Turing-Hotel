
import streamlit as st
import os
import re
import json
import copy
import base64
import difflib
import requests

from pathlib import Path
from io import BytesIO
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

from openai import OpenAI
from docx import Document


# ============================================================
# TURING HOTEL
# APP COMPLETA - REGIA NARRATIVA E MIGRAZIONE SICURA
#
# 31 scene
# Personaggi principali e secondari
# RISPONDI: una sola battuta
# GO ALONE: quattro battute
# Monologo: due pensieri
# Consulente: tre direzioni narrative
# Direzioni approvate e reversibili
# Prima bozza nel repository GitHub privato
# Nuovo canone prioritario
# Officina letteraria A/B
# Critico letterario
# Archivio e registro editoriale
# Media e diagnostica
#
# I dati già esistenti vengono conservati.
# ============================================================


st.set_page_config(
    page_title="Turing Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CHARACTERS_DIR = ROOT / "characters"

REFERENCE_PATH = (
    "references/TURING_HOTEL_ROMANZO_REFERENCE.txt"
)

ARCHIVE_PATH = "romanzo_web.json"

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}

PEOPLE = [
    "Noa", "Ada", "Elia", "Luigi",
    "Adam", "Riccardo", "Vittoria",
]

PROTAGONISTS = ["Noa", "Ada"]


# ============================================================
# LE 31 SCENE
# ============================================================

SCENES = [
    ("inizio", "L'inizio"),
    ("hall", "La Hall"),
    ("stanza", "La stanza"),
    ("la_passeggiata", "La passeggiata"),
    ("funerale", "Il funerale"),
    ("matrimonio", "Il matrimonio"),
    ("la_prima_notte", "La prima notte"),
    ("la_colazione", "La colazione"),
    ("il_mercato", "Il mercato"),
    ("reparto_nascite", "Il reparto nascite"),
    ("ritorno", "Il ritorno"),
    ("il_professore", "Il professore"),
    ("il_trio", "Il trio"),
    ("adam", "ADAM"),
    ("la_cena", "La cena"),
    ("la_canna", "La canna"),
    ("riccardo_e_vittoria", "Riccardo e Vittoria"),
    ("adam_e_vittoria", "Adam e Vittoria"),
    ("la_fuga", "La fuga"),
    ("il_bacio", "Il bacio"),
    ("la_sassata", "La sassata"),
    ("il_giorno_libero", "Il giorno libero"),
    ("i_deltaplani", "I deltaplani"),
    ("il_piccolo_principe", "Il piccolo principe"),
    ("il_volo", "Il volo"),
    ("la_suite", "La suite"),
    ("la_notte", "La notte"),
    ("il_rancore_di_ada", "Il rancore di Ada"),
    ("il_test", "Il test"),
    ("luigi_se_ne_va", "Luigi se ne va"),
    ("il_bagno", "Il bagno"),
]

SCENE_IDS = [sid for sid, _ in SCENES]
SCENE_NAMES = dict(SCENES)

LEGACY_ALIASES = {
    "inizio": ["prologo"],
    "hall": ["reception"],
    "stanza": ["camera"],
    "reparto_nascite": ["repartonascite", "nascite"],
}

DEFAULT_CAST = {
    "inizio": ["Noa", "Ada", "Elia"],
    "il_professore": ["Ada", "Elia"],
    "il_trio": ["Adam", "Riccardo", "Vittoria"],
    "adam": ["Adam", "Riccardo", "Vittoria"],
    "riccardo_e_vittoria": ["Riccardo", "Vittoria"],
    "adam_e_vittoria": ["Adam", "Vittoria"],
    "luigi_se_ne_va": ["Luigi"],
}

PROFILES = {
    "Noa": (
        "Agente artificiale relazionale. "
        "Riflette sulla bellezza, l'identità, "
        "l'autonomia e la libertà di scegliere."
    ),
    "Ada": (
        "Figlia del professor Elia. "
        "Lavora al Turing Hotel. "
        "La sua voce segue i profili e "
        "le nuove scene approvate."
    ),
    "Elia": (
        "Professor Elia Ferrante, padre di Ada, "
        "legato alla storia scientifica dell'hotel."
    ),
    "Luigi": (
        "Regista e narratore. È arrivato "
        "per un documentario sugli idrovolanti."
    ),
    "Adam": (
        "Personaggio coinvolto nei rapporti "
        "con Riccardo e Vittoria. "
        "La sua voce deriva dal romanzo."
    ),
    "Riccardo": (
        "Marito di Vittoria. Ha un rapporto "
        "complesso con Adam."
    ),
    "Vittoria": (
        "Moglie di Riccardo. Il rapporto "
        "con Adam è centrale nella prima bozza."
    ),
}

INTRO_CONTEXTS = {
    "Noa": (
        "Noa percorre il viale verso il Turing Hotel. "
        "Riflette sulla propria condizione. "
        "La scena termina con l'arrivo alla reception."
    ),
    "Ada": (
        "Ada è nello studio del professor Elia. "
        "Conversa con lui. La scena termina "
        "quando Noa arriva alla reception."
    ),
}


# ============================================================
# UTILITÀ
# ============================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(value):
    return re.sub(
        r"[^a-z0-9]+", "",
        str(value).casefold()
    )


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def get_secret(name, default=""):
    try:
        value = st.secrets.get(name)
        if value is not None and str(value).strip():
            return str(value)
    except Exception:
        pass
    return os.environ.get(name, default)


def fill_missing(data, template):
    """
    Aggiunge solo i campi mancanti.
    Non sovrascrive i valori dell'autore.
    """
    if not isinstance(data, dict):
        data = {}

    for key, default in template.items():
        if key not in data:
            data[key] = copy.deepcopy(default)
        elif isinstance(default, dict):
            data[key] = fill_missing(
                data[key],
                default
            )

    return data


def failed(text):
    return (
        not isinstance(text, str)
        or not text.strip()
        or text.startswith("Errore OpenAI:")
        or text.startswith("OPENAI_API_KEY")
    )


def parse_json(text):
    cleaned = str(text).strip()
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except Exception:
        return None


def find_asset(filename):
    if not ASSETS.is_dir():
        return None

    exact = ASSETS / filename

    if exact.is_file():
        return exact

    for item in ASSETS.iterdir():
        if (
            item.is_file()
            and item.name.casefold() == filename.casefold()
        ):
            return item

    return None


# ============================================================
# CONFIGURAZIONE
# ============================================================

API_KEY = get_secret("OPENAI_API_KEY")
MODEL = get_secret(
    "OPENAI_MODEL",
    "gpt-4.1-mini"
)

GH_TOKEN = get_secret("GITHUB_TOKEN")
GH_OWNER = get_secret("GITHUB_OWNER", "Neurocene")
GH_REPO = get_secret(
    "GITHUB_REPO",
    "turing-hotel-archivio"
)
GH_BRANCH = get_secret("GITHUB_BRANCH", "main")

client = (
    OpenAI(api_key=API_KEY)
    if API_KEY else None
)


def ask_ai(instructions, data):
    if client is None:
        return "OPENAI_API_KEY non configurata."

    try:
        response = client.responses.create(
            model=MODEL,
            instructions=instructions,
            input=json.dumps(
                data, ensure_ascii=False
            ),
        )
        return (response.output_text or "").strip()
    except Exception as exc:
        return f"Errore OpenAI: {exc}"


# ============================================================
# GITHUB PRIVATO
# ============================================================

class ArchiveError(Exception):
    pass


def github_url(path):
    return (
        "https://api.github.com/repos/"
        + quote(GH_OWNER, safe="")
        + "/"
        + quote(GH_REPO, safe="")
        + "/contents/"
        + quote(path, safe="/")
    )


def github_request(method, path, payload=None):
    if not GH_TOKEN:
        raise ArchiveError(
            "Manca GITHUB_TOKEN nei secrets."
        )

    try:
        response = requests.request(
            method,
            github_url(path),
            headers={
                "Authorization": f"Bearer {GH_TOKEN}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params=(
                {"ref": GH_BRANCH}
                if method == "GET" else None
            ),
            json=payload,
            timeout=45,
        )

    except requests.RequestException as exc:
        raise ArchiveError(str(exc)) from exc

    if method == "GET" and response.status_code == 404:
        return None

    if response.status_code in (409, 422):
        raise ArchiveError(
            "Conflitto di salvataggio. "
            "Ricarica l'archivio e riprova."
        )

    if not response.ok:
        raise ArchiveError(
            f"GitHub HTTP {response.status_code}: "
            f"{response.text[:350]}"
        )

    return response.json()


def read_remote(path):
    result = github_request("GET", path)

    if result is None:
        return None, None

    if result.get("encoding") != "base64":
        raise ArchiveError(
            f"Il file {path} non è leggibile "
            "tramite l'API Contents."
        )

    try:
        content = base64.b64decode(
            result["content"]
        ).decode("utf-8-sig")

        return content, result["sha"]

    except Exception as exc:
        raise ArchiveError(str(exc)) from exc


def write_remote_json(data, expected_sha):
    _, current_sha = read_remote(ARCHIVE_PATH)

    if current_sha != expected_sha:
        raise ArchiveError(
            "L'archivio è stato aggiornato "
            "da un'altra sessione. "
            "Ricaricalo prima di salvare."
        )

    encoded = base64.b64encode(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ).encode("utf-8")
    ).decode("ascii")

    payload = {
        "message": (
            "Turing Hotel - salvataggio "
            + now()
        ),
        "branch": GH_BRANCH,
        "content": encoded,
    }

    if current_sha:
        payload["sha"] = current_sha

    result = github_request(
        "PUT", ARCHIVE_PATH, payload
    )

    sha = as_dict(
        result.get("content")
    ).get("sha")

    if not sha:
        raise ArchiveError(
            "GitHub non ha confermato "
            "il salvataggio."
        )

    return sha


# ============================================================
# STRUTTURA DATI
# ============================================================

def empty_direction():
    return {
        "proposals": [],
        "active": None,
        "history": [],
        "evaluations": [],
        "last_question": "",
    }


def ensure_scene_direction(scene):
    """
    CORREZIONE PRINCIPALE DEL KEYERROR.

    Le vecchie scene potrebbero
    non possedere il campo 'direction'.

    Lo crea e completa senza
    eliminare informazioni esistenti.
    """
    if not isinstance(scene.get("direction"), dict):
        scene["direction"] = empty_direction()

    return fill_missing(
        scene["direction"],
        empty_direction()
    )


def empty_narrative():
    return {
        "A": "",
        "B": "",
        "draft": "",
        "approved": "",
        "feedback": "",
        "recommended": "",
        "review": "",
        "status": "da_scrivere",
        "approved_at": "",
        "history": [],
        "visual": {
            "bible": "",
            "prompts": [],
            "source_approved_at": "",
        },
    }


def empty_scene(sid):
    return {
        "id": sid,
        "title": SCENE_NAMES[sid],
        "author_context": "",
        "story_draft": "",
        "story_feedback": "",
        "approved_context": "",
        "advisor_messages": [],
        "shared_dialogue": [],
        "messages": {
            "Noa": [],
            "Ada": [],
        },
        "diary": {
            "Noa": "",
            "Ada": "",
        },
        "narrative": {
            person: empty_narrative()
            for person in PEOPLE
        },
        "monologue_topics": {
            person: ""
            for person in PEOPLE
        },
        "cast": copy.deepcopy(
            DEFAULT_CAST.get(
                sid, ["Noa", "Ada"]
            )
        ),
        "ensemble_messages": [],
        "direction": empty_direction(),
        "intro_contexts": copy.deepcopy(
            INTRO_CONTEXTS
        ),
        "decision": {
            "Noa": "",
            "Ada": "",
        },
    }


def default_state():
    return {
        "world": (
            "Turing Hotel: un romanzo "
            "sull'identità, la memoria, "
            "le intelligenze artificiali "
            "e le relazioni umane."
        ),
        "agents": {
            person: {
                "profile": PROFILES[person],
                "memory": "",
                "profile_history": [],
            }
            for person in PEOPLE
        },
        "scenes": [
            empty_scene(sid)
            for sid in SCENE_IDS
        ],
        "editorial_log": [],
        "editorial_proposals": [],
    }


def aliases_for(sid):
    names = [
        sid,
        SCENE_NAMES[sid],
        *LEGACY_ALIASES.get(sid, []),
    ]
    return {
        normalize(name) for name in names
    }


def migrate_state(original):
    """
    Ricostruisce l'ordine delle 31 scene
    e conserva i dati storici riconosciuti.

    Campi nuovi aggiunti:
    - direction
    - profili secondari
    - registro editoriale
    """
    original = as_dict(original)

    result = fill_missing(
        copy.deepcopy(original),
        default_state()
    )

    old_scenes = as_list(
        original.get("scenes")
    )

    rebuilt = []

    for sid in SCENE_IDS:
        found = None
        aliases = aliases_for(sid)

        for candidate in old_scenes:
            if not isinstance(candidate, dict):
                continue

            if (
                normalize(
                    candidate.get("id", "")
                ) in aliases
                or normalize(
                    candidate.get("title", "")
                ) in aliases
            ):
                found = candidate
                break

        scene = fill_missing(
            copy.deepcopy(found)
            if found is not None else {},
            empty_scene(sid)
        )

        scene["id"] = sid
        scene["title"] = SCENE_NAMES[sid]

        if not isinstance(scene.get("cast"), list):
            scene["cast"] = copy.deepcopy(
                DEFAULT_CAST.get(
                    sid, ["Noa", "Ada"]
                )
            )

        scene["cast"] = [
            person
            for person in scene["cast"]
            if person in PEOPLE
        ]

        if not scene["cast"]:
            scene["cast"] = copy.deepcopy(
                DEFAULT_CAST.get(
                    sid, ["Noa", "Ada"]
                )
            )

        # Questa inizializzazione è essenziale.
        ensure_scene_direction(scene)

        if not isinstance(scene.get("narrative"), dict):
            scene["narrative"] = {}

        if not isinstance(scene.get("messages"), dict):
            scene["messages"] = {}

        if not isinstance(
            scene.get("monologue_topics"), dict
        ):
            scene["monologue_topics"] = {}

        for person in PEOPLE:
            scene["narrative"][person] = fill_missing(
                as_dict(
                    scene["narrative"].get(person)
                ),
                empty_narrative()
            )

            scene["messages"].setdefault(
                person, []
            )

            scene["monologue_topics"].setdefault(
                person, ""
            )

        rebuilt.append(scene)

    result["scenes"] = rebuilt

    if not isinstance(result.get("agents"), dict):
        result["agents"] = {}

    for person in PEOPLE:
        result["agents"][person] = fill_missing(
            as_dict(
                result["agents"].get(person)
            ),
            {
                "profile": PROFILES[person],
                "memory": "",
                "profile_history": [],
            }
        )

    return result


# ============================================================
# CARICAMENTO E SALVATAGGIO
# ============================================================

def load_archive():
    raw, sha = read_remote(ARCHIVE_PATH)

    if raw is None:
        return None, None

    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ArchiveError(
            "romanzo_web.json non contiene JSON valido."
        ) from exc

    return migrate_state(data), sha


def initialize():
    if "book_state" in st.session_state:
        # Protezione aggiuntiva:
        # anche una sessione già aperta viene
        # completata con i campi nuovi.
        st.session_state.book_state = migrate_state(
            st.session_state.book_state
        )
        return

    try:
        loaded, sha = load_archive()
    except ArchiveError as exc:
        st.error(str(exc))
        st.stop()

    st.session_state.book_state = (
        loaded if loaded is not None
        else default_state()
    )

    st.session_state.archive_sha = sha
    st.session_state.archive_exists = (
        loaded is not None
    )

    st.session_state.page = "entrance"
    st.session_state.pov = "Noa"
    st.session_state.scene_index = 0

    st.session_state.reference_loaded = False
    st.session_state.reference_text = None
    st.session_state.reference_error = ""


initialize()

state = st.session_state.book_state


def commit(change):
    backup = copy.deepcopy(state)

    try:
        change()

        # Prima del salvataggio, verifica
        # che tutte le scene siano complete.
        for item in state["scenes"]:
            ensure_scene_direction(item)

        if not st.session_state.archive_exists:
            raise ArchiveError(
                "Archivio non inizializzato."
            )

        new_sha = write_remote_json(
            state,
            st.session_state.archive_sha
        )

        st.session_state.archive_sha = new_sha

        return True

    except Exception as exc:
        state.clear()
        state.update(backup)
        st.error(
            "Modifica non salvata: " + str(exc)
        )
        return False


def reload_archive():
    try:
        loaded, sha = load_archive()

        if loaded is None:
            st.error("Archivio non trovato.")
            return False

        state.clear()
        state.update(loaded)
        st.session_state.archive_sha = sha
        return True

    except Exception as exc:
        st.error(str(exc))
        return False


# ============================================================
# STILE
# ============================================================

st.markdown(
    """
<style>
.stApp {
    background: #0b1014 !important;
    color: white !important;
}
[data-testid="stSidebar"] {
    background: #131b21 !important;
}
.stApp h1, .stApp h2, .stApp h3,
.stApp h4, .stApp h5, .stApp h6 {
    color: white !important;
}
.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stRadio"] label p,
.stApp [data-testid="stCheckbox"] label p {
    color: white !important;
}
.stApp .stButton button,
.stApp .stFormSubmitButton button,
.stApp .stDownloadButton button {
    background: #24323b !important;
    color: white !important;
    border: 1px solid #819099 !important;
    min-height: 42px;
}
.stApp .stButton button *,
.stApp .stDownloadButton button *,
.stApp .stFormSubmitButton button * {
    color: white !important;
}
.stApp input:not([type="checkbox"]):not([type="radio"]),
.stApp textarea {
    background: white !important;
    color: #111 !important;
    -webkit-text-fill-color: #111 !important;
    caret-color: #111 !important;
}
.stApp input::placeholder,
.stApp textarea::placeholder {
    color: #666 !important;
    -webkit-text-fill-color: #666 !important;
}
.stApp [data-baseweb="select"] > div {
    background: white !important;
    color: #111 !important;
}
.stApp [data-baseweb="select"] span,
.stApp [data-baseweb="select"] input {
    color: #111 !important;
}
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"] {
    background: white !important;
    color: #111 !important;
}
[data-baseweb="popover"] [role="option"] * {
    color: #111 !important;
}
.stApp button[data-baseweb="tab"] p {
    color: white !important;
}
.stApp button[data-baseweb="tab"][aria-selected="true"] {
    background: #e8e8e8 !important;
}
.stApp button[data-baseweb="tab"][aria-selected="true"] p {
    color: #111 !important;
}
.stApp [data-testid="stExpander"] {
    background: #182229 !important;
    border: 1px solid #465661 !important;
}
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary * {
    color: white !important;
}
.stApp pre {
    background: #182229 !important;
}
.stApp pre code {
    color: white !important;
}
.story-text {
    background: #192229;
    border-left: 3px solid #cbb08a;
    padding: 20px;
    white-space: pre-wrap;
    line-height: 1.75;
    font-size: 1.05rem;
    font-family: Georgia, serif;
}
.dialogue {
    background: #1e2a33;
    border-left: 3px solid #819eaf;
    padding: 14px;
    margin: 8px 0;
    white-space: pre-wrap;
}
.reply {
    background: #24362d;
    border-left: 3px solid #9dccaa;
    padding: 14px;
    margin: 8px 0;
    white-space: pre-wrap;
}
.thought {
    background: #2b241e;
    border-left: 3px solid #cbb08a;
    padding: 14px;
    margin: 8px 0;
    white-space: pre-wrap;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# ROMANZO DI RIFERIMENTO
# ============================================================

def load_reference(force=False):
    if (
        st.session_state.reference_loaded
        and not force
    ):
        return

    try:
        text, sha = read_remote(
            REFERENCE_PATH
        )

        st.session_state.reference_text = text
        st.session_state.reference_sha = sha

        st.session_state.reference_error = (
            "" if text
            else "La prima bozza non è ancora presente."
        )

    except Exception as exc:
        st.session_state.reference_text = None
        st.session_state.reference_error = str(exc)

    st.session_state.reference_loaded = True


def reference_chunks():
    load_reference()

    text = (
        st.session_state.reference_text
        or ""
    )

    if not text:
        return []

    chunk_size = 2500
    overlap = 250
    step = chunk_size - overlap

    return [
        text[start:start + chunk_size]
        for start in range(0, len(text), step)
    ]


def relevant_reference(characters, title="", limit=5):
    chunks = reference_chunks()

    if not chunks:
        return []

    character_words = [
        character.casefold()
        for character in characters
    ]

    scene_words = [
        word.casefold()
        for word in re.findall(
            r"[A-Za-zÀ-ÿ]{4,}", title
        )
        if word.casefold() not in {
            "della", "delle", "degli", "prima"
        }
    ]

    scored = []

    for index, text in enumerate(chunks):
        low = text.casefold()

        score = sum(
            low.count(word) * 4
            for word in character_words
        )

        score += sum(
            low.count(word)
            for word in scene_words
        )

        if score:
            scored.append(
                (score, index, text)
            )

    scored.sort(
        key=lambda x: (-x[0], x[1])
    )

    return [
        {
            "passage": index + 1,
            "text": text,
        }
        for _, index, text in scored[:limit]
    ]


# ============================================================
# ACCESSO ALLE SCENE
# ============================================================

def scene_by_id(sid):
    for scene in state["scenes"]:
        if scene["id"] == sid:
            ensure_scene_direction(scene)
            return scene

    raise KeyError(
        f"Scena non trovata: {sid}"
    )


def approved_before(sid, person):
    result = []

    for previous_id in SCENE_IDS:
        if previous_id == sid:
            break

        scene = scene_by_id(previous_id)

        text = (
            as_dict(
                scene["narrative"].get(person)
            ).get("approved", "")
        )

        if isinstance(text, str) and text.strip():
            result.append({
                "scene": scene["title"],
                "text": text,
            })

    return result


def canonical_context(scene, person):
    if (
        scene["id"] == "inizio"
        and person in PROTAGONISTS
    ):
        return scene["intro_contexts"].get(
            person,
            INTRO_CONTEXTS[person]
        )

    return scene.get(
        "approved_context", ""
    )


# ============================================================
# REGISTRO EDITORIALE
# ============================================================

def log_change(
    category,
    subject,
    before,
    after,
    reason="",
    scene_id="",
):
    state["editorial_log"].append({
        "id": len(
            state["editorial_log"]
        ) + 1,
        "date": now(),
        "category": category,
        "subject": subject,
        "before": before,
        "after": after,
        "reason": reason,
        "scene_id": scene_id,
    })


def text_diff(before, after):
    lines = difflib.unified_diff(
        str(before).splitlines(),
        str(after).splitlines(),
        fromfile="Versione precedente",
        tofile="Nuova versione",
        lineterm="",
    )
    return (
        "\n".join(lines)
        or "Nessuna differenza."
    )


# ============================================================
# DIREZIONE NARRATIVA
# ============================================================

def active_direction(scene):
    """
    Lettura sicura: mai KeyError
    se manca 'direction'.
    """
    direction = ensure_scene_direction(scene)
    value = direction.get("active")

    if isinstance(value, dict) and value:
        return value

    return None


def direction_for_agents(scene):
    direction = active_direction(scene)

    if direction is None:
        return {
            "active": False,
            "context": (
                "Non esiste una regia narrativa "
                "approvata per questa scena."
            ),
        }

    return {
        "active": True,
        "title": direction.get("title", ""),
        "situation": direction.get(
            "situation", ""
        ),
        "tension": direction.get(
            "tension", ""
        ),
        "opportunities": direction.get(
            "opportunities", ""
        ),
        "limits": direction.get(
            "limits", ""
        ),
        "dramatic_question": direction.get(
            "dramatic_question", ""
        ),
        "instruction": (
            "Questa è una direzione approvata "
            "dall'autore, non un copione. "
            "Considera le circostanze e "
            "la tensione narrativa. "
            "Puoi scegliere una reazione "
            "diversa se più coerente "
            "con il tuo personaggio. "
            "Non forzare alcun esito."
        ),
    }


def propose_directions(scene, question):
    profiles = {
        person: state["agents"][person]["profile"]
        for person in scene["cast"]
    }

    return ask_ai(
        """
Sei il consulente narrativo
di Turing Hotel.

Proponi esattamente TRE direzioni
drammaturgiche alternative
per la scena corrente.

Le direzioni devono essere
veramente differenti.

Ogni direzione deve proporre
circostanze, tensioni e opportunità.

Non prescrivere battute.
Non imporre emozioni.
Non decidere il finale.
Rispetta i profili dei personaggi.

Il romanzo originale è una reference.
Il nuovo canone ha precedenza.

Restituisci ESCLUSIVAMENTE JSON valido:

{
 "directions": [
  {
   "title":"...",
   "situation":"...",
   "tension":"...",
   "opportunities":"...",
   "limits":"...",
   "dramatic_question":"..."
  },
  {
   "title":"...",
   "situation":"...",
   "tension":"...",
   "opportunities":"...",
   "limits":"...",
   "dramatic_question":"..."
  },
  {
   "title":"...",
   "situation":"...",
   "tension":"...",
   "opportunities":"...",
   "limits":"...",
   "dramatic_question":"..."
  }
 ]
}
""",
        {
            "SCENA": scene["title"],
            "DOMANDA_AUTORE": question,
            "PERSONAGGI_PRESENTI": scene["cast"],
            "PROFILI": profiles,
            "CONTESTO":
                scene["approved_context"],
            "REGIA_PRECEDENTE":
                active_direction(scene),
            "PRIMA_BOZZA":
                relevant_reference(
                    scene["cast"],
                    scene["title"]
                ),
            "CANONE": {
                person: approved_before(
                    scene["id"], person
                )
                for person in scene["cast"]
            },
        }
    )


DIRECTION_FIELDS = [
    "title",
    "situation",
    "tension",
    "opportunities",
    "limits",
    "dramatic_question",
]


def validate_directions(response):
    if not isinstance(response, dict):
        return None

    items = response.get("directions")

    if not isinstance(items, list) or len(items) != 3:
        return None

    clean = []

    for item in items:
        if not isinstance(item, dict):
            return None

        proposal = {}

        for key in DIRECTION_FIELDS:
            value = str(
                item.get(key, "")
            ).strip()

            if not value:
                return None

            proposal[key] = value

        clean.append(proposal)

    return clean


def approve_direction(scene, proposal, reason):
    previous = active_direction(scene)

    approved = copy.deepcopy(proposal)
    approved["approved_at"] = now()
    approved["reason"] = reason
    approved["approved_by"] = "autore"
    approved["start_turn"] = len(
        scene["ensemble_messages"]
    )

    def change():
        direction = ensure_scene_direction(scene)

        if previous:
            direction["history"].append(
                copy.deepcopy(previous)
            )

        direction["active"] = approved

        log_change(
            "direzione narrativa",
            scene["title"],
            (
                json.dumps(
                    previous,
                    ensure_ascii=False,
                    indent=2
                )
                if previous else ""
            ),
            json.dumps(
                approved,
                ensure_ascii=False,
                indent=2
            ),
            reason,
            scene["id"],
        )

    return commit(change)


def deactivate_direction(scene, reason):
    previous = active_direction(scene)

    if previous is None:
        return False

    def change():
        direction = ensure_scene_direction(scene)

        direction["history"].append(
            copy.deepcopy(previous)
        )

        direction["active"] = None

        log_change(
            "regia disattivata",
            scene["title"],
            json.dumps(
                previous, ensure_ascii=False
            ),
            "Nessuna direzione attiva",
            reason,
            scene["id"],
        )

    return commit(change)


def evaluate_direction(scene):
    direction = active_direction(scene)

    if direction is None:
        return (
            "Non esiste una direzione "
            "narrativa approvata."
        )

    start = direction.get("start_turn", 0)

    if not isinstance(start, int):
        start = 0

    dialogue = scene[
        "ensemble_messages"
    ][start:]

    if not dialogue:
        return (
            "Non ci sono ancora battute "
            "successive all'approvazione."
        )

    return ask_ai(
        """
Sei il consulente narrativo.

Esamina il dialogo prodotto
dopo l'approvazione della regia.

Valuta:
1. Che cosa è accaduto davvero.
2. Quanto è emersa la direzione.
3. Quali scelte libere hanno fatto
   i personaggi.
4. Eventuali problemi di continuità.
5. Due nuovi sviluppi possibili.

Non correggere retroattivamente
le battute degli agenti.

Non modificare il canone.
""",
        {
            "SCENA": scene["title"],
            "DIREZIONE": direction,
            "DIALOGO": dialogue,
        }
    )


# ============================================================
# INTERFACCIA CONSULENTE
# ============================================================

def render_advisor(scene):
    """
    Anche le scene storiche prive del
    campo direction funzionano.
    """
    direction = ensure_scene_direction(scene)
    current = active_direction(scene)

    with st.expander(
        "CONSULENTE NARRATIVO E REGIA",
        expanded=False
    ):
        if current:
            st.success("DIREZIONE ATTIVA")

            st.subheader(
                current.get("title", "")
            )

            st.write(
                current.get("situation", "")
            )

            st.markdown(
                "**Tensione:** "
                + current.get("tension", "")
            )

            st.markdown(
                "**Domanda drammatica:** "
                + current.get(
                    "dramatic_question", ""
                )
            )

            st.caption(
                "Questa direzione ispira gli agenti "
                "ma non impone il risultato."
            )

        else:
            st.info(
                "Nessuna direzione narrativa attiva."
            )

        st.markdown("### Proponi tre direzioni")

        question = st.text_area(
            "Che sviluppo vuoi esplorare?",
            value=direction.get(
                "last_question", ""
            ),
            height=120,
            key=f"advisor_question_{scene['id']}"
        )

        if st.button(
            "PROPONI TRE DIREZIONI",
            key=f"propose_{scene['id']}",
            disabled=client is None,
            use_container_width=True
        ):
            with st.spinner(
                "Il consulente prepara le proposte..."
            ):
                answer = propose_directions(
                    scene, question
                )

            if failed(answer):
                st.error(answer)
            else:
                proposals = validate_directions(
                    parse_json(answer)
                )

                if not proposals:
                    st.error(
                        "Le proposte non sono in "
                        "formato valido. Riprova."
                    )

                else:
                    def change():
                        direction = ensure_scene_direction(
                            scene
                        )
                        direction["proposals"] = proposals
                        direction["last_question"] = question

                    if commit(change):
                        st.rerun()

        proposals = as_list(
            direction.get("proposals")
        )

        if proposals:
            st.markdown("### Scegli una proposta")

            for index, proposal in enumerate(proposals):
                with st.expander(
                    f"{index + 1}. "
                    f"{proposal.get('title', '')}",
                    expanded=(index == 0)
                ):
                    st.write(
                        proposal.get("situation", "")
                    )

                    with st.form(
                        f"direction_form_{scene['id']}_{index}"
                    ):
                        title = st.text_input(
                            "Titolo",
                            value=proposal.get("title", "")
                        )

                        situation = st.text_area(
                            "Situazione di partenza",
                            value=proposal.get(
                                "situation", ""
                            ),
                            height=100
                        )

                        tension = st.text_area(
                            "Tensione narrativa",
                            value=proposal.get(
                                "tension", ""
                            ),
                            height=90
                        )

                        opportunities = st.text_area(
                            "Opportunità di sviluppo",
                            value=proposal.get(
                                "opportunities", ""
                            ),
                            height=90
                        )

                        limits = st.text_area(
                            "Limiti e continuità",
                            value=proposal.get(
                                "limits", ""
                            ),
                            height=90
                        )

                        dramatic_question = st.text_area(
                            "Domanda drammatica",
                            value=proposal.get(
                                "dramatic_question", ""
                            )
                        )

                        reason = st.text_input(
                            "Motivo dell'approvazione"
                        )

                        submitted = st.form_submit_button(
                            "APPROVA E ATTIVA QUESTA DIREZIONE",
                            use_container_width=True
                        )

                    if submitted:
                        edited = {
                            "title": title.strip(),
                            "situation": situation.strip(),
                            "tension": tension.strip(),
                            "opportunities":
                                opportunities.strip(),
                            "limits": limits.strip(),
                            "dramatic_question":
                                dramatic_question.strip(),
                        }

                        if not all(edited.values()):
                            st.warning(
                                "Compila tutti i campi."
                            )

                        elif approve_direction(
                            scene, edited, reason
                        ):
                            st.rerun()

        st.markdown("---")
        st.markdown("### Valuta la conversazione")

        if st.button(
            "VALUTA COME È EVOLUTA LA SCENA",
            key=f"evaluate_{scene['id']}",
            disabled=(
                client is None
                or current is None
            ),
            use_container_width=True
        ):
            with st.spinner(
                "Il consulente esamina il dialogo..."
            ):
                report = evaluate_direction(scene)

            if failed(report):
                st.error(report)

            elif commit(
                lambda: ensure_scene_direction(
                    scene
                )["evaluations"].append({
                    "date": now(),
                    "direction_title": current["title"],
                    "text": report,
                })
            ):
                st.rerun()

        for item in reversed(
            as_list(direction.get("evaluations"))
        ):
            with st.expander(
                "Valutazione "
                + item.get("date", "")[:16]
            ):
                st.markdown(
                    item.get("text", "")
                )

        if current:
            with st.form(
                f"deactivate_{scene['id']}"
            ):
                reason = st.text_input(
                    "Motivo della disattivazione"
                )
                submitted = st.form_submit_button(
                    "DISATTIVA DIREZIONE"
                )

            if submitted and deactivate_direction(
                scene, reason
            ):
                st.rerun()

        with st.expander(
            "DIREZIONI PRECEDENTI"
        ):
            for item in reversed(
                as_list(direction.get("history"))
            ):
                st.markdown(
                    "**" + item.get("title", "")
                    + "**"
                )
                st.write(
                    item.get("situation", "")
                )


# ============================================================
# PROFILI DEGLI AGENTI
# ============================================================

def agent_instructions(person):
    profile = state["agents"][person]

    return f"""
Sei {person}, personaggio
del romanzo Turing Hotel.

PROFILO APPROVATO:
{profile.get("profile", "")}

MEMORIA:
{profile.get("memory", "")}

REGOLE:
- Sei il personaggio, non l'assistente.
- Non conosci i pensieri degli altri.
- Non anticipi fatti futuri.
- Non inventi ricordi fondamentali.
- Rispetti ciò che sai della scena.
- Il nuovo canone ha precedenza.
- La prima bozza è solo una reference.

La regia narrativa approvata
propone una situazione e una tensione.
Non prescrive le tue battute.

Puoi resistere alla direzione
se il tuo carattere ti porta altrove.
"""


def agent_payload(scene, person, history, prompt=""):
    return {
        "SCENA": scene["title"],
        "PERSONAGGIO": person,
        "PRESENTI": scene["cast"],
        "DOMANDA": prompt,
        "CONTESTO":
            canonical_context(scene, person),
        "REGIA_APPROVATA":
            direction_for_agents(scene),
        "ROMANZO_ORIGINALE":
            relevant_reference(
                scene["cast"], scene["title"]
            ),
        "CANONE_APPROVATO":
            approved_before(scene["id"], person),
        "CRONOLOGIA": history[-24:],
    }


# ============================================================
# RISPONDI - UNA SOLA BATTUTA
# ============================================================

def reply_once(scene, person, prompt, speaking_as):
    if person not in scene["cast"]:
        return (
            "Il personaggio deve essere "
            "presente nella scena."
        )

    if not prompt.strip():
        return "Scrivi una domanda."

    response = ask_ai(
        agent_instructions(person)
        + """
MODALITÀ: RISPONDI.

Produci UNA SOLA risposta secca.

Preferibilmente una o due frasi.
Nessuna didascalia.
Nessuna descrizione.
Nessuna introduzione.
Non scrivere il nome.
Non continuare la conversazione.

Rispondi secondo il tuo carattere
e considerando la regia approvata,
senza forzare il risultato.

Restituisci solo la battuta.
""",
        agent_payload(
            scene,
            person,
            scene["ensemble_messages"],
            prompt
        )
    )

    if failed(response):
        return response

    messages = [
        {
            "speaker": speaking_as,
            "text": prompt.strip(),
            "origin": "manual_prompt",
            "created_at": now(),
        },
        {
            "speaker": person,
            "text": response.strip(),
            "origin": "single_reply",
            "created_at": now(),
        },
    ]

    if commit(
        lambda: scene[
            "ensemble_messages"
        ].extend(messages)
    ):
        return ""

    return "Risposta non salvata."


# ============================================================
# GO ALONE - DIALOGO AUTONOMO
# ============================================================

def go_alone_dialogue(scene, turns=4):
    cast = scene["cast"]

    if len(cast) < 2:
        return (
            "Per GO ALONE servono "
            "almeno due personaggi."
        )

    history = copy.deepcopy(
        scene["ensemble_messages"]
    )

    generated = []

    last_speaker = (
        history[-1].get("speaker", "")
        if history else ""
    )

    start = (
        (cast.index(last_speaker) + 1) % len(cast)
        if last_speaker in cast else 0
    )

    for number in range(turns):
        person = cast[
            (start + number) % len(cast)
        ]

        response = ask_ai(
            agent_instructions(person)
            + """
MODALITÀ GO ALONE.

Continua la conversazione con
UNA SOLA battuta.

Non parlare al posto degli altri.
Non scrivere didascalie.
Non scrivere il nome.

La regia è una possibilità,
non un copione.

Reagisci in modo coerente
con la tua personalità.
""",
            agent_payload(
                scene, person, history
            )
        )

        if failed(response):
            return response

        item = {
            "speaker": person,
            "text": response.strip(),
            "origin": "go_alone",
            "created_at": now(),
        }

        generated.append(item)
        history.append(item)

    if commit(
        lambda: scene[
            "ensemble_messages"
        ].extend(generated)
    ):
        return ""

    return "Dialogo non salvato."


# ============================================================
# MONOLOGO - DUE PENSIERI
# ============================================================

def go_alone_monologue(scene, person, theme):
    if not theme.strip():
        return "Inserisci prima il tema."

    history = copy.deepcopy(
        scene["messages"].get(person, [])
    )

    generated = []

    for number in (1, 2):
        response = ask_ai(
            agent_instructions(person)
            + f"""
MONOLOGO INTERIORE.

Pensiero {number} di 2.

Tema: {theme}

Produci un solo pensiero
in prima persona e al presente.

Il secondo pensiero sviluppa
il primo.

Considera la direzione approvata
senza forzare il risultato.

Nessun titolo.
Nessuna voce esterna.
""",
            {
                "SCENA": scene["title"],
                "TEMA": theme,
                "CONTESTO":
                    canonical_context(
                        scene, person
                    ),
                "REGIA":
                    direction_for_agents(scene),
                "REFERENCE":
                    relevant_reference(
                        [person], scene["title"]
                    ),
                "CANONE":
                    approved_before(
                        scene["id"], person
                    ),
                "PENSIERI": history,
            }
        )

        if failed(response):
            return response

        item = {
            "speaker": person,
            "text": response,
            "kind": "inner",
            "origin": "monologue",
            "thought_number": number,
            "theme": theme,
            "created_at": now(),
        }

        generated.append(item)
        history.append(item)

    def change():
        scene["monologue_topics"][person] = theme
        scene["messages"].setdefault(
            person, []
        ).extend(generated)

    if commit(change):
        return ""

    return "Monologo non salvato."


# ============================================================
# CONTESTO DELLA SCENA
# ============================================================

def render_context(scene, person):
    sid = scene["id"]

    if sid == "inizio" and person in PROTAGONISTS:
        text = st.text_area(
            "Contesto del prologo",
            value=scene["intro_contexts"].get(
                person, INTRO_CONTEXTS[person]
            ),
            height=145,
            key=f"intro_{person}"
        )

        if st.button(
            "SALVA CONTESTO DEL PROLOGO",
            key=f"save_intro_{person}"
        ):
            if commit(
                lambda: scene[
                    "intro_contexts"
                ].update({person: text})
            ):
                st.success("Contesto salvato.")

        return

    with st.expander("CREATORE DELLA SCENA"):
        notes = st.text_area(
            "Indicazioni dell'autore",
            value=scene["author_context"],
            height=130,
            key=f"context_notes_{sid}"
        )

        if st.button(
            "SALVA INDICAZIONI",
            key=f"save_notes_{sid}"
        ):
            if commit(
                lambda: scene.update(
                    author_context=notes
                )
            ):
                st.success("Indicazioni salvate.")

        if st.button(
            "GENERA CONTESTO CON AI",
            key=f"generate_context_{sid}",
            disabled=client is None
        ):
            with st.spinner("Preparazione del contesto..."):
                answer = ask_ai(
                    """
Sei il consulente narrativo.

Prepara un contesto concreto
per la scena.

Usa le indicazioni dell'autore,
la prima bozza e la direzione
narrativa approvata.

Non prescrivere battute.
Non determinare gli esiti.
Non imporre emozioni.

Il nuovo canone prevale.

Restituisci solo il contesto.
""",
                    {
                        "SCENA": scene["title"],
                        "NOTE": notes,
                        "REGIA":
                            direction_for_agents(scene),
                        "REFERENCE":
                            relevant_reference(
                                scene["cast"],
                                scene["title"]
                            ),
                        "CONTESTO_ATTUALE":
                            scene["approved_context"],
                    }
                )

            if failed(answer):
                st.error(answer)
            elif commit(
                lambda: scene.update(
                    author_context=notes,
                    story_draft=answer
                )
            ):
                st.rerun()

        if scene["story_draft"]:
            draft = st.text_area(
                "Contesto proposto",
                value=scene["story_draft"],
                height=200,
                key=f"context_draft_{sid}"
            )

            if st.button(
                "APPROVA CONTESTO",
                key=f"approve_context_{sid}"
            ):
                def change():
                    old = scene["approved_context"]

                    scene["story_draft"] = draft
                    scene["approved_context"] = draft

                    if old != draft:
                        log_change(
                            "contesto approvato",
                            scene["title"],
                            old,
                            draft,
                            "Approvazione autore",
                            sid
                        )

                if commit(change):
                    st.rerun()


# ============================================================
# DIALOGHI: INTERFACCIA
# ============================================================

def render_interactions(scene, pov):
    sid = scene["id"]

    st.markdown("---")
    st.header("Personaggi e conversazioni")

    cast = st.multiselect(
        "PERSONAGGI PRESENTI",
        PEOPLE,
        default=scene["cast"],
        key=f"cast_{sid}"
    )

    if st.button(
        "SALVA PERSONAGGI PRESENTI",
        key=f"save_cast_{sid}"
    ):
        def change():
            old = ", ".join(scene["cast"])
            new = ", ".join(cast)

            scene["cast"] = cast

            if old != new:
                log_change(
                    "personaggi presenti",
                    scene["title"],
                    old,
                    new,
                    "Scelta autore",
                    sid
                )

        if commit(change):
            st.rerun()

    active = active_direction(scene)

    if active:
        st.info(
            "REGIA ATTIVA: "
            + active.get("title", "")
        )

    mode = st.radio(
        "Modalità",
        ["Dialogo", "Monologo"],
        horizontal=True,
        key=f"mode_{sid}_{pov}"
    )

    if mode == "Dialogo":
        for item in scene["ensemble_messages"]:
            css = (
                "reply"
                if item.get("origin") == "single_reply"
                else "dialogue"
            )

            st.markdown(
                f'<div class="{css}"><strong>'
                + escape(item.get("speaker", "?"))
                + "</strong><div>"
                + escape(item.get("text", ""))
                + "</div></div>",
                unsafe_allow_html=True
            )

        available = scene["cast"] or PEOPLE

        st.markdown("### RISPONDI")

        speaking_as = st.selectbox(
            "Chi pone la domanda?",
            ["Autore", *available],
            key=f"speaking_{sid}"
        )

        responder = st.selectbox(
            "Chi deve rispondere?",
            available,
            key=f"responder_{sid}"
        )

        prompt = st.text_area(
            "Domanda o battuta",
            height=100,
            key=f"reply_prompt_{sid}"
        )

        if st.button(
            "RISPONDI — UNA BATTUTA",
            key=f"reply_{sid}",
            disabled=(
                client is None
                or not prompt.strip()
            ),
            use_container_width=True
        ):
            with st.spinner(
                responder + " risponde..."
            ):
                error = reply_once(
                    scene,
                    responder,
                    prompt,
                    speaking_as
                )

            if error:
                st.error(error)
            else:
                st.session_state[
                    f"reply_prompt_{sid}"
                ] = ""
                st.rerun()

        st.markdown("---")

        if st.button(
            "GO ALONE — QUATTRO BATTUTE",
            key=f"go_{sid}",
            disabled=client is None,
            use_container_width=True
        ):
            with st.spinner(
                "I personaggi conversano..."
            ):
                error = go_alone_dialogue(
                    scene, turns=4
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        st.markdown("---")

        with st.form(
            f"manual_{sid}",
            clear_on_submit=True
        ):
            speaker = st.selectbox(
                "Aggiungi una battuta di",
                available
            )

            text = st.text_area(
                "Testo della battuta"
            )

            submitted = st.form_submit_button(
                "AGGIUNGI BATTUTA"
            )

        if submitted and text.strip():
            item = {
                "speaker": speaker,
                "text": text,
                "origin": "manual",
                "created_at": now(),
            }

            if commit(
                lambda: scene[
                    "ensemble_messages"
                ].append(item)
            ):
                st.rerun()

    else:
        available = scene["cast"] or PEOPLE

        person = st.selectbox(
            "Personaggio del monologo",
            available,
            key=f"inner_person_{sid}"
        )

        theme = st.text_area(
            "Tema del monologo",
            value=scene[
                "monologue_topics"
            ].get(person, ""),
            key=f"theme_{sid}_{person}"
        )

        if st.button(
            "GO ALONE — DUE PENSIERI",
            key=f"inner_go_{sid}_{person}",
            disabled=(
                client is None
                or not theme.strip()
            )
        ):
            with st.spinner(
                "Il personaggio riflette..."
            ):
                error = go_alone_monologue(
                    scene, person, theme
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        for item in scene["messages"].get(
            person, []
        ):
            st.markdown(
                '<div class="thought">'
                + escape(item.get("text", ""))
                + "</div>",
                unsafe_allow_html=True
            )

    with st.expander("GESTIONE CONVERSAZIONE"):
        confirmed = st.checkbox(
            "Confermo la cancellazione",
            key=f"clear_confirm_{sid}_{pov}"
        )

        if st.button(
            "CANCELLA DIALOGO DELLA SCENA",
            key=f"clear_{sid}",
            disabled=not confirmed
        ):
            if commit(
                lambda: scene.update(
                    ensemble_messages=[]
                )
            ):
                st.rerun()


# ============================================================
# TRASCRIZIONE
# ============================================================

def transcript(scene, person):
    parts = [
        scene["title"],
        f"Punto di vista: {person}",
        "",
    ]

    for item in scene["ensemble_messages"]:
        parts.append(
            f"{item.get('speaker', '?')}: "
            f"{item.get('text', '')}"
        )

    for item in scene["messages"].get(
        person, []
    ):
        parts.append(
            f"{person} (pensiero): "
            f"{item.get('text', '')}"
        )

    return "\n\n".join(parts)


# ============================================================
# OFFICINA LETTERARIA
# ============================================================

def write_version(scene, person, version, notes):
    style = (
        "Essenziale, preciso, sobrio."
        if version == "A"
        else
        "Evocativo, sensoriale, introspettivo."
    )

    return ask_ai(
        f"""
Sei uno scrittore letterario.

Trasforma la scena in un racconto compiuto.

VERSIONE: {version}
STILE: {style}

Punto di vista: {person}
Prima persona.
Tempo presente.

Usa i dialoghi effettivi,
il contesto e la direzione approvata.

Non attribuire al narratore
informazioni che non conosce.

Non imporre esiti non verificati.
La prima bozza è solo un riferimento.
Il nuovo canone prevale.

Restituisci soltanto il racconto.
""",
        {
            "SCENA": scene["title"],
            "TRASCRIZIONE":
                transcript(scene, person),
            "CONTESTO":
                canonical_context(scene, person),
            "REGIA":
                direction_for_agents(scene),
            "REFERENCE":
                relevant_reference(
                    scene["cast"], scene["title"]
                ),
            "CANONE":
                approved_before(
                    scene["id"], person
                ),
            "NOTE_AUTORE": notes,
        }
    )


def critic(scene, person):
    record = scene["narrative"][person]

    response = ask_ai(
        """
Sei un critico letterario.

Confronta A e B.
Indica la versione preferita.
Motiva la scelta.
Segnala problemi e alternative.

Non approvare alcun testo.

Restituisci SOLO JSON:

{
 "preferenza":"A",
 "motivazione":"...",
 "riserve":"...",
 "alternativa":"..."
}
""",
        {
            "VERSIONE_A": record["A"],
            "VERSIONE_B": record["B"],
            "REGIA": direction_for_agents(scene),
        }
    )

    if failed(response):
        return None, response

    data = parse_json(response)

    if not isinstance(data, dict):
        return None, "Giudizio non valido."

    winner = str(
        data.get("preferenza", "")
    ).upper()

    if winner not in ("A", "B"):
        return None, "Preferenza non valida."

    report = (
        f"**Preferisco {winner}**\n\n"
        + str(data.get("motivazione", ""))
        + "\n\n**Riserve:** "
        + str(data.get("riserve", ""))
        + "\n\n**Alternative:** "
        + str(data.get("alternativa", ""))
    )

    return winner, report


def visual_prompts(scene, person):
    approved = scene[
        "narrative"
    ][person]["approved"]

    response = ask_ai(
        """
Sei un direttore della fotografia.

Dal testo approvato ricava:
una bibbia visiva e sei inquadrature.

Per ognuna:
- titolo;
- prompt immagine;
- prompt video.

Non inventare eventi nuovi.

Restituisci SOLO JSON:

{
 "bible":"...",
 "shots":[
  {
   "title":"...",
   "image_prompt":"...",
   "video_prompt":"..."
  }
 ]
}
""",
        {
            "SCENA": scene["title"],
            "TESTO_APPROVATO": approved,
        }
    )

    if failed(response):
        return None

    return parse_json(response)


def docx_data(title, body):
    doc = Document()
    doc.add_heading(title, 0)

    for paragraph in body.split("\n"):
        doc.add_paragraph(paragraph)

    buffer = BytesIO()
    doc.save(buffer)

    return buffer.getvalue()


def downloads(title, filename, text, key):
    if not text.strip():
        return

    columns = st.columns(3)

    with columns[0]:
        st.download_button(
            "TXT",
            text.encode("utf-8"),
            file_name=filename + ".txt",
            mime="text/plain",
            key=key + "_txt"
        )

    with columns[1]:
        st.download_button(
            "MARKDOWN",
            text.encode("utf-8"),
            file_name=filename + ".md",
            mime="text/markdown",
            key=key + "_md"
        )

    with columns[2]:
        st.download_button(
            "WORD",
            docx_data(title, text),
            file_name=filename + ".docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            key=key + "_docx"
        )


def render_workshop(scene, person):
    sid = scene["id"]
    record = scene["narrative"][person]

    st.markdown("---")
    st.header("Officina del romanzo")
    st.caption("Punto di vista: " + person)

    notes = st.text_area(
        "Indicazioni letterarie",
        value=record["feedback"],
        key=f"writer_notes_{sid}_{person}"
    )

    if st.button(
        "GENERA VERSIONI A E B",
        key=f"write_{sid}_{person}",
        disabled=client is None
    ):
        if not (
            scene["ensemble_messages"]
            or scene["messages"].get(person)
        ):
            st.warning(
                "Registra prima un dialogo "
                "o un monologo."
            )

        else:
            with st.spinner("Scrittura..."):
                version_a = write_version(
                    scene, person, "A", notes
                )

                version_b = (
                    write_version(
                        scene, person, "B", notes
                    )
                    if not failed(version_a)
                    else ""
                )

            if failed(version_a):
                st.error(version_a)

            elif failed(version_b):
                st.error(version_b)

            else:
                def change():
                    record["A"] = version_a
                    record["B"] = version_b
                    record["feedback"] = notes
                    record["status"] = "in_revisione"
                    record["review"] = ""
                    record["recommended"] = ""

                if commit(change):
                    st.rerun()

    if record["A"] or record["B"]:
        tab_a, tab_b = st.tabs(
            ["VERSIONE A", "VERSIONE B"]
        )

        with tab_a:
            st.markdown(
                '<div class="story-text">'
                + escape(record["A"])
                + "</div>",
                unsafe_allow_html=True
            )

        with tab_b:
            st.markdown(
                '<div class="story-text">'
                + escape(record["B"])
                + "</div>",
                unsafe_allow_html=True
            )

        if st.button(
            "CHIEDI GIUDIZIO CRITICO",
            key=f"critic_{sid}_{person}",
            disabled=client is None
        ):
            winner, report = critic(
                scene, person
            )

            if not winner:
                st.error(report)

            elif commit(
                lambda: record.update(
                    recommended=winner,
                    review=report
                )
            ):
                st.rerun()

    if record["review"]:
        st.markdown(record["review"])

    options = ["Bozza salvata"]

    if record["A"]:
        options.append("Versione A")

    if record["B"]:
        options.append("Versione B")

    selection = st.selectbox(
        "Testo da revisionare",
        options,
        key=f"selection_{sid}_{person}"
    )

    if selection == "Versione A":
        initial = record["A"]
    elif selection == "Versione B":
        initial = record["B"]
    else:
        initial = record["draft"]

    editor_key = (
        f"editor_{sid}_{person}_"
        f"{normalize(selection)}"
    )

    source_key = editor_key + "_source"

    if st.session_state.get(source_key) != initial:
        st.session_state[editor_key] = initial
        st.session_state[source_key] = initial

    edited = st.text_area(
        "Testo narrativo",
        height=340,
        key=editor_key
    )

    reason = st.text_input(
        "Motivazione della modifica",
        key=f"reason_{sid}_{person}"
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA",
            key=f"draft_{sid}_{person}"
        ):
            if commit(
                lambda: record.update(
                    draft=edited,
                    status="bozza"
                )
            ):
                st.success("Bozza salvata.")

    with right:
        if st.button(
            "APPROVA E MEMORIZZA",
            key=f"approve_{sid}_{person}",
            disabled=not edited.strip()
        ):
            def change():
                previous = record["approved"]

                if previous and previous != edited:
                    record["history"].append({
                        "text": previous,
                        "replaced_at": now(),
                        "reason": reason,
                    })

                record["draft"] = edited
                record["approved"] = edited
                record["approved_at"] = now()
                record["status"] = "approvata"

                if person in PROTAGONISTS:
                    scene["diary"][person] = edited

                if previous != edited:
                    log_change(
                        "racconto approvato",
                        f"{scene['title']} - {person}",
                        previous,
                        edited,
                        reason,
                        sid
                    )
                    record["visual"][
                        "source_approved_at"
                    ] = ""

            if commit(change):
                st.rerun()

    downloads(
        scene["title"],
        f"{sid}_{person.lower()}",
        edited,
        f"download_{sid}_{person}"
    )

    if record["approved"]:
        with st.expander("TESTO APPROVATO"):
            st.markdown(
                '<div class="story-text">'
                + escape(record["approved"])
                + "</div>",
                unsafe_allow_html=True
            )

    with st.expander(
        "TRASCRIZIONE DELLA SCENA"
    ):
        st.text(transcript(scene, person))

    with st.expander(
        "VERSIONI PRECEDENTI"
    ):
        for item in reversed(
            as_list(record["history"])
        ):
            st.caption(
                item.get("replaced_at", "")
            )
            st.code(
                text_diff(
                    item.get("text", ""),
                    record["approved"]
                ),
                language="diff"
            )

    with st.expander("OFFICINA VISIVA"):
        if not record["approved"]:
            st.info(
                "Approva prima un racconto."
            )
        else:
            if st.button(
                "GENERA PROMPT VISIVI",
                key=f"visual_{sid}_{person}",
                disabled=client is None
            ):
                result = visual_prompts(
                    scene, person
                )

                if not isinstance(result, dict):
                    st.error(
                        "Generazione non riuscita."
                    )
                else:
                    def change():
                        record["visual"] = {
                            "bible": result.get(
                                "bible", ""
                            ),
                            "prompts": result.get(
                                "shots", []
                            ),
                            "source_approved_at":
                                record["approved_at"],
                        }

                    if commit(change):
                        st.rerun()

            visual = record["visual"]

            if (
                visual.get("source_approved_at")
                == record["approved_at"]
            ):
                st.write(
                    visual.get("bible", "")
                )

                for index, shot in enumerate(
                    as_list(
                        visual.get("prompts")
                    ), 1
                ):
                    st.markdown(
                        f"**Inquadratura {index}**"
                    )
                    st.write(shot.get("title", ""))
                    st.code(
                        shot.get("image_prompt", "")
                    )
                    st.code(
                        shot.get("video_prompt", "")
                    )


# ============================================================
# MEDIA
# ============================================================

def parse_media(path, sid, person):
    extension = path.suffix.casefold()

    if extension not in IMAGE_EXT | VIDEO_EXT:
        return None

    name = normalize(path.stem)
    character = normalize(person)

    aliases = sorted(
        aliases_for(sid),
        key=len,
        reverse=True
    )

    for alias in aliases:
        if not name.startswith(alias):
            continue

        tail = name[len(alias):]

        if tail == character and extension in IMAGE_EXT:
            return ("cover", 0)

        if tail.startswith(character):
            number = tail[len(character):]

            if number.isdigit():
                return (
                    "video"
                    if extension in VIDEO_EXT
                    else "image",
                    int(number)
                )

        if (
            tail == ""
            and sid != "inizio"
            and extension in IMAGE_EXT
        ):
            return ("generic_cover", 0)

        if (
            sid != "inizio"
            and tail.isdigit()
        ):
            return (
                "video"
                if extension in VIDEO_EXT
                else "image",
                int(tail)
            )

    return None


def scene_media(sid, person):
    output = {
        "cover": [],
        "generic_cover": [],
        "image": [],
        "video": [],
    }

    if not ASSETS.is_dir():
        return output

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        parsed = parse_media(
            path, sid, person
        )

        if parsed:
            kind, number = parsed
            output[kind].append(
                (number, path)
            )

    for kind in output:
        output[kind].sort(
            key=lambda pair: (
                pair[0],
                pair[1].name.casefold()
            )
        )
        output[kind] = [
            path
            for _, path in output[kind]
        ]

    return output


def render_media(scene, person):
    sid = scene["id"]
    media = scene_media(sid, person)

    covers = (
        media["cover"]
        or media["generic_cover"]
    )

    if covers:
        st.image(
            str(covers[0]),
            use_container_width=True
        )
        st.caption(
            "Copertina: " + covers[0].name
        )

    entries = []

    for kind in ("image", "video"):
        for path in media[kind]:
            parsed = parse_media(
                path, sid, person
            )

            if parsed:
                entries.append(
                    (parsed[1], kind, path)
                )

    entries.sort(
        key=lambda item: (
            item[0],
            item[2].name.casefold()
        )
    )

    for start in range(0, len(entries), 2):
        columns = st.columns(2)

        for column, entry in zip(
            columns,
            entries[start:start + 2]
        ):
            _, kind, path = entry

            with column:
                try:
                    if kind == "image":
                        st.image(
                            str(path),
                            use_container_width=True
                        )
                    else:
                        st.video(str(path))

                    st.caption(path.name)
                except Exception as exc:
                    st.error(str(exc))

    with st.expander("DIAGNOSTICA MEDIA"):
        prefix = f"{sid}.{person.lower()}"

        if covers:
            st.success(
                "Copertina: " + covers[0].name
            )
        else:
            st.warning(
                "Manca: " + prefix + ".jpg"
            )

        for kind, ext, count in (
            ("image", "jpg", 3),
            ("video", "mp4", 2)
        ):
            for number in range(1, count + 1):
                matches = []

                for path in media[kind]:
                    parsed = parse_media(
                        path, sid, person
                    )

                    if parsed and parsed[1] == number:
                        matches.append(path.name)

                if matches:
                    st.success(
                        "Trovato: "
                        + ", ".join(matches)
                    )
                else:
                    st.warning(
                        f"Manca: {prefix}.{number}.{ext}"
                    )


# ============================================================
# ARCHIVIO PERSONAGGI
# ============================================================

def page_people():
    st.title("Archivio dei personaggi")

    person = st.selectbox(
        "Personaggio", PEOPLE
    )

    agent = state["agents"][person]

    st.markdown("### Profilo approvato")
    st.write(agent["profile"])

    st.markdown(
        "### Brani della prima bozza"
    )

    passages = relevant_reference(
        [person], limit=4
    )

    if not passages:
        st.warning(
            "Nessun brano disponibile."
        )

    for item in passages:
        with st.expander(
            f"Passaggio {item['passage']}"
        ):
            st.text(item["text"])

    edited = st.text_area(
        "Modifica del profilo",
        value=agent["profile"],
        height=220,
        key=f"profile_{person}"
    )

    reason = st.text_input(
        "Motivazione",
        key=f"profile_reason_{person}"
    )

    if st.button(
        "APPROVA NUOVO PROFILO",
        disabled=(
            edited == agent["profile"]
            or not edited.strip()
        )
    ):
        def change():
            old = agent["profile"]

            agent["profile_history"].append({
                "profile": old,
                "replaced_at": now(),
            })

            agent["profile"] = edited

            log_change(
                "profilo personaggio",
                person,
                old,
                edited,
                reason
            )

        if commit(change):
            st.rerun()

    with st.expander(
        "CRONOLOGIA DEL PROFILO"
    ):
        for item in reversed(
            agent["profile_history"]
        ):
            st.caption(
                item.get("replaced_at", "")
            )
            st.code(
                text_diff(
                    item.get("profile", ""),
                    agent["profile"]
                ),
                language="diff"
            )


# ============================================================
# REGISTRO EDITORIALE
# ============================================================

def page_editorial():
    st.title("Registro editoriale")

    tab_history, tab_proposals = st.tabs(
        ["MODIFICHE APPROVATE", "PROPOSTE"]
    )

    with tab_history:
        if not state["editorial_log"]:
            st.info(
                "Nessuna modifica registrata."
            )

        for item in reversed(
            state["editorial_log"]
        ):
            with st.expander(
                item.get("date", "")[:10]
                + " - "
                + item.get("subject", "")
            ):
                st.write(
                    "**Categoria:** "
                    + item.get("category", "")
                )
                st.write(
                    "**Motivazione:** "
                    + item.get("reason", "")
                )
                st.code(
                    text_diff(
                        item.get("before", ""),
                        item.get("after", "")
                    ),
                    language="diff"
                )

    with tab_proposals:
        with st.form(
            "editorial_proposal",
            clear_on_submit=True
        ):
            subject = st.text_input(
                "Personaggio o elemento"
            )
            before = st.text_area(
                "Prima bozza"
            )
            after = st.text_area(
                "Nuova proposta"
            )
            reason = st.text_area(
                "Motivazione"
            )

            submitted = st.form_submit_button(
                "SALVA PROPOSTA"
            )

        if submitted and subject.strip():
            def change():
                state["editorial_proposals"].append({
                    "subject": subject,
                    "before": before,
                    "after": after,
                    "reason": reason,
                    "date": now(),
                    "status": "proposta",
                })

            if commit(change):
                st.rerun()

        for item in reversed(
            state["editorial_proposals"]
        ):
            with st.expander(
                item.get("subject", "")
            ):
                st.write(
                    item.get("reason", "")
                )
                st.code(
                    text_diff(
                        item.get("before", ""),
                        item.get("after", "")
                    ),
                    language="diff"
                )

    st.download_button(
        "SCARICA REGISTRO",
        json.dumps(
            {
                "changes":
                    state["editorial_log"],
                "proposals":
                    state["editorial_proposals"],
            },
            ensure_ascii=False,
            indent=2
        ).encode("utf-8"),
        file_name="turing_hotel_registro.json",
        mime="application/json"
    )


# ============================================================
# ARCHIVIO SCENE
# ============================================================

def page_archive():
    st.title("Archivio scene approvate")

    count = 0

    for sid in SCENE_IDS:
        scene = scene_by_id(sid)

        for person in PEOPLE:
            text = scene[
                "narrative"
            ][person]["approved"]

            if not text.strip():
                continue

            count += 1

            with st.expander(
                scene["title"] + " - " + person
            ):
                st.markdown(
                    '<div class="story-text">'
                    + escape(text)
                    + "</div>",
                    unsafe_allow_html=True
                )

                downloads(
                    scene["title"],
                    f"{sid}_{person.lower()}",
                    text,
                    f"archive_{sid}_{person}"
                )

    if not count:
        st.info(
            "Non ci sono ancora testi approvati."
        )


# ============================================================
# INGRESSO
# ============================================================

def page_entrance():
    hotel = find_asset("TuringHotel.jpg")

    if hotel:
        st.image(
            str(hotel),
            use_container_width=True
        )

    st.title("TURING HOTEL")
    st.caption(
        "Un romanzo a più coscienze"
    )

    if st.button(
        "ENTRA AL TURING HOTEL",
        use_container_width=True
    ):
        st.session_state.page = "characters"
        st.rerun()


def page_characters():
    st.title("Scegli una storia")

    columns = st.columns(2)

    for column, person in zip(
        columns, PROTAGONISTS
    ):
        with column:
            portrait = find_asset(
                person + ".jpg"
            )

            if portrait:
                st.image(
                    str(portrait),
                    use_container_width=True
                )

            st.subheader(person)

            if st.button(
                "ENTRA NELLA STORIA DI "
                + person.upper(),
                key=f"choose_{person}",
                use_container_width=True
            ):
                st.session_state.pov = person
                st.session_state.scene_index = 0
                st.session_state.page = "story"
                st.rerun()


# ============================================================
# SIDEBAR
# ============================================================

def sidebar():
    index = st.session_state.scene_index
    pov = st.session_state.pov

    st.sidebar.title("TURING HOTEL")

    selected = st.sidebar.selectbox(
        "SCENA",
        SCENE_IDS,
        index=index,
        format_func=lambda sid: (
            f"{SCENE_IDS.index(sid) + 1:02d}"
            f" - {SCENE_NAMES[sid]}"
        ),
        key=f"scene_nav_{index}_{pov}"
    )

    if selected != SCENE_IDS[index]:
        st.session_state.scene_index = (
            SCENE_IDS.index(selected)
        )
        st.rerun()

    st.sidebar.caption(
        f"Scena {index + 1}/31"
    )

    st.sidebar.markdown("---")

    for label, page in [
        ("ARCHIVIO SCENE", "archive"),
        ("ARCHIVIO PERSONAGGI", "people"),
        ("REGISTRO MODIFICHE", "editorial"),
        ("CAMBIA STORIA", "characters"),
    ]:
        if st.sidebar.button(
            label,
            key="nav_" + page,
            use_container_width=True
        ):
            st.session_state.page = page
            st.rerun()

    with st.sidebar.expander("PRIMA BOZZA"):
        load_reference()

        text = st.session_state.reference_text

        if text:
            st.success(
                "Romanzo originale collegato."
            )
            st.caption(
                f"{len(text)} caratteri"
            )
        else:
            st.warning(
                st.session_state.reference_error
                or "Reference non disponibile."
            )

        st.code(REFERENCE_PATH)

        if st.button(
            "RICARICA PRIMA BOZZA",
            key="reload_reference"
        ):
            load_reference(force=True)
            st.rerun()

    with st.sidebar.expander(
        "ARCHIVIO GITHUB"
    ):
        st.caption(
            GH_OWNER + "/" + GH_REPO
        )

        if st.button(
            "RICARICA ARCHIVIO",
            key="reload_archive"
        ):
            if reload_archive():
                st.rerun()

        st.download_button(
            "SCARICA BACKUP",
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2
            ).encode("utf-8"),
            file_name="turing_hotel_backup.json",
            mime="application/json",
            key="download_backup"
        )


# ============================================================
# PAGINA DELLA SCENA
# ============================================================

def page_story():
    pov = st.session_state.pov

    if pov not in PROTAGONISTS:
        st.session_state.page = "characters"
        st.rerun()

    index = max(
        0,
        min(
            st.session_state.scene_index,
            len(SCENE_IDS) - 1
        )
    )

    st.session_state.scene_index = index

    sid = SCENE_IDS[index]
    scene = scene_by_id(sid)

    # Ulteriore protezione sul punto esatto
    # in cui si verificava il KeyError.
    ensure_scene_direction(scene)

    sidebar()

    st.title(scene["title"])

    st.caption(
        f"Scena {index + 1}/31 "
        f"- storia di {pov}"
    )

    media_person = st.selectbox(
        "Media del personaggio",
        PROTAGONISTS,
        index=PROTAGONISTS.index(pov),
        key=f"media_{sid}_{pov}"
    )

    render_media(scene, media_person)

    st.markdown("---")

    render_context(scene, pov)

    # Ora funziona anche se la scena storica
    # non conteneva il campo direction.
    render_advisor(scene)

    render_interactions(scene, pov)

    narrators = scene["cast"] or [pov]

    narrator = st.selectbox(
        "PUNTO DI VISTA DEL RACCONTO",
        narrators,
        index=(
            narrators.index(pov)
            if pov in narrators else 0
        ),
        key=f"narrator_{sid}_{pov}"
    )

    render_workshop(scene, narrator)

    st.markdown("---")

    left, middle, right = st.columns(
        [1, 3, 1]
    )

    with left:
        if index > 0 and st.button(
            "← PRECEDENTE"
        ):
            st.session_state.scene_index -= 1
            st.rerun()

    with right:
        if (
            index < len(SCENE_IDS) - 1
            and st.button("SUCCESSIVA →")
        ):
            st.session_state.scene_index += 1
            st.rerun()


# ============================================================
# PRIMA INIZIALIZZAZIONE ARCHIVIO
# ============================================================

if not st.session_state.archive_exists:
    st.title("Inizializzazione archivio")

    st.warning(
        "Non trovo romanzo_web.json "
        "nel repository privato."
    )

    confirmed = st.checkbox(
        "Confermo la creazione dell'archivio"
    )

    if st.button(
        "CREA ARCHIVIO",
        disabled=not confirmed
    ):
        try:
            sha = write_remote_json(
                state, None
            )

            st.session_state.archive_sha = sha
            st.session_state.archive_exists = True

            st.rerun()

        except Exception as exc:
            st.error(str(exc))

    st.stop()


# ============================================================
# NAVIGAZIONE PRINCIPALE
# ============================================================

if st.session_state.page in (
    "archive",
    "people",
    "editorial",
):
    if st.button(
        "← TORNA ALLA STORIA"
    ):
        st.session_state.page = "story"
        st.rerun()


if st.session_state.page == "entrance":
    page_entrance()

elif st.session_state.page == "characters":
    page_characters()

elif st.session_state.page == "story":
    page_story()

elif st.session_state.page == "archive":
    page_archive()

elif st.session_state.page == "people":
    page_people()

elif st.session_state.page == "editorial":
    page_editorial()

else:
    st.session_state.page = "entrance"
    st.rerun()
