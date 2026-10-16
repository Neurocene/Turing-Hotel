
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
# APP COMPLETA - REGIA NARRATIVA
#
# Correzioni:
# - KeyError direction
# - StreamlitWidgetAlreadyInstantiatedError
# - RISPONDI con form clear_on_submit
# - Migrazione delle scene precedenti
#
# Il canone è costituito dai testi approvati.
# La prima bozza è una fonte di riferimento.
# ============================================================

st.set_page_config(
    page_title="Turing Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"

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

SCENE_IDS = [item[0] for item in SCENES]
SCENE_NAMES = dict(SCENES)

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
        "l'autonomia e la libertà."
    ),
    "Ada": (
        "Figlia di Elia, lavora al Turing Hotel. "
        "La sua voce deriva dai profili e dal canone."
    ),
    "Elia": (
        "Professor Elia Ferrante, padre di Ada, "
        "legato alla storia scientifica dell'hotel."
    ),
    "Luigi": (
        "Regista e narratore arrivato per preparare "
        "un documentario sugli idrovolanti."
    ),
    "Adam": (
        "Personaggio della prima bozza coinvolto "
        "nei rapporti con Riccardo e Vittoria."
    ),
    "Riccardo": (
        "Marito di Vittoria. Ha un rapporto "
        "complesso con Adam."
    ),
    "Vittoria": (
        "Moglie di Riccardo, coinvolta "
        "in un rapporto complesso con Adam."
    ),
}

INTRO_CONTEXTS = {
    "Noa": (
        "Noa percorre il viale verso il Turing Hotel. "
        "La scena termina con l'arrivo alla reception."
    ),
    "Ada": (
        "Ada conversa nello studio del professor Elia. "
        "La scena termina all'arrivo di Noa alla reception."
    ),
}


# ============================================================
# UTILITÀ
# ============================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def dictionary(value):
    return value if isinstance(value, dict) else {}


def sequence(value):
    return value if isinstance(value, list) else []


def secret(name, default=""):
    try:
        result = st.secrets.get(name)
        if result is not None and str(result).strip():
            return str(result)
    except Exception:
        pass
    return os.environ.get(name, default)


def fill_missing(data, template):
    if not isinstance(data, dict):
        data = {}

    for key, default in template.items():
        if key not in data:
            data[key] = copy.deepcopy(default)
        elif isinstance(default, dict):
            data[key] = fill_missing(data[key], default)

    return data


def ai_error(value):
    return (
        not isinstance(value, str)
        or not value.strip()
        or value.startswith("Errore OpenAI:")
        or value.startswith("OPENAI_API_KEY")
    )


def parse_ai_json(value):
    text = str(value).strip()
    text = re.sub(
        r"^```(?:json)?\s*", "", text,
        flags=re.IGNORECASE
    )
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        return None


def asset(name):
    if not ASSETS.is_dir():
        return None

    exact = ASSETS / name
    if exact.is_file():
        return exact

    for path in ASSETS.iterdir():
        if path.is_file() and path.name.casefold() == name.casefold():
            return path
    return None


# ============================================================
# OPENAI
# ============================================================

API_KEY = secret("OPENAI_API_KEY")
MODEL = secret("OPENAI_MODEL", "gpt-4.1-mini")

client = OpenAI(api_key=API_KEY) if API_KEY else None


def ask_ai(instructions, payload):
    if client is None:
        return "OPENAI_API_KEY non configurata."

    try:
        response = client.responses.create(
            model=MODEL,
            instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False),
        )
        return (response.output_text or "").strip()
    except Exception as exc:
        return f"Errore OpenAI: {exc}"


# ============================================================
# GITHUB
# ============================================================

GH_TOKEN = secret("GITHUB_TOKEN")
GH_OWNER = secret("GITHUB_OWNER", "Neurocene")
GH_REPO = secret("GITHUB_REPO", "turing-hotel-archivio")
GH_BRANCH = secret("GITHUB_BRANCH", "main")


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
            "GITHUB_TOKEN non configurato."
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
            params={"ref": GH_BRANCH} if method == "GET" else None,
            json=payload,
            timeout=45,
        )
    except requests.RequestException as exc:
        raise ArchiveError(str(exc)) from exc

    if method == "GET" and response.status_code == 404:
        return None

    if response.status_code in (409, 422):
        raise ArchiveError(
            "Conflitto con una versione più recente. "
            "Ricarica l'archivio."
        )

    if not response.ok:
        raise ArchiveError(
            f"GitHub HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    return response.json()


def read_remote(path):
    result = github_request("GET", path)
    if result is None:
        return None, None

    try:
        content = base64.b64decode(
            result["content"]
        ).decode("utf-8-sig")
        return content, result["sha"]
    except Exception as exc:
        raise ArchiveError(
            f"File non leggibile: {path}: {exc}"
        ) from exc


def save_remote_json(data, expected_sha):
    _, remote_sha = read_remote(ARCHIVE_PATH)

    if remote_sha != expected_sha:
        raise ArchiveError(
            "Archivio modificato da un'altra sessione. "
            "Ricarica prima di salvare."
        )

    payload = {
        "message": "Turing Hotel - salvataggio " + now(),
        "branch": GH_BRANCH,
        "content": base64.b64encode(
            json.dumps(
                data, ensure_ascii=False, indent=2
            ).encode("utf-8")
        ).decode("ascii"),
    }

    if remote_sha:
        payload["sha"] = remote_sha

    result = github_request("PUT", ARCHIVE_PATH, payload)
    sha = dictionary(result.get("content")).get("sha")

    if not sha:
        raise ArchiveError(
            "Salvataggio non confermato da GitHub."
        )

    return sha


# ============================================================
# SCHEMA
# ============================================================

def blank_direction():
    return {
        "proposals": [],
        "active": None,
        "history": [],
        "evaluations": [],
        "last_question": "",
    }


def ensure_direction(scene):
    if not isinstance(scene.get("direction"), dict):
        scene["direction"] = blank_direction()

    return fill_missing(
        scene["direction"],
        blank_direction()
    )


def blank_narrative():
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


def blank_scene(sid):
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
            person: blank_narrative()
            for person in PEOPLE
        },
        "monologue_topics": {
            person: "" for person in PEOPLE
        },
        "cast": copy.deepcopy(
            DEFAULT_CAST.get(sid, ["Noa", "Ada"])
        ),
        "ensemble_messages": [],
        "direction": blank_direction(),
        "intro_contexts": copy.deepcopy(INTRO_CONTEXTS),
        "decision": {
            "Noa": "",
            "Ada": "",
        },
    }


def default_state():
    return {
        "world": (
            "Turing Hotel: romanzo sull'identità, "
            "la memoria e le relazioni."
        ),
        "agents": {
            name: {
                "profile": PROFILES[name],
                "memory": "",
                "profile_history": [],
            }
            for name in PEOPLE
        },
        "scenes": [blank_scene(sid) for sid in SCENE_IDS],
        "editorial_log": [],
        "editorial_proposals": [],
    }


def migrate_state(original):
    original = dictionary(original)

    result = fill_missing(
        copy.deepcopy(original),
        default_state()
    )

    old_scenes = sequence(original.get("scenes"))
    indexed = {}

    for item in old_scenes:
        if isinstance(item, dict):
            key = str(item.get("id", "")).strip()
            if key:
                indexed[key] = item

    rebuilt = []

    for sid in SCENE_IDS:
        previous = indexed.get(sid)

        if previous is None:
            for item in old_scenes:
                if not isinstance(item, dict):
                    continue

                if norm(item.get("title", "")) == norm(
                    SCENE_NAMES[sid]
                ):
                    previous = item
                    break

        scene = fill_missing(
            copy.deepcopy(previous) if previous else {},
            blank_scene(sid),
        )

        scene["id"] = sid
        scene["title"] = SCENE_NAMES[sid]

        if not isinstance(scene.get("cast"), list):
            scene["cast"] = copy.deepcopy(
                DEFAULT_CAST.get(sid, ["Noa", "Ada"])
            )

        scene["cast"] = [
            person for person in scene["cast"]
            if person in PEOPLE
        ]

        if not scene["cast"]:
            scene["cast"] = copy.deepcopy(
                DEFAULT_CAST.get(sid, ["Noa", "Ada"])
            )

        ensure_direction(scene)

        scene["narrative"] = dictionary(
            scene.get("narrative")
        )
        scene["messages"] = dictionary(
            scene.get("messages")
        )
        scene["monologue_topics"] = dictionary(
            scene.get("monologue_topics")
        )

        for person in PEOPLE:
            scene["narrative"][person] = fill_missing(
                dictionary(scene["narrative"].get(person)),
                blank_narrative(),
            )
            scene["messages"].setdefault(person, [])
            scene["monologue_topics"].setdefault(person, "")

        rebuilt.append(scene)

    result["scenes"] = rebuilt

    result["agents"] = dictionary(result.get("agents"))

    for person in PEOPLE:
        result["agents"][person] = fill_missing(
            dictionary(result["agents"].get(person)),
            {
                "profile": PROFILES[person],
                "memory": "",
                "profile_history": [],
            },
        )

    return result


# ============================================================
# SESSIONE
# ============================================================

def load_archive():
    raw, sha = read_remote(ARCHIVE_PATH)

    if raw is None:
        return None, None

    try:
        return migrate_state(json.loads(raw)), sha
    except ValueError as exc:
        raise ArchiveError(
            "romanzo_web.json non è un JSON valido."
        ) from exc


def initialize():
    if "book_state" in st.session_state:
        # Mantiene compatibili le sessioni già aperte.
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
        loaded if loaded is not None else default_state()
    )
    st.session_state.archive_sha = sha
    st.session_state.archive_exists = loaded is not None
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

        for item in state["scenes"]:
            ensure_direction(item)

        if not st.session_state.archive_exists:
            raise ArchiveError(
                "Archivio non inizializzato."
            )

        sha = save_remote_json(
            state, st.session_state.archive_sha
        )
        st.session_state.archive_sha = sha
        return True

    except Exception as exc:
        state.clear()
        state.update(backup)
        st.error(
            "Salvataggio non riuscito: " + str(exc)
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
    border: 1px solid #85929a !important;
    min-height: 42px;
}
.stApp .stButton button *,
.stApp .stDownloadButton button * {
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
    if st.session_state.reference_loaded and not force:
        return

    try:
        text, sha = read_remote(REFERENCE_PATH)
        st.session_state.reference_text = text
        st.session_state.reference_sha = sha
        st.session_state.reference_error = (
            "" if text else "Prima bozza non trovata."
        )
    except Exception as exc:
        st.session_state.reference_text = None
        st.session_state.reference_error = str(exc)

    st.session_state.reference_loaded = True


def reference_chunks():
    load_reference()
    text = st.session_state.reference_text or ""

    if not text:
        return []

    size = 2500
    overlap = 250
    step = size - overlap

    return [
        text[start:start + size]
        for start in range(0, len(text), step)
    ]


def relevant_reference(characters, title="", limit=5):
    chunks = reference_chunks()

    if not chunks:
        return []

    names = [name.casefold() for name in characters]
    words = [
        word.casefold()
        for word in re.findall(r"[A-Za-zÀ-ÿ]{4,}", title)
        if word.casefold() not in {
            "della", "delle", "degli", "prima"
        }
    ]

    scored = []

    for index, content in enumerate(chunks):
        lower = content.casefold()
        score = sum(lower.count(name) * 4 for name in names)
        score += sum(lower.count(word) for word in words)

        if score:
            scored.append((score, index, content))

    scored.sort(key=lambda item: (-item[0], item[1]))

    return [
        {"passage": index + 1, "text": content}
        for _, index, content in scored[:limit]
    ]


# ============================================================
# CANONE E PERSONAGGI
# ============================================================

def scene_by_id(sid):
    for scene in state["scenes"]:
        if scene["id"] == sid:
            ensure_direction(scene)
            return scene
    raise KeyError(f"Scena non trovata: {sid}")


def approved_before(sid, person):
    result = []

    for previous_id in SCENE_IDS:
        if previous_id == sid:
            break

        scene = scene_by_id(previous_id)
        text = dictionary(
            scene["narrative"].get(person)
        ).get("approved", "")

        if isinstance(text, str) and text.strip():
            result.append({
                "scene": scene["title"],
                "text": text,
            })

    return result


def canonical_context(scene, person):
    if scene["id"] == "inizio" and person in PROTAGONISTS:
        return scene["intro_contexts"].get(
            person, INTRO_CONTEXTS[person]
        )
    return scene.get("approved_context", "")


def agent_instructions(person):
    agent = state["agents"][person]

    return f"""
Sei {person}, personaggio di Turing Hotel.

PROFILO APPROVATO:
{agent.get("profile", "")}

MEMORIA:
{agent.get("memory", "")}

REGOLE:
Sei il personaggio, non un assistente.
Non conosci i pensieri altrui.
Non anticipare fatti futuri.
Non inventare ricordi importanti.
Il nuovo canone prevale sulla prima bozza.

La regia narrativa approvata propone
circostanze e tensioni, non battute
obbligatorie o un risultato da raggiungere.

Reagisci secondo il tuo carattere.
"""


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
        "id": len(state["editorial_log"]) + 1,
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
    return "\n".join(lines) or "Nessuna differenza."


# ============================================================
# REGIA NARRATIVA
# ============================================================

def active_direction(scene):
    value = ensure_direction(scene).get("active")
    return value if isinstance(value, dict) and value else None


def direction_for_agents(scene):
    active = active_direction(scene)

    if active is None:
        return {
            "active": False,
            "instruction": "Nessuna direzione narrativa attiva.",
        }

    return {
        "active": True,
        "title": active.get("title", ""),
        "situation": active.get("situation", ""),
        "tension": active.get("tension", ""),
        "opportunities": active.get("opportunities", ""),
        "limits": active.get("limits", ""),
        "dramatic_question": active.get("dramatic_question", ""),
        "instruction": (
            "Direzione approvata dall'autore. "
            "Considerala una circostanza, non un copione. "
            "Rispondi liberamente secondo il tuo carattere."
        ),
    }


def propose_directions(scene, question):
    profiles = {
        person: state["agents"][person]["profile"]
        for person in scene["cast"]
    }

    return ask_ai(
        """
Sei il consulente narrativo di Turing Hotel.

Proponi ESATTAMENTE TRE direzioni
drammaturgiche alternative.

Ogni direzione presenta una situazione,
una tensione, opportunità, limiti
di continuità e una domanda drammatica.

Non prescrivere battute o un finale.
Il nuovo canone prevale sulla prima bozza.

Restituisci soltanto JSON valido:
{
 "directions":[
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
            "DOMANDA": question,
            "PERSONAGGI": scene["cast"],
            "PROFILI": profiles,
            "CONTESTO": scene["approved_context"],
            "REGIA_ATTUALE": active_direction(scene),
            "PRIMA_BOZZA": relevant_reference(
                scene["cast"], scene["title"]
            ),
            "CANONE": {
                person: approved_before(scene["id"], person)
                for person in scene["cast"]
            },
        },
    )


DIRECTION_FIELDS = (
    "title",
    "situation",
    "tension",
    "opportunities",
    "limits",
    "dramatic_question",
)


def validate_directions(value):
    if not isinstance(value, dict):
        return None

    items = value.get("directions")

    if not isinstance(items, list) or len(items) != 3:
        return None

    result = []

    for item in items:
        if not isinstance(item, dict):
            return None

        proposal = {
            key: str(item.get(key, "")).strip()
            for key in DIRECTION_FIELDS
        }

        if not all(proposal.values()):
            return None

        result.append(proposal)

    return result


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
        direction = ensure_direction(scene)

        if previous:
            direction["history"].append(
                copy.deepcopy(previous)
            )

        direction["active"] = approved

        log_change(
            "direzione narrativa",
            scene["title"],
            json.dumps(previous, ensure_ascii=False)
            if previous else "",
            json.dumps(approved, ensure_ascii=False),
            reason,
            scene["id"],
        )

    return commit(change)


def deactivate_direction(scene, reason):
    previous = active_direction(scene)

    if not previous:
        return False

    def change():
        direction = ensure_direction(scene)
        direction["history"].append(
            copy.deepcopy(previous)
        )
        direction["active"] = None

        log_change(
            "regia disattivata",
            scene["title"],
            json.dumps(previous, ensure_ascii=False),
            "Nessuna direzione attiva",
            reason,
            scene["id"],
        )

    return commit(change)


def evaluate_direction(scene):
    direction = active_direction(scene)

    if direction is None:
        return "Nessuna direzione attiva."

    start = direction.get("start_turn", 0)
    if not isinstance(start, int):
        start = 0

    dialogue = scene["ensemble_messages"][start:]

    if not dialogue:
        return (
            "Non esistono ancora battute successive "
            "all'approvazione della direzione."
        )

    return ask_ai(
        """
Sei il consulente narrativo.

Valuta quanto la direzione approvata
sia emersa dal dialogo.

Distingui fatti emersi, scelte autonome
dei personaggi, eventuali deviazioni
e due possibili sviluppi.

Non modificare il canone.
Non inventare eventi mancanti.
""",
        {
            "SCENA": scene["title"],
            "DIREZIONE": direction,
            "DIALOGO": dialogue,
        },
    )


# ============================================================
# CONSULENTE - INTERFACCIA
# ============================================================

def render_advisor(scene):
    direction = ensure_direction(scene)
    active = active_direction(scene)

    with st.expander(
        "CONSULENTE NARRATIVO E REGIA"
    ):
        if active:
            st.success("DIREZIONE ATTIVA")
            st.subheader(active.get("title", ""))
            st.write(active.get("situation", ""))
            st.markdown(
                "**Tensione:** "
                + active.get("tension", "")
            )
            st.markdown(
                "**Domanda drammatica:** "
                + active.get("dramatic_question", "")
            )
        else:
            st.info("Nessuna direzione attiva.")

        st.markdown("### Proponi tre direzioni")

        question = st.text_area(
            "Quale sviluppo vuoi esplorare?",
            value=direction.get("last_question", ""),
            height=120,
            key=f"advisor_question_{scene['id']}",
        )

        if st.button(
            "PROPONI TRE DIREZIONI",
            key=f"propose_{scene['id']}",
            disabled=client is None,
            use_container_width=True,
        ):
            with st.spinner("Il consulente prepara le proposte..."):
                answer = propose_directions(scene, question)

            if ai_error(answer):
                st.error(answer)
            else:
                proposals = validate_directions(
                    parse_ai_json(answer)
                )

                if not proposals:
                    st.error(
                        "Il consulente non ha restituito "
                        "tre proposte valide."
                    )
                else:
                    def change():
                        item = ensure_direction(scene)
                        item["proposals"] = proposals
                        item["last_question"] = question

                    if commit(change):
                        st.rerun()

        proposals = sequence(direction.get("proposals"))

        for index, proposal in enumerate(proposals):
            with st.expander(
                f"{index + 1}. {proposal.get('title', '')}"
            ):
                with st.form(
                    f"direction_form_{scene['id']}_{index}"
                ):
                    title = st.text_input(
                        "Titolo",
                        value=proposal.get("title", ""),
                    )
                    situation = st.text_area(
                        "Situazione",
                        value=proposal.get("situation", ""),
                    )
                    tension = st.text_area(
                        "Tensione",
                        value=proposal.get("tension", ""),
                    )
                    opportunities = st.text_area(
                        "Opportunità",
                        value=proposal.get("opportunities", ""),
                    )
                    limits = st.text_area(
                        "Limiti",
                        value=proposal.get("limits", ""),
                    )
                    dramatic_question = st.text_area(
                        "Domanda drammatica",
                        value=proposal.get("dramatic_question", ""),
                    )
                    reason = st.text_input(
                        "Motivazione"
                    )

                    approved = st.form_submit_button(
                        "APPROVA E ATTIVA"
                    )

                if approved:
                    edited = {
                        "title": title.strip(),
                        "situation": situation.strip(),
                        "tension": tension.strip(),
                        "opportunities": opportunities.strip(),
                        "limits": limits.strip(),
                        "dramatic_question":
                            dramatic_question.strip(),
                    }

                    if not all(edited.values()):
                        st.warning("Compila tutti i campi.")
                    elif approve_direction(
                        scene, edited, reason
                    ):
                        st.rerun()

        st.markdown("---")

        if st.button(
            "VALUTA L'EVOLUZIONE DELLA SCENA",
            key=f"evaluate_{scene['id']}",
            disabled=client is None or active is None,
        ):
            with st.spinner("Analisi dell'evoluzione..."):
                result = evaluate_direction(scene)

            if ai_error(result):
                st.error(result)
            else:
                def change():
                    ensure_direction(scene)[
                        "evaluations"
                    ].append({
                        "date": now(),
                        "direction_title": active["title"],
                        "text": result,
                    })

                if commit(change):
                    st.rerun()

        for item in reversed(
            sequence(direction.get("evaluations"))
        ):
            with st.expander(
                "Valutazione "
                + item.get("date", "")[:16]
            ):
                st.markdown(item.get("text", ""))

        if active:
            with st.form(
                f"deactivate_{scene['id']}"
            ):
                reason = st.text_input(
                    "Motivo della disattivazione"
                )
                submitted = st.form_submit_button(
                    "DISATTIVA DIREZIONE"
                )

            if submitted and deactivate_direction(scene, reason):
                st.rerun()

        with st.expander("DIREZIONI PRECEDENTI"):
            for previous in reversed(
                sequence(direction.get("history"))
            ):
                st.markdown(
                    "**" + previous.get("title", "") + "**"
                )
                st.write(previous.get("situation", ""))


# ============================================================
# GENERAZIONE DIALOGO
# ============================================================

def agent_payload(scene, person, history, prompt=""):
    return {
        "SCENA": scene["title"],
        "PERSONAGGIO": person,
        "PRESENTI": scene["cast"],
        "DOMANDA": prompt,
        "CONTESTO": canonical_context(scene, person),
        "REGIA": direction_for_agents(scene),
        "ROMANZO_ORIGINALE": relevant_reference(
            scene["cast"], scene["title"]
        ),
        "CANONE_APPROVATO": approved_before(
            scene["id"], person
        ),
        "CRONOLOGIA": history[-24:],
    }


def reply_once(scene, person, prompt, speaking_as):
    if person not in scene["cast"]:
        return "Personaggio non presente nella scena."

    if not prompt.strip():
        return "Scrivi una domanda."

    answer = ask_ai(
        agent_instructions(person)
        + """
MODALITÀ RISPONDI.

Produci UNA SOLA battuta breve.
Preferibilmente una o due frasi.
Niente didascalie.
Niente descrizioni.
Non scrivere il tuo nome.
Non continuare autonomamente il dialogo.

La direzione narrativa è un contesto,
non un esito obbligatorio.

Restituisci solo la risposta.
""",
        agent_payload(
            scene,
            person,
            scene["ensemble_messages"],
            prompt,
        ),
    )

    if ai_error(answer):
        return answer

    messages = [
        {
            "speaker": speaking_as,
            "text": prompt.strip(),
            "origin": "manual_prompt",
            "created_at": now(),
        },
        {
            "speaker": person,
            "text": answer.strip(),
            "origin": "single_reply",
            "created_at": now(),
        },
    ]

    if commit(
        lambda: scene["ensemble_messages"].extend(messages)
    ):
        return ""

    return "La risposta non è stata salvata."


def go_alone_dialogue(scene, turns=4):
    cast = scene["cast"]

    if len(cast) < 2:
        return "Seleziona almeno due personaggi."

    history = copy.deepcopy(
        scene["ensemble_messages"]
    )
    generated = []

    last = (
        history[-1].get("speaker", "")
        if history else ""
    )

    start = (
        (cast.index(last) + 1) % len(cast)
        if last in cast else 0
    )

    for index in range(turns):
        person = cast[(start + index) % len(cast)]

        answer = ask_ai(
            agent_instructions(person)
            + """
MODALITÀ GO ALONE.

Continua la conversazione
con UNA SOLA battuta.

Non parlare al posto degli altri.
Non scrivere didascalie.
Non scrivere il tuo nome.

Segui liberamente la psicologia
del personaggio e considera
la regia approvata come circostanza.
""",
            agent_payload(scene, person, history),
        )

        if ai_error(answer):
            return answer

        item = {
            "speaker": person,
            "text": answer,
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

    return "GO ALONE non salvato."


def go_alone_monologue(scene, person, theme):
    if not theme.strip():
        return "Scrivi un tema."

    history = copy.deepcopy(
        scene["messages"].get(person, [])
    )
    generated = []

    for number in (1, 2):
        answer = ask_ai(
            agent_instructions(person)
            + f"""
MONOLOGO - PENSIERO {number} DI 2.

Scrivi un solo pensiero interiore
in prima persona e al presente.

Tema: {theme}

Il secondo pensiero sviluppa il primo.
Nessun titolo.
Nessuna voce esterna.
Non anticipare eventi futuri.
""",
            {
                "SCENA": scene["title"],
                "CONTESTO": canonical_context(
                    scene, person
                ),
                "REGIA": direction_for_agents(scene),
                "REFERENCE": relevant_reference(
                    [person], scene["title"]
                ),
                "CANONE": approved_before(
                    scene["id"], person
                ),
                "PENSIERI": history,
            },
        )

        if ai_error(answer):
            return answer

        item = {
            "speaker": person,
            "text": answer,
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
# CREAZIONE CONTESTO
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
            key=f"intro_{person}",
        )

        if st.button(
            "SALVA CONTESTO INIZIALE",
            key=f"save_intro_{person}",
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
            key=f"context_notes_{sid}",
        )

        if st.button(
            "SALVA INDICAZIONI",
            key=f"save_notes_{sid}",
        ):
            if commit(
                lambda: scene.update(author_context=notes)
            ):
                st.success("Indicazioni salvate.")

        if st.button(
            "GENERA CONTESTO CON AI",
            key=f"generate_context_{sid}",
            disabled=client is None,
        ):
            with st.spinner("Preparazione del contesto..."):
                answer = ask_ai(
                    """
Sei il consulente narrativo.

Costruisci un contesto concreto
che includa la direzione narrativa
approvata, se presente.

Non prescrivere battute.
Non imporre un esito.
Rispetta il nuovo canone.

Restituisci solo il contesto.
""",
                    {
                        "SCENA": scene["title"],
                        "NOTE": notes,
                        "REGIA": direction_for_agents(scene),
                        "PRIMA_BOZZA": relevant_reference(
                            scene["cast"], scene["title"]
                        ),
                        "CONTESTO_ATTUALE":
                            scene["approved_context"],
                    },
                )

            if ai_error(answer):
                st.error(answer)
            elif commit(
                lambda: scene.update(
                    author_context=notes,
                    story_draft=answer,
                )
            ):
                st.rerun()

        if scene["story_draft"]:
            draft = st.text_area(
                "Contesto proposto",
                value=scene["story_draft"],
                height=200,
                key=f"context_draft_{sid}",
            )

            if st.button(
                "APPROVA CONTESTO",
                key=f"approve_context_{sid}",
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
                            sid,
                        )

                if commit(change):
                    st.rerun()


# ============================================================
# INTERAZIONI
# ============================================================

def render_interactions(scene, pov):
    sid = scene["id"]

    st.markdown("---")
    st.header("Personaggi e conversazioni")

    cast = st.multiselect(
        "PERSONAGGI PRESENTI",
        PEOPLE,
        default=scene["cast"],
        key=f"cast_{sid}",
    )

    if st.button(
        "SALVA PERSONAGGI PRESENTI",
        key=f"save_cast_{sid}",
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
                    sid,
                )

        if commit(change):
            st.rerun()

    active = active_direction(scene)

    if active:
        st.info(
            "REGIA ATTIVA: " + active.get("title", "")
        )

    mode = st.radio(
        "Modalità",
        ["Dialogo", "Monologo"],
        horizontal=True,
        key=f"mode_{sid}_{pov}",
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
                unsafe_allow_html=True,
            )

        available = scene["cast"] or PEOPLE

        st.markdown("### RISPONDI — UNA BATTUTA")

        # ====================================================
        # CORREZIONE DEL SECONDO ERRORE:
        # La domanda vive dentro un form
        # con clear_on_submit=True.
        #
        # Non si scrive mai in session_state
        # dopo aver creato il widget.
        # ====================================================

        with st.form(
            key=f"reply_form_{sid}",
            clear_on_submit=True,
        ):
            speaking_as = st.selectbox(
                "Chi pone la domanda?",
                ["Autore", *available],
            )

            responder = st.selectbox(
                "Chi deve rispondere?",
                available,
            )

            prompt = st.text_area(
                "Domanda o battuta",
                height=100,
                placeholder="Scrivi qui una domanda...",
            )

            submitted = st.form_submit_button(
                "RISPONDI — UNA BATTUTA",
                disabled=client is None,
                use_container_width=True,
            )

        if submitted:
            if not prompt.strip():
                st.warning("Scrivi prima una domanda.")
            else:
                with st.spinner(
                    responder + " risponde..."
                ):
                    error = reply_once(
                        scene,
                        responder,
                        prompt,
                        speaking_as,
                    )

                if error:
                    st.error(error)
                else:
                    # Il form svuota il campo.
                    # Nessuna modifica manuale
                    # di st.session_state.
                    st.rerun()

        st.markdown("---")
        st.markdown("### GO ALONE")

        if st.button(
            "GO ALONE — QUATTRO BATTUTE",
            key=f"go_{sid}",
            disabled=client is None,
            use_container_width=True,
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
        st.markdown("### AGGIUNGI BATTUTA MANUALE")

        with st.form(
            f"manual_{sid}",
            clear_on_submit=True,
        ):
            person = st.selectbox(
                "Personaggio",
                available,
            )
            text = st.text_area(
                "Testo della battuta"
            )
            sent = st.form_submit_button(
                "AGGIUNGI BATTUTA"
            )

        if sent and text.strip():
            item = {
                "speaker": person,
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
            key=f"inner_person_{sid}",
        )

        theme = st.text_area(
            "Tema del monologo",
            value=scene[
                "monologue_topics"
            ].get(person, ""),
            key=f"theme_{sid}_{person}",
        )

        if st.button(
            "GO ALONE — DUE PENSIERI",
            key=f"inner_go_{sid}_{person}",
            disabled=(
                client is None
                or not theme.strip()
            ),
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

        for item in scene["messages"].get(person, []):
            st.markdown(
                '<div class="thought">'
                + escape(item.get("text", ""))
                + "</div>",
                unsafe_allow_html=True,
            )

    with st.expander("GESTIONE CONVERSAZIONE"):
        confirmed = st.checkbox(
            "Confermo la cancellazione",
            key=f"confirm_clear_{sid}_{pov}",
        )

        if st.button(
            "CANCELLA DIALOGO DELLA SCENA",
            key=f"clear_{sid}",
            disabled=not confirmed,
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
    lines = [
        scene["title"],
        "Punto di vista: " + person,
        "",
    ]

    for item in scene["ensemble_messages"]:
        lines.append(
            f"{item.get('speaker', '?')}: "
            f"{item.get('text', '')}"
        )

    for item in scene["messages"].get(person, []):
        lines.append(
            f"{person} (pensiero): "
            f"{item.get('text', '')}"
        )

    return "\n\n".join(lines)


# ============================================================
# OFFICINA LETTERARIA
# ============================================================

def write_version(scene, person, version, notes):
    style = (
        "Essenziale, sobrio e preciso."
        if version == "A"
        else "Evocativo, sensoriale e introspettivo."
    )

    return ask_ai(
        f"""
Sei uno scrittore letterario di Turing Hotel.

Scrivi una scena compiuta.
Versione: {version}
Stile: {style}
Punto di vista: {person}
Prima persona.
Tempo presente.

Trasforma i dialoghi in un racconto.
Non inventare conoscenze non possedute.
Non imporre eventi non verificati.
Il nuovo canone approvato prevale.
La prima bozza è solo un riferimento.

Restituisci esclusivamente il racconto.
""",
        {
            "SCENA": scene["title"],
            "DIALOGHI": transcript(scene, person),
            "CONTESTO": canonical_context(scene, person),
            "REGIA": direction_for_agents(scene),
            "REFERENCE": relevant_reference(
                scene["cast"], scene["title"]
            ),
            "CANONE": approved_before(
                scene["id"], person
            ),
            "NOTE": notes,
        },
    )


def critic(scene, person):
    record = scene["narrative"][person]

    answer = ask_ai(
        """
Sei il critico letterario.

Confronta le due versioni e scegli
quella più convincente.

Segnala meriti, problemi e alternative.
Non approvare il testo.

Rispondi solo con JSON valido:
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
        },
    )

    if ai_error(answer):
        return None, answer

    result = parse_ai_json(answer)

    if not isinstance(result, dict):
        return None, "Giudizio non valido."

    winner = str(
        result.get("preferenza", "")
    ).upper()

    if winner not in ("A", "B"):
        return None, "Preferenza non valida."

    report = (
        f"**Preferenza: {winner}**\n\n"
        + str(result.get("motivazione", ""))
        + "\n\n**Riserve:** "
        + str(result.get("riserve", ""))
        + "\n\n**Alternativa:** "
        + str(result.get("alternativa", ""))
    )

    return winner, report


def visual_prompts(scene, person):
    text = scene["narrative"][person]["approved"]

    answer = ask_ai(
        """
Sei direttore della fotografia.

Dal testo approvato ricava:
- bibbia visiva;
- sei inquadrature;
- prompt immagine;
- prompt video.

Non inventare eventi nuovi.

Restituisci solo JSON:
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
            "TESTO_APPROVATO": text,
        },
    )

    if ai_error(answer):
        return None

    return parse_ai_json(answer)


def docx_data(title, text):
    document = Document()
    document.add_heading(title, 0)

    for paragraph in text.split("\n"):
        document.add_paragraph(paragraph)

    buffer = BytesIO()
    document.save(buffer)
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
            key=key + "_txt",
        )

    with columns[1]:
        st.download_button(
            "MARKDOWN",
            text.encode("utf-8"),
            file_name=filename + ".md",
            mime="text/markdown",
            key=key + "_md",
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
            key=key + "_docx",
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
        key=f"writer_notes_{sid}_{person}",
    )

    if st.button(
        "GENERA VERSIONI A E B",
        key=f"write_{sid}_{person}",
        disabled=client is None,
    ):
        if not (
            scene["ensemble_messages"]
            or scene["messages"].get(person)
        ):
            st.warning(
                "Registra prima un dialogo o un monologo."
            )
        else:
            with st.spinner("Scrittura delle versioni..."):
                version_a = write_version(
                    scene, person, "A", notes
                )
                version_b = (
                    write_version(scene, person, "B", notes)
                    if not ai_error(version_a)
                    else ""
                )

            if ai_error(version_a):
                st.error(version_a)
            elif ai_error(version_b):
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
                unsafe_allow_html=True,
            )

        with tab_b:
            st.markdown(
                '<div class="story-text">'
                + escape(record["B"])
                + "</div>",
                unsafe_allow_html=True,
            )

        if st.button(
            "CHIEDI GIUDIZIO CRITICO",
            key=f"critic_{sid}_{person}",
            disabled=client is None,
        ):
            winner, report = critic(scene, person)

            if not winner:
                st.error(report)
            elif commit(
                lambda: record.update(
                    recommended=winner,
                    review=report,
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

    selected = st.selectbox(
        "Testo da revisionare",
        options,
        key=f"version_{sid}_{person}",
    )

    if selected == "Versione A":
        initial = record["A"]
    elif selected == "Versione B":
        initial = record["B"]
    else:
        initial = record["draft"]

    editor_key = (
        f"editor_{sid}_{person}_{norm(selected)}"
    )
    source_key = editor_key + "_source"

    if st.session_state.get(source_key) != initial:
        st.session_state[editor_key] = initial
        st.session_state[source_key] = initial

    edited = st.text_area(
        "Testo narrativo",
        height=340,
        key=editor_key,
    )

    reason = st.text_input(
        "Motivazione della modifica",
        key=f"reason_{sid}_{person}",
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA",
            key=f"draft_{sid}_{person}",
        ):
            if commit(
                lambda: record.update(
                    draft=edited,
                    status="bozza",
                )
            ):
                st.success("Bozza salvata.")

    with right:
        if st.button(
            "APPROVA E MEMORIZZA",
            key=f"approve_{sid}_{person}",
            disabled=not edited.strip(),
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
                        sid,
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
        f"download_{sid}_{person}",
    )

    if record["approved"]:
        with st.expander("TESTO APPROVATO"):
            st.markdown(
                '<div class="story-text">'
                + escape(record["approved"])
                + "</div>",
                unsafe_allow_html=True,
            )

    with st.expander("TRASCRIZIONE"):
        st.text(transcript(scene, person))

    with st.expander("VERSIONI PRECEDENTI"):
        for item in reversed(
            sequence(record["history"])
        ):
            st.caption(item.get("replaced_at", ""))
            st.code(
                text_diff(
                    item.get("text", ""),
                    record["approved"],
                ),
                language="diff",
            )

    with st.expander("OFFICINA VISIVA"):
        if not record["approved"]:
            st.info("Approva prima un racconto.")
        else:
            if st.button(
                "GENERA PROMPT VISIVI",
                key=f"visual_{sid}_{person}",
                disabled=client is None,
            ):
                result = visual_prompts(scene, person)

                if not isinstance(result, dict):
                    st.error(
                        "Generazione visiva non riuscita."
                    )
                else:
                    def change():
                        record["visual"] = {
                            "bible": result.get("bible", ""),
                            "prompts": result.get("shots", []),
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
                st.write(visual.get("bible", ""))

                for index, shot in enumerate(
                    sequence(visual.get("prompts")), 1
                ):
                    st.markdown(
                        f"**Inquadratura {index}**"
                    )
                    st.write(shot.get("title", ""))
                    st.code(shot.get("image_prompt", ""))
                    st.code(shot.get("video_prompt", ""))


# ============================================================
# MEDIA
# ============================================================

def scene_media(sid, person):
    result = {
        "cover": [],
        "generic_cover": [],
        "image": [],
        "video": [],
    }

    if not ASSETS.is_dir():
        return result

    scene_key = norm(sid)
    person_key = norm(person)

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        ext = path.suffix.casefold()
        if ext not in IMAGE_EXT | VIDEO_EXT:
            continue

        name = norm(path.stem)

        if not name.startswith(scene_key):
            continue

        tail = name[len(scene_key):]

        if tail == person_key and ext in IMAGE_EXT:
            result["cover"].append((0, path))

        elif tail.startswith(person_key):
            number = tail[len(person_key):]

            if number.isdigit():
                kind = (
                    "video" if ext in VIDEO_EXT
                    else "image"
                )
                result[kind].append((int(number), path))

        elif tail == "" and sid != "inizio":
            if ext in IMAGE_EXT:
                result["generic_cover"].append((0, path))

        elif tail.isdigit() and sid != "inizio":
            kind = (
                "video" if ext in VIDEO_EXT
                else "image"
            )
            result[kind].append((int(tail), path))

    for kind in result:
        result[kind].sort(
            key=lambda item: (
                item[0], item[1].name.casefold()
            )
        )
        result[kind] = [
            path for _, path in result[kind]
        ]

    return result


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
            use_container_width=True,
        )
        st.caption(covers[0].name)

    entries = []

    for kind in ("image", "video"):
        for path in media[kind]:
            entries.append((kind, path))

    for offset in range(0, len(entries), 2):
        cols = st.columns(2)

        for column, (kind, path) in zip(
            cols, entries[offset:offset + 2]
        ):
            with column:
                try:
                    if kind == "image":
                        st.image(
                            str(path),
                            use_container_width=True,
                        )
                    else:
                        st.video(str(path))

                    st.caption(path.name)
                except Exception as exc:
                    st.error(str(exc))

    with st.expander("DIAGNOSTICA MEDIA"):
        st.caption(
            f"Scena: {sid} | Personaggio: {person}"
        )
        if covers:
            st.success(
                "Copertina trovata: " + covers[0].name
            )
        else:
            st.warning(
                f"Manca: {sid}.{person.lower()}.jpg"
            )

        for kind in ("image", "video"):
            for path in media[kind]:
                st.success(path.name)


# ============================================================
# ARCHIVIO PERSONAGGI
# ============================================================

def page_people():
    st.title("Archivio dei personaggi")

    person = st.selectbox("Personaggio", PEOPLE)
    agent = state["agents"][person]

    st.subheader("Profilo approvato")
    st.write(agent["profile"])

    st.subheader("Passaggi della prima bozza")

    passages = relevant_reference([person], limit=4)

    if not passages:
        st.warning(
            "Non ci sono passaggi disponibili."
        )

    for passage in passages:
        with st.expander(
            f"Passaggio {passage['passage']}"
        ):
            st.text(passage["text"])

    edited = st.text_area(
        "Nuovo profilo",
        value=agent["profile"],
        height=220,
        key=f"profile_{person}",
    )
    reason = st.text_input(
        "Motivazione",
        key=f"profile_reason_{person}",
    )

    if st.button(
        "APPROVA NUOVO PROFILO",
        disabled=(
            not edited.strip()
            or edited == agent["profile"]
        ),
    ):
        def change():
            previous = agent["profile"]

            agent["profile_history"].append({
                "profile": previous,
                "replaced_at": now(),
            })

            agent["profile"] = edited

            log_change(
                "profilo personaggio",
                person,
                previous,
                edited,
                reason,
            )

        if commit(change):
            st.rerun()

    with st.expander("CRONOLOGIA DEL PROFILO"):
        for item in reversed(
            agent["profile_history"]
        ):
            st.caption(item.get("replaced_at", ""))
            st.code(
                text_diff(
                    item.get("profile", ""),
                    agent["profile"],
                ),
                language="diff",
            )


# ============================================================
# REGISTRO
# ============================================================

def page_editorial():
    st.title("Registro editoriale")

    tab1, tab2 = st.tabs(
        ["MODIFICHE APPROVATE", "PROPOSTE"]
    )

    with tab1:
        for item in reversed(state["editorial_log"]):
            with st.expander(
                item.get("date", "")[:10]
                + " - " + item.get("subject", "")
            ):
                st.write(item.get("category", ""))
                st.write(item.get("reason", ""))
                st.code(
                    text_diff(
                        item.get("before", ""),
                        item.get("after", ""),
                    ),
                    language="diff",
                )

    with tab2:
        with st.form(
            "editorial_proposal",
            clear_on_submit=True,
        ):
            subject = st.text_input("Elemento narrativo")
            before = st.text_area("Prima bozza")
            after = st.text_area("Nuova proposta")
            reason = st.text_area("Motivazione")

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
                st.write(item.get("reason", ""))
                st.code(
                    text_diff(
                        item.get("before", ""),
                        item.get("after", ""),
                    ),
                    language="diff",
                )

    st.download_button(
        "SCARICA REGISTRO",
        json.dumps(
            {
                "changes": state["editorial_log"],
                "proposals": state["editorial_proposals"],
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        file_name="turing_hotel_registro.json",
        mime="application/json",
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
            text = scene["narrative"][person]["approved"]

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
                    unsafe_allow_html=True,
                )
                downloads(
                    scene["title"],
                    f"{sid}_{person.lower()}",
                    text,
                    f"archive_{sid}_{person}",
                )

    if count == 0:
        st.info(
            "Non ci sono ancora scene approvate."
        )


# ============================================================
# INGRESSO
# ============================================================

def page_entrance():
    hotel = asset("TuringHotel.jpg")

    if hotel:
        st.image(
            str(hotel),
            use_container_width=True,
        )

    st.title("TURING HOTEL")
    st.caption("Un romanzo a più coscienze")

    if st.button(
        "ENTRA AL TURING HOTEL",
        use_container_width=True,
    ):
        st.session_state.page = "characters"
        st.rerun()


def page_characters():
    st.title("Scegli una storia")

    cols = st.columns(2)

    for column, person in zip(
        cols, PROTAGONISTS
    ):
        with column:
            portrait = asset(person + ".jpg")

            if portrait:
                st.image(
                    str(portrait),
                    use_container_width=True,
                )

            st.subheader(person)

            if st.button(
                "ENTRA NELLA STORIA DI "
                + person.upper(),
                key=f"choose_{person}",
                use_container_width=True,
            ):
                st.session_state.pov = person
                st.session_state.scene_index = 0
                st.session_state.page = "story"
                st.rerun()


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():
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
        key=f"scene_nav_{index}_{pov}",
    )

    if selected != SCENE_IDS[index]:
        st.session_state.scene_index = (
            SCENE_IDS.index(selected)
        )
        st.rerun()

    st.sidebar.caption(f"Scena {index + 1}/31")

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
            use_container_width=True,
        ):
            st.session_state.page = page
            st.rerun()

    with st.sidebar.expander("PRIMA BOZZA"):
        load_reference()

        reference = st.session_state.reference_text

        if reference:
            st.success(
                "Romanzo originale collegato."
            )
            st.caption(
                f"{len(reference)} caratteri"
            )
        else:
            st.warning(
                st.session_state.reference_error
                or "Reference non disponibile."
            )

        st.code(REFERENCE_PATH)

        if st.button(
            "RICARICA PRIMA BOZZA",
            key="reload_reference",
        ):
            load_reference(force=True)
            st.rerun()

    with st.sidebar.expander("ARCHIVIO GITHUB"):
        st.caption(GH_OWNER + "/" + GH_REPO)

        if st.button(
            "RICARICA ARCHIVIO",
            key="reload_archive",
        ):
            if reload_archive():
                st.rerun()

        st.download_button(
            "SCARICA BACKUP",
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
            file_name="turing_hotel_backup.json",
            mime="application/json",
            key="backup_download",
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
            len(SCENE_IDS) - 1,
        ),
    )
    st.session_state.scene_index = index

    sid = SCENE_IDS[index]
    scene = scene_by_id(sid)

    ensure_direction(scene)

    render_sidebar()

    st.title(scene["title"])
    st.caption(
        f"Scena {index + 1}/31 "
        f"- storia di {pov}"
    )

    media_person = st.selectbox(
        "Media del personaggio",
        PROTAGONISTS,
        index=PROTAGONISTS.index(pov),
        key=f"media_{sid}_{pov}",
    )

    render_media(scene, media_person)

    st.markdown("---")

    render_context(scene, pov)
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
        key=f"narrator_{sid}_{pov}",
    )

    render_workshop(scene, narrator)

    st.markdown("---")
    left, _, right = st.columns([1, 3, 1])

    with left:
        if index > 0 and st.button(
            "← PRECEDENTE"
        ):
            st.session_state.scene_index -= 1
            st.rerun()

    with right:
        if index < len(SCENE_IDS) - 1 and st.button(
            "SUCCESSIVA →"
        ):
            st.session_state.scene_index += 1
            st.rerun()


# ============================================================
# EVENTUALE INIZIALIZZAZIONE ARCHIVIO
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
        disabled=not confirmed,
    ):
        try:
            sha = save_remote_json(state, None)
            st.session_state.archive_sha = sha
            st.session_state.archive_exists = True
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.stop()


# ============================================================
# NAVIGAZIONE
# ============================================================

if st.session_state.page in (
    "archive", "people", "editorial"
):
    if st.button("← TORNA ALLA STORIA"):
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
