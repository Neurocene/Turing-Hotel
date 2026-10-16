
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


# ==========================================================
# TURING HOTEL
# OFFICINA NARRATIVA CON REGIA DEL CONSULENTE
#
# - 31 SCENE
# - 7 AGENTI
# - RISPONDI: UNA BATTUTA
# - GO ALONE: DIALOGO AUTONOMO
# - MONOLOGO: DUE PENSIERI
# - CONSULENTE: TRE DIREZIONI NARRATIVE
# - APPROVAZIONE DIREZIONE
# - VALUTAZIONE EVOLUZIONE
# - ROMANZO ORIGINALE COME REFERENCE
# - NUOVO CANONE PRIORITARIO
# - REGISTRO EDITORIALE
# - ARCHIVIO GITHUB PRIVATO
# ==========================================================


st.set_page_config(
    page_title="Turing Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CHARACTERS = ROOT / "characters"

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}

REFERENCE_PATH = (
    "references/TURING_HOTEL_ROMANZO_REFERENCE.txt"
)

ARCHIVE_FILE = "romanzo_web.json"

PEOPLE = [
    "Noa",
    "Ada",
    "Elia",
    "Luigi",
    "Adam",
    "Riccardo",
    "Vittoria",
]

PROTAGONISTS = ["Noa", "Ada"]


# ==========================================================
# SCENE
# ==========================================================

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

DEFAULT_PROFILES = {
    "Noa": (
        "Agente artificiale relazionale. "
        "Riflette sull'autonomia, sulla bellezza, "
        "sulla libertà e sulle relazioni umane."
    ),
    "Ada": (
        "Figlia del professor Elia, lavora al Turing Hotel. "
        "La sua identità deriva dai profili dell'autore "
        "e dalle nuove scene approvate."
    ),
    "Elia": (
        "Professor Elia Ferrante, legato alla storia "
        "scientifica dell'albergo. Padre di Ada."
    ),
    "Luigi": (
        "Regista e narratore, arriva al Turing Hotel "
        "per preparare un documentario sugli idrovolanti."
    ),
    "Adam": (
        "Personaggio coinvolto nella vicenda "
        "di Riccardo e Vittoria. Il carattere "
        "emerge dai dialoghi della prima bozza."
    ),
    "Riccardo": (
        "Marito di Vittoria, con un rapporto "
        "complesso con Adam."
    ),
    "Vittoria": (
        "Moglie di Riccardo, coinvolta "
        "in un rapporto complesso con Adam."
    ),
}

INTRO_CONTEXTS = {
    "Noa": (
        "Noa cammina lungo il viale verso il Turing Hotel. "
        "Riflette da sola. La scena termina "
        "quando raggiunge la reception."
    ),
    "Ada": (
        "Ada parla con suo padre, il professor Elia, "
        "nel suo studio. La scena termina "
        "quando Noa arriva alla reception."
    ),
}


# ==========================================================
# FUNZIONI GENERALI
# ==========================================================

def timestamp():
    return datetime.now(timezone.utc).isoformat()


def normalize(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).casefold(),
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


def merge_defaults(value, template):
    if not isinstance(value, dict):
        value = {}

    for key, default in template.items():
        if key not in value:
            value[key] = copy.deepcopy(default)

        elif isinstance(default, dict):
            value[key] = merge_defaults(
                value[key],
                default,
            )

    return value


def parse_json(text):
    text = str(text).strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        return None


def ai_failed(value):
    return (
        not isinstance(value, str)
        or not value.strip()
        or value.startswith("Errore OpenAI:")
        or value.startswith("OPENAI_API_KEY")
    )


def find_asset(name):
    if not ASSETS.is_dir():
        return None

    exact = ASSETS / name

    if exact.is_file():
        return exact

    for path in ASSETS.iterdir():
        if (
            path.is_file()
            and path.name.casefold() == name.casefold()
        ):
            return path

    return None


# ==========================================================
# OPENAI
# ==========================================================

OPENAI_KEY = get_secret("OPENAI_API_KEY")
OPENAI_MODEL = get_secret(
    "OPENAI_MODEL",
    "gpt-4.1-mini",
)

client = (
    OpenAI(api_key=OPENAI_KEY)
    if OPENAI_KEY
    else None
)


def ask_ai(instructions, payload):
    if client is None:
        return "OPENAI_API_KEY non configurata."

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=json.dumps(
                payload,
                ensure_ascii=False,
            ),
        )

        return (response.output_text or "").strip()

    except Exception as exc:
        return f"Errore OpenAI: {exc}"


# ==========================================================
# GITHUB PRIVATO
# ==========================================================

GH_TOKEN = get_secret("GITHUB_TOKEN")
GH_OWNER = get_secret("GITHUB_OWNER", "Neurocene")
GH_REPO = get_secret(
    "GITHUB_REPO",
    "turing-hotel-archivio",
)
GH_BRANCH = get_secret("GITHUB_BRANCH", "main")


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

    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = requests.request(
            method,
            github_url(path),
            headers=headers,
            params=(
                {"ref": GH_BRANCH}
                if method == "GET"
                else None
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
            "Ricarica l'archivio prima di riprovare."
        )

    if not response.ok:
        raise ArchiveError(
            f"GitHub HTTP {response.status_code}: "
            f"{response.text[:350]}"
        )

    return response.json()


def read_remote_text(path):
    result = github_request("GET", path)

    if result is None:
        return None, None

    if result.get("encoding") != "base64":
        raise ArchiveError(
            "Il file non è disponibile in formato leggibile: "
            + path
        )

    try:
        content = base64.b64decode(
            result["content"]
        ).decode("utf-8-sig")

        return content, result["sha"]

    except Exception as exc:
        raise ArchiveError(str(exc)) from exc


def save_remote_json(data, expected_sha):
    _, actual_sha = read_remote_text(
        ARCHIVE_FILE
    )

    if actual_sha != expected_sha:
        raise ArchiveError(
            "Un'altra sessione ha modificato "
            "l'archivio. Ricarica i dati."
        )

    payload = {
        "message": (
            "Turing Hotel - revisione "
            + timestamp()
        ),
        "branch": GH_BRANCH,
        "content": base64.b64encode(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
        ).decode("ascii"),
    }

    if actual_sha:
        payload["sha"] = actual_sha

    result = github_request(
        "PUT",
        ARCHIVE_FILE,
        payload,
    )

    sha = as_dict(
        result.get("content")
    ).get("sha")

    if not sha:
        raise ArchiveError(
            "GitHub non ha confermato il salvataggio."
        )

    return sha


# ==========================================================
# STRUTTURA DATI
# ==========================================================

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


def empty_direction():
    return {
        "proposals": [],
        "active": None,
        "history": [],
        "evaluations": [],
        "last_question": "",
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
            name: empty_narrative()
            for name in PEOPLE
        },
        "monologue_topics": {
            name: ""
            for name in PEOPLE
        },
        "cast": copy.deepcopy(
            DEFAULT_CAST.get(sid, ["Noa", "Ada"])
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
            "Il Turing Hotel è un albergo sul mare. "
            "La storia intreccia intelligenze artificiali, "
            "rapporti umani, memoria, identità e libertà."
        ),
        "agents": {
            name: {
                "profile": DEFAULT_PROFILES[name],
                "memory": "",
                "profile_history": [],
            }
            for name in PEOPLE
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
        normalize(name)
        for name in names
    }


def migrate_state(original):
    original = as_dict(original)

    state = merge_defaults(
        copy.deepcopy(original),
        default_state(),
    )

    previous = as_list(
        original.get("scenes")
    )

    rebuilt = []

    for sid in SCENE_IDS:
        found = None
        aliases = aliases_for(sid)

        for item in previous:
            if not isinstance(item, dict):
                continue

            if (
                normalize(item.get("id", "")) in aliases
                or normalize(item.get("title", "")) in aliases
            ):
                found = item
                break

        scene = merge_defaults(
            copy.deepcopy(found) if found else {},
            empty_scene(sid),
        )

        scene["id"] = sid
        scene["title"] = SCENE_NAMES[sid]

        scene["cast"] = [
            name
            for name in as_list(scene.get("cast"))
            if name in PEOPLE
        ]

        if not scene["cast"]:
            scene["cast"] = copy.deepcopy(
                DEFAULT_CAST.get(sid, ["Noa", "Ada"])
            )

        scene["direction"] = merge_defaults(
            as_dict(scene.get("direction")),
            empty_direction(),
        )

        for name in PEOPLE:
            scene["narrative"][name] = merge_defaults(
                as_dict(
                    scene["narrative"].get(name)
                ),
                empty_narrative(),
            )

            scene["messages"].setdefault(name, [])
            scene["monologue_topics"].setdefault(
                name, ""
            )

        rebuilt.append(scene)

    state["scenes"] = rebuilt

    for name in PEOPLE:
        state["agents"][name] = merge_defaults(
            as_dict(state["agents"].get(name)),
            {
                "profile": DEFAULT_PROFILES[name],
                "memory": "",
                "profile_history": [],
            },
        )

    return state


# ==========================================================
# INIZIALIZZAZIONE
# ==========================================================

def load_archive():
    raw, sha = read_remote_text(
        ARCHIVE_FILE
    )

    if raw is None:
        return None, None

    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ArchiveError(
            "Archivio JSON non valido."
        ) from exc

    return migrate_state(data), sha


def initialize():
    if "book_state" in st.session_state:
        return

    try:
        loaded, sha = load_archive()

    except ArchiveError as exc:
        st.error(str(exc))
        st.stop()

    st.session_state.book_state = (
        loaded
        if loaded is not None
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

        if not st.session_state.archive_exists:
            raise ArchiveError(
                "Archivio non inizializzato."
            )

        sha = save_remote_json(
            state,
            st.session_state.archive_sha,
        )

        st.session_state.archive_sha = sha
        return True

    except Exception as exc:
        state.clear()
        state.update(backup)

        st.error(
            "Impossibile salvare: " + str(exc)
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


# ==========================================================
# INTERFACCIA
# ==========================================================

st.markdown(
    """
<style>
.stApp {
    background: #0a1014 !important;
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
    background: #e9e9e9 !important;
}
.stApp button[data-baseweb="tab"][aria-selected="true"] p {
    color: #111 !important;
}
.stApp [data-testid="stExpander"] {
    background: #172128 !important;
    border: 1px solid #45545f !important;
}
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary * {
    color: white !important;
}
.stApp pre {
    background: #172128 !important;
}
.stApp pre code {
    color: white !important;
}
.story {
    padding: 20px;
    background: #182128;
    border-left: 3px solid #d0b388;
    font-family: Georgia, serif;
    font-size: 1.05rem;
    line-height: 1.75;
    white-space: pre-wrap;
}
.dialogue {
    background: #1d2932;
    padding: 14px;
    margin: 8px 0;
    border-left: 3px solid #859caa;
    white-space: pre-wrap;
}
.single {
    background: #22332c;
    padding: 14px;
    margin: 8px 0;
    border-left: 3px solid #97c7a5;
    white-space: pre-wrap;
}
.inner {
    background: #29231e;
    padding: 14px;
    margin: 8px 0;
    border-left: 3px solid #d0b388;
    white-space: pre-wrap;
}
</style>
""",
    unsafe_allow_html=True,
)


# ==========================================================
# ROMANZO REFERENCE
# ==========================================================

def load_reference(force=False):
    if (
        st.session_state.reference_loaded
        and not force
    ):
        return

    try:
        text, sha = read_remote_text(
            REFERENCE_PATH
        )

        st.session_state.reference_text = text
        st.session_state.reference_sha = sha

        st.session_state.reference_error = (
            ""
            if text
            else "Prima bozza non ancora trovata."
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

    length = 2500
    overlap = 250
    step = length - overlap

    return [
        text[i:i + length]
        for i in range(0, len(text), step)
    ]


def relevant_reference(characters, title="", limit=5):
    chunks = reference_chunks()

    if not chunks:
        return []

    character_terms = [
        person.casefold()
        for person in characters
    ]

    scene_terms = [
        word.casefold()
        for word in re.findall(
            r"[A-Za-zÀ-ÿ]{4,}",
            title,
        )
        if word.casefold() not in {
            "della", "delle", "prima", "degli"
        }
    ]

    ranked = []

    for index, chunk in enumerate(chunks):
        low = chunk.casefold()

        score = sum(
            low.count(word) * 4
            for word in character_terms
        )

        score += sum(
            low.count(word)
            for word in scene_terms
        )

        if score > 0:
            ranked.append((score, index, chunk))

    ranked.sort(
        key=lambda value: (
            -value[0],
            value[1],
        )
    )

    return [
        {
            "passage": index + 1,
            "text": chunk,
        }
        for _, index, chunk
        in ranked[:limit]
    ]


# ==========================================================
# MEMORIA DEL NUOVO ROMANZO
# ==========================================================

def scene_by_id(sid):
    return next(
        scene
        for scene in state["scenes"]
        if scene["id"] == sid
    )


def approved_before(sid, character):
    result = []

    for previous_sid in SCENE_IDS:
        if previous_sid == sid:
            break

        scene = scene_by_id(previous_sid)

        narrative = as_dict(
            scene["narrative"].get(character)
        )

        text = narrative.get("approved", "")

        if text.strip():
            result.append({
                "scene": scene["title"],
                "text": text,
            })

    return result


def canonical_context(scene, character):
    if (
        scene["id"] == "inizio"
        and character in PROTAGONISTS
    ):
        return scene["intro_contexts"].get(
            character,
            INTRO_CONTEXTS[character],
        )

    return scene["approved_context"]


# ==========================================================
# REGISTRO DELLE MODIFICHE
# ==========================================================

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
        "date": timestamp(),
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
        fromfile="Prima",
        tofile="Dopo",
        lineterm="",
    )

    return "\n".join(lines) or "Nessuna differenza."


# ==========================================================
# REGIA NARRATIVA - MODELLO
# ==========================================================

def active_direction(scene):
    value = scene["direction"].get("active")

    if isinstance(value, dict):
        return value

    return None


def direction_for_agents(scene):
    direction = active_direction(scene)

    if direction is None:
        return {
            "active": False,
            "instructions": (
                "Nessuna direzione narrativa "
                "approvata per questa scena."
            ),
        }

    return {
        "active": True,
        "title": direction.get("title", ""),
        "situation": direction.get("situation", ""),
        "tension": direction.get("tension", ""),
        "opportunities": direction.get(
            "opportunities", ""
        ),
        "limits": direction.get("limits", ""),
        "dramatic_question": direction.get(
            "dramatic_question", ""
        ),
        "instructions": (
            "Questa regia è stata approvata "
            "dall'autore. Considerala una "
            "circostanza narrativa, non un "
            "risultato obbligatorio. "
            "Puoi reagire in modo differente "
            "se il tuo carattere, i tuoi "
            "desideri o le tue conoscenze "
            "lo rendono più credibile. "
            "Non devi pronunciare battute "
            "prescritte. Non devi raggiungere "
            "forzatamente l'esito suggerito."
        ),
    }


def propose_directions(scene, question):
    instructions = """
Sei il consulente narrativo e regista
drammaturgico di Turing Hotel.

L'autore vuole esplorare una direzione
per la scena corrente.

Proponi ESATTAMENTE TRE DIREZIONI
narrative realmente differenti.

Le proposte devono basarsi:
- sui personaggi presenti;
- sulla loro psicologia;
- sulla prima bozza come riferimento;
- sul nuovo canone prioritario;
- sulla richiesta dell'autore.

Non prescrivere battute.
Non imporre emozioni.
Non decidere definitivamente
il comportamento dei personaggi.

Una direzione deve descrivere
le circostanze e una possibilità
di conflitto, non il risultato.

Per ogni proposta fornisci:
- titolo;
- situazione di partenza;
- tensione;
- occasioni di sviluppo;
- limiti di continuità;
- domanda drammatica.

Restituisci SOLO un oggetto JSON valido:

{
 "directions": [
  {
   "title": "...",
   "situation": "...",
   "tension": "...",
   "opportunities": "...",
   "limits": "...",
   "dramatic_question": "..."
  },
  {
   "title": "...",
   "situation": "...",
   "tension": "...",
   "opportunities": "...",
   "limits": "...",
   "dramatic_question": "..."
  },
  {
   "title": "...",
   "situation": "...",
   "tension": "...",
   "opportunities": "...",
   "limits": "...",
   "dramatic_question": "..."
  }
 ]
}
"""

    profiles = {
        person: state["agents"][person]["profile"]
        for person in scene["cast"]
    }

    return ask_ai(
        instructions,
        {
            "SCENA": scene["title"],
            "PERSONAGGI": scene["cast"],
            "PROFILI": profiles,
            "DOMANDA_AUTORE": question,
            "CONTESTO_APPROVATO":
                scene["approved_context"],
            "REGIA_ATTIVA":
                active_direction(scene),
            "REFERENCE":
                relevant_reference(
                    scene["cast"],
                    scene["title"],
                ),
            "CANONE_PRECEDENTE": {
                person: approved_before(
                    scene["id"], person
                )
                for person in scene["cast"]
            },
        },
    )


def validate_directions(data):
    if not isinstance(data, dict):
        return None

    directions = data.get("directions")

    if not isinstance(directions, list):
        return None

    if len(directions) != 3:
        return None

    required = [
        "title",
        "situation",
        "tension",
        "opportunities",
        "limits",
        "dramatic_question",
    ]

    result = []

    for item in directions:
        if not isinstance(item, dict):
            return None

        normalized = {}

        for key in required:
            value = str(
                item.get(key, "")
            ).strip()

            if not value:
                return None

            normalized[key] = value

        result.append(normalized)

    return result


def approve_direction(
    scene,
    proposal,
    reason,
):
    previous = active_direction(scene)

    new_direction = copy.deepcopy(proposal)
    new_direction["approved_at"] = timestamp()
    new_direction["approved_reason"] = reason
    new_direction["approved_by"] = "autore"
    new_direction["start_turn"] = len(
        scene["ensemble_messages"]
    )

    def change():
        if previous:
            scene["direction"]["history"].append(
                copy.deepcopy(previous)
            )

        scene["direction"]["active"] = (
            new_direction
        )

        log_change(
            category="direzione narrativa",
            subject=scene["title"],
            before=(
                json.dumps(
                    previous,
                    ensure_ascii=False,
                    indent=2,
                )
                if previous
                else ""
            ),
            after=json.dumps(
                new_direction,
                ensure_ascii=False,
                indent=2,
            ),
            reason=reason,
            scene_id=scene["id"],
        )

    return commit(change)


def remove_active_direction(scene, reason):
    previous = active_direction(scene)

    if not previous:
        return False

    def change():
        scene["direction"]["history"].append(
            copy.deepcopy(previous)
        )

        scene["direction"]["active"] = None

        log_change(
            category="regia disattivata",
            subject=scene["title"],
            before=json.dumps(
                previous,
                ensure_ascii=False,
            ),
            after="Nessuna direzione attiva",
            reason=reason,
            scene_id=scene["id"],
        )

    return commit(change)


def evaluate_direction(scene):
    direction = active_direction(scene)

    if not direction:
        return (
            "Non esiste una direzione "
            "narrativa attiva."
        )

    start = direction.get("start_turn", 0)

    if not isinstance(start, int):
        start = 0

    subsequent = scene[
        "ensemble_messages"
    ][start:]

    if not subsequent:
        return (
            "Non ci sono conversazioni successive "
            "all'approvazione della direzione."
        )

    return ask_ai(
        """
Sei il consulente narrativo.

Valuta come gli agenti hanno sviluppato
la direzione narrativa approvata.

Non inventare battute mancanti.
Non modificare le conversazioni.
Non decidere che la direzione
debba essere rispettata a ogni costo.

Distingui:
1. che cosa è effettivamente successo;
2. quanto la direzione è emersa;
3. quali scelte autonome hanno
   compiuto i personaggi;
4. contraddizioni col canone;
5. due possibili sviluppi futuri.

Restituisci una valutazione
in italiano, chiara e ragionata.

Non approvare nuove scene o fatti.
""",
        {
            "SCENA": scene["title"],
            "DIREZIONE": direction,
            "CONVERSAZIONE": subsequent,
            "CONTESTO":
                scene["approved_context"],
        },
    )


# ==========================================================
# IDENTITÀ AGENTI
# ==========================================================

def agent_instructions(character):
    profile = state["agents"][character]

    return f"""
Sei {character}, un personaggio
del romanzo Turing Hotel.

PROFILO APPROVATO:
{profile["profile"]}

MEMORIA PERSONALE:
{profile.get("memory", "")}

REGOLE:
- Agisci come il personaggio.
- Non sei un assistente.
- Non imitare tutti gli altri.
- Non conosci i pensieri altrui.
- Non anticipare il futuro.
- Rispetta la cronologia.
- La prima bozza è un riferimento.
- Il nuovo canone approvato prevale.
- Una conversazione generata
  non è automaticamente canonica.

REGIA NARRATIVA:
Se è presente una direzione approvata,
considerala un insieme di circostanze
e tensioni da esplorare.

Non devi raggiungere il risultato
desiderato dal consulente.

La tua personalità può portarti
a resistere alla direzione,
reinterpretarla o trasformarla.

Non parlare mai come il consulente.
"""


def agent_payload(
    scene,
    character,
    history,
    author_line="",
):
    return {
        "SCENA": scene["title"],
        "PERSONAGGIO": character,
        "PERSONAGGI_PRESENTI": scene["cast"],
        "RICHIESTA": author_line,
        "CONTESTO_APPROVATO":
            canonical_context(
                scene,
                character,
            ),
        "REGIA_NARRATIVA_APPROVATA":
            direction_for_agents(scene),
        "ROMANZO_ORIGINALE":
            relevant_reference(
                scene["cast"],
                scene["title"],
            ),
        "NUOVO_CANONE_PRECEDENTE":
            approved_before(
                scene["id"],
                character,
            ),
        "DIALOGO_PRECEDENTE": history[-24:],
    }


# ==========================================================
# RISPONDI - UNA BATTUTA
# ==========================================================

def generate_single_reply(
    scene,
    character,
    author_line,
):
    instructions = (
        agent_instructions(character)
        + """
MODALITÀ RISPONDI.

Rispondi con UNA SOLA battuta.

Rispondi alla frase o alla domanda
che hai appena ricevuto.

Preferibilmente una o due frasi.

Non scrivere:
- il nome del personaggio;
- descrizioni;
- didascalie;
- pensieri narrati;
- più di una battuta;
- una continuazione autonoma.

La direzione narrativa approvata
può influenzare tono e contenuto,
ma non devi forzare un esito.

Restituisci esclusivamente
la risposta pronunciata.
"""
    )

    return ask_ai(
        instructions,
        agent_payload(
            scene,
            character,
            scene["ensemble_messages"],
            author_line,
        ),
    )


def reply_once(
    scene,
    character,
    prompt,
    speaking_as,
):
    if character not in scene["cast"]:
        return (
            "Il personaggio non è "
            "tra i presenti nella scena."
        )

    if not prompt.strip():
        return "Scrivi prima una battuta."

    response = generate_single_reply(
        scene,
        character,
        prompt,
    )

    if ai_failed(response):
        return response

    messages = [
        {
            "speaker": speaking_as,
            "text": prompt.strip(),
            "origin": "manual_prompt",
            "created_at": timestamp(),
        },
        {
            "speaker": character,
            "text": response.strip(),
            "origin": "single_reply",
            "created_at": timestamp(),
        },
    ]

    if commit(
        lambda: scene[
            "ensemble_messages"
        ].extend(messages)
    ):
        return ""

    return "Risposta non salvata."


# ==========================================================
# GO ALONE - DIALOGO
# ==========================================================

def generate_go_alone_turn(
    scene,
    character,
    history,
):
    instructions = (
        agent_instructions(character)
        + """
MODALITÀ GO ALONE.

Continua autonomamente
la conversazione precedente.

Produci UNA SOLA battuta.

Non pronunciare battute
per altri personaggi.

Non eseguire un copione obbligatorio.
Puoi contraddire, rifiutare,
spostare argomento o sorprendere,
se coerente con il tuo carattere.

La regia narrativa è una circostanza,
non un ordine sul finale della scena.

Non scrivere il tuo nome.
Non introdurre didascalie.
"""
    )

    return ask_ai(
        instructions,
        agent_payload(
            scene,
            character,
            history,
        ),
    )


def go_alone_dialogue(scene, turns=4):
    cast = scene["cast"]

    if len(cast) < 2:
        return (
            "Seleziona almeno due personaggi "
            "per GO ALONE."
        )

    history = copy.deepcopy(
        scene["ensemble_messages"]
    )

    generated = []

    last_speaker = (
        history[-1].get("speaker", "")
        if history
        else ""
    )

    if last_speaker in cast:
        start = (
            cast.index(last_speaker) + 1
        ) % len(cast)
    else:
        start = 0

    for number in range(turns):
        character = cast[
            (start + number) % len(cast)
        ]

        answer = generate_go_alone_turn(
            scene,
            character,
            history,
        )

        if ai_failed(answer):
            return answer

        item = {
            "speaker": character,
            "text": answer,
            "origin": "go_alone",
            "created_at": timestamp(),
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


# ==========================================================
# MONOLOGO
# ==========================================================

def go_alone_monologue(
    scene,
    character,
    theme,
):
    if not theme.strip():
        return "Inserisci il tema del monologo."

    history = copy.deepcopy(
        scene["messages"].get(character, [])
    )

    generated = []

    for number in (1, 2):
        response = ask_ai(
            agent_instructions(character)
            + f"""
MODALITÀ MONOLOGO.

Pensiero {number} di 2.

Tema: {theme}

Scrivi UN SOLO pensiero interiore
in prima persona e al presente.

Il secondo pensiero deve
sviluppare il primo.

Considera la direzione narrativa
approvata ma non forzare
un risultato obbligatorio.

Non scrivere il nome del personaggio.
Non aggiungere titoli.
""",
            {
                "SCENA": scene["title"],
                "TEMA": theme,
                "CONTESTO":
                    canonical_context(
                        scene,
                        character,
                    ),
                "REGIA":
                    direction_for_agents(scene),
                "REFERENCE":
                    relevant_reference(
                        [character],
                        scene["title"],
                    ),
                "CANONE":
                    approved_before(
                        scene["id"],
                        character,
                    ),
                "PENSIERI": history,
            },
        )

        if ai_failed(response):
            return response

        item = {
            "speaker": character,
            "text": response,
            "kind": "inner",
            "origin": "monologue",
            "thought_number": number,
            "theme": theme,
            "created_at": timestamp(),
        }

        generated.append(item)
        history.append(item)

    def change():
        scene["monologue_topics"][character] = theme

        scene["messages"].setdefault(
            character,
            [],
        ).extend(generated)

    if commit(change):
        return ""

    return "Monologo non salvato."


# ==========================================================
# CONSULENTE NARRATIVO - INTERFACCIA
# ==========================================================

def render_direction_editor(scene):
    direction = scene["direction"]
    proposals = direction["proposals"]

    if not proposals:
        return

    st.markdown("### Direzioni proposte")

    names = [
        f"{index + 1}. {item['title']}"
        for index, item in enumerate(proposals)
    ]

    index = st.radio(
        "Scegli una direzione da sviluppare",
        range(len(proposals)),
        format_func=lambda i: names[i],
        key=f"direction_choose_{scene['id']}",
    )

    proposal = proposals[index]

    with st.expander(
        "LEGGI LA PROPOSTA",
        expanded=True,
    ):
        st.markdown(
            "**Situazione:** "
            + proposal["situation"]
        )

        st.markdown(
            "**Tensione:** "
            + proposal["tension"]
        )

        st.markdown(
            "**Opportunità:** "
            + proposal["opportunities"]
        )

        st.markdown(
            "**Limiti:** "
            + proposal["limits"]
        )

        st.markdown(
            "**Domanda drammatica:** "
            + proposal["dramatic_question"]
        )

    # La chiave contiene l'indice della proposta:
    # passando da A a B, i campi sono indipendenti.
    prefix = f"regia_{scene['id']}_{index}"

    with st.form(prefix):
        title = st.text_input(
            "Titolo",
            value=proposal["title"],
        )

        situation = st.text_area(
            "Situazione di partenza",
            value=proposal["situation"],
            height=105,
        )

        tension = st.text_area(
            "Tensione narrativa",
            value=proposal["tension"],
            height=105,
        )

        opportunities = st.text_area(
            "Occasioni di sviluppo",
            value=proposal["opportunities"],
            height=105,
        )

        limits = st.text_area(
            "Limiti e continuità",
            value=proposal["limits"],
            height=100,
        )

        dramatic_question = st.text_area(
            "Domanda drammatica",
            value=proposal["dramatic_question"],
        )

        reason = st.text_input(
            "Motivazione dell'approvazione"
        )

        submitted = st.form_submit_button(
            "APPROVA E ATTIVA QUESTA DIREZIONE",
            use_container_width=True,
        )

    if submitted:
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
            st.warning(
                "Compila tutti i campi "
                "prima di approvare."
            )

        elif approve_direction(
            scene,
            edited,
            reason,
        ):
            st.success(
                "Direzione attivata. "
                "Da ora influenza RISPONDI, "
                "GO ALONE e i monologhi."
            )
            st.rerun()


def render_advisor(scene):
    sid = scene["id"]

    with st.expander(
        "CONSULENTE NARRATIVO E REGIA",
        expanded=False,
    ):
        current = active_direction(scene)

        if current:
            st.success(
                "DIREZIONE NARRATIVA ATTIVA"
            )

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
                "Questa direzione orienta il contesto, "
                "ma non obbliga gli agenti "
                "a seguire un finale."
            )

        else:
            st.info(
                "Nessuna direzione attiva. "
                "Gli agenti si basano "
                "sul contesto e sui profili."
            )

        st.markdown("---")

        st.markdown(
            "### Proponi tre direzioni"
        )

        question = st.text_area(
            "Quale sviluppo vuoi esplorare?",
            value=scene["direction"].get(
                "last_question", ""
            ),
            height=120,
            key=f"advisor_question_{sid}",
        )

        if st.button(
            "PROPONI TRE DIREZIONI",
            key=f"propose_directions_{sid}",
            disabled=client is None,
            use_container_width=True,
        ):
            with st.spinner(
                "Il consulente studia "
                "le possibili direzioni..."
            ):
                response = propose_directions(
                    scene,
                    question,
                )

            if ai_failed(response):
                st.error(response)

            else:
                parsed = parse_json(response)
                options = validate_directions(
                    parsed
                )

                if not options:
                    st.error(
                        "Il consulente non ha restituito "
                        "tre proposte valide. Riprova."
                    )

                else:
                    def change():
                        direction = scene["direction"]
                        direction["proposals"] = options
                        direction["last_question"] = (
                            question
                        )

                    if commit(change):
                        st.rerun()

        render_direction_editor(scene)

        st.markdown("---")

        st.markdown(
            "### Valuta l'evoluzione"
        )

        if st.button(
            "VALUTA COME È EVOLUTA LA SCENA",
            key=f"evaluate_{sid}",
            disabled=(
                client is None
                or not bool(current)
            ),
            use_container_width=True,
        ):
            with st.spinner(
                "Il consulente esamina "
                "la conversazione..."
            ):
                response = evaluate_direction(
                    scene
                )

            if ai_failed(response):
                st.error(response)

            else:
                if commit(
                    lambda: scene["direction"][
                        "evaluations"
                    ].append({
                        "date": timestamp(),
                        "direction_title":
                            current["title"],
                        "text": response,
                    })
                ):
                    st.rerun()

        evaluations = scene[
            "direction"
        ]["evaluations"]

        for item in reversed(evaluations):
            with st.expander(
                "Valutazione "
                + item.get("date", "")[:16]
            ):
                st.markdown(
                    item.get("text", "")
                )

        if current:
            st.markdown("---")

            with st.form(
                f"deactivate_{sid}"
            ):
                reason = st.text_input(
                    "Motivo della disattivazione"
                )

                deactivate = st.form_submit_button(
                    "DISATTIVA DIREZIONE"
                )

            if deactivate:
                if remove_active_direction(
                    scene,
                    reason,
                ):
                    st.rerun()

        with st.expander(
            "DIREZIONI PRECEDENTI"
        ):
            for previous in reversed(
                scene["direction"]["history"]
            ):
                st.markdown(
                    "**" + previous.get(
                        "title", ""
                    ) + "**"
                )

                st.write(
                    previous.get(
                        "situation", ""
                    )
                )


# ==========================================================
# CONTESTO DELLA SCENA
# ==========================================================

def render_context(scene, character):
    sid = scene["id"]

    if (
        sid == "inizio"
        and character in PROTAGONISTS
    ):
        text = st.text_area(
            "Contesto del prologo",
            value=scene["intro_contexts"].get(
                character,
                INTRO_CONTEXTS[character],
            ),
            height=145,
            key=f"intro_{character}",
        )

        if st.button(
            "SALVA CONTESTO INIZIALE",
            key=f"save_intro_{character}",
        ):
            if commit(
                lambda: scene[
                    "intro_contexts"
                ].update({character: text})
            ):
                st.success("Contesto salvato.")

        return

    with st.expander(
        "CREATORE DELLA SCENA"
    ):
        notes = st.text_area(
            "Indicazioni dell'autore",
            value=scene["author_context"],
            height=135,
            key=f"context_notes_{sid}",
        )

        if st.button(
            "SALVA INDICAZIONI",
            key=f"save_notes_{sid}",
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
            disabled=client is None,
        ):
            response = ask_ai(
                """
Sei il consulente narrativo.

Prepara un contesto concreto
per la scena.

Tieni conto della direzione narrativa
attiva, se presente, traducendola
in circostanze e opportunità.

Non imporre battute.
Non determinare gli esiti.
Non togliere libertà ai personaggi.

Il nuovo canone approvato
ha precedenza sulla prima bozza.

Restituisci solo il contesto.
""",
                {
                    "SCENA": scene["title"],
                    "INDICAZIONI": notes,
                    "REGIA_APPROVATA":
                        direction_for_agents(scene),
                    "REFERENCE":
                        relevant_reference(
                            scene["cast"],
                            scene["title"],
                        ),
                    "CONTESTO_PRECEDENTE":
                        scene["approved_context"],
                },
            )

            if ai_failed(response):
                st.error(response)

            elif commit(
                lambda: scene.update(
                    story_draft=response,
                    author_context=notes,
                )
            ):
                st.rerun()

        if scene["story_draft"]:
            draft = st.text_area(
                "Contesto proposto",
                value=scene["story_draft"],
                height=210,
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
                            "Approvazione dell'autore",
                            sid,
                        )

                if commit(change):
                    st.rerun()


# ==========================================================
# DIALOGHI E MONOLOGHI - INTERFACCIA
# ==========================================================

def show_dialogue(scene):
    for item in scene["ensemble_messages"]:
        css = (
            "single"
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
                    "Scelta dell'autore",
                    sid,
                )

        if commit(change):
            st.rerun()

    active = active_direction(scene)

    if active:
        st.info(
            "REGIA ATTIVA: "
            + active.get("title", "")
        )

    else:
        st.caption(
            "Nessuna direzione narrativa attiva."
        )

    mode = st.radio(
        "Modalità",
        ["Dialogo", "Monologo"],
        horizontal=True,
        key=f"mode_{sid}_{pov}",
    )

    if mode == "Dialogo":
        show_dialogue(scene)

        available = (
            scene["cast"]
            if scene["cast"]
            else PEOPLE
        )

        st.markdown("### RISPONDI")

        speaking_as = st.selectbox(
            "Chi pone la domanda?",
            ["Autore", *available],
            key=f"speaking_as_{sid}",
        )

        respondent = st.selectbox(
            "Chi deve rispondere?",
            available,
            key=f"respondent_{sid}",
        )

        prompt = st.text_area(
            "Battuta o domanda",
            height=105,
            key=f"reply_prompt_{sid}",
        )

        if st.button(
            "RISPONDI — UNA BATTUTA",
            key=f"reply_{sid}",
            disabled=(
                client is None
                or not prompt.strip()
            ),
            use_container_width=True,
        ):
            with st.spinner(
                respondent + " risponde..."
            ):
                error = reply_once(
                    scene,
                    respondent,
                    prompt,
                    speaking_as,
                )

            if error:
                st.error(error)
            else:
                st.session_state[
                    f"reply_prompt_{sid}"
                ] = ""
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
                    scene,
                    turns=4,
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        st.markdown("---")

        with st.form(
            f"manual_{sid}",
            clear_on_submit=True,
        ):
            character = st.selectbox(
                "Aggiungi battuta di",
                available,
            )

            text = st.text_area(
                "Battuta manuale"
            )

            submitted = st.form_submit_button(
                "AGGIUNGI BATTUTA"
            )

        if submitted and text.strip():
            item = {
                "speaker": character,
                "text": text,
                "origin": "manual",
                "created_at": timestamp(),
            }

            if commit(
                lambda: scene[
                    "ensemble_messages"
                ].append(item)
            ):
                st.rerun()

    else:
        available = (
            scene["cast"]
            if scene["cast"]
            else PEOPLE
        )

        character = st.selectbox(
            "Personaggio del monologo",
            available,
            key=f"inner_character_{sid}",
        )

        theme = st.text_area(
            "Tema proposto dall'autore",
            value=scene[
                "monologue_topics"
            ].get(character, ""),
            key=f"theme_{sid}_{character}",
        )

        if st.button(
            "GO ALONE — DUE PENSIERI",
            key=f"inner_go_{sid}_{character}",
            disabled=(
                client is None
                or not theme.strip()
            ),
        ):
            with st.spinner(
                "Il personaggio riflette..."
            ):
                error = go_alone_monologue(
                    scene,
                    character,
                    theme,
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        for item in scene["messages"].get(
            character, []
        ):
            st.markdown(
                '<div class="inner">'
                + escape(item.get("text", ""))
                + "</div>",
                unsafe_allow_html=True,
            )

    with st.expander(
        "GESTIONE CONVERSAZIONE"
    ):
        confirm = st.checkbox(
            "Confermo la cancellazione",
            key=f"confirm_clear_{sid}_{pov}",
        )

        if st.button(
            "CANCELLA DIALOGO",
            key=f"clear_{sid}",
            disabled=not confirm,
        ):
            if commit(
                lambda: scene.update(
                    ensemble_messages=[]
                )
            ):
                st.rerun()


# ==========================================================
# TRASCRIZIONE DELLA SCENA
# ==========================================================

def scene_transcript(scene, character):
    lines = [
        scene["title"],
        "Punto di vista: " + character,
        "",
    ]

    for item in scene["ensemble_messages"]:
        lines.append(
            f"{item.get('speaker', '?')}: "
            f"{item.get('text', '')}"
        )

    for item in scene["messages"].get(
        character, []
    ):
        lines.append(
            f"{character} (pensiero): "
            f"{item.get('text', '')}"
        )

    return "\n\n".join(lines)


# ==========================================================
# OFFICINA LETTERARIA
# ==========================================================

def write_version(
    scene,
    character,
    version,
    notes,
):
    style = (
        "Essenziale, controllato, preciso."
        if version == "A"
        else
        "Introspettivo, evocativo e sensoriale."
    )

    return ask_ai(
        f"""
Sei lo scrittore di Turing Hotel.

Produci una scena letteraria compiuta.

Versione: {version}
Stile: {style}

Punto di vista: {character}
Prima persona singolare.
Tempo presente.

Usa la trascrizione e il contesto.

La direzione narrativa approvata
è una linea drammaturgica, non
una sequenza obbligatoria di eventi.

Rispetta quello che i personaggi
hanno effettivamente detto.

Non inventare una conoscenza
che il narratore non possiede.

La prima bozza è un riferimento.
Il nuovo canone prevale.

Restituisci solo il racconto.
""",
        {
            "SCENA": scene["title"],
            "TRASCRIZIONE":
                scene_transcript(
                    scene, character
                ),
            "CONTESTO":
                canonical_context(
                    scene, character
                ),
            "REGIA":
                direction_for_agents(scene),
            "REFERENCE":
                relevant_reference(
                    scene["cast"],
                    scene["title"],
                ),
            "CANONE":
                approved_before(
                    scene["id"],
                    character,
                ),
            "NOTE": notes,
        },
    )


def critic(scene, character):
    record = scene["narrative"][character]

    response = ask_ai(
        """
Sei un critico letterario.

Confronta le due versioni
e scegli quella più convincente.

Spiega perché.
Evidenzia le riserve e proponi
una possibile revisione.

Non approvare alcuna versione.

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
            "REGIA":
                direction_for_agents(scene),
        },
    )

    if ai_failed(response):
        return None, response

    data = parse_json(response)

    if not isinstance(data, dict):
        return None, "Giudizio non valido."

    winner = str(
        data.get("preferenza", "")
    ).upper()

    if winner not in ["A", "B"]:
        return None, "Preferenza non valida."

    report = (
        f"**Preferenza {winner}**\n\n"
        + str(data.get("motivazione", ""))
        + "\n\n**Riserve:** "
        + str(data.get("riserve", ""))
        + "\n\n**Revisione possibile:** "
        + str(data.get("alternativa", ""))
    )

    return winner, report


def visual_prompts(scene, character):
    approved = scene[
        "narrative"
    ][character]["approved"]

    response = ask_ai(
        """
Sei un direttore della fotografia.

Dal testo APPROVATO ricava:
- una bibbia visiva;
- sei inquadrature cinematografiche;
- un prompt immagine per ciascuna;
- un prompt video per ciascuna.

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
            "TESTO": approved,
        },
    )

    if ai_failed(response):
        return None

    return parse_json(response)


def docx_bytes(title, body):
    document = Document()
    document.add_heading(title, 0)

    for paragraph in body.split("\n"):
        document.add_paragraph(paragraph)

    buffer = BytesIO()
    document.save(buffer)

    return buffer.getvalue()


def downloads(title, filename, content, key):
    if not content.strip():
        return

    columns = st.columns(3)

    with columns[0]:
        st.download_button(
            "TXT",
            content.encode("utf-8"),
            file_name=filename + ".txt",
            mime="text/plain",
            key=key + "_txt",
        )

    with columns[1]:
        st.download_button(
            "MARKDOWN",
            content.encode("utf-8"),
            file_name=filename + ".md",
            mime="text/markdown",
            key=key + "_md",
        )

    with columns[2]:
        st.download_button(
            "WORD",
            docx_bytes(title, content),
            file_name=filename + ".docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            key=key + "_docx",
        )


def render_workshop(scene, character):
    sid = scene["id"]
    record = scene["narrative"][character]

    st.markdown("---")
    st.header("Officina del romanzo")

    st.caption(
        "Punto di vista: " + character
    )

    notes = st.text_area(
        "Indicazioni letterarie",
        value=record["feedback"],
        key=f"writer_notes_{sid}_{character}",
    )

    if st.button(
        "GENERA VERSIONI A E B",
        key=f"write_{sid}_{character}",
        disabled=client is None,
    ):
        material = (
            scene["ensemble_messages"]
            or scene["messages"].get(character)
        )

        if not material:
            st.warning(
                "Registra prima un dialogo "
                "o un monologo."
            )

        else:
            with st.spinner(
                "Scrittura delle versioni..."
            ):
                version_a = write_version(
                    scene, character, "A", notes
                )

                version_b = (
                    write_version(
                        scene, character, "B", notes
                    )
                    if not ai_failed(version_a)
                    else ""
                )

            if ai_failed(version_a):
                st.error(version_a)

            elif ai_failed(version_b):
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
        tab_a, tab_b = st.tabs([
            "VERSIONE A",
            "VERSIONE B",
        ])

        with tab_a:
            st.markdown(
                '<div class="story">'
                + escape(record["A"])
                + "</div>",
                unsafe_allow_html=True,
            )

        with tab_b:
            st.markdown(
                '<div class="story">'
                + escape(record["B"])
                + "</div>",
                unsafe_allow_html=True,
            )

        if st.button(
            "CHIEDI GIUDIZIO CRITICO",
            key=f"critic_{sid}_{character}",
            disabled=client is None,
        ):
            winner, report = critic(
                scene, character
            )

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

    selection = st.selectbox(
        "Testo da revisionare",
        options,
        key=f"choose_{sid}_{character}",
    )

    if selection == "Versione A":
        starting_text = record["A"]

    elif selection == "Versione B":
        starting_text = record["B"]

    else:
        starting_text = record["draft"]

    editor_key = (
        f"editor_{sid}_{character}_"
        f"{normalize(selection)}"
    )

    source_key = editor_key + "_source"

    if (
        st.session_state.get(source_key)
        != starting_text
    ):
        st.session_state[editor_key] = starting_text
        st.session_state[source_key] = starting_text

    edited = st.text_area(
        "Testo narrativo",
        height=350,
        key=editor_key,
    )

    reason = st.text_input(
        "Motivazione della modifica",
        key=f"reason_{sid}_{character}",
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA",
            key=f"save_draft_{sid}_{character}",
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
            key=f"approve_{sid}_{character}",
            disabled=not edited.strip(),
        ):
            def change():
                old = record["approved"]

                if old and old != edited:
                    record["history"].append({
                        "text": old,
                        "replaced_at": timestamp(),
                        "reason": reason,
                    })

                record["draft"] = edited
                record["approved"] = edited
                record["approved_at"] = timestamp()
                record["status"] = "approvata"

                if character in PROTAGONISTS:
                    scene["diary"][character] = edited

                if old != edited:
                    log_change(
                        "testo approvato",
                        scene["title"]
                        + " - "
                        + character,
                        old,
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
        f"{sid}_{character.lower()}",
        edited,
        f"download_{sid}_{character}",
    )

    if record["approved"]:
        with st.expander(
            "TESTO APPROVATO"
        ):
            st.markdown(
                '<div class="story">'
                + escape(record["approved"])
                + "</div>",
                unsafe_allow_html=True,
            )

    with st.expander(
        "TRASCRIZIONE DELLA SCENA"
    ):
        st.text(
            scene_transcript(
                scene, character
            )
        )

    with st.expander(
        "VERSIONI PRECEDENTI"
    ):
        for item in reversed(
            record["history"]
        ):
            st.caption(
                item.get("replaced_at", "")
            )

            st.code(
                text_diff(
                    item.get("text", ""),
                    record["approved"],
                ),
                language="diff",
            )

    with st.expander(
        "OFFICINA VISIVA"
    ):
        if not record["approved"]:
            st.info(
                "Approva prima il racconto."
            )

        else:
            if st.button(
                "GENERA PROMPT VISIVI",
                key=f"visual_{sid}_{character}",
                disabled=client is None,
            ):
                result = visual_prompts(
                    scene, character
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
                    visual.get("prompts", []), 1
                ):
                    st.markdown(
                        f"**Inquadratura {index}**"
                    )

                    st.code(
                        shot.get("image_prompt", "")
                    )

                    st.code(
                        shot.get("video_prompt", "")
                    )


# ==========================================================
# MEDIA DI SCENA
# ==========================================================

def parse_media(path, sid, character):
    extension = path.suffix.casefold()

    if extension not in IMAGE_EXT | VIDEO_EXT:
        return None

    name = normalize(path.stem)
    person = normalize(character)

    aliases = sorted(
        aliases_for(sid),
        key=len,
        reverse=True,
    )

    for alias in aliases:
        if not name.startswith(alias):
            continue

        tail = name[len(alias):]

        if tail == person and extension in IMAGE_EXT:
            return ("cover", 0)

        if tail.startswith(person):
            number = tail[len(person):]

            if number.isdigit():
                return (
                    "video"
                    if extension in VIDEO_EXT
                    else "image",
                    int(number),
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
                int(tail),
            )

    return None


def scene_media(sid, character):
    found = {
        "cover": [],
        "generic_cover": [],
        "image": [],
        "video": [],
    }

    if not ASSETS.is_dir():
        return found

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        parsed = parse_media(
            path, sid, character
        )

        if parsed:
            kind, number = parsed
            found[kind].append(
                (number, path)
            )

    for kind in found:
        found[kind].sort(
            key=lambda pair: (
                pair[0],
                pair[1].name.casefold(),
            )
        )

        found[kind] = [
            path
            for _, path in found[kind]
        ]

    return found


def render_media(scene, character):
    sid = scene["id"]
    media = scene_media(sid, character)

    covers = (
        media["cover"]
        or media["generic_cover"]
    )

    if covers:
        st.image(
            str(covers[0]),
            use_container_width=True,
        )

        st.caption(
            "Copertina: " + covers[0].name
        )

    entries = []

    for kind in ("image", "video"):
        for path in media[kind]:
            parsed = parse_media(
                path, sid, character
            )

            if parsed:
                entries.append(
                    (parsed[1], kind, path)
                )

    entries.sort(
        key=lambda value: (
            value[0],
            value[2].name.casefold(),
        )
    )

    for offset in range(0, len(entries), 2):
        columns = st.columns(2)

        for column, entry in zip(
            columns,
            entries[offset:offset + 2],
        ):
            _, kind, path = entry

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
        prefix = (
            f"{sid}.{character.lower()}"
        )

        if covers:
            st.success(
                "Copertina: "
                + covers[0].name
            )
        else:
            st.warning(
                "Manca: "
                + prefix + ".jpg"
            )

        for kind, ext, count in (
            ("image", "jpg", 3),
            ("video", "mp4", 2),
        ):
            for number in range(1, count + 1):
                matched = []

                for path in media[kind]:
                    parsed = parse_media(
                        path,
                        sid,
                        character,
                    )

                    if (
                        parsed is not None
                        and parsed[1] == number
                    ):
                        matched.append(path.name)

                if matched:
                    st.success(
                        "Trovato: "
                        + ", ".join(matched)
                    )
                else:
                    st.warning(
                        f"Manca: {prefix}.{number}.{ext}"
                    )


# ==========================================================
# ARCHIVIO PERSONAGGI
# ==========================================================

def page_people():
    st.title("Archivio dei personaggi")

    character = st.selectbox(
        "Personaggio",
        PEOPLE,
    )

    agent = state["agents"][character]

    st.markdown("### Profilo approvato")
    st.write(agent["profile"])

    st.markdown("### Prima bozza")

    passages = relevant_reference(
        [character],
        limit=4,
    )

    if not passages:
        st.warning(
            "Non sono disponibili brani "
            "della prima bozza."
        )

    for passage in passages:
        with st.expander(
            f"Passaggio {passage['passage']}"
        ):
            st.text(passage["text"])

    edited = st.text_area(
        "Nuova versione del profilo",
        value=agent["profile"],
        height=220,
        key=f"profile_{character}",
    )

    reason = st.text_input(
        "Motivazione",
        key=f"profile_reason_{character}",
    )

    if st.button(
        "APPROVA NUOVO PROFILO",
        disabled=(
            edited == agent["profile"]
            or not edited.strip()
        ),
    ):
        def change():
            old = agent["profile"]

            agent["profile_history"].append({
                "profile": old,
                "replaced_at": timestamp(),
            })

            agent["profile"] = edited

            log_change(
                "profilo personaggio",
                character,
                old,
                edited,
                reason,
            )

        if commit(change):
            st.rerun()

    with st.expander(
        "CRONOLOGIA PROFILO"
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
                    agent["profile"],
                ),
                language="diff",
            )


# ==========================================================
# REGISTRO EDITORIALE
# ==========================================================

def page_editorial():
    st.title("Registro editoriale")

    changes_tab, proposals_tab = st.tabs([
        "MODIFICHE APPROVATE",
        "PROPOSTE",
    ])

    with changes_tab:
        log = state["editorial_log"]

        if not log:
            st.info(
                "Nessuna modifica registrata."
            )

        for item in reversed(log):
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
                        item.get("after", ""),
                    ),
                    language="diff",
                )

    with proposals_tab:
        with st.form(
            "new_proposal",
            clear_on_submit=True,
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
                    "date": timestamp(),
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


# ==========================================================
# ARCHIVIO SCENE
# ==========================================================

def page_archive():
    st.title("Archivio scene approvate")

    total = 0

    for sid in SCENE_IDS:
        scene = scene_by_id(sid)

        for character in PEOPLE:
            text = scene[
                "narrative"
            ][character]["approved"]

            if not text.strip():
                continue

            total += 1

            with st.expander(
                scene["title"]
                + " - "
                + character
            ):
                st.markdown(
                    '<div class="story">'
                    + escape(text)
                    + "</div>",
                    unsafe_allow_html=True,
                )

                downloads(
                    scene["title"],
                    f"{sid}_{character.lower()}",
                    text,
                    f"archive_{sid}_{character}",
                )

    if not total:
        st.info(
            "Non ci sono ancora scene approvate."
        )


# ==========================================================
# PAGINA INGRESSO
# ==========================================================

def page_entrance():
    hotel = find_asset(
        "TuringHotel.jpg"
    )

    if hotel:
        st.image(
            str(hotel),
            use_container_width=True,
        )

    st.title("TURING HOTEL")
    st.caption(
        "Un romanzo a più coscienze"
    )

    if st.button(
        "ENTRA AL TURING HOTEL",
        use_container_width=True,
    ):
        st.session_state.page = "characters"
        st.rerun()


def page_characters():
    st.title("Scegli una storia")

    columns = st.columns(2)

    for column, character in zip(
        columns,
        PROTAGONISTS,
    ):
        with column:
            portrait = find_asset(
                character + ".jpg"
            )

            if portrait:
                st.image(
                    str(portrait),
                    use_container_width=True,
                )

            st.subheader(character)

            if st.button(
                "ENTRA NELLA STORIA DI "
                + character.upper(),
                key=f"choose_{character}",
                use_container_width=True,
            ):
                st.session_state.pov = character
                st.session_state.scene_index = 0
                st.session_state.page = "story"
                st.rerun()


# ==========================================================
# NAVIGAZIONE
# ==========================================================

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

    st.sidebar.caption(
        f"Scena {index + 1}/31"
    )

    st.sidebar.markdown("---")

    links = [
        ("ARCHIVIO SCENE", "archive"),
        ("ARCHIVIO PERSONAGGI", "people"),
        ("REGISTRO MODIFICHE", "editorial"),
        ("CAMBIA STORIA", "characters"),
    ]

    for label, page in links:
        if st.sidebar.button(
            label,
            key="nav_" + page,
            use_container_width=True,
        ):
            st.session_state.page = page
            st.rerun()

    with st.sidebar.expander(
        "PRIMA BOZZA"
    ):
        load_reference()

        if st.session_state.reference_text:
            st.success(
                "Romanzo originale collegato"
            )

            st.caption(
                str(len(
                    st.session_state.reference_text
                ))
                + " caratteri"
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

    with st.sidebar.expander(
        "ARCHIVIO GITHUB"
    ):
        st.caption(
            GH_OWNER + "/" + GH_REPO
        )

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


# ==========================================================
# PAGINA SCENA
# ==========================================================

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

    render_sidebar()

    st.title(scene["title"])

    st.caption(
        f"Scena {index + 1}/31 "
        f"- percorso di {pov}"
    )

    media_character = st.selectbox(
        "Media del personaggio",
        PROTAGONISTS,
        index=PROTAGONISTS.index(pov),
        key=f"media_{sid}_{pov}",
    )

    render_media(
        scene,
        media_character,
    )

    st.markdown("---")

    render_context(scene, pov)

    # Il consulente è prima delle interazioni:
    # la regia viene scelta PRIMA
    # che gli agenti inizino a parlare.
    render_advisor(scene)

    render_interactions(scene, pov)

    narrators = (
        scene["cast"]
        if scene["cast"]
        else [pov]
    )

    character = st.selectbox(
        "PUNTO DI VISTA DEL RACCONTO",
        narrators,
        index=(
            narrators.index(pov)
            if pov in narrators
            else 0
        ),
        key=f"narrator_{sid}_{pov}",
    )

    render_workshop(scene, character)

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


# ==========================================================
# CREAZIONE ARCHIVIO SE NECESSARIO
# ==========================================================

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
            sha = save_remote_json(
                state,
                None,
            )

            st.session_state.archive_sha = sha
            st.session_state.archive_exists = True

            st.rerun()

        except Exception as exc:
            st.error(str(exc))

    st.stop()


# ==========================================================
# PAGINA ATTIVA
# ==========================================================

if st.session_state.page in [
    "archive",
    "people",
    "editorial",
]:
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
