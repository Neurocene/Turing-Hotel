
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
# OFFICINA DEL ROMANZO — NOA E ADA
# ============================================================

st.set_page_config(
    page_title="Turing Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BASE_DIR = Path(__file__).parent
ASSETS = BASE_DIR / "assets"
CHARACTERS_DIR = BASE_DIR / "characters"
LOCAL_FILE = BASE_DIR / "data_web" / "romanzo_web.json"

ASSETS.mkdir(exist_ok=True)
CHARACTERS_DIR.mkdir(exist_ok=True)

CHARACTERS = ("Noa", "Ada")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}

HOTEL_IMAGE = ASSETS / "TuringHotel.jpg"
NOA_IMAGE = ASSETS / "Noa.jpg"
ADA_IMAGE = ASSETS / "Ada.jpg"


# ============================================================
# SCENE
# ============================================================

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
    "stanza": ["stanza", "camera", "la stanza"],
    "funerale": ["funerale"],
    "matrimonio": ["matrimonio"],
    "reparto_nascite": [
        "repartonascite",
        "reparto_nascite",
        "reparto-nascite",
        "nascite"
    ],
    "ritorno": ["ritorno", "finale"]
}


# ============================================================
# PROLOGHI INDIPENDENTI
# ============================================================

INTRO_CONTEXTS = {
    "Noa": (
        "Noa percorre a piedi il viale che conduce "
        "al Turing Hotel, vicino al mare Adriatico. "
        "Durante il cammino sviluppa un monologo "
        "interiore nel quale osserva il luogo, "
        "riflette sulla propria natura artificiale "
        "e sulle proprie aspettative. "
        "Le sue riflessioni devono nascere dal suo "
        "profilo, dai suoi dati e dalle interazioni. "
        "Non anticipare informazioni sconosciute. "
        "La scena termina con l'incontro con Ada. "
        "Non proseguire nel dialogo successivo."
    ),
    "Ada": (
        "Ada si trova nello studio di suo padre, "
        "il professor Elia, all'interno del "
        "Turing Hotel. "
        "La scena si sviluppa attraverso il dialogo "
        "tra Ada e il Professore. "
        "Le risposte di Ada devono essere autonome, "
        "coerenti con il suo profilo e con quanto "
        "il Professore effettivamente le dice. "
        "Non anticipare eventi successivi. "
        "La scena termina quando Noa arriva "
        "alla reception del Turing Hotel."
    )
}


# ============================================================
# IMPOSTAZIONI
# ============================================================

def setting(name, default=""):
    try:
        value = st.secrets.get(name)
        if value is not None and value != "":
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)


OPENAI_KEY = setting("OPENAI_API_KEY")
OPENAI_MODEL = setting("OPENAI_MODEL", "gpt-5.6")

GH_TOKEN = setting("GITHUB_TOKEN")
GH_OWNER = setting("GITHUB_OWNER")
GH_REPO = setting("GITHUB_REPO")
GH_BRANCH = setting("GITHUB_BRANCH", "main")

REMOTE_FILE = "romanzo_web.json"

client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def safe_list(value):
    return value if isinstance(value, list) else []


def normalize(value):
    return re.sub(
        r"[\s._-]+",
        "",
        str(value).lower().strip()
    )


def ai_error(value):
    return (
        not isinstance(value, str)
        or not value.strip()
        or value.startswith("Errore OpenAI:")
        or value.startswith("OPENAI_API_KEY non configurata.")
    )


def ask_ai(instructions, data):
    if not client:
        return "OPENAI_API_KEY non configurata."

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=json.dumps(
                data,
                ensure_ascii=False
            )
        )
        return response.output_text.strip()

    except Exception as exc:
        return f"Errore OpenAI: {exc}"


def clean_ai(text):
    text = str(text or "").strip()
    text = re.sub(
        r"^```(?:json|markdown|text)?\s*",
        "",
        text,
        flags=re.I
    )
    return re.sub(r"\s*```$", "", text).strip()


def parse_ai_json(text):
    try:
        return json.loads(clean_ai(text))
    except (ValueError, TypeError):
        return None


# ============================================================
# INTERFACCIA — CONTRASTO CORRETTO
# ============================================================

st.markdown("""
<style>

:root {
    --hotel-dark: #080a0c;
    --hotel-panel: #111518;
    --hotel-button: #1b2227;
    --hotel-light: #ffffff;
    --hotel-gold: #b79c72;
}

.stApp {
    background-color: #080a0c !important;
    color: #ffffff !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

[data-testid="stSidebar"] {
    background: #101418 !important;
    color: #ffffff !important;
    border-right: 1px solid #272d31;
}

h1, h2, h3, h4 {
    font-family: Georgia, serif;
}

/* Testo nei pannelli scuri */

.stApp .stMarkdown p,
.stApp .stMarkdown h1,
.stApp .stMarkdown h2,
.stApp .stMarkdown h3,
.stApp .stMarkdown h4,
.stApp .stMarkdown li {
    color: #ffffff;
}

/* Pulsanti */

.stApp .stButton > button,
.stApp .stFormSubmitButton > button,
.stApp .stDownloadButton > button {
    background-color: #1b2227 !important;
    color: #ffffff !important;
    border: 1px solid #68747d !important;
    border-radius: 4px !important;
    min-height: 42px;
    font-weight: 600 !important;
}

.stApp .stButton > button *,
.stApp .stFormSubmitButton > button *,
.stApp .stDownloadButton > button * {
    color: #ffffff !important;
}

.stApp .stButton > button:hover,
.stApp .stFormSubmitButton > button:hover,
.stApp .stDownloadButton > button:hover {
    background-color: #303b43 !important;
    color: #ffffff !important;
    border-color: #b79c72 !important;
}

.stApp button:disabled {
    opacity: .45 !important;
}

/* Campi di scrittura */

.stApp textarea,
.stApp input:not([type="checkbox"]):not([type="radio"]) {
    background-color: #ffffff !important;
    color: #111111 !important;
    -webkit-text-fill-color: #111111 !important;
}

.stApp textarea::placeholder,
.stApp input::placeholder {
    color: #666666 !important;
    -webkit-text-fill-color: #666666 !important;
}

/* Selectbox */

.stApp [data-baseweb="select"] > div {
    background-color: #ffffff !important;
    color: #111111 !important;
}

.stApp [data-baseweb="select"] span,
.stApp [data-baseweb="select"] input {
    color: #111111 !important;
}

[data-baseweb="popover"] [role="listbox"] {
    background: #ffffff !important;
}

[data-baseweb="popover"] [role="option"],
[data-baseweb="popover"] [role="option"] * {
    color: #111111 !important;
}

[data-baseweb="popover"] [role="option"] {
    background: #ffffff !important;
}

[data-baseweb="popover"] [role="option"]:hover {
    background: #e4e4e4 !important;
}

/* Tabs */

.stApp button[data-baseweb="tab"] {
    background: #171d22 !important;
    color: #ffffff !important;
}

.stApp button[data-baseweb="tab"] * {
    color: inherit !important;
}

.stApp button[data-baseweb="tab"][aria-selected="true"] {
    background: #ede8df !important;
    color: #111111 !important;
}

/* Pannelli */

.stApp [data-testid="stExpander"] {
    background: #111518;
    color: #ffffff;
}

/* La textarea ha fondo chiaro e testo nero */

.stApp [data-testid="stTextArea"] textarea {
    color: #111111 !important;
}

/* Blocchi narrativi */

.scene-title {
    font-family: Georgia, serif;
    font-size: 3rem;
    line-height: 1.1;
    color: #ffffff;
    margin-bottom: 12px;
}

.pov-label {
    font-size: .8rem;
    letter-spacing: .15em;
    color: #b79c72;
    margin-bottom: 16px;
}

.story-text {
    background: #111518;
    border-left: 3px solid #b79c72;
    color: #ffffff;
    padding: 22px;
    font-family: Georgia, serif;
    font-size: 1.05rem;
    line-height: 1.8;
    white-space: pre-wrap;
}

.chat-text {
    background: #151b20;
    color: #ffffff;
    border-left: 2px solid #66747c;
    padding: 13px 15px;
    margin: 8px 0;
    white-space: pre-wrap;
}

.inner-text {
    background: #211b1a;
    color: #ffffff;
    border-left: 2px solid #b09470;
    padding: 13px 15px;
    margin: 8px 0;
    white-space: pre-wrap;
}

.scene-status {
    color: #b79c72;
    font-size: .85rem;
}

/* Codice su fondo scuro */

.stApp pre,
.stApp pre code {
    color: #ffffff !important;
}

/* Accessibilità */

.stApp button:focus-visible,
.stApp textarea:focus-visible,
.stApp input:focus-visible {
    outline: 2px solid #b79c72 !important;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# ARCHIVIO GITHUB PRIVATO
# ============================================================

class ArchiveError(Exception):
    pass


def archive_configured():
    return all([
        GH_TOKEN,
        GH_OWNER,
        GH_REPO,
        GH_BRANCH
    ])


def github_url(path):
    owner = quote(GH_OWNER, safe="")
    repo = quote(GH_REPO, safe="")
    encoded_path = quote(path, safe="/")

    return (
        "https://api.github.com/repos/"
        f"{owner}/{repo}/contents/{encoded_path}"
    )


def github_request(method, path, payload=None):
    if not archive_configured():
        raise ArchiveError(
            "Configura i Secrets GitHub."
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
            "Repository, file o ramo GitHub non trovato."
        )

    if response.status_code in (409, 422):
        raise ArchiveError(
            "Conflitto di versione. Ricarica "
            "l'archivio prima di salvare."
        )

    if not response.ok:
        raise ArchiveError(
            f"Errore GitHub HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    return response.json()


def read_remote(path):
    result = github_request("GET", path)

    if result is None:
        return None, None

    encoded = result.get("content")
    sha = result.get("sha")

    if not encoded or not sha:
        raise ArchiveError(
            "Risposta GitHub incompleta."
        )

    try:
        content = base64.b64decode(
            encoded
        ).decode("utf-8")
    except Exception as exc:
        raise ArchiveError(
            "Impossibile leggere il file remoto."
        ) from exc

    return content, sha


def write_remote(path, content, expected_sha):
    _, current_sha = read_remote(path)

    if current_sha != expected_sha:
        raise ArchiveError(
            "Il file è cambiato in un'altra sessione. "
            "Il salvataggio è stato bloccato."
        )

    payload = {
        "message": (
            "Turing Hotel — salvataggio "
            + now()
        ),
        "content": base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii"),
        "branch": GH_BRANCH
    }

    if expected_sha:
        payload["sha"] = expected_sha

    response = github_request(
        "PUT",
        path,
        payload
    )

    new_sha = safe_dict(
        response.get("content")
    ).get("sha")

    if not new_sha:
        raise ArchiveError(
            "GitHub non ha confermato il salvataggio."
        )

    return new_sha


# ============================================================
# STRUTTURA NARRATIVA
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


def empty_scene(sid):
    scene = {
        "id": sid,
        "title": SCENE_TITLES[sid],
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

    if sid == "inizio":
        scene["intro_contexts"] = copy.deepcopy(
            INTRO_CONTEXTS
        )
        scene["author_context"] = (
            "Due inizi indipendenti: "
            "Noa sul viale, Ada nello studio del Professore."
        )

    if sid == "stanza":
        scene["author_context"] = (
            "Ada accompagna Noa nella sua stanza "
            "al Turing Hotel. "
            "Nel percorso di Ada emerge il loro dialogo. "
            "Nel percorso di Noa, dopo l'incontro, "
            "Noa riflette sola davanti allo specchio. "
            "Non anticipare la scena successiva."
        )
        scene["approved_context"] = scene["author_context"]

    if sid == "ritorno":
        scene["decision"] = {
            "Noa": "",
            "Ada": ""
        }

    return scene


DEFAULT_STATE = {
    "world": (
        "Il Turing Hotel è un antico albergo "
        "sul mare Adriatico."
    ),
    "agents": {
        "Noa": {
            "profile": (
                "Noa è un agente artificiale relazionale. "
                "Sa di essere artificiale. "
                "È intelligente, osservatrice, ironica "
                "e capace di seduzione. "
                "È progettata per comprendere "
                "gli esseri umani e creare empatia."
            ),
            "memory": ""
        },
        "Ada": {
            "profile": (
                "Ada è la figlia del professor Elia. "
                "È cresciuta nel Turing Hotel. "
                "È intelligente, pratica, riservata "
                "e osservatrice."
            ),
            "memory": ""
        }
    },
    "scenes": [
        empty_scene(sid)
        for sid in SCENE_ORDER
    ]
}


def find_existing_scene(scenes, sid):
    aliases = {
        normalize(value)
        for value in SCENE_ALIASES[sid]
    }
    aliases.add(normalize(sid))

    for scene in safe_list(scenes):
        if not isinstance(scene, dict):
            continue

        if (
            normalize(scene.get("id", "")) in aliases
            or normalize(scene.get("title", "")) in aliases
        ):
            return scene

    return None


def migrate_state(old):
    fresh = copy.deepcopy(DEFAULT_STATE)
    old = safe_dict(old)

    if isinstance(old.get("world"), str):
        fresh["world"] = old["world"]

    old_agents = safe_dict(
        old.get("agents")
    )

    for pov in CHARACTERS:
        source = safe_dict(
            old_agents.get(pov)
        )

        for key in ("profile", "memory"):
            if isinstance(source.get(key), str):
                fresh["agents"][pov][key] = source[key]

    for new_scene in fresh["scenes"]:
        previous = find_existing_scene(
            old.get("scenes"),
            new_scene["id"]
        )

        if not previous:
            continue

        for field in (
            "author_context",
            "story_draft",
            "story_feedback",
            "approved_context"
        ):
            if isinstance(previous.get(field), str):
                new_scene[field] = previous[field]

        for field in (
            "advisor_messages",
            "shared_dialogue"
        ):
            new_scene[field] = copy.deepcopy(
                safe_list(previous.get(field))
            )

        if new_scene["id"] == "inizio":
            old_contexts = safe_dict(
                previous.get("intro_contexts")
            )

            for pov in CHARACTERS:
                old_text = old_contexts.get(pov)
                if isinstance(old_text, str):
                    new_scene["intro_contexts"][pov] = old_text

        for pov in CHARACTERS:
            new_scene["messages"][pov] = copy.deepcopy(
                safe_list(
                    safe_dict(
                        previous.get("messages")
                    ).get(pov)
                )
            )

            old_diary = str(
                safe_dict(
                    previous.get("diary")
                ).get(pov, "")
            )

            new_scene["diary"][pov] = old_diary

            old_record = safe_dict(
                safe_dict(
                    previous.get("narrative")
                ).get(pov)
            )

            target = new_scene["narrative"][pov]

            for key in target:
                if key in old_record:
                    target[key] = copy.deepcopy(
                        old_record[key]
                    )

            if not old_record and old_diary.strip():
                target["draft"] = old_diary
                target["status"] = "bozza_legacy"

            target["visual"] = {
                **empty_narrative()["visual"],
                **safe_dict(target.get("visual"))
            }

        if new_scene["id"] == "ritorno":
            decisions = safe_dict(
                previous.get("decision")
            )

            for pov in CHARACTERS:
                new_scene["decision"][pov] = str(
                    decisions.get(pov, "")
                )

    return fresh


# ============================================================
# CARICAMENTO REMOTO
# ============================================================

def load_archive():
    raw, sha = read_remote(REMOTE_FILE)

    if raw is None:
        return None, None

    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ArchiveError(
            "Il JSON remoto non è valido."
        ) from exc

    return migrate_state(data), sha


def initialize_session():
    if "state" in st.session_state:
        return

    if not archive_configured():
        st.error(
            "Configura prima il repository GitHub "
            "nei Secrets di Streamlit."
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
        else copy.deepcopy(DEFAULT_STATE)
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
            "Archivio non inizializzato."
        )

    content = json.dumps(
        state,
        ensure_ascii=False,
        indent=2
    )

    new_sha = write_remote(
        REMOTE_FILE,
        content,
        st.session_state.archive_sha
    )

    st.session_state.archive_sha = new_sha


def commit_change(change):
    snapshot = copy.deepcopy(state)

    try:
        change()
        save_state()
        return True

    except Exception as exc:
        state.clear()
        state.update(snapshot)

        st.error(
            f"Salvataggio non riuscito: {exc}"
        )
        return False


def refresh_archive():
    try:
        loaded, sha = load_archive()

        if loaded is None:
            st.error("Archivio remoto mancante.")
            return False

        state.clear()
        state.update(loaded)

        st.session_state.archive_sha = sha
        return True

    except ArchiveError as exc:
        st.error(str(exc))
        return False


# ============================================================
# PRIMA INIZIALIZZAZIONE
# ============================================================

def initialize_archive_panel():
    if st.session_state.archive_ready:
        return

    st.warning(
        "Il file romanzo_web.json non è ancora "
        "presente nel repository privato."
    )

    use_local = False

    if LOCAL_FILE.exists():
        st.info(
            "È stato trovato un archivio locale precedente."
        )

        use_local = st.checkbox(
            "Importa il vecchio archivio locale"
        )

    confirmed = st.checkbox(
        "Confermo l'inizializzazione "
        "dell'archivio privato."
    )

    if st.button(
        "INIZIALIZZA ARCHIVIO",
        disabled=not confirmed,
        use_container_width=True
    ):
        try:
            if use_local:
                old = json.loads(
                    LOCAL_FILE.read_text(
                        encoding="utf-8"
                    )
                )
                selected = migrate_state(old)
            else:
                selected = copy.deepcopy(
                    DEFAULT_STATE
                )

            content = json.dumps(
                selected,
                ensure_ascii=False,
                indent=2
            )

            sha = write_remote(
                REMOTE_FILE,
                content,
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


initialize_archive_panel()


# ============================================================
# FONTI E DOCUMENTI
# ============================================================

def read_reference(path):
    try:
        if path.suffix.lower() in (".txt", ".md"):
            return path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))

            return "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )
    except Exception:
        pass

    return ""


def turing_context():
    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        if path.suffix.lower() not in (".txt", ".md"):
            continue

        if normalize(path.stem) == "contestoturinghotel":
            return read_reference(path)

    root = BASE_DIR / "TURING_HOTEL_CONTESTO_AGENTE.md"

    if root.exists():
        return read_reference(root)

    return ""


def character_sources(pov):
    result = []
    used = 0

    for path in sorted(CHARACTERS_DIR.iterdir()):
        if not path.is_file():
            continue

        if path.suffix.lower() not in (
            ".txt", ".md", ".pdf"
        ):
            continue

        name = path.name.lower()

        if not (
            name.startswith(pov.lower())
            or name.startswith("shared")
        ):
            continue

        text = read_reference(path)
        remaining = 80000 - used

        if remaining <= 0:
            break

        excerpt = text[:remaining]

        if excerpt:
            result.append({
                "file": path.name,
                "contenuto": excerpt
            })
            used += len(excerpt)

    return result


def writer_books():
    result = []

    for path in sorted(ASSETS.iterdir()):
        if not path.is_file():
            continue

        if path.suffix.lower() not in (
            ".txt", ".md", ".pdf"
        ):
            continue

        if not normalize(path.stem).startswith(
            "libriagenti"
        ):
            continue

        content = read_reference(path)

        if content:
            result.append({
                "file": path.name,
                "testo": content[:20000]
            })

    return result


# ============================================================
# MEDIA SCENE
# ============================================================

def scene_media(sid, pov, kind):
    results = []

    aliases = sorted(
        {
            normalize(value)
            for value in SCENE_ALIASES[sid]
        },
        key=len,
        reverse=True
    )

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        suffix = path.suffix.lower()

        if kind == "video" and suffix not in VIDEO_EXT:
            continue

        if kind != "video" and suffix not in IMAGE_EXT:
            continue

        name = normalize(path.stem)

        for alias in aliases:
            if not name.startswith(alias):
                continue

            remainder = name[len(alias):]
            character = pov.lower()

            if kind == "cover":
                if remainder == character:
                    results.append((0, path))
                elif remainder == "":
                    results.append((1, path))

            elif remainder.isdigit():
                results.append(
                    (int(remainder), path)
                )

            elif remainder.startswith(character):
                number = remainder[len(character):]

                if number.isdigit():
                    results.append(
                        (int(number), path)
                    )

            break

    results.sort(
        key=lambda item: (
            item[0],
            item[1].name.lower()
        )
    )

    return [
        path
        for _, path in results
    ]


def intro_videos(pov):
    results = []

    for path in ASSETS.iterdir():
        if path.suffix.lower() not in VIDEO_EXT:
            continue

        compact = normalize(path.stem)

        if re.match(
            rf"^{pov.lower()}video\d+$",
            compact
        ):
            results.append(path)

    return sorted(
        results,
        key=lambda p: p.name
    )


@st.dialog("Immagine", width="large")
def image_dialog(path):
    st.image(
        path,
        use_container_width=True
    )


def render_media(scene, pov, kind):
    files = scene_media(
        scene["id"], pov, kind
    )

    if not files:
        return

    if kind == "video":
        st.subheader("Video della scena")

        for path in files:
            st.video(str(path))

    else:
        st.subheader("Immagini della scena")

        for start in range(0, len(files), 3):
            cols = st.columns(3)

            for i, path in enumerate(
                files[start:start + 3]
            ):
                with cols[i]:
                    st.image(
                        str(path),
                        use_container_width=True
                    )

                    if st.button(
                        "INGRANDISCI",
                        key=(
                            f"zoom_{scene['id']}_"
                            f"{pov}_{path.name}"
                        )
                    ):
                        image_dialog(str(path))


# ============================================================
# SCENE E MEMORIE
# ============================================================

def scene_by_id(sid):
    return next(
        scene
        for scene in state["scenes"]
        if scene["id"] == sid
    )


def record_for(scene, pov):
    return scene["narrative"][pov]


def scene_context(scene, pov):
    if scene["id"] == "inizio":
        contexts = safe_dict(
            scene.get("intro_contexts")
        )

        return contexts.get(
            pov,
            INTRO_CONTEXTS[pov]
        )

    return scene.get(
        "approved_context", ""
    )


def previous_memories(scene_id, pov):
    result = []

    for sid in SCENE_ORDER:
        if sid == scene_id:
            break

        scene = scene_by_id(sid)

        approved = record_for(
            scene, pov
        ).get("approved", "")

        if approved.strip():
            result.append({
                "scena": scene["title"],
                "ricordo": approved
            })

    return result


def all_previous_memories(scene_id):
    return {
        pov: previous_memories(scene_id, pov)
        for pov in CHARACTERS
    }


def later_approved(scene_id, pov):
    index = SCENE_ORDER.index(scene_id)
    result = []

    for sid in SCENE_ORDER[index + 1:]:
        scene = scene_by_id(sid)

        if record_for(
            scene, pov
        )["approved"].strip():
            result.append(scene["title"])

    return result


# ============================================================
# CREATORE DELLA SCENA
# ============================================================

def create_context(scene):
    return ask_ai(
        """
Sei il CREATORE DELLA SCENA di Turing Hotel.

Trasforma le indicazioni dell'autore in un
contesto narrativo oggettivo.

Rispetta il canone del Turing Hotel.

Definisci:
- luogo;
- momento;
- atmosfera;
- oggetti;
- persone;
- fatti osservabili;
- circostanze.

Non decidere i pensieri, le emozioni
o le reazioni di Noa e Ada.

Non aggiungere eventi fondamentali.

Restituisci soltanto il contesto.
""",
        {
            "CANONE": turing_context(),
            "SCENA": scene["title"],
            "INDICAZIONI": scene["author_context"],
            "BOZZA": scene["story_draft"],
            "CORREZIONI": scene["story_feedback"]
        }
    )


def refine_context(scene):
    return ask_ai(
        """
Sei l'AGENTE SCRITTORE.

Migliora la qualità narrativa del contesto:
ritmo, immagini, precisione, atmosfera,
fluidità e tensione.

Non cambiare i fatti.
Non decidere le reazioni di Noa e Ada.

Usa LIBRIAGENTI come riferimenti tecnici.
Non copiarli.

Restituisci soltanto il contesto rifinito.
""",
        {
            "SCENA": scene["title"],
            "CONTESTO": scene["story_draft"],
            "CANONE": turing_context(),
            "LIBRIAGENTI": writer_books()
        }
    )


# ============================================================
# CONSULENTE NARRATIVO
# ============================================================

def ask_advisor(scene):
    return ask_ai(
        """
Sei il CONSULENTE NARRATIVO di Turing Hotel.

Parli con l'autore.
Non interpreti Noa e Ada.

Puoi individuare problemi di coerenza,
suggerire collegamenti, alternative,
tensioni e sviluppi narrativi.

Quando presenti più alternative,
DEVI indicare quale preferisci e perché.

Motiva il giudizio.
Segnala i rischi.
Spiega quando sceglieresti l'altra proposta.

Distingui sempre fatti canonici
e ipotesi dell'autore.

Non modificare nulla autonomamente.
Rispondi in italiano.
""",
        {
            "CANONE": turing_context(),
            "SCENA": scene["title"],
            "CONTESTO": scene["approved_context"],
            "BOZZA": scene["story_draft"],
            "RICORDI": all_previous_memories(
                scene["id"]
            ),
            "CONVERSAZIONE": scene["advisor_messages"]
        }
    )


# ============================================================
# PERSONAGGI NOA E ADA
# ============================================================

def character_prompt(pov, mode):
    agent = state["agents"][pov]

    prompt = f"""
SEI {pov}, personaggio di Turing Hotel.

Non sei un assistente.
Interpreti soltanto {pov}.

MONDO:
{state["world"]}

PROFILO:
{agent["profile"]}

MEMORIA GENERALE:
{agent["memory"]}

MEMORIA CANONICA:
Ricordi soltanto le tue versioni narrative
APPROVATE delle scene precedenti.

Non hai accesso ai pensieri e ai ricordi
privati dell'altro personaggio.

Puoi dubitare, mentire, sospettare,
fraintendere, desiderare e ricordare male.

Non trasformare sospetti in certezze.

La tua reazione deve nascere
dalla tua personalità e dalle tue esperienze.

Non scrivere battute altrui.
Non restituire JSON.
Scrivi in italiano naturale.
"""

    if mode == "inner":
        prompt += """
Stai pensando tra te e te.

Prosegui il tuo dialogo interiore.
Non fingere un interlocutore esterno.
"""
    else:
        prompt += """
Sei presente nella scena.
Rispondi naturalmente al tuo interlocutore.
"""

    return prompt


def answer_character(scene, pov, mode):
    instructions = character_prompt(
        pov, mode
    )

    if scene["id"] == "inizio":
        if pov == "Noa":
            instructions += """
Sei nel prologo.

Cammini lungo il viale che porta
al Turing Hotel.

La modalità è monologo interiore.

Non anticipare l'incontro con Ada
finché la scena non arriva alla conclusione.
"""
        else:
            instructions += """
Sei nel prologo.

Ti trovi nello studio del Professore.
Il Professore è tuo padre, Elia.

Rispondi alle sue battute.
Non inventare le sue risposte.

Non anticipare l'arrivo di Noa.
"""

    return ask_ai(
        instructions,
        {
            "SCENA": scene["title"],
            "CONTESTO": scene_context(scene, pov),
            "CANONE": turing_context(),
            "FONTI": character_sources(pov),
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "MESSAGGI": scene["messages"][pov],
            "DIALOGO_CONDIVISO":
                scene["shared_dialogue"],
            "MODALITA": mode
        }
    )


# ============================================================
# GO ALONE
# ============================================================

def go_alone(scene, start="Ada"):
    if scene["id"] == "inizio":
        return (
            "GO ALONE è disattivato nel prologo, "
            "che ha una struttura specifica."
        )

    other = "Noa" if start == "Ada" else "Ada"

    for speaker in [
        start, other, start, other
    ]:
        counterpart = (
            "Noa" if speaker == "Ada" else "Ada"
        )

        raw = ask_ai(
            character_prompt(speaker, "external")
            + f"""
MODALITÀ GO ALONE.

Parli con {counterpart}.

Scrivi soltanto la tua prossima battuta
pronunciata ad alta voce.

Non interpretare l'altro personaggio.
Non creare eventi irreversibili.
""",
            {
                "SCENA": scene["title"],
                "CONTESTO": scene_context(
                    scene, speaker
                ),
                "FONTI": character_sources(speaker),
                "RICORDI": previous_memories(
                    scene["id"], speaker
                ),
                "DIALOGO": scene["shared_dialogue"][-24:]
            }
        )

        if ai_error(raw):
            return raw

        turn = {
            "speaker": speaker,
            "text": clean_ai(raw),
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
# TRASCRIZIONE
# ============================================================

def transcript(scene, pov):
    lines = [
        f"TURING HOTEL — {scene['title']}",
        f"Prospettiva di {pov}",
        "",
        "TRASCRIZIONE",
        ""
    ]

    for message in scene["messages"][pov]:
        if not isinstance(message, dict):
            continue

        speaker = message.get(
            "speaker", "?"
        )

        if message.get("kind") == "inner":
            speaker += " (pensiero)"

        lines.append(
            f"{speaker}: "
            f"{message.get('text', '')}"
        )
        lines.append("")

    return "\n".join(lines)


# ============================================================
# AGENTE SCRITTORE — VERSIONI A E B
# ============================================================

def write_narrative(scene, pov, version, feedback):
    if version == "A":
        style = (
            "Prosa essenziale, concreta e densa. "
            "Dialoghi, gesti, silenzi, precisione "
            "e sottotesto."
        )
    else:
        style = (
            "Prosa introspettiva e sensoriale. "
            "Profondità emotiva, immagini evocative "
            "e contraddizioni interiori."
        )

    intro_rule = ""

    if scene["id"] == "inizio":
        if pov == "Noa":
            intro_rule = (
                "Racconta il monologo di Noa mentre "
                "cammina lungo il viale. "
                "La scena termina con l'incontro con Ada. "
                "Non inventare un dialogo successivo."
            )
        else:
            intro_rule = (
                "Racconta il dialogo fra Ada e il "
                "Professore nello studio. "
                "La scena termina con l'arrivo "
                "di Noa alla reception."
            )

    return ask_ai(
        f"""
Sei l'AGENTE SCRITTORE di Turing Hotel.

Trasforma le interazioni in un vero
brano letterario compiuto.

NARRATORE: {pov}.
SCRIVI IN PRIMA PERSONA SINGOLARE.
USA IL TEMPO PRESENTE.

Non scrivere un riassunto.

Conserva gli eventi e i dialoghi significativi.
Non inventare svolte fondamentali.
Non attribuire al narratore informazioni
che non conosce.

Distingui i fatti dalle interpretazioni.

Rispetta le memorie approvate precedenti.

INDIRIZZO STILISTICO:
{style}

REGOLE SPECIFICHE:
{intro_rule}

Usa LIBRIAGENTI soltanto come riferimenti
di tecnica narrativa, senza copiare.

Applica le correzioni dell'autore.

Restituisci soltanto il racconto.
""",
        {
            "PERSONAGGIO": pov,
            "SCENA": scene["title"],
            "CONTESTO": scene_context(scene, pov),
            "TRASCRIZIONE": transcript(scene, pov),
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "PROFILO": state["agents"][pov]["profile"],
            "FONTI": character_sources(pov),
            "LIBRIAGENTI": writer_books(),
            "CORREZIONI": feedback
        }
    )


# ============================================================
# AGENTE CRITICO — PREFERENZA MOTIVATA
# ============================================================

def critic(scene, pov):
    record = record_for(scene, pov)

    raw = ask_ai(
        """
Sei il CRITICO LETTERARIO di Turing Hotel.

Confronta le versioni A e B della stessa scena.

Valuta:
1. Qualità letteraria.
2. Fedeltà agli eventi.
3. Coerenza psicologica.
4. Originalità della voce.
5. Efficacia drammatica.
6. Continuità narrativa.
7. Idoneità all'inserimento nel romanzo.

DEVI ESPRIMERE UNA PREFERENZA:
A oppure B.

Non dire semplicemente che entrambe
sono valide.

Spiega:
- quale versione preferisci;
- perché;
- quali elementi sono più efficaci;
- quali riserve hai;
- quando sceglieresti l'altra.

Se entrambe sono deboli, segnalalo.

Non approvare automaticamente nulla.

Restituisci soltanto JSON valido:
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
            "PERSONAGGIO": pov,
            "TRASCRIZIONE": transcript(scene, pov),
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "VERSIONE_A": record["A"],
            "VERSIONE_B": record["B"]
        }
    )

    if ai_error(raw):
        return None, raw

    result = parse_ai_json(raw)

    if not isinstance(result, dict):
        return None, "Giudizio critico non valido."

    winner = str(
        result.get("preferenza", "")
    ).upper()

    if winner not in ("A", "B"):
        return None, "Preferenza A/B mancante."

    review = (
        f"**Preferisco la versione {winner}.**\n\n"
        f"{result.get('motivazione', '')}\n\n"
        f"**Riserve:** {result.get('riserve', '')}\n\n"
        f"**Quando sceglierei l'altra:** "
        f"{result.get('alternativa', '')}\n\n"
        f"**Pronta per l'approvazione:** "
        + (
            "Sì"
            if result.get("pronta") is True
            else "Consiglio una revisione"
        )
    )

    return winner, review


# ============================================================
# ESPORTAZIONI
# ============================================================

def make_docx(title, text):
    document = Document()
    document.add_heading(title, 0)

    for paragraph in text.split("\n"):
        document.add_paragraph(paragraph)

    output = BytesIO()
    document.save(output)

    return output.getvalue()


def downloads(scene, pov, text, suffix):
    if not text.strip():
        st.caption("Testo non disponibile.")
        return

    base = (
        f"{scene['id']}_{pov.lower()}_{suffix}"
    )

    cols = st.columns(3)

    with cols[0]:
        st.download_button(
            "TXT",
            data=text.encode("utf-8"),
            file_name=base + ".txt",
            mime="text/plain",
            key="txt_" + base,
            use_container_width=True
        )

    with cols[1]:
        st.download_button(
            "MARKDOWN",
            data=text.encode("utf-8"),
            file_name=base + ".md",
            mime="text/markdown",
            key="md_" + base,
            use_container_width=True
        )

    with cols[2]:
        st.download_button(
            "WORD",
            data=make_docx(
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
# OFFICINA VISIVA — NANO BANANA E VIDEO
# ============================================================

def generate_visual_prompts(scene, pov, count):
    record = record_for(scene, pov)
    approved = record.get("approved", "")

    if not approved.strip():
        return None, "Scena non approvata."

    raw = ask_ai(
        f"""
Sei il DIRETTORE DELLA FOTOGRAFIA
di Turing Hotel.

Trasforma il racconto APPROVATO
in {count} inquadrature coerenti.

Usa soltanto:
- testo letterario approvato;
- contesto visivo canonico;
- identità dei personaggi.

Non introdurre eventi nuovi.

Prima costruisci una BIBBIA VISIVA:
luoghi, personaggi, abiti, luce,
atmosfera, oggetti e continuità.

I dettagli non specificati non devono
diventare arbitrariamente canonici.

Per ogni inquadratura genera:

1. titolo;
2. momento narrativo;
3. prompt Nano Banana;
4. prompt video;
5. vincoli di continuità;
6. riferimenti fotografici.

Nei prompt immagine richiedi
fotorealismo cinematografico
e l'uso di Noa.jpg o Ada.jpg
quando il personaggio appare.

Nei prompt video descrivi
movimento di macchina,
azione visibile, luce e
durata suggerita.

Non rappresentare letteralmente
pensieri astratti inventando azioni.

I prompt devono essere utilizzabili
separatamente, ma coerenti fra loro.

Restituisci soltanto JSON valido:

{
 "bible": "bibbia visiva della scena",
 "shots": [
   {
     "title": "titolo",
     "moment": "momento",
     "image_prompt": "prompt Nano Banana",
     "video_prompt": "prompt video",
     "continuity": "continuità",
     "reference": "riferimenti"
   }
 ]
}
""",
        {
            "SCENA": scene["title"],
            "POV": pov,
            "RACCONTO_APPROVATO": approved,
            "CONTESTO_CANONICO": turing_context(),
            "FOTO_PERSONAGGI": [
                "assets/Noa.jpg",
                "assets/Ada.jpg"
            ]
        }
    )

    if ai_error(raw):
        return None, raw

    result = parse_ai_json(raw)

    if not isinstance(result, dict):
        return None, "Formato dei prompt non valido."

    if not isinstance(
        result.get("bible"), str
    ):
        return None, "Bibbia visiva mancante."

    shots = result.get("shots")

    if not isinstance(shots, list) or not shots:
        return None, "Inquadrature mancanti."

    fields = (
        "title", "moment", "image_prompt",
        "video_prompt", "continuity", "reference"
    )

    for shot in shots:
        if not isinstance(shot, dict):
            return None, "Inquadratura non valida."

        if not all(
            isinstance(shot.get(field), str)
            for field in fields
        ):
            return None, "Campi prompt incompleti."

    return result, ""


def visual_as_text(visual):
    lines = [
        "TURING HOTEL — OFFICINA VISIVA",
        "",
        "BIBBIA VISIVA",
        visual.get("bible", ""),
        ""
    ]

    for i, shot in enumerate(
        visual.get("prompts", []), 1
    ):
        lines.extend([
            f"INQUADRATURA {i}",
            shot.get("title", ""),
            "",
            "MOMENTO",
            shot.get("moment", ""),
            "",
            "NANO BANANA",
            shot.get("image_prompt", ""),
            "",
            "VIDEO",
            shot.get("video_prompt", ""),
            "",
            "CONTINUITÀ",
            shot.get("continuity", ""),
            "",
            "RIFERIMENTI",
            shot.get("reference", ""),
            "",
            "---",
            ""
        ])

    return "\n".join(lines)


def render_visual_workshop(scene, pov):
    record = record_for(scene, pov)
    approved = record.get("approved", "")

    st.markdown("---")
    st.subheader("Officina visiva")

    if not approved.strip():
        st.info(
            "Approva prima il racconto "
            "per generare i prompt visivi."
        )
        return

    count = st.slider(
        "Numero di inquadrature",
        min_value=2,
        max_value=12,
        value=6,
        key=f"shots_{scene['id']}_{pov}"
    )

    if st.button(
        "GENERA PROMPT NANO BANANA + VIDEO",
        key=f"generate_visual_{scene['id']}_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        with st.spinner(
            "Creazione della sequenza visiva..."
        ):
            result, error = generate_visual_prompts(
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
                        record.get("approved_at", "")
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

    if (
        visual.get("source_approved_at")
        != record.get("approved_at")
    ):
        st.warning(
            "I prompt si riferiscono a una "
            "versione precedente. Rigenerali."
        )
        return

    with st.expander(
        "BIBBIA VISIVA",
        expanded=True
    ):
        st.write(
            visual.get("bible", "")
        )

    for i, shot in enumerate(prompts, 1):
        with st.expander(
            f"{i:02d} — {shot.get('title', '')}"
        ):
            st.markdown("**Momento narrativo**")
            st.write(shot.get("moment", ""))

            st.markdown("**Prompt Nano Banana**")
            st.code(
                shot.get("image_prompt", ""),
                language=None
            )

            st.markdown("**Prompt video**")
            st.code(
                shot.get("video_prompt", ""),
                language=None
            )

            st.markdown("**Continuità**")
            st.write(shot.get("continuity", ""))

            st.markdown("**Riferimenti**")
            st.write(shot.get("reference", ""))

    downloads(
        scene,
        pov,
        visual_as_text(visual),
        "prompt_visivi"
    )


# ============================================================
# EDITOR PROLOGHI
# ============================================================

def render_intro_editor(scene, pov):
    st.subheader(f"Prologo di {pov}")

    if pov == "Noa":
        st.caption(
            "Monologo lungo il viale. "
            "La scena finisce con l'incontro con Ada."
        )
    else:
        st.caption(
            "Dialogo con il Professore nello studio. "
            "La scena finisce con l'arrivo "
            "di Noa alla reception."
        )

    contexts = safe_dict(
        scene.get("intro_contexts")
    )

    current = contexts.get(
        pov,
        INTRO_CONTEXTS[pov]
    )

    edited = st.text_area(
        "Contesto iniziale",
        value=current,
        height=190,
        key=f"intro_editor_{pov}"
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
                "Contesto iniziale salvato su GitHub."
            )


# ============================================================
# EDITOR CONTESTO SCENE STANDARD
# ============================================================

def render_context_editor(scene):
    with st.expander("CREATORE DELLA SCENA"):
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
            temporary_scene = copy.deepcopy(scene)
            temporary_scene["author_context"] = notes

            result = create_context(temporary_scene)

            if ai_error(result):
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
                key=f"rewrite_{scene['id']}"
            ):
                temporary_scene = copy.deepcopy(scene)
                temporary_scene["story_feedback"] = feedback

                result = create_context(temporary_scene)

                if ai_error(result):
                    st.error(result)
                else:
                    if commit_change(
                        lambda: scene.update(
                            story_feedback=feedback,
                            story_draft=result
                        )
                    ):
                        st.rerun()

            if st.button(
                "AGENTE SCRITTORE",
                disabled=not bool(client),
                key=f"refine_{scene['id']}"
            ):
                result = refine_context(scene)

                if ai_error(result):
                    st.error(result)
                elif commit_change(
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
            st.markdown("**Contesto approvato**")
            st.write(scene["approved_context"])


# ============================================================
# CONSULENTE
# ============================================================

def render_advisor(scene):
    with st.expander("CONSULENTE NARRATIVO"):
        for message in scene["advisor_messages"]:
            role = message.get("role")

            st.markdown(
                "**Tu:**"
                if role == "user"
                else "**Consulente:**"
            )

            st.write(
                message.get("text", "")
            )

        with st.form(
            f"advisor_form_{scene['id']}"
        ):
            question = st.text_area(
                "Domanda al consulente"
            )

            submit = st.form_submit_button(
                "CHIEDI AL CONSULENTE"
            )

        if submit and question.strip():
            messages = copy.deepcopy(
                scene["advisor_messages"]
            )

            messages.append({
                "role": "user",
                "text": question
            })

            temporary_scene = copy.deepcopy(scene)
            temporary_scene["advisor_messages"] = messages

            result = ask_advisor(temporary_scene)

            if ai_error(result):
                st.error(result)

            else:
                messages.append({
                    "role": "assistant",
                    "text": result
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

    messages = scene["messages"][pov]

    with st.container(
        height=370,
        border=True
    ):
        if not messages:
            st.caption(
                "La conversazione non è ancora iniziata."
            )

        for message in messages:
            if not isinstance(message, dict):
                continue

            inner = (
                message.get("kind") == "inner"
            )

            if scene["id"] == "stanza":
                if pov == "Ada" and inner:
                    continue

                if pov == "Noa" and not inner:
                    continue

            speaker = escape(
                str(message.get("speaker", "?"))
            )

            content = escape(
                str(message.get("text", ""))
            )

            css = (
                "inner-text"
                if inner
                else "chat-text"
            )

            st.markdown(
                f'<div class="{css}">'
                f'<strong>{speaker}</strong>'
                f'<div>{content}</div></div>',
                unsafe_allow_html=True
            )

    if scene["id"] != "inizio":
        if st.button(
            "GO ALONE · 2 SCAMBI",
            key=f"go_{scene['id']}_{pov}",
            disabled=not bool(client),
            use_container_width=True
        ):
            with st.spinner(
                "Noa e Ada stanno dialogando..."
            ):
                error = go_alone(scene)

            if error:
                st.error(error)
            else:
                st.rerun()

    else:
        st.caption(
            "Nel prologo GO ALONE è disattivato "
            "per rispettare l'apertura specifica."
        )

    other = (
        "Noa"
        if pov == "Ada"
        else "Ada"
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
            height=100
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

        temporary_scene = copy.deepcopy(scene)
        temporary_scene["messages"][pov].append(
            copy.deepcopy(turn)
        )

        with st.spinner(
            f"{pov} sta reagendo..."
        ):
            result = answer_character(
                temporary_scene,
                pov,
                mode
            )

        if ai_error(result):
            st.error(result)

        else:
            reply = {
                "speaker": pov,
                "text": clean_ai(result),
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
            "Cancellare la conversazione non cancella "
            "le memorie già approvate."
        )

        confirmed = st.checkbox(
            "Confermo la cancellazione",
            key=f"confirm_delete_{scene['id']}_{pov}"
        )

        if st.button(
            "CANCELLA CONVERSAZIONE",
            disabled=not confirmed,
            key=f"delete_{scene['id']}_{pov}"
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
    record = record_for(scene, pov)

    st.markdown("---")
    st.header("Officina del romanzo")

    st.caption(
        f"Prima persona presente — {pov}. "
        "Solo il testo approvato diventa memoria."
    )

    st.write(
        f"**Stato:** {record['status']}"
    )

    feedback = st.text_area(
        "Indicazioni per le due stesure",
        value=record.get("feedback", ""),
        key=f"narrative_feedback_{scene['id']}_{pov}"
    )

    if st.button(
        "GENERA VERSIONI A E B",
        key=f"generate_pair_{scene['id']}_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        if not scene["messages"][pov]:
            st.warning(
                "Prima crea alcune interazioni."
            )

        else:
            with st.spinner(
                "Scrittura delle due versioni..."
            ):
                version_a = write_narrative(
                    scene, pov, "A", feedback
                )

                version_b = (
                    write_narrative(
                        scene, pov, "B", feedback
                    )
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
                    record["feedback"] = feedback
                    record["recommended"] = ""
                    record["review"] = ""
                    record["status"] = "in_revisione"

                if commit_change(change):
                    st.rerun()

    if record["A"] or record["B"]:
        tab_a, tab_b = st.tabs([
            "VERSIONE A — Essenziale",
            "VERSIONE B — Introspettiva"
        ])

        with tab_a:
            st.markdown(
                '<div class="story-text">'
                + escape(record["A"])
                + '</div>',
                unsafe_allow_html=True
            )

            downloads(
                scene, pov, record["A"], "A"
            )

        with tab_b:
            st.markdown(
                '<div class="story-text">'
                + escape(record["B"])
                + '</div>',
                unsafe_allow_html=True
            )

            downloads(
                scene, pov, record["B"], "B"
            )

        if st.button(
            "CHIEDI IL GIUDIZIO CRITICO",
            key=f"critic_{scene['id']}_{pov}",
            disabled=not bool(client),
            use_container_width=True
        ):
            with st.spinner(
                "Valutazione letteraria..."
            ):
                winner, review = critic(
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

    if record["A"]:
        choices.append("Versione A")

    if record["B"]:
        choices.append("Versione B")

    recommended_choice = (
        "Versione "
        + record.get("recommended", "")
    )

    default_index = (
        choices.index(recommended_choice)
        if recommended_choice in choices
        else 0
    )

    choice = st.selectbox(
        "Versione da revisionare",
        choices,
        index=default_index,
        key=f"choice_{scene['id']}_{pov}"
    )

    selected = record["draft"]

    if choice == "Versione A":
        selected = record["A"]

    elif choice == "Versione B":
        selected = record["B"]

    # Se la versione proposta cambia, inizializza
    # il relativo editor senza perdere altre versioni.
    editor_key = (
        f"editor_{scene['id']}_{pov}_{choice}"
    )

    source_key = editor_key + "_source"

    if st.session_state.get(source_key) != selected:
        st.session_state[editor_key] = selected
        st.session_state[source_key] = selected

    edited = st.text_area(
        "Testo definitivo modificabile",
        height=440,
        key=editor_key
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "SALVA BOZZA SU GITHUB",
            key=f"save_draft_{scene['id']}_{pov}",
            use_container_width=True
        ):
            def change():
                record["draft"] = edited
                if not record["approved"].strip():
                    record["status"] = "bozza"

            if commit_change(change):
                st.success(
                    "Bozza salvata permanentemente."
                )

    with col2:
        if st.button(
            "APPROVA E MEMORIZZA",
            key=f"approve_{scene['id']}_{pov}",
            type="primary",
            use_container_width=True
        ):
            if not edited.strip():
                st.warning(
                    "Il testo è vuoto."
                )

            else:
                def change():
                    previous = record.get(
                        "approved", ""
                    )

                    if (
                        previous.strip()
                        and previous != edited
                    ):
                        record.setdefault(
                            "history", []
                        ).append({
                            "text": previous,
                            "replaced_at": now()
                        })

                    timestamp = now()

                    record["draft"] = edited
                    record["approved"] = edited
                    record["approved_at"] = timestamp
                    record["status"] = "approvata"

                    scene["diary"][pov] = edited

                    if previous != edited:
                        record["visual"][
                            "source_approved_at"
                        ] = ""

                if commit_change(change):
                    st.success(
                        "Scena approvata, salvata "
                        "e disponibile nell'archivio."
                    )
                    st.rerun()

    st.markdown(
        "**Esporta il testo in revisione**"
    )

    downloads(
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

            downloads(
                scene, pov, approved, "approvata"
            )

            later = later_approved(
                scene["id"], pov
            )

            if later:
                st.warning(
                    "Controlla la continuità con: "
                    + ", ".join(later)
                )

            if record.get("history"):
                st.caption(
                    "Versioni precedenti: "
                    + str(len(record["history"]))
                )

    with st.expander(
        "TRASCRIZIONE ORIGINALE"
    ):
        text = transcript(scene, pov)

        st.text(text)

        downloads(
            scene, pov, text, "trascrizione"
        )

    render_visual_workshop(scene, pov)


# ============================================================
# ARCHIVIO SCENE SALVATE
# ============================================================

def render_saved_scenes():
    st.header("Archivio scene salvate")

    st.caption(
        "Le versioni approvate costituiscono "
        "sia il manoscritto sia la memoria canonica "
        "dei rispettivi personaggi."
    )

    total = 0

    for sid in SCENE_ORDER:
        scene = scene_by_id(sid)

        for pov in CHARACTERS:
            record = record_for(scene, pov)

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
                    "Approvata il "
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

                downloads(
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
            f"Scene letterarie archiviate: {total}"
        )


# ============================================================
# DECISIONE FINALE
# ============================================================

def render_return(scene, pov):
    st.markdown("---")
    st.subheader("La decisione finale")

    memories = previous_memories(
        scene["id"], pov
    )

    with st.expander(
        "RICORDI PRECEDENTI"
    ):
        if not memories:
            st.caption(
                "Nessuna memoria precedente approvata."
            )

        for memory in memories:
            st.markdown(
                f"**{memory['scena']}**"
            )
            st.write(memory["ricordo"])

    if st.button(
        f"LASCIA DECIDERE {pov.upper()}",
        key=f"decide_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        if not memories:
            st.warning(
                "Non ci sono ancora ricordi sufficienti."
            )

        else:
            result = ask_ai(
                character_prompt(pov, "inner")
                + """
Questa è la scena finale.

Prendi autonomamente una decisione.

Usa soltanto i tuoi ricordi approvati,
il contesto e le tue esperienze.

Non cercare di soddisfare l'autore.

Non utilizzare l'interiorità
dell'altro personaggio.

Mostra quello che fai, dici o scegli.
""",
                {
                    "SCENA": scene["title"],
                    "CONTESTO": scene_context(
                        scene, pov
                    ),
                    "RICORDI": memories,
                    "CONVERSAZIONE":
                        scene["messages"][pov]
                }
            )

            if ai_error(result):
                st.error(result)

            elif commit_change(
                lambda: scene["decision"].update(
                    {pov: clean_ai(result)}
                )
            ):
                st.rerun()

    decision = scene["decision"].get(
        pov, ""
    )

    if decision:
        st.markdown("### Decisione")
        st.write(decision)


# ============================================================
# PAGINA INGRESSO
# ============================================================

def page_entrance():
    if HOTEL_IMAGE.exists():
        st.image(
            str(HOTEL_IMAGE),
            use_container_width=True
        )

    else:
        st.info(
            "Manca assets/TuringHotel.jpg"
        )

    left, center, right = st.columns(
        [2, 1.4, 2]
    )

    with center:
        if st.button(
            "ENTRA AL TURING HOTEL",
            type="primary",
            use_container_width=True
        ):
            st.session_state.page = "characters"
            st.rerun()


# ============================================================
# SCELTA PERSONAGGIO
# ============================================================

def page_characters():
    cols = st.columns([1, .08, 1])

    for pov, col, image in (
        ("Noa", cols[0], NOA_IMAGE),
        ("Ada", cols[2], ADA_IMAGE)
    ):
        with col:
            if image.exists():
                st.image(
                    str(image),
                    use_container_width=True
                )

            st.markdown(
                f"## {pov.upper()}"
            )

            for video in intro_videos(pov):
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
# PAGINA STORIA
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

    st.sidebar.header(pov)

    portrait = (
        NOA_IMAGE
        if pov == "Noa"
        else ADA_IMAGE
    )

    if portrait.exists():
        st.sidebar.image(
            str(portrait),
            use_container_width=True
        )

    st.sidebar.markdown("---")

    for i, sid in enumerate(SCENE_ORDER):
        label = (
            "● " if i == index else ""
        ) + SCENE_TITLES[sid]

        if st.sidebar.button(
            label,
            key=f"nav_{pov}_{sid}",
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
            scene["id"], pov
        )

        if not memories:
            st.caption(
                "Nessuna memoria precedente."
            )

        for memory in memories:
            st.markdown(
                f"**{memory['scena']}**"
            )

            st.caption(
                memory["ricordo"][:350]
            )

    with st.sidebar.expander(
        "ARCHIVIO GITHUB"
    ):
        st.success(
            "Archivio privato collegato."
        )

        st.caption(
            f"{GH_OWNER}/{GH_REPO} — {GH_BRANCH}"
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
        "DATI AGENTE"
    ):
        sources = character_sources(pov)

        for source in sources:
            st.write(source["file"])

    with st.sidebar.expander(
        "LIBRI AGENTE SCRITTORE"
    ):
        for book in writer_books():
            st.write(book["file"])

    if st.sidebar.button(
        "CAMBIA STORIA",
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
        '<div class="scene-title">'
        + escape(scene["title"])
        + '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="pov-label">'
        + f"STORIA DI {pov.upper()}"
        + '</div>',
        unsafe_allow_html=True
    )

    covers = scene_media(
        scene["id"], pov, "cover"
    )

    if covers:
        st.image(
            str(covers[0]),
            use_container_width=True
        )

    if scene["id"] == "inizio":
        render_intro_editor(scene, pov)
    else:
        render_context_editor(scene)

    render_advisor(scene)
    render_media(scene, pov, "video")
    render_chat(scene, pov)

    if scene["id"] == "ritorno":
        render_return(scene, pov)

    render_workshop(scene, pov)
    render_media(scene, pov, "image")

    st.markdown("---")

    previous, middle, following = st.columns(
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

    with following:
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
        "← TORNA AL ROMANZO",
        use_container_width=False
    ):
        st.session_state.page = "story"
        st.rerun()

    render_saved_scenes()


# ============================================================
# ROUTER
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
