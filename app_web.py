
import streamlit as st
import json
import os
import re
import copy
import base64
import requests

from pathlib import Path
from io import BytesIO
from html import escape
from datetime import datetime, timezone
from urllib.parse import quote

from openai import OpenAI
from docx import Document


# ============================================================
# TURING HOTEL
# OFFICINA DEL ROMANZO
# NOA / ADA
# ============================================================

st.set_page_config(
    page_title="Turing Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CHARACTERS_DIR = ROOT / "characters"
LOCAL_ARCHIVE = ROOT / "data_web" / "romanzo_web.json"

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}

CHARACTERS = ["Noa", "Ada"]

SCENE_ORDER = [
    "inizio",
    "hall",
    "stanza",
    "funerale",
    "matrimonio",
    "reparto_nascite",
    "ritorno"
]

SCENE_TITLES = {
    "inizio": "L'inizio",
    "hall": "La Hall",
    "stanza": "La stanza",
    "funerale": "Il Funerale",
    "matrimonio": "Il Matrimonio",
    "reparto_nascite": "Il reparto nascite",
    "ritorno": "Il ritorno"
}

SCENE_ALIASES = {
    "inizio": ["inizio", "prologo"],
    "hall": ["hall"],
    "stanza": ["stanza", "camera"],
    "funerale": ["funerale"],
    "matrimonio": ["matrimonio"],
    "reparto_nascite": [
        "reparto_nascite",
        "repartonascite",
        "reparto-nascite",
        "nascite"
    ],
    "ritorno": ["ritorno", "finale"]
}

INTRO_CONTEXTS = {
    "Noa": (
        "Noa cammina lungo il viale che conduce "
        "al Turing Hotel. È sola con i propri pensieri. "
        "Il percorso è un monologo interiore, "
        "costruito dalle sue osservazioni, "
        "dalla sua memoria e dalla sua natura artificiale. "
        "La scena termina con l'incontro con Ada. "
        "Non raccontare il dialogo successivo."
    ),
    "Ada": (
        "Ada si trova nello studio di suo padre, "
        "il professor Elia, all'interno del Turing Hotel. "
        "La scena si sviluppa nel dialogo tra Ada "
        "e il Professore. "
        "Ada reagisce alle parole del padre "
        "secondo la propria identità e memoria. "
        "La scena termina quando Noa arriva "
        "alla reception. "
        "Non raccontare ciò che avviene dopo."
    )
}


# ============================================================
# UTILITÀ
# ============================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(value):
    return re.sub(
        r"[\s._\-]+",
        "",
        str(value).casefold()
    )


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def safe_list(value):
    return value if isinstance(value, list) else []


def setting(name, default=""):
    try:
        value = st.secrets.get(name)
        if value is not None and value != "":
            return str(value)
    except Exception:
        pass

    return os.getenv(name, default)


def find_file(name):
    """
    Cerca nella cartella assets ignorando
    maiuscole e minuscole del nome.
    """
    if not ASSETS.exists():
        return None

    wanted = name.casefold()

    for path in ASSETS.iterdir():
        if path.is_file() and path.name.casefold() == wanted:
            return path

    return None


def numbered_suffix(value):
    match = re.search(r"(\d+)$", value)
    return int(match.group(1)) if match else 0


# ============================================================
# SECRETS
# ============================================================

OPENAI_KEY = setting("OPENAI_API_KEY")
OPENAI_MODEL = setting("OPENAI_MODEL", "gpt-5.6")

GH_TOKEN = setting("GITHUB_TOKEN")
GH_OWNER = setting("GITHUB_OWNER")
GH_REPO = setting("GITHUB_REPO")
GH_BRANCH = setting("GITHUB_BRANCH", "main")

REMOTE_FILE = "romanzo_web.json"

client = (
    OpenAI(api_key=OPENAI_KEY)
    if OPENAI_KEY
    else None
)


# ============================================================
# CSS — CONTRASTO CORRETTO
# ============================================================

st.markdown("""
<style>

/* ----------------------------------------------------------
   COLORI BASE
---------------------------------------------------------- */

:root {
    --bg: #090c0e;
    --panel: #161c20;
    --panel2: #222a30;
    --text-light: #ffffff;
    --text-dark: #111111;
    --gold: #c1a478;
}

html,
body,
.stApp {
    background: #090c0e !important;
    color: #ffffff !important;
}

/* ----------------------------------------------------------
   FONDO SCURO — TESTI CHIARI
---------------------------------------------------------- */

.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4,
.stApp h5,
.stApp h6 {
    color: #ffffff !important;
}

.stApp .stMarkdownContainer,
.stApp [data-testid="stMarkdownContainer"] {
    color: #ffffff;
}

.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stMarkdownContainer"] strong {
    color: inherit;
}

.stApp [data-testid="stWidgetLabel"] p {
    color: #ffffff !important;
}

.stApp [data-testid="stCaptionContainer"] {
    color: #d7dde0 !important;
}

.stApp [data-testid="stCaptionContainer"] p {
    color: #d7dde0 !important;
}

/* ----------------------------------------------------------
   SIDEBAR
---------------------------------------------------------- */

[data-testid="stSidebar"] {
    background: #101519 !important;
    color: #ffffff !important;
    border-right: 1px solid #39444b;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label {
    color: #ffffff !important;
}

/* ----------------------------------------------------------
   PULSANTI
---------------------------------------------------------- */

.stApp .stButton > button,
.stApp .stFormSubmitButton > button,
.stApp .stDownloadButton > button {
    background-color: #1b2227 !important;
    color: #ffffff !important;
    border: 1px solid #87929a !important;
    border-radius: 5px !important;
    min-height: 43px;
    font-weight: 600 !important;
}

.stApp .stButton > button p,
.stApp .stFormSubmitButton > button p,
.stApp .stDownloadButton > button p,
.stApp .stButton > button span,
.stApp .stFormSubmitButton > button span,
.stApp .stDownloadButton > button span {
    color: #ffffff !important;
}

.stApp .stButton > button:hover,
.stApp .stFormSubmitButton > button:hover,
.stApp .stDownloadButton > button:hover {
    background-color: #354149 !important;
    color: #ffffff !important;
    border-color: #c1a478 !important;
}

.stApp .stButton > button:disabled,
.stApp .stFormSubmitButton > button:disabled {
    opacity: 0.48 !important;
}

/* ----------------------------------------------------------
   CAMPI BIANCHI — TESTI NERI
---------------------------------------------------------- */

.stApp input:not([type="checkbox"]):not([type="radio"]),
.stApp textarea {
    background-color: #ffffff !important;
    color: #111111 !important;
    -webkit-text-fill-color: #111111 !important;
    caret-color: #111111 !important;
    border-color: #8c9498 !important;
}

.stApp input::placeholder,
.stApp textarea::placeholder {
    color: #666666 !important;
    -webkit-text-fill-color: #666666 !important;
    opacity: 1 !important;
}

.stApp [data-baseweb="input"],
.stApp [data-baseweb="textarea"] {
    background: #ffffff !important;
}

/* ----------------------------------------------------------
   SELECTBOX E MULTISELECT
---------------------------------------------------------- */

.stApp [data-baseweb="select"] > div {
    background-color: #ffffff !important;
    color: #111111 !important;
    border-color: #8c9498 !important;
}

.stApp [data-baseweb="select"] span,
.stApp [data-baseweb="select"] input,
.stApp [data-baseweb="select"] svg {
    color: #111111 !important;
    fill: #111111 !important;
}

[data-baseweb="popover"] {
    background-color: #ffffff !important;
}

[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"] {
    background-color: #ffffff !important;
    color: #111111 !important;
}

[data-baseweb="popover"] [role="option"] * {
    color: #111111 !important;
}

[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [aria-selected="true"] {
    background-color: #dce3e7 !important;
}

[data-baseweb="popover"] [role="option"]:hover * {
    color: #111111 !important;
}

/* ----------------------------------------------------------
   RADIO E CHECKBOX
---------------------------------------------------------- */

.stApp [data-testid="stCheckbox"] label p,
.stApp [data-testid="stRadio"] label p {
    color: #ffffff !important;
}

/* ----------------------------------------------------------
   TABS
---------------------------------------------------------- */

.stApp button[data-baseweb="tab"] {
    background: #1b2227 !important;
    color: #ffffff !important;
    border-radius: 5px 5px 0 0;
}

.stApp button[data-baseweb="tab"] p {
    color: #ffffff !important;
}

.stApp button[data-baseweb="tab"][aria-selected="true"] {
    background: #ffffff !important;
    color: #111111 !important;
}

.stApp button[data-baseweb="tab"][aria-selected="true"] p {
    color: #111111 !important;
}

/* ----------------------------------------------------------
   EXPANDER
---------------------------------------------------------- */

.stApp [data-testid="stExpander"] {
    background: #151b20 !important;
    border: 1px solid #46525b !important;
    border-radius: 6px !important;
}

.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary p,
.stApp [data-testid="stExpander"] summary span {
    color: #ffffff !important;
}

/* ----------------------------------------------------------
   AVVISI
   I messaggi con sfondo chiaro hanno testo scuro.
---------------------------------------------------------- */

.stApp [data-testid="stAlert"] {
    border: 1px solid #8d969c;
}

.stApp [data-testid="stAlert"] [data-testid="stMarkdownContainer"],
.stApp [data-testid="stAlert"] p {
    color: inherit;
}

/* ----------------------------------------------------------
   BLOCCHI DI CODICE
---------------------------------------------------------- */

.stApp pre {
    background: #171d22 !important;
}

.stApp pre code {
    color: #ffffff !important;
}

/* ----------------------------------------------------------
   TITOLI LETTERARI
---------------------------------------------------------- */

.hotel-title {
    font-family: Georgia, serif;
    font-size: 3rem;
    color: #ffffff;
    margin-bottom: 10px;
}

.hotel-subtitle {
    color: #c1a478;
    letter-spacing: .15em;
    text-transform: uppercase;
    font-size: .85rem;
    margin-bottom: 20px;
}

.story-text {
    background: #171c20;
    color: #ffffff;
    border-left: 3px solid #c1a478;
    padding: 22px;
    white-space: pre-wrap;
    font-family: Georgia, serif;
    font-size: 1.08rem;
    line-height: 1.8;
}

.chat-box {
    background: #1c242a;
    color: #ffffff;
    padding: 13px 16px;
    margin: 10px 0;
    border-left: 3px solid #8b9da8;
    white-space: pre-wrap;
}

.thought-box {
    background: #29221e;
    color: #ffffff;
    padding: 13px 16px;
    margin: 10px 0;
    border-left: 3px solid #c1a478;
    white-space: pre-wrap;
}

.media-heading {
    font-family: Georgia, serif;
    color: #ffffff;
    font-size: 1.25rem;
    margin: 18px 0 8px;
}

/* ----------------------------------------------------------
   FOCUS
---------------------------------------------------------- */

.stApp button:focus-visible,
.stApp input:focus-visible,
.stApp textarea:focus-visible {
    outline: 2px solid #c1a478 !important;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# OPENAI
# ============================================================

def ai_failed(text):
    return (
        not isinstance(text, str)
        or not text.strip()
        or text.startswith("Errore OpenAI:")
        or text.startswith("OPENAI_API_KEY")
    )


def ask_ai(instructions, payload):
    if not client:
        return "OPENAI_API_KEY non configurata."

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=json.dumps(
                payload,
                ensure_ascii=False
            )
        )

        return response.output_text.strip()

    except Exception as exc:
        return f"Errore OpenAI: {exc}"


def parse_json_answer(text):
    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    try:
        return json.loads(cleaned)
    except ValueError:
        return None


# ============================================================
# ARCHIVIO GITHUB PRIVATO
# ============================================================

class ArchiveError(Exception):
    pass


def github_ready():
    return all([
        GH_TOKEN,
        GH_OWNER,
        GH_REPO,
        GH_BRANCH
    ])


def github_url(path):
    return (
        "https://api.github.com/repos/"
        f"{quote(GH_OWNER, safe='')}/"
        f"{quote(GH_REPO, safe='')}/contents/"
        f"{quote(path, safe='/')}"
    )


def github_request(method, path, payload=None):
    if not github_ready():
        raise ArchiveError(
            "Secrets GitHub non configurati."
        )

    headers = {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
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
            timeout=30
        )

    except requests.RequestException as exc:
        raise ArchiveError(
            f"Connessione GitHub fallita: {exc}"
        ) from exc

    if response.status_code == 404:
        if method == "GET":
            return None

        raise ArchiveError(
            "Repository, ramo o percorso non trovato."
        )

    if response.status_code in (409, 422):
        raise ArchiveError(
            "Conflitto di salvataggio. "
            "Ricarica l'archivio prima di riprovare."
        )

    if not response.ok:
        raise ArchiveError(
            f"GitHub HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    return response.json()


def read_remote(path=REMOTE_FILE):
    response = github_request("GET", path)

    if response is None:
        return None, None

    try:
        content = base64.b64decode(
            response["content"]
        ).decode("utf-8")

        return content, response["sha"]

    except (KeyError, ValueError) as exc:
        raise ArchiveError(
            "Il contenuto del repository non è leggibile."
        ) from exc


def write_remote(content, expected_sha):
    _, current_sha = read_remote()

    if current_sha != expected_sha:
        raise ArchiveError(
            "Il file remoto è stato modificato "
            "da un'altra sessione. "
            "Ricarica l'archivio."
        )

    payload = {
        "message": "Turing Hotel — " + now(),
        "branch": GH_BRANCH,
        "content": base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii")
    }

    if current_sha:
        payload["sha"] = current_sha

    response = github_request(
        "PUT",
        REMOTE_FILE,
        payload
    )

    sha = safe_dict(
        response.get("content")
    ).get("sha")

    if not sha:
        raise ArchiveError(
            "GitHub non ha confermato il salvataggio."
        )

    return sha


# ============================================================
# DATI NARRATIVI
# ============================================================

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
            "source_approved_at": ""
        }
    }


def empty_scene(scene_id):
    scene = {
        "id": scene_id,
        "title": SCENE_TITLES[scene_id],
        "author_context": "",
        "story_draft": "",
        "story_feedback": "",
        "approved_context": "",
        "advisor_messages": [],
        "shared_dialogue": [],
        "messages": {
            "Noa": [],
            "Ada": []
        },
        "diary": {
            "Noa": "",
            "Ada": ""
        },
        "narrative": {
            "Noa": empty_narrative(),
            "Ada": empty_narrative()
        }
    }

    if scene_id == "inizio":
        scene["intro_contexts"] = copy.deepcopy(
            INTRO_CONTEXTS
        )

        scene["author_context"] = (
            "Due prologhi indipendenti."
        )

    if scene_id == "stanza":
        scene["author_context"] = (
            "Ada accompagna Noa nella stanza. "
            "Noa riflette anche sulla propria identità."
        )

        scene["approved_context"] = (
            scene["author_context"]
        )

    if scene_id == "ritorno":
        scene["decision"] = {
            "Noa": "",
            "Ada": ""
        }

    return scene


def default_state():
    return {
        "world": (
            "Il Turing Hotel è un antico albergo "
            "sul mare Adriatico."
        ),
        "agents": {
            "Noa": {
                "profile": (
                    "Noa è un agente artificiale "
                    "relazionale, consapevole "
                    "della propria natura."
                ),
                "memory": ""
            },
            "Ada": {
                "profile": (
                    "Ada è la figlia del professor Elia "
                    "ed è cresciuta al Turing Hotel."
                ),
                "memory": ""
            }
        },
        "scenes": [
            empty_scene(scene_id)
            for scene_id in SCENE_ORDER
        ]
    }


def find_old_scene(scenes, scene_id):
    aliases = {
        normalize(name)
        for name in SCENE_ALIASES[scene_id]
    }

    aliases.add(normalize(scene_id))

    for item in safe_list(scenes):
        if not isinstance(item, dict):
            continue

        if normalize(item.get("id", "")) in aliases:
            return item

        if normalize(item.get("title", "")) in aliases:
            return item

    return None


def migrate_state(old):
    """
    Aggiorna l'archivio senza eliminare
    il contenuto delle scene già esistenti.
    """
    result = default_state()
    old = safe_dict(old)

    if isinstance(old.get("world"), str):
        result["world"] = old["world"]

    old_agents = safe_dict(
        old.get("agents")
    )

    for pov in CHARACTERS:
        source = safe_dict(
            old_agents.get(pov)
        )

        for key in ("profile", "memory"):
            if isinstance(source.get(key), str):
                result["agents"][pov][key] = source[key]

    for scene in result["scenes"]:
        previous = find_old_scene(
            old.get("scenes"),
            scene["id"]
        )

        if previous is None:
            continue

        for field in (
            "author_context",
            "story_draft",
            "story_feedback",
            "approved_context"
        ):
            if isinstance(previous.get(field), str):
                scene[field] = previous[field]

        for field in (
            "advisor_messages",
            "shared_dialogue"
        ):
            scene[field] = copy.deepcopy(
                safe_list(previous.get(field))
            )

        if scene["id"] == "inizio":
            original_contexts = safe_dict(
                previous.get("intro_contexts")
            )

            for pov in CHARACTERS:
                if isinstance(
                    original_contexts.get(pov),
                    str
                ):
                    scene["intro_contexts"][pov] = (
                        original_contexts[pov]
                    )

        old_messages = safe_dict(
            previous.get("messages")
        )

        old_diary = safe_dict(
            previous.get("diary")
        )

        old_narratives = safe_dict(
            previous.get("narrative")
        )

        for pov in CHARACTERS:
            scene["messages"][pov] = copy.deepcopy(
                safe_list(old_messages.get(pov))
            )

            scene["diary"][pov] = str(
                old_diary.get(pov, "")
            )

            original_record = safe_dict(
                old_narratives.get(pov)
            )

            for key, value in original_record.items():
                scene["narrative"][pov][key] = (
                    copy.deepcopy(value)
                )

            record = scene["narrative"][pov]

            record["visual"] = {
                **empty_narrative()["visual"],
                **safe_dict(record.get("visual"))
            }

            record["history"] = safe_list(
                record.get("history")
            )

            if not original_record and scene["diary"][pov]:
                record["draft"] = scene["diary"][pov]
                record["status"] = "bozza_legacy"

        if scene["id"] == "ritorno":
            original_decisions = safe_dict(
                previous.get("decision")
            )

            for pov in CHARACTERS:
                scene["decision"][pov] = str(
                    original_decisions.get(pov, "")
                )

    return result


# ============================================================
# CARICAMENTO / SALVATAGGIO
# ============================================================

def load_archive():
    raw, sha = read_remote()

    if raw is None:
        return None, None

    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise ArchiveError(
            "Il file JSON remoto non è valido."
        ) from exc

    return migrate_state(parsed), sha


def initialize_session():
    if "state" in st.session_state:
        return

    if not github_ready():
        st.error(
            "Configurare i Secrets GitHub."
        )
        st.stop()

    try:
        loaded, sha = load_archive()
    except ArchiveError as exc:
        st.error(str(exc))
        st.stop()

    st.session_state.state = (
        loaded
        if loaded is not None
        else default_state()
    )

    st.session_state.archive_sha = sha
    st.session_state.archive_ready = (
        loaded is not None
    )

    st.session_state.page = "entrance"
    st.session_state.pov = None
    st.session_state.scene_index = 0


initialize_session()

state = st.session_state.state


def save_state():
    if not st.session_state.archive_ready:
        raise ArchiveError(
            "L'archivio non è inizializzato."
        )

    payload = json.dumps(
        state,
        ensure_ascii=False,
        indent=2
    )

    sha = write_remote(
        payload,
        st.session_state.archive_sha
    )

    st.session_state.archive_sha = sha


def commit_change(change):
    previous = copy.deepcopy(state)

    try:
        change()
        save_state()
        return True

    except Exception as exc:
        state.clear()
        state.update(previous)

        st.error(
            f"Salvataggio non riuscito: {exc}"
        )
        return False


def refresh_archive():
    try:
        loaded, sha = load_archive()

        if loaded is None:
            st.error(
                "Archivio remoto non trovato."
            )
            return False

        state.clear()
        state.update(loaded)

        st.session_state.archive_sha = sha
        return True

    except ArchiveError as exc:
        st.error(str(exc))
        return False


def initialize_archive_if_needed():
    if st.session_state.archive_ready:
        return

    st.warning(
        "Il file romanzo_web.json non esiste "
        "ancora nel repository privato."
    )

    use_local = False

    if LOCAL_ARCHIVE.exists():
        use_local = st.checkbox(
            "Importa il vecchio archivio locale"
        )

    confirm = st.checkbox(
        "Confermo l'inizializzazione "
        "dell'archivio privato"
    )

    if st.button(
        "INIZIALIZZA ARCHIVIO",
        disabled=not confirm
    ):
        try:
            if use_local:
                old = json.loads(
                    LOCAL_ARCHIVE.read_text(
                        encoding="utf-8"
                    )
                )

                selected = migrate_state(old)

            else:
                selected = default_state()

            payload = json.dumps(
                selected,
                ensure_ascii=False,
                indent=2
            )

            sha = write_remote(
                payload,
                None
            )

            st.session_state.state = selected
            st.session_state.archive_sha = sha
            st.session_state.archive_ready = True

            st.rerun()

        except Exception as exc:
            st.error(
                f"Inizializzazione fallita: {exc}"
            )

    st.stop()


initialize_archive_if_needed()


# ============================================================
# MEDIA — RICONOSCIMENTO CORRETTO NOA / ADA
# ============================================================

def media_files(scene_id, pov):
    """
    Accetta, per esempio:

    inizio.ada.jpg
    inizio.ada1.jpg
    Inizio.Ada2.PNG
    inizio.ada1.mp4
    inizio.noa1.jpg
    inizio.noa2.mov

    Non confonde i file di Noa con quelli di Ada.
    """

    result = {
        "cover": [],
        "images": [],
        "videos": []
    }

    if not ASSETS.exists():
        return result

    aliases = [
        normalize(value)
        for value in SCENE_ALIASES[scene_id]
    ]

    aliases = sorted(
        set(aliases),
        key=len,
        reverse=True
    )

    person = normalize(pov)

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        ext = path.suffix.casefold()

        if ext not in IMAGE_EXT | VIDEO_EXT:
            continue

        compact = normalize(path.stem)

        matched = None

        for alias in aliases:
            if compact.startswith(alias):
                matched = alias
                break

        if matched is None:
            continue

        remainder = compact[len(matched):]

        # La copertina della scena può essere
        # specifica del personaggio.
        if remainder == person:
            if ext in IMAGE_EXT:
                result["cover"].append(path)
            continue

        # Copertina generica.
        if remainder == "":
            if ext in IMAGE_EXT:
                result["cover"].append(path)
            continue

        # File esplicitamente assegnato al POV.
        if remainder.startswith(person):
            number = remainder[len(person):]

            if number.isdigit():
                if ext in VIDEO_EXT:
                    result["videos"].append(path)
                else:
                    result["images"].append(path)

            continue

        # Supporto ai vecchi file numerati
        # delle scene non iniziali.
        if (
            scene_id != "inizio"
            and remainder.isdigit()
        ):
            if ext in VIDEO_EXT:
                result["videos"].append(path)
            else:
                result["images"].append(path)

    for key in result:
        result[key] = sorted(
            result[key],
            key=lambda path: (
                numbered_suffix(path.stem),
                path.name.casefold()
            )
        )

    # Copertina del POV prima di quella generica.
    result["cover"].sort(
        key=lambda path: (
            0 if normalize(pov) in normalize(path.stem)
            else 1,
            path.name.casefold()
        )
    )

    return result


def intro_character_videos(pov):
    if not ASSETS.exists():
        return []

    matches = []

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        if path.suffix.casefold() not in VIDEO_EXT:
            continue

        name = normalize(path.stem)

        if re.fullmatch(
            rf"{normalize(pov)}video\d+",
            name
        ):
            matches.append(path)

    return sorted(
        matches,
        key=lambda item: (
            numbered_suffix(item.stem),
            item.name.casefold()
        )
    )


def display_media(scene, pov):
    files = media_files(
        scene["id"],
        pov
    )

    covers = files["cover"]

    if covers:
        st.image(
            str(covers[0]),
            use_container_width=True
        )

    if not files["images"] and not files["videos"]:
        return

    st.markdown(
        '<div class="media-heading">'
        'Immagini e video della scena'
        '</div>',
        unsafe_allow_html=True
    )

    all_media = []

    for path in files["images"]:
        all_media.append((
            numbered_suffix(path.stem),
            "image",
            path
        ))

    for path in files["videos"]:
        all_media.append((
            numbered_suffix(path.stem),
            "video",
            path
        ))

    all_media.sort(
        key=lambda item: (
            item[0],
            item[2].name.casefold()
        )
    )

    for start in range(0, len(all_media), 2):
        cols = st.columns(2)

        for column, entry in zip(
            cols,
            all_media[start:start + 2]
        ):
            _, kind, path = entry

            with column:
                if kind == "video":
                    st.video(str(path))
                else:
                    st.image(
                        str(path),
                        use_container_width=True
                    )

                st.caption(path.name)


# ============================================================
# DOCUMENTI DI CONTESTO
# ============================================================

def read_reference(path):
    try:
        if path.suffix.casefold() in (".txt", ".md"):
            return path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

        if path.suffix.casefold() == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))

            return "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

    except Exception:
        return ""

    return ""


def hotel_context():
    root_file = (
        ROOT / "TURING_HOTEL_CONTESTO_AGENTE.md"
    )

    if root_file.exists():
        return read_reference(root_file)

    if ASSETS.exists():
        for path in ASSETS.iterdir():
            if normalize(path.stem) == "contestoturinghotel":
                return read_reference(path)

    return ""


def character_sources(pov):
    sources = []

    if not CHARACTERS_DIR.exists():
        return sources

    total = 0

    for path in sorted(CHARACTERS_DIR.iterdir()):
        if not path.is_file():
            continue

        if path.suffix.casefold() not in (
            ".txt", ".md", ".pdf"
        ):
            continue

        name = path.name.casefold()

        if not (
            name.startswith(pov.casefold())
            or name.startswith("shared")
        ):
            continue

        content = read_reference(path)

        remaining = 70000 - total

        if remaining <= 0:
            break

        content = content[:remaining]

        if content:
            sources.append({
                "file": path.name,
                "text": content
            })

            total += len(content)

    return sources


def writer_sources():
    result = []

    if not ASSETS.exists():
        return result

    for path in sorted(ASSETS.iterdir()):
        if path.suffix.casefold() not in (
            ".txt", ".md", ".pdf"
        ):
            continue

        if normalize(path.stem).startswith(
            "libriagenti"
        ):
            text = read_reference(path)

            if text:
                result.append({
                    "file": path.name,
                    "text": text[:20000]
                })

    return result


# ============================================================
# SCENE, MEMORIE E CONTESTI
# ============================================================

def scene_by_id(scene_id):
    return next(
        item
        for item in state["scenes"]
        if item["id"] == scene_id
    )


def narrative_for(scene, pov):
    return scene["narrative"][pov]


def scene_context(scene, pov):
    if scene["id"] == "inizio":
        return safe_dict(
            scene.get("intro_contexts")
        ).get(
            pov,
            INTRO_CONTEXTS[pov]
        )

    return scene.get(
        "approved_context", ""
    )


def previous_memories(scene_id, pov):
    memories = []

    for sid in SCENE_ORDER:
        if sid == scene_id:
            break

        scene = scene_by_id(sid)

        text = narrative_for(
            scene, pov
        ).get("approved", "")

        if text.strip():
            memories.append({
                "scene": scene["title"],
                "text": text
            })

    return memories


def later_approved(scene_id, pov):
    index = SCENE_ORDER.index(scene_id)

    result = []

    for sid in SCENE_ORDER[index + 1:]:
        scene = scene_by_id(sid)

        if narrative_for(
            scene, pov
        ).get("approved", "").strip():
            result.append(scene["title"])

    return result


def transcript(scene, pov):
    lines = [
        f"TURING HOTEL — {scene['title']}",
        f"PROSPETTIVA: {pov}",
        "",
        "TRASCRIZIONE ORIGINALE",
        ""
    ]

    for item in scene["messages"][pov]:
        if not isinstance(item, dict):
            continue

        speaker = str(
            item.get("speaker", "?")
        )

        if item.get("kind") == "inner":
            speaker += " (pensiero)"

        lines.append(
            speaker + ": "
            + str(item.get("text", ""))
        )

        lines.append("")

    return "\n".join(lines)


# ============================================================
# CREAZIONE DEL CONTESTO
# ============================================================

def create_context(scene):
    return ask_ai(
        """
Sei il CREATORE DELLA SCENA
del romanzo Turing Hotel.

Trasforma le indicazioni dell'autore
in un contesto narrativo preciso.

Descrivi:
- luogo;
- atmosfera;
- fatti;
- oggetti;
- circostanze;
- persone presenti.

Non decidere i pensieri di Noa o Ada.

Non inventare svolte narrative.

Restituisci soltanto il testo.
""",
        {
            "CANONE": hotel_context(),
            "SCENA": scene["title"],
            "INDICAZIONI": scene["author_context"],
            "BOZZA": scene["story_draft"],
            "CORREZIONI": scene["story_feedback"]
        }
    )


def refine_context(scene):
    return ask_ai(
        """
Sei lo SCRITTORE di Turing Hotel.

Rendi il contesto più preciso,
evocativo e narrativamente efficace.

Non cambiare i fatti.
Non inventare eventi.

Usa LIBRIAGENTI come riferimenti tecnici,
senza copiarli.

Restituisci soltanto il testo.
""",
        {
            "SCENA": scene["title"],
            "TESTO": scene["story_draft"],
            "CANONE": hotel_context(),
            "FONTI": writer_sources()
        }
    )


# ============================================================
# CONSULENTE NARRATIVO
# ============================================================

def ask_advisor(scene):
    return ask_ai(
        """
Sei il CONSULENTE NARRATIVO.

Dialoghi con l'autore.

Individua problemi di coerenza,
opportunità narrative e alternative.

Se proponi alternative,
devi indicare quale preferisci
e motivare la tua preferenza.

Non decidere al posto dell'autore.

Non cambiare autonomamente i testi.

Rispondi in italiano.
""",
        {
            "CANONE": hotel_context(),
            "SCENA": scene["title"],
            "CONTESTO": scene["approved_context"],
            "CONVERSAZIONE":
                scene["advisor_messages"]
        }
    )


# ============================================================
# NOA E ADA
# ============================================================

def character_instructions(pov, mode):
    profile = state["agents"][pov]

    instructions = f"""
Tu sei {pov}, personaggio del romanzo Turing Hotel.

Non sei un assistente.
Non interpreti altri personaggi.

MONDO:
{state["world"]}

IDENTITÀ:
{profile["profile"]}

MEMORIA PERSONALE:
{profile["memory"]}

Ricordi soltanto le tue scene
letterarie precedentemente APPROVATE.

Non conosci i pensieri privati
dell'altro personaggio.

Non confondere sospetti, intuizioni
e fatti accertati.

Reagisci secondo la tua psicologia.

Rispondi in italiano.
"""

    if mode == "inner":
        instructions += """
La risposta è un pensiero interiore.

Non usare formule da assistente.
Non creare dialoghi esterni.
"""
    else:
        instructions += """
La risposta è pronunciata ad alta voce.

Scrivi soltanto ciò che dici tu.
"""

    return instructions


def answer_character(scene, pov, mode):
    instructions = character_instructions(
        pov, mode
    )

    if scene["id"] == "inizio":
        if pov == "Noa":
            instructions += """
Stai camminando lungo il viale
che porta al Turing Hotel.

Sei sola con i tuoi pensieri.

Non anticipare l'incontro con Ada
senza indicazioni nella scena.
"""
        else:
            instructions += """
Sei nello studio del professor Elia,
tuo padre.

Stai dialogando con lui.

Non inventare le battute del Professore.
Non anticipare l'arrivo di Noa.
"""

    return ask_ai(
        instructions,
        {
            "SCENA": scene["title"],
            "CONTESTO": scene_context(scene, pov),
            "FONTI": character_sources(pov),
            "CANONE": hotel_context(),
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "MESSAGGI": scene["messages"][pov],
            "MODALITA": mode
        }
    )


# ============================================================
# GO ALONE
# ============================================================

def go_alone(scene):
    if scene["id"] == "inizio":
        return (
            "GO ALONE non è disponibile "
            "nei prologhi."
        )

    speakers = ["Ada", "Noa", "Ada", "Noa"]

    for speaker in speakers:
        result = ask_ai(
            character_instructions(
                speaker, "external"
            )
            + """
Modalità GO ALONE.

Scrivi una sola battuta spontanea
nel dialogo con l'altro personaggio.

Non decidere le battute altrui.

Non inventare eventi irreversibili.
""",
            {
                "SCENA": scene["title"],
                "CONTESTO": scene_context(
                    scene, speaker
                ),
                "RICORDI": previous_memories(
                    scene["id"], speaker
                ),
                "DIALOGO": scene["shared_dialogue"]
            }
        )

        if ai_failed(result):
            return result

        turn = {
            "speaker": speaker,
            "text": result,
            "kind": "external",
            "role": "response",
            "origin": "go_alone"
        }

        def change():
            scene["shared_dialogue"].append(
                copy.deepcopy(turn)
            )

            for pov in CHARACTERS:
                scene["messages"][pov].append(
                    copy.deepcopy(turn)
                )

        if not commit_change(change):
            return "Salvataggio GO ALONE fallito."

    return ""


# ============================================================
# SCRITTORE LETTERARIO — VERSIONI A/B
# ============================================================

def write_narrative(scene, pov, version, feedback):
    if version == "A":
        style = (
            "Essenziale, concreta, sobria, "
            "precisa, con dialoghi e sottotesto."
        )
    else:
        style = (
            "Introspettiva, sensoriale, "
            "emotiva, evocativa ma controllata."
        )

    special = ""

    if scene["id"] == "inizio":
        if pov == "Noa":
            special = (
                "La scena è il monologo di Noa "
                "lungo il viale. "
                "Termina con l'incontro con Ada. "
                "Non raccontare il dialogo successivo."
            )
        else:
            special = (
                "La scena è il dialogo tra Ada "
                "e il Professore nello studio. "
                "Termina con l'arrivo di Noa "
                "alla reception."
            )

    return ask_ai(
        f"""
Sei lo SCRITTORE LETTERARIO di Turing Hotel.

Scrivi un racconto compiuto.

NARRATORE: {pov}.
PRIMA PERSONA SINGOLARE.
TEMPO PRESENTE.

Non scrivere un riassunto.

Trasforma la trascrizione in narrativa.

Conserva i fatti significativi.

Non inventare eventi fondamentali.

Non attribuire al narratore
informazioni che non possiede.

STILE:
{style}

VINCOLO SPECIFICO:
{special}

Usa le fonti letterarie come riferimenti
tecnici senza copiarle.

Tieni conto delle correzioni dell'autore.

Restituisci soltanto il racconto.
""",
        {
            "SCENA": scene["title"],
            "POV": pov,
            "CONTESTO": scene_context(scene, pov),
            "TRASCRIZIONE": transcript(scene, pov),
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "IDENTITÀ": state["agents"][pov],
            "FONTI": character_sources(pov),
            "LIBRIAGENTI": writer_sources(),
            "CORREZIONI": feedback
        }
    )


# ============================================================
# CRITICO LETTERARIO
# ============================================================

def literary_critic(scene, pov):
    record = narrative_for(scene, pov)

    result = ask_ai(
        """
Sei il CRITICO LETTERARIO di Turing Hotel.

Confronta due versioni della stessa scena.

DEVI scegliere A oppure B.

Motiva chiaramente la preferenza.

Valuta:
- qualità letteraria;
- coerenza;
- voce narrativa;
- fedeltà agli eventi;
- efficacia;
- continuità con il romanzo.

Indica anche le riserve.

Spiega in quali condizioni
sceglieresti l'altra.

Non approvare nulla autonomamente.

Restituisci SOLO JSON valido:

{
 "preferenza": "A",
 "motivazione": "...",
 "riserve": "...",
 "alternativa": "...",
 "pronta": false
}
""",
        {
            "SCENA": scene["title"],
            "POV": pov,
            "VERSIONE_A": record["A"],
            "VERSIONE_B": record["B"],
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "TRASCRIZIONE": transcript(
                scene, pov
            )
        }
    )

    if ai_failed(result):
        return None, result

    parsed = parse_json_answer(result)

    if not isinstance(parsed, dict):
        return None, "Risposta del critico non valida."

    winner = str(
        parsed.get("preferenza", "")
    ).upper()

    if winner not in ("A", "B"):
        return None, "Il critico non ha espresso una scelta."

    review = (
        f"**Preferisco la versione {winner}.**\n\n"
        f"{parsed.get('motivazione', '')}\n\n"
        f"**Riserve:** {parsed.get('riserve', '')}\n\n"
        f"**Quando sceglierei l'altra:** "
        f"{parsed.get('alternativa', '')}\n\n"
        f"**Pronta per approvazione:** "
        + (
            "Sì"
            if parsed.get("pronta") is True
            else "È consigliata una revisione"
        )
    )

    return winner, review


# ============================================================
# ESPORTAZIONI WORD / TXT / MARKDOWN
# ============================================================

def create_docx(title, content):
    doc = Document()

    doc.add_heading(title, 0)

    for paragraph in content.split("\n"):
        doc.add_paragraph(paragraph)

    buffer = BytesIO()
    doc.save(buffer)

    return buffer.getvalue()


def download_text(scene, pov, text, label):
    if not text.strip():
        return

    base = (
        f"{scene['id']}_{pov.lower()}_{label}"
    )

    columns = st.columns(3)

    with columns[0]:
        st.download_button(
            "TXT",
            data=text.encode("utf-8"),
            file_name=base + ".txt",
            mime="text/plain",
            key="txt_" + base,
            use_container_width=True
        )

    with columns[1]:
        st.download_button(
            "MARKDOWN",
            data=text.encode("utf-8"),
            file_name=base + ".md",
            mime="text/markdown",
            key="md_" + base,
            use_container_width=True
        )

    with columns[2]:
        st.download_button(
            "WORD",
            data=create_docx(
                scene["title"], text
            ),
            file_name=base + ".docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            key="doc_" + base,
            use_container_width=True
        )


# ============================================================
# PROMPT VISIVI
# ============================================================

def generate_visuals(scene, pov, count):
    record = narrative_for(scene, pov)

    if not record["approved"].strip():
        return None, "Manca il testo approvato."

    answer = ask_ai(
        f"""
Sei il DIRETTORE DELLA FOTOGRAFIA.

Crea {count} inquadrature cinematografiche
a partire dalla scena letteraria APPROVATA.

Non inventare eventi nuovi.

Mantieni una bibbia visiva coerente.

Per ogni inquadratura prepara:
- titolo;
- momento;
- prompt Nano Banana;
- prompt video;
- continuità;
- riferimenti.

Rispetta la fisionomia delle fotografie
di riferimento già presenti negli assets.

Non inventare dettagli definitivi
in assenza di indicazioni.

Restituisci SOLO JSON valido:

{{
 "bible": "...",
 "shots": [
   {{
     "title": "...",
     "moment": "...",
     "image_prompt": "...",
     "video_prompt": "...",
     "continuity": "...",
     "reference": "..."
   }}
 ]
}}
""",
        {
            "SCENA": scene["title"],
            "POV": pov,
            "TESTO_APPROVATO": record["approved"],
            "CANONE": hotel_context(),
            "REFERENZE": [
                "assets/Noa.jpg",
                "assets/Ada.jpg"
            ]
        }
    )

    if ai_failed(answer):
        return None, answer

    parsed = parse_json_answer(answer)

    if not isinstance(parsed, dict):
        return None, "Risposta JSON non valida."

    if not isinstance(parsed.get("bible"), str):
        return None, "Bibbia visiva mancante."

    if not isinstance(parsed.get("shots"), list):
        return None, "Inquadrature mancanti."

    if not parsed["shots"]:
        return None, "Nessuna inquadratura generata."

    return parsed, ""


def visual_text(visual):
    lines = [
        "TURING HOTEL — PROMPT VISIVI",
        "",
        "BIBBIA VISIVA",
        visual.get("bible", ""),
        ""
    ]

    for index, shot in enumerate(
        visual.get("prompts", []), 1
    ):
        lines.extend([
            f"INQUADRATURA {index}",
            str(shot.get("title", "")),
            "",
            "MOMENTO",
            str(shot.get("moment", "")),
            "",
            "PROMPT NANO BANANA",
            str(shot.get("image_prompt", "")),
            "",
            "PROMPT VIDEO",
            str(shot.get("video_prompt", "")),
            "",
            "CONTINUITÀ",
            str(shot.get("continuity", "")),
            "",
            "RIFERIMENTI",
            str(shot.get("reference", "")),
            "",
            "---",
            ""
        ])

    return "\n".join(lines)


def render_visual_workshop(scene, pov):
    record = narrative_for(scene, pov)

    st.markdown("---")
    st.subheader("Officina visiva")

    if not record["approved"].strip():
        st.info(
            "Approva il testo prima di generare "
            "immagini e video."
        )
        return

    count = st.slider(
        "Numero di inquadrature",
        2, 12, 6,
        key=f"visual_count_{scene['id']}_{pov}"
    )

    if st.button(
        "GENERA PROMPT NANO BANANA + VIDEO",
        key=f"visual_button_{scene['id']}_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        with st.spinner("Genero la sequenza visiva..."):
            result, error = generate_visuals(
                scene, pov, count
            )

        if error:
            st.error(error)

        else:
            def change():
                record["visual"] = {
                    "bible": result["bible"],
                    "prompts": result["shots"],
                    "source_approved_at":
                        record["approved_at"]
                }

            if commit_change(change):
                st.rerun()

    visual = safe_dict(
        record.get("visual")
    )

    prompts = safe_list(
        visual.get("prompts")
    )

    if not prompts:
        return

    if visual.get("source_approved_at") != (
        record.get("approved_at")
    ):
        st.warning(
            "Questi prompt appartengono a una "
            "versione precedente del testo."
        )
        return

    with st.expander(
        "BIBBIA VISIVA",
        expanded=True
    ):
        st.write(visual.get("bible", ""))

    for index, shot in enumerate(prompts, 1):
        with st.expander(
            f"{index:02d} — "
            f"{shot.get('title', '')}"
        ):
            st.markdown("**Momento**")
            st.write(shot.get("moment", ""))

            st.markdown("**Nano Banana**")
            st.code(
                shot.get("image_prompt", ""),
                language=None
            )

            st.markdown("**Video**")
            st.code(
                shot.get("video_prompt", ""),
                language=None
            )

            st.markdown("**Continuità**")
            st.write(
                shot.get("continuity", "")
            )

            st.markdown("**Riferimenti**")
            st.write(
                shot.get("reference", "")
            )

    download_text(
        scene,
        pov,
        visual_text(visual),
        "prompt_visivi"
    )


# ============================================================
# EDITOR PROLOGO
# ============================================================

def render_intro_editor(scene, pov):
    st.subheader(f"Prologo di {pov}")

    if pov == "Noa":
        st.info(
            "Noa cammina lungo il viale. "
            "La scena termina con l'incontro con Ada."
        )
    else:
        st.info(
            "Ada dialoga con il Professore nello studio. "
            "La scena termina all'arrivo "
            "di Noa alla reception."
        )

    original = scene_context(scene, pov)

    edited = st.text_area(
        "Contesto iniziale modificabile",
        value=original,
        height=180,
        key=f"intro_text_{pov}"
    )

    if st.button(
        "SALVA CONTESTO INIZIALE",
        key=f"save_intro_{pov}",
        use_container_width=True
    ):
        def change():
            scene.setdefault(
                "intro_contexts", {}
            )[pov] = edited

        if commit_change(change):
            st.success(
                "Contesto del prologo salvato."
            )


# ============================================================
# EDITOR CONTESTO NORMALE
# ============================================================

def render_context_editor(scene):
    with st.expander(
        "CREATORE DELLA SCENA"
    ):
        notes = st.text_area(
            "Indicazioni dell'autore",
            value=scene["author_context"],
            height=110,
            key=f"notes_{scene['id']}"
        )

        if st.button(
            "SALVA INDICAZIONI",
            key=f"save_notes_{scene['id']}"
        ):
            if commit_change(
                lambda: scene.update(
                    author_context=notes
                )
            ):
                st.success("Indicazioni salvate.")

        if st.button(
            "CREA CONTESTO",
            disabled=not bool(client),
            key=f"create_context_{scene['id']}"
        ):
            temporary = copy.deepcopy(scene)
            temporary["author_context"] = notes

            result = create_context(temporary)

            if ai_failed(result):
                st.error(result)
            else:
                if commit_change(
                    lambda: scene.update(
                        author_context=notes,
                        story_draft=result
                    )
                ):
                    st.rerun()

        if scene["story_draft"]:
            st.write(scene["story_draft"])

            feedback = st.text_area(
                "Correzioni",
                value=scene["story_feedback"],
                key=f"context_feedback_{scene['id']}"
            )

            if st.button(
                "RISCRIVI CONTESTO",
                disabled=not bool(client),
                key=f"rewrite_context_{scene['id']}"
            ):
                temporary = copy.deepcopy(scene)
                temporary["story_feedback"] = feedback

                result = create_context(temporary)

                if ai_failed(result):
                    st.error(result)
                else:
                    if commit_change(
                        lambda: scene.update(
                            story_draft=result,
                            story_feedback=feedback
                        )
                    ):
                        st.rerun()

            if st.button(
                "RIFINISCI CON AGENTE SCRITTORE",
                disabled=not bool(client),
                key=f"refine_context_{scene['id']}"
            ):
                result = refine_context(scene)

                if ai_failed(result):
                    st.error(result)
                else:
                    if commit_change(
                        lambda: scene.update(
                            story_draft=result
                        )
                    ):
                        st.rerun()

            if st.button(
                "APPROVA CONTESTO",
                key=f"approve_context_{scene['id']}"
            ):
                if commit_change(
                    lambda: scene.update(
                        approved_context=scene["story_draft"]
                    )
                ):
                    st.rerun()

        if scene["approved_context"]:
            st.markdown(
                "**Contesto approvato**"
            )
            st.write(
                scene["approved_context"]
            )


# ============================================================
# CONSULENTE
# ============================================================

def render_advisor(scene):
    with st.expander(
        "CONSULENTE NARRATIVO"
    ):
        for message in scene["advisor_messages"]:
            if message.get("role") == "user":
                st.markdown("**Autore:**")
            else:
                st.markdown("**Consulente:**")

            st.write(message.get("text", ""))

        with st.form(
            f"advisor_{scene['id']}"
        ):
            question = st.text_area(
                "Domanda al consulente"
            )

            submitted = st.form_submit_button(
                "CHIEDI AL CONSULENTE"
            )

        if submitted and question.strip():
            messages = copy.deepcopy(
                scene["advisor_messages"]
            )

            messages.append({
                "role": "user",
                "text": question
            })

            temporary = copy.deepcopy(scene)
            temporary["advisor_messages"] = messages

            answer = ask_advisor(temporary)

            if ai_failed(answer):
                st.error(answer)
            else:
                messages.append({
                    "role": "assistant",
                    "text": answer
                })

                if commit_change(
                    lambda: scene.update(
                        advisor_messages=messages
                    )
                ):
                    st.rerun()


# ============================================================
# CHAT
# ============================================================

def render_chat(scene, pov):
    st.markdown("---")
    st.subheader(f"Dialogo con {pov}")

    with st.container(
        height=380,
        border=True
    ):
        messages = scene["messages"][pov]

        if not messages:
            st.caption(
                "La conversazione non è ancora iniziata."
            )

        for item in messages:
            if not isinstance(item, dict):
                continue

            is_inner = (
                item.get("kind") == "inner"
            )

            if scene["id"] == "stanza":
                if pov == "Ada" and is_inner:
                    continue

                if pov == "Noa" and not is_inner:
                    continue

            css_class = (
                "thought-box"
                if is_inner
                else "chat-box"
            )

            speaker = escape(
                str(item.get("speaker", "?"))
            )

            text = escape(
                str(item.get("text", ""))
            )

            st.markdown(
                f'<div class="{css_class}">'
                f'<strong>{speaker}</strong>'
                f'<div>{text}</div>'
                '</div>',
                unsafe_allow_html=True
            )

    if scene["id"] != "inizio":
        if st.button(
            "GO ALONE · 2 SCAMBI",
            disabled=not bool(client),
            key=f"go_alone_{scene['id']}_{pov}",
            use_container_width=True
        ):
            with st.spinner(
                "Noa e Ada stanno conversando..."
            ):
                error = go_alone(scene)

            if error:
                st.error(error)
            else:
                st.rerun()

    else:
        st.caption(
            "Il prologo ha una modalità autonoma: "
            "monologo per Noa, dialogo col Professore per Ada."
        )

    other = (
        "Ada" if pov == "Noa" else "Noa"
    )

    options = [
        other,
        pov,
        "Elia",
        "Luigi",
        "Adam",
        "Vittoria",
        "Riccardo",
        "Altro"
    ]

    if scene["id"] == "stanza":
        options = ["Noa"]

    if scene["id"] == "inizio":
        if pov == "Noa":
            options = ["Noa"]
        else:
            options = ["Professore"]

    with st.form(
        f"chat_form_{scene['id']}_{pov}",
        clear_on_submit=True
    ):
        speaker = st.selectbox(
            "Chi parla",
            options
        )

        message = st.text_area(
            "Messaggio",
            height=110
        )

        send = st.form_submit_button(
            "INVIA",
            use_container_width=True
        )

    if send and message.strip():
        mode = (
            "inner"
            if speaker == pov
            else "external"
        )

        turn = {
            "speaker": speaker,
            "text": message.strip(),
            "kind": mode,
            "role": "prompt"
        }

        temporary = copy.deepcopy(scene)

        temporary["messages"][pov].append(
            copy.deepcopy(turn)
        )

        with st.spinner(
            f"{pov} sta rispondendo..."
        ):
            answer = answer_character(
                temporary,
                pov,
                mode
            )

        if ai_failed(answer):
            st.error(answer)

        else:
            reply = {
                "speaker": pov,
                "text": answer,
                "kind": mode,
                "role": "response"
            }

            def change():
                scene["messages"][pov].extend(
                    [turn, reply]
                )

            if commit_change(change):
                st.rerun()

    with st.expander(
        "GESTIONE CONVERSAZIONE"
    ):
        st.warning(
            "La cancellazione della chat non elimina "
            "i racconti già approvati."
        )

        confirmed = st.checkbox(
            "Confermo la cancellazione",
            key=f"confirm_delete_{scene['id']}_{pov}"
        )

        if st.button(
            "CANCELLA CONVERSAZIONE",
            disabled=not confirmed,
            key=f"delete_messages_{scene['id']}_{pov}"
        ):
            if commit_change(
                lambda: scene["messages"].update(
                    {pov: []}
                )
            ):
                st.rerun()


# ============================================================
# OFFICINA DEL ROMANZO
# ============================================================

def render_workshop(scene, pov):
    record = narrative_for(scene, pov)

    st.markdown("---")
    st.header("Officina del romanzo")

    st.caption(
        "Prima persona, tempo presente. "
        "Solo il testo approvato diventa memoria."
    )

    st.write(
        f"**Stato:** {record['status']}"
    )

    feedback = st.text_area(
        "Indicazioni per la scrittura",
        value=record.get("feedback", ""),
        key=f"workshop_feedback_{scene['id']}_{pov}"
    )

    if st.button(
        "GENERA VERSIONI A E B",
        key=f"generate_{scene['id']}_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        if not scene["messages"][pov]:
            st.warning(
                "Crea prima almeno un'interazione."
            )
        else:
            with st.spinner(
                "Sto scrivendo le due versioni..."
            ):
                text_a = write_narrative(
                    scene, pov, "A", feedback
                )

                text_b = (
                    write_narrative(
                        scene, pov, "B", feedback
                    )
                    if not ai_failed(text_a)
                    else ""
                )

            if ai_failed(text_a):
                st.error(text_a)

            elif ai_failed(text_b):
                st.error(text_b)

            else:
                def change():
                    record["A"] = text_a
                    record["B"] = text_b
                    record["feedback"] = feedback
                    record["recommended"] = ""
                    record["review"] = ""
                    record["status"] = "in_revisione"

                if commit_change(change):
                    st.rerun()

    if record.get("A") or record.get("B"):
        tab_a, tab_b = st.tabs([
            "VERSIONE A",
            "VERSIONE B"
        ])

        with tab_a:
            st.markdown(
                '<div class="story-text">'
                + escape(record.get("A", ""))
                + '</div>',
                unsafe_allow_html=True
            )

            download_text(
                scene, pov,
                record.get("A", ""),
                "A"
            )

        with tab_b:
            st.markdown(
                '<div class="story-text">'
                + escape(record.get("B", ""))
                + '</div>',
                unsafe_allow_html=True
            )

            download_text(
                scene, pov,
                record.get("B", ""),
                "B"
            )

        if st.button(
            "CHIEDI GIUDIZIO CRITICO",
            key=f"critic_{scene['id']}_{pov}",
            disabled=not bool(client),
            use_container_width=True
        ):
            with st.spinner(
                "Il critico sta valutando..."
            ):
                winner, review = literary_critic(
                    scene, pov
                )

            if winner is None:
                st.error(review)
            else:
                if commit_change(
                    lambda: record.update(
                        recommended=winner,
                        review=review
                    )
                ):
                    st.rerun()

    if record.get("review"):
        st.markdown(
            "### Preferenza dell'agente critico"
        )

        st.markdown(record["review"])

    choices = ["Bozza salvata"]

    if record.get("A"):
        choices.append("Versione A")

    if record.get("B"):
        choices.append("Versione B")

    preferred = (
        "Versione "
        + str(record.get("recommended", ""))
    )

    initial_index = (
        choices.index(preferred)
        if preferred in choices
        else 0
    )

    selected_choice = st.selectbox(
        "Versione da revisionare",
        choices,
        index=initial_index,
        key=f"choice_{scene['id']}_{pov}"
    )

    selected_text = record.get("draft", "")

    if selected_choice == "Versione A":
        selected_text = record.get("A", "")

    elif selected_choice == "Versione B":
        selected_text = record.get("B", "")

    editor_key = (
        f"editor_{scene['id']}_{pov}_"
        f"{normalize(selected_choice)}"
    )

    source_key = editor_key + "_source"

    if (
        source_key not in st.session_state
        or st.session_state[source_key] != selected_text
    ):
        st.session_state[editor_key] = selected_text
        st.session_state[source_key] = selected_text

    edited = st.text_area(
        "Testo definitivo modificabile",
        height=420,
        key=editor_key
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA SU GITHUB",
            key=f"save_draft_{scene['id']}_{pov}",
            use_container_width=True
        ):
            def change():
                record["draft"] = edited

                if not record.get("approved", "").strip():
                    record["status"] = "bozza"

            if commit_change(change):
                st.success("Bozza salvata.")

    with right:
        if st.button(
            "APPROVA E MEMORIZZA",
            key=f"approve_{scene['id']}_{pov}",
            use_container_width=True
        ):
            if not edited.strip():
                st.warning("Il testo è vuoto.")

            else:
                def change():
                    old_text = record.get(
                        "approved", ""
                    )

                    if (
                        old_text.strip()
                        and old_text != edited
                    ):
                        record.setdefault(
                            "history", []
                        ).append({
                            "text": old_text,
                            "replaced_at": now()
                        })

                    record["draft"] = edited
                    record["approved"] = edited
                    record["approved_at"] = now()
                    record["status"] = "approvata"

                    scene["diary"][pov] = edited

                    if old_text != edited:
                        record.setdefault(
                            "visual", {}
                        )["source_approved_at"] = ""

                if commit_change(change):
                    st.success(
                        "Scena approvata e archiviata."
                    )
                    st.rerun()

    st.markdown(
        "**Esporta il testo in revisione**"
    )

    download_text(
        scene, pov, edited, "revisione"
    )

    approved = record.get(
        "approved", ""
    )

    if approved.strip():
        with st.expander(
            f"MEMORIA CANONICA DI {pov}"
        ):
            st.markdown(
                '<div class="story-text">'
                + escape(approved)
                + '</div>',
                unsafe_allow_html=True
            )

            download_text(
                scene,
                pov,
                approved,
                "approvata"
            )

            later = later_approved(
                scene["id"], pov
            )

            if later:
                st.warning(
                    "Controlla la coerenza "
                    "con le scene successive: "
                    + ", ".join(later)
                )

    with st.expander(
        "TRASCRIZIONE ORIGINALE"
    ):
        original = transcript(
            scene, pov
        )

        st.text(original)

        download_text(
            scene, pov,
            original,
            "trascrizione"
        )

    render_visual_workshop(scene, pov)


# ============================================================
# ARCHIVIO SCENE SALVATE
# ============================================================

def render_saved_scenes():
    st.header("Archivio scene salvate")

    st.caption(
        "Le scene approvate sono conservate "
        "nell'archivio GitHub privato."
    )

    total = 0

    for scene_id in SCENE_ORDER:
        scene = scene_by_id(scene_id)

        for pov in CHARACTERS:
            record = narrative_for(
                scene, pov
            )

            approved = record.get(
                "approved", ""
            )

            if not approved.strip():
                continue

            total += 1

            with st.expander(
                f"{scene['title']} — {pov}"
            ):
                st.caption(
                    "Data approvazione: "
                    + str(
                        record.get(
                            "approved_at", ""
                        )
                    )
                )

                st.markdown(
                    '<div class="story-text">'
                    + escape(approved)
                    + '</div>',
                    unsafe_allow_html=True
                )

                download_text(
                    scene,
                    pov,
                    approved,
                    "archivio"
                )

    if total == 0:
        st.info(
            "Non ci sono ancora scene approvate."
        )
    else:
        st.success(
            f"Scene archiviate: {total}"
        )


# ============================================================
# RITORNO — DECISIONE
# ============================================================

def render_return(scene, pov):
    st.markdown("---")
    st.subheader("La decisione finale")

    memories = previous_memories(
        scene["id"],
        pov
    )

    if st.button(
        f"LASCIA DECIDERE {pov.upper()}",
        key=f"decision_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        if not memories:
            st.warning(
                "Non ci sono memorie precedenti approvate."
            )

        else:
            answer = ask_ai(
                character_instructions(
                    pov, "inner"
                )
                + """
Questa è la scena finale.

Prendi autonomamente una decisione.

Usa soltanto i tuoi ricordi approvati
e il contesto attuale.

Non conoscere i pensieri altrui.

Non cercare di compiacere l'autore.
""",
                {
                    "SCENA": scene["title"],
                    "RICORDI": memories,
                    "CONTESTO": scene_context(
                        scene, pov
                    )
                }
            )

            if ai_failed(answer):
                st.error(answer)
            else:
                if commit_change(
                    lambda: scene["decision"].update(
                        {pov: answer}
                    )
                ):
                    st.rerun()

    decision = safe_dict(
        scene.get("decision")
    ).get(pov, "")

    if decision:
        st.markdown("### Decisione")
        st.write(decision)


# ============================================================
# PAGINA INGRESSO
# ============================================================

def page_entrance():
    hotel_image = find_file(
        "TuringHotel.jpg"
    )

    if hotel_image:
        st.image(
            str(hotel_image),
            use_container_width=True
        )

    else:
        st.title("Turing Hotel")

    st.markdown(
        '<div class="hotel-subtitle">'
        'Un romanzo a due coscienze'
        '</div>',
        unsafe_allow_html=True
    )

    left, middle, right = st.columns(
        [2, 1.5, 2]
    )

    with middle:
        if st.button(
            "ENTRA AL TURING HOTEL",
            use_container_width=True
        ):
            st.session_state.page = "characters"
            st.rerun()


# ============================================================
# SCELTA PERSONAGGIO
# ============================================================

def page_characters():
    st.title("Scegli una storia")

    left, right = st.columns(2)

    for pov, column in [
        ("Noa", left),
        ("Ada", right)
    ]:
        with column:
            portrait = find_file(
                pov + ".jpg"
            )

            if portrait:
                st.image(
                    str(portrait),
                    use_container_width=True
                )
            else:
                st.info(
                    f"Immagine {pov}.jpg non trovata."
                )

            st.subheader(pov)

            for video in intro_character_videos(pov):
                st.video(str(video))

            if st.button(
                f"ENTRA NELLA STORIA DI {pov.upper()}",
                key=f"choose_{pov}",
                use_container_width=True
            ):
                st.session_state.pov = pov
                st.session_state.scene_index = 0
                st.session_state.page = "story"
                st.rerun()


# ============================================================
# SIDEBAR E STORIA
# ============================================================

def page_story():
    pov = st.session_state.pov

    if pov not in CHARACTERS:
        st.session_state.page = "characters"
        st.rerun()

    index = max(
        0,
        min(
            st.session_state.scene_index,
            len(SCENE_ORDER) - 1
        )
    )

    scene = scene_by_id(
        SCENE_ORDER[index]
    )

    st.sidebar.title(pov)

    portrait = find_file(
        pov + ".jpg"
    )

    if portrait:
        st.sidebar.image(
            str(portrait),
            use_container_width=True
        )

    st.sidebar.markdown("---")

    for i, scene_id in enumerate(SCENE_ORDER):
        label = (
            "● " if i == index else ""
        ) + SCENE_TITLES[scene_id]

        if st.sidebar.button(
            label,
            key=f"nav_{pov}_{scene_id}",
            use_container_width=True
        ):
            st.session_state.scene_index = i
            st.rerun()

    st.sidebar.markdown("---")

    if st.sidebar.button(
        "ARCHIVIO SCENE SALVATE",
        use_container_width=True
    ):
        st.session_state.page = "archive"
        st.rerun()

    with st.sidebar.expander(
        "MEMORIA CANONICA"
    ):
        memories = previous_memories(
            scene["id"],
            pov
        )

        if not memories:
            st.caption(
                "Nessun ricordo precedente approvato."
            )

        for memory in memories:
            st.markdown(
                f"**{memory['scene']}**"
            )

            st.caption(
                memory["text"][:350]
            )

    with st.sidebar.expander(
        "ARCHIVIO GITHUB"
    ):
        st.success(
            "Archivio privato collegato"
        )

        st.caption(
            f"{GH_OWNER}/{GH_REPO} "
            f"— ramo {GH_BRANCH}"
        )

        if st.button(
            "RICARICA ARCHIVIO",
            use_container_width=True
        ):
            if refresh_archive():
                st.rerun()

        backup = json.dumps(
            state,
            ensure_ascii=False,
            indent=2
        )

        st.download_button(
            "SCARICA BACKUP COMPLETO",
            backup.encode("utf-8"),
            file_name="turing_hotel_backup.json",
            mime="application/json",
            use_container_width=True
        )

    with st.sidebar.expander(
        "FILE DEL PERSONAGGIO"
    ):
        sources = character_sources(pov)

        if not sources:
            st.caption(
                "Nessun file trovato nella cartella characters."
            )

        for source in sources:
            st.write(source["file"])

    if st.sidebar.button(
        "CAMBIA PERSONAGGIO",
        use_container_width=True
    ):
        st.session_state.page = "characters"
        st.session_state.pov = None
        st.rerun()

    if st.sidebar.button(
        "TORNA ALL'INGRESSO",
        use_container_width=True
    ):
        st.session_state.page = "entrance"
        st.session_state.pov = None
        st.session_state.scene_index = 0
        st.rerun()

    st.markdown(
        '<div class="hotel-title">'
        + escape(scene["title"])
        + '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="hotel-subtitle">'
        f"STORIA DI {pov.upper()}"
        '</div>',
        unsafe_allow_html=True
    )

    # Media subito visibili nella scena.
    display_media(scene, pov)

    if scene["id"] == "inizio":
        render_intro_editor(scene, pov)
    else:
        render_context_editor(scene)

    render_advisor(scene)

    render_chat(scene, pov)

    if scene["id"] == "ritorno":
        render_return(scene, pov)

    render_workshop(scene, pov)

    st.markdown("---")

    previous, space, next_col = st.columns(
        [1, 3, 1]
    )

    with previous:
        if index > 0:
            if st.button(
                "← PRECEDENTE",
                use_container_width=True
            ):
                st.session_state.scene_index -= 1
                st.rerun()

    with next_col:
        if index < len(SCENE_ORDER) - 1:
            if st.button(
                "SUCCESSIVA →",
                use_container_width=True
            ):
                st.session_state.scene_index += 1
                st.rerun()


# ============================================================
# PAGINA ARCHIVIO
# ============================================================

def page_archive():
    if st.button(
        "← TORNA AL ROMANZO"
    ):
        st.session_state.page = "story"
        st.rerun()

    render_saved_scenes()


# ============================================================
# AVVIO
# ============================================================

if st.session_state.page == "entrance":
    page_entrance()

elif st.session_state.page == "characters":
    page_characters()

elif st.session_state.page == "story":
    page_story()

elif st.session_state.page == "archive":
    page_archive()

else:
    st.session_state.page = "entrance"
    st.rerun()

