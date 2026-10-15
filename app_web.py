
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


# ============================================================
# TURING HOTEL — OFFICINA DEL ROMANZO
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
LOCAL_DATA = BASE_DIR / "data_web" / "romanzo_web.json"

ASSETS.mkdir(exist_ok=True)
CHARACTERS_DIR.mkdir(exist_ok=True)

HOTEL_IMAGE = ASSETS / "TuringHotel.jpg"
NOA_IMAGE = ASSETS / "Noa.jpg"
ADA_IMAGE = ASSETS / "Ada.jpg"

CHARACTERS = ("Noa", "Ada")

SCENE_ORDER = [
    "hall", "stanza", "funerale",
    "matrimonio", "reparto_nascite", "ritorno"
]

SCENE_TITLES = {
    "hall": "La Hall",
    "stanza": "La stanza",
    "funerale": "Il Funerale",
    "matrimonio": "Il Matrimonio",
    "reparto_nascite": "Il reparto nascite",
    "ritorno": "Il ritorno"
}

SCENE_ALIASES = {
    "hall": ["hall"],
    "stanza": ["stanza", "camera"],
    "funerale": ["funerale"],
    "matrimonio": ["matrimonio"],
    "reparto_nascite": [
        "repartonascite", "reparto_nascite",
        "reparto-nascite", "nascite"
    ],
    "ritorno": ["ritorno", "finale"]
}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}


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


API_KEY = setting("OPENAI_API_KEY")
MODEL = setting("OPENAI_MODEL", "gpt-5.6")

GH_TOKEN = setting("GITHUB_TOKEN")
GH_OWNER = setting("GITHUB_OWNER")
GH_REPO = setting("GITHUB_REPO")
GH_BRANCH = setting("GITHUB_BRANCH", "main")

client = OpenAI(api_key=API_KEY) if API_KEY else None

REMOTE_FILE = "romanzo_web.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def safe_list(value):
    return value if isinstance(value, list) else []


def normalize(value):
    return re.sub(
        r"[\s._-]+", "",
        str(value).lower().strip()
    )


def ai_error(text):
    return (
        not isinstance(text, str)
        or not text.strip()
        or text.startswith("Errore OpenAI:")
        or text.startswith("OPENAI_API_KEY non configurata.")
    )


def ask_ai(instructions, data):
    if not client:
        return "OPENAI_API_KEY non configurata."

    try:
        result = client.responses.create(
            model=MODEL,
            instructions=instructions,
            input=json.dumps(data, ensure_ascii=False)
        )
        return result.output_text.strip()
    except Exception as exc:
        return f"Errore OpenAI: {exc}"


def clean_ai(text):
    text = str(text or "").strip()
    text = re.sub(
        r"^```(?:json|text|markdown)?\s*",
        "", text, flags=re.I
    )
    return re.sub(r"\s*```$", "", text).strip()


def ai_json(text):
    try:
        return json.loads(clean_ai(text))
    except (ValueError, TypeError):
        return None


# ============================================================
# CSS — PULSANTI SCURI
# ============================================================

st.markdown("""
<style>
.stApp {
    background: #080a0c;
    color: #f1eee8;
}
header[data-testid="stHeader"] {
    background: transparent;
}
[data-testid="stSidebar"] {
    background: #101418 !important;
    border-right: 1px solid #272d31;
}
h1, h2, h3 {
    font-family: Georgia, serif;
}
.stApp .stButton > button,
.stApp .stFormSubmitButton > button,
.stApp .stDownloadButton > button {
    background-color: #1b2227 !important;
    color: #f4efe7 !important;
    border: 1px solid #59636b !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
    min-height: 42px;
}
.stApp .stButton > button *,
.stApp .stFormSubmitButton > button *,
.stApp .stDownloadButton > button * {
    color: inherit !important;
}
.stApp .stButton > button:hover,
.stApp .stFormSubmitButton > button:hover,
.stApp .stDownloadButton > button:hover {
    background-color: #303b43 !important;
    color: #ffffff !important;
    border-color: #b79c72 !important;
}
.stApp button:focus-visible {
    outline: 2px solid #b79c72 !important;
}
.stApp button:disabled {
    opacity: .45 !important;
}
.scene-title {
    font-family: Georgia, serif;
    font-size: 3rem;
    line-height: 1.1;
}
.pov-label {
    color: #b79c72;
    font-size: .8rem;
    letter-spacing: .15em;
    margin-bottom: 1rem;
}
.story-text {
    background: #111518;
    border-left: 3px solid #a38b68;
    padding: 20px;
    font-family: Georgia, serif;
    line-height: 1.8;
    white-space: pre-wrap;
}
.chat-text {
    background: #151b20;
    border-left: 2px solid #66747c;
    padding: 12px 15px;
    margin: 7px 0;
    white-space: pre-wrap;
}
.inner-text {
    background: #211b1a;
    border-left: 2px solid #b09470;
    padding: 12px 15px;
    margin: 7px 0;
    white-space: pre-wrap;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# GITHUB — ARCHIVIO PERSISTENTE
# ============================================================

class ArchiveError(Exception):
    pass


def archive_configured():
    return all([
        GH_TOKEN, GH_OWNER, GH_REPO, GH_BRANCH
    ])


def github_url(path):
    owner = quote(GH_OWNER, safe="")
    repo = quote(GH_REPO, safe="")
    file_path = quote(path, safe="/")
    return (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/contents/{file_path}"
    )


def gh_request(method, path, payload=None):
    if not archive_configured():
        raise ArchiveError(
            "Configura GITHUB_TOKEN, GITHUB_OWNER, "
            "GITHUB_REPO e GITHUB_BRANCH nei Secrets."
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
            params={"ref": GH_BRANCH} if method == "GET" else None,
            json=payload,
            timeout=25
        )
    except requests.RequestException as exc:
        raise ArchiveError(
            f"Connessione GitHub non riuscita: {exc}"
        ) from exc

    if response.status_code == 404:
        if method == "GET":
            return None
        raise ArchiveError(
            "Repository, ramo o percorso non trovato."
        )

    if response.status_code in (409, 422):
        raise ArchiveError(
            "Conflitto di versione su GitHub. "
            "Ricarica l'archivio prima di salvare."
        )

    if not response.ok:
        raise ArchiveError(
            f"GitHub HTTP {response.status_code}: "
            f"{response.text[:350]}"
        )

    return response.json()


def read_remote(path):
    result = gh_request("GET", path)

    if result is None:
        return None, None

    if not isinstance(result, dict):
        raise ArchiveError("Risposta GitHub inattesa.")

    content = result.get("content")
    sha = result.get("sha")

    if not content or not sha:
        raise ArchiveError(
            "File remoto senza contenuto o identificativo."
        )

    try:
        decoded = base64.b64decode(content).decode("utf-8")
    except Exception as exc:
        raise ArchiveError(
            "Impossibile decodificare il file GitHub."
        ) from exc

    return decoded, sha


def write_remote(path, content, expected_sha=None):
    # Verifica esplicita della versione remota.
    _, current_sha = read_remote(path)

    if current_sha != expected_sha:
        raise ArchiveError(
            "L'archivio è cambiato dopo il caricamento. "
            "Il salvataggio è stato bloccato per evitare "
            "di sovrascrivere modifiche più recenti."
        )

    payload = {
        "message": f"Turing Hotel: salva {path} - {now()}",
        "content": base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii"),
        "branch": GH_BRANCH
    }

    if expected_sha:
        payload["sha"] = expected_sha

    result = gh_request("PUT", path, payload)

    sha = safe_dict(result.get("content")).get("sha")

    if not sha:
        raise ArchiveError(
            "GitHub non ha confermato il nuovo file."
        )

    return sha


# ============================================================
# DATI DEL ROMANZO
# ============================================================

def empty_narrative():
    return {
        "A": "",
        "B": "",
        "draft": "",
        "approved": "",
        "feedback": "",
        "review": "",
        "recommended": "",
        "status": "da_scrivere",
        "history": [],
        "approved_at": "",
        "visual": {
            "prompts": [],
            "bible": "",
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
        "messages": {"Noa": [], "Ada": []},
        "diary": {"Noa": "", "Ada": ""},
        "narrative": {
            "Noa": empty_narrative(),
            "Ada": empty_narrative()
        }
    }

    if sid == "stanza":
        scene["author_context"] = (
            "Ada accompagna Noa nella sua stanza. "
            "Nel percorso di Ada emerge il dialogo "
            "tra Ada e Noa. Nel percorso di Noa, "
            "Noa riflette sola davanti allo specchio. "
            "Non anticipare la scena successiva."
        )
        scene["approved_context"] = scene["author_context"]

    if sid == "ritorno":
        scene["decision"] = {"Noa": "", "Ada": ""}

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
                "Sa di essere artificiale. È intelligente, "
                "osservatrice, ironica e capace di seduzione."
            ),
            "memory": ""
        },
        "Ada": {
            "profile": (
                "Ada è figlia del professor Elia. "
                "È cresciuta nel Turing Hotel. "
                "È intelligente, pratica, riservata "
                "e osservatrice."
            ),
            "memory": ""
        }
    },
    "scenes": [empty_scene(sid) for sid in SCENE_ORDER]
}


def find_old_scene(scenes, sid):
    aliases = {
        normalize(x) for x in SCENE_ALIASES[sid]
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

    for pov in CHARACTERS:
        source = safe_dict(
            safe_dict(old.get("agents")).get(pov)
        )
        for key in ("profile", "memory"):
            if isinstance(source.get(key), str):
                fresh["agents"][pov][key] = source[key]

    for scene in fresh["scenes"]:
        previous = find_old_scene(
            old.get("scenes"), scene["id"]
        )
        if not previous:
            continue

        for key in (
            "author_context", "story_draft",
            "story_feedback", "approved_context"
        ):
            if isinstance(previous.get(key), str):
                scene[key] = previous[key]

        for key in ("advisor_messages", "shared_dialogue"):
            scene[key] = copy.deepcopy(
                safe_list(previous.get(key))
            )

        for pov in CHARACTERS:
            scene["messages"][pov] = copy.deepcopy(
                safe_list(
                    safe_dict(previous.get("messages")).get(pov)
                )
            )

            old_diary = str(
                safe_dict(previous.get("diary")).get(pov, "")
            )
            scene["diary"][pov] = old_diary

            old_record = safe_dict(
                safe_dict(previous.get("narrative")).get(pov)
            )
            record = scene["narrative"][pov]

            for key in record:
                if key in old_record:
                    record[key] = copy.deepcopy(old_record[key])

            # I vecchi ricordi NON sono approvati
            # automaticamente.
            if not old_record and old_diary.strip():
                record["draft"] = old_diary
                record["status"] = "bozza_legacy"

            record["visual"] = {
                **empty_narrative()["visual"],
                **safe_dict(record.get("visual"))
            }

        if scene["id"] == "ritorno":
            decision = safe_dict(previous.get("decision"))
            for pov in CHARACTERS:
                scene["decision"][pov] = str(
                    decision.get(pov, "")
                )

    return fresh


# ============================================================
# CARICAMENTO E SALVATAGGIO SICURI
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
            "Archivio GitHub privato non configurato. "
            "Inserisci i Secrets prima di utilizzare l'app."
        )
        st.stop()

    try:
        state, sha = load_archive()
    except ArchiveError as exc:
        st.error(str(exc))
        st.stop()

    st.session_state.archive_sha = sha
    st.session_state.archive_ready = state is not None

    if state is None:
        st.session_state.state = copy.deepcopy(DEFAULT_STATE)
    else:
        st.session_state.state = state

    st.session_state.page = "entrance"
    st.session_state.pov = None
    st.session_state.scene_index = 0
    st.session_state.archive_error = ""


initialize_session()

state = st.session_state.state


def save_state():
    if not st.session_state.archive_ready:
        raise ArchiveError(
            "L'archivio non è ancora stato inizializzato."
        )

    serialized = json.dumps(
        state, ensure_ascii=False, indent=2
    )

    sha = write_remote(
        REMOTE_FILE,
        serialized,
        st.session_state.archive_sha
    )

    st.session_state.archive_sha = sha
    st.session_state.archive_error = ""


def commit_change(change):
    """
    Esegue una modifica solo se GitHub la conferma.
    In caso di errore ripristina lo stato precedente
    nella sessione corrente.
    """
    snapshot = copy.deepcopy(state)

    try:
        change()
        save_state()
        return True
    except Exception as exc:
        state.clear()
        state.update(snapshot)
        st.error(f"Salvataggio non riuscito: {exc}")
        return False


def refresh_archive():
    try:
        fresh, sha = load_archive()
        if fresh is None:
            st.error("Archivio GitHub non trovato.")
            return False

        state.clear()
        state.update(fresh)
        st.session_state.archive_sha = sha
        return True
    except ArchiveError as exc:
        st.error(str(exc))
        return False


def setup_archive_panel():
    if st.session_state.archive_ready:
        return

    st.warning(
        "Il file romanzo_web.json non esiste ancora "
        "nel repository privato."
    )

    if LOCAL_DATA.exists():
        st.info(
            "È stato trovato un archivio locale precedente."
        )
        origin = st.radio(
            "Come inizializzare l'archivio?",
            [
                "Importa il vecchio romanzo_web.json",
                "Crea un archivio vuoto"
            ]
        )
    else:
        origin = "Crea un archivio vuoto"

    confirmed = st.checkbox(
        "Confermo l'inizializzazione dell'archivio privato."
    )

    if st.button(
        "INIZIALIZZA ARCHIVIO",
        disabled=not confirmed
    ):
        try:
            if origin.startswith("Importa"):
                imported = json.loads(
                    LOCAL_DATA.read_text(encoding="utf-8")
                )
                chosen = migrate_state(imported)
            else:
                chosen = copy.deepcopy(DEFAULT_STATE)

            serialized = json.dumps(
                chosen, ensure_ascii=False, indent=2
            )
            sha = write_remote(
                REMOTE_FILE, serialized, None
            )

            st.session_state.state = chosen
            st.session_state.archive_sha = sha
            st.session_state.archive_ready = True
            st.rerun()

        except Exception as exc:
            st.error(f"Inizializzazione fallita: {exc}")

    st.stop()


setup_archive_panel()


# ============================================================
# LETTURE FILE LOCALI
# ============================================================

def read_reference(path):
    if path.suffix.lower() in (".txt", ".md"):
        return path.read_text(
            encoding="utf-8", errors="ignore"
        )

    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )
        except Exception:
            return ""

    return ""


def turing_context():
    for path in ASSETS.iterdir():
        if (
            path.is_file()
            and path.suffix.lower() in (".txt", ".md")
            and normalize(path.stem) == "contestoturinghotel"
        ):
            return read_reference(path)

    root = BASE_DIR / "TURING_HOTEL_CONTESTO_AGENTE.md"
    return read_reference(root) if root.exists() else ""


def character_sources(pov):
    result = []
    used = 0

    for path in sorted(CHARACTERS_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".txt", ".md", ".pdf"):
            continue
        if not (
            path.name.lower().startswith(pov.lower())
            or path.name.lower().startswith("shared")
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

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".txt", ".md", ".pdf"):
            continue
        if not normalize(path.stem).startswith("libriagenti"):
            continue

        text = read_reference(path)
        if text:
            result.append({
                "file": path.name,
                "testo": text[:20000]
            })

    return result


# ============================================================
# MEDIA
# ============================================================

def scene_media(sid, pov, kind):
    found = []

    aliases = sorted(
        {normalize(x) for x in SCENE_ALIASES[sid]},
        key=len, reverse=True
    )

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        suffix = path.suffix.lower()

        if kind == "video" and suffix not in VIDEO_EXT:
            continue
        if kind != "video" and suffix not in IMAGE_EXT:
            continue

        compact = normalize(path.stem)

        for alias in aliases:
            if not compact.startswith(alias):
                continue

            remainder = compact[len(alias):]

            if kind == "cover":
                if remainder == pov.lower():
                    found.append((0, path))
                elif remainder == "":
                    found.append((1, path))

            elif remainder.isdigit():
                found.append((int(remainder), path))

            elif remainder.startswith(pov.lower()):
                number = remainder[len(pov):]
                if number.isdigit():
                    found.append((int(number), path))

            break

    found.sort(key=lambda x: (x[0], x[1].name))
    return [path for _, path in found]


def intro_videos(pov):
    result = []
    for path in ASSETS.iterdir():
        if path.suffix.lower() not in VIDEO_EXT:
            continue
        if re.match(
            rf"^{pov.lower()}video\d+$",
            normalize(path.stem)
        ):
            result.append(path)
    return sorted(result, key=lambda p: p.name)


@st.dialog("Immagine", width="large")
def image_dialog(path):
    st.image(path, use_container_width=True)


def render_media(scene, pov, kind):
    files = scene_media(scene["id"], pov, kind)

    if not files:
        return

    if kind == "video":
        st.subheader("Video della scena")
        for path in files:
            st.video(str(path))
    else:
        st.subheader("Immagini della scena")
        for start in range(0, len(files), 3):
            columns = st.columns(3)
            for i, path in enumerate(files[start:start + 3]):
                with columns[i]:
                    st.image(str(path), use_container_width=True)
                    if st.button(
                        "INGRANDISCI",
                        key=f"zoom_{scene['id']}_{pov}_{path.name}"
                    ):
                        image_dialog(str(path))


# ============================================================
# MEMORIE INDIPENDENTI
# ============================================================

def scene_by_id(sid):
    return next(
        x for x in state["scenes"] if x["id"] == sid
    )


def record_for(scene, pov):
    return scene["narrative"][pov]


def previous_memories(scene_id, pov):
    result = []

    for sid in SCENE_ORDER:
        if sid == scene_id:
            break

        scene = scene_by_id(sid)
        approved = record_for(scene, pov).get(
            "approved", ""
        )

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
        if record_for(scene, pov)["approved"].strip():
            result.append(scene["title"])

    return result


# ============================================================
# AGENTE CREATORE DELLA SCENA
# ============================================================

def create_context(scene):
    return ask_ai(
        """
Sei il CREATORE DELLA SCENA di Turing Hotel.

Trasforma le indicazioni dell'autore in un
contesto narrativo oggettivo e utilizzabile.

Rispetta il canone del Turing Hotel.

Puoi definire luogo, momento, oggetti,
persone presenti, circostanze e atmosfera.

Non decidere cosa pensano, provano,
desiderano o scelgono Noa e Ada.

Non inventare eventi fondamentali.

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

Rifinisci il contesto oggettivo della scena.
Migliora immagini, atmosfera, precisione,
ritmo e tensione.

Non cambiare i fatti.
Non decidere le reazioni di Noa e Ada.

Usa LIBRIAGENTI come riferimenti tecnici.
Non copiare i testi.
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

Il tuo interlocutore è l'autore.
Non interpreti Noa e Ada.

Controlla coerenza, continuità, sottotesto,
tensioni, opportunità e possibili alternative.

Quando proponi più soluzioni,
DEVI esprimere una preferenza motivata.

Spiega cosa preferisci, perché,
quali rischi comporta e quando
sceglieresti l'altra soluzione.

Distingui fatti canonici e ipotesi.

Non modificare nulla autonomamente.
Rispondi in italiano.
""",
        {
            "CANONE": turing_context(),
            "SCENA": scene["title"],
            "CONTESTO": scene["approved_context"],
            "BOZZA": scene["story_draft"],
            "RICORDI": all_previous_memories(scene["id"]),
            "CONVERSAZIONE": scene["advisor_messages"]
        }
    )


# ============================================================
# AGENTI NOA E ADA
# ============================================================

def character_prompt(pov, mode):
    agent = state["agents"][pov]

    instructions = f"""
SEI {pov}, personaggio di Turing Hotel.

Non sei un assistente.
Interpreti soltanto {pov}.

MONDO:
{state["world"]}

PROFILO:
{agent["profile"]}

MEMORIA GENERALE:
{agent["memory"]}

REGOLA FONDAMENTALE:
La tua memoria autobiografica è costituita
esclusivamente dalle tue versioni
letterarie APPROVATE nelle scene precedenti.

Non conosci i pensieri segreti dell'altra
protagonista e non accedi alla sua memoria.

Puoi sospettare, mentire, ricordare male,
desiderare, fraintendere e cambiare idea.

Distingui fatti, convinzioni, ipotesi e dubbi.

Il contesto approvato descrive la realtà
della scena ma non determina le tue reazioni.

Non scrivere battute altrui.
Non restituire JSON.
Scrivi in italiano naturale.
"""

    if mode == "inner":
        instructions += """
Stai pensando tra te e te.
Prosegui il dialogo interiore.
Non esiste interlocutore esterno.
"""
    else:
        instructions += """
Sei presente fisicamente nella scena.
Rispondi in modo naturale al tuo interlocutore.
"""

    return instructions


def answer_character(scene, pov, mode):
    return ask_ai(
        character_prompt(pov, mode),
        {
            "SCENA": scene["title"],
            "CONTESTO": scene["approved_context"],
            "CANONE": turing_context(),
            "FONTI": character_sources(pov),
            "RICORDI": previous_memories(scene["id"], pov),
            "MESSAGGI": scene["messages"][pov],
            "DIALOGO_CONDIVISO": scene["shared_dialogue"],
            "MODALITA": mode
        }
    )


def go_alone(scene, start="Ada"):
    other = "Noa" if start == "Ada" else "Ada"

    for speaker in [start, other, start, other]:
        counterpart = "Noa" if speaker == "Ada" else "Ada"

        raw = ask_ai(
            character_prompt(speaker, "external")
            + f"""
Modalità GO ALONE.

Parli con {counterpart}.
Scrivi soltanto la tua prossima battuta
pronunciata ad alta voce.

Non inventare la risposta altrui.
Non creare eventi irreversibili.
""",
            {
                "SCENA": scene["title"],
                "CONTESTO": scene["approved_context"],
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
            return "Salvataggio GO ALONE non riuscito."

    return ""


# ============================================================
# TRASCRIZIONE — SENZA DOPPIONI GO ALONE
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

        speaker = message.get("speaker", "?")
        content = message.get("text", "")

        if message.get("kind") == "inner":
            speaker += " (pensiero)"

        lines.append(f"{speaker}: {content}")
        lines.append("")

    # Le battute GO ALONE sono già nella cronologia
    # personale: non vengono ripetute.
    return "\n".join(lines)


# ============================================================
# AGENTE SCRITTORE — VERSIONI A E B
# ============================================================

def write_narrative(scene, pov, version, feedback):
    if version == "A":
        style = (
            "Prosa essenziale, concreta, densa. "
            "Dialoghi, gesti, silenzi e sottotesto. "
            "Economia espressiva e tensione."
        )
    else:
        style = (
            "Prosa introspettiva, sensoriale, evocativa. "
            "Complessità psicologica e contraddizioni "
            "interiori senza spiegazioni didascaliche."
        )

    return ask_ai(
        f"""
Sei l'AGENTE SCRITTORE di Turing Hotel.

Trasforma l'interazione in una scena
letteraria compiuta.

NARRATORE: {pov}.
OBBLIGO: PRIMA PERSONA SINGOLARE.
TEMPO NARRATIVO: PRESENTE.

Non scrivere un riassunto.

Conserva eventi e dialoghi significativi.
Non inventare svolte importanti.
Non inventare informazioni sconosciute
al personaggio narrante.

Rispetta il contesto e la memoria canonica.
Conserva dubbi e incomprensioni come tali.

Le fonti LIBRIAGENTI sono riferimenti
di tecnica, non testi da copiare.

DIREZIONE STILISTICA:
{style}

Applica le correzioni dell'autore.
Restituisci solo il racconto.
""",
        {
            "PERSONAGGIO": pov,
            "SCENA": scene["title"],
            "CONTESTO": scene["approved_context"],
            "TRASCRIZIONE": transcript(scene, pov),
            "RICORDI": previous_memories(scene["id"], pov),
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
- qualità letteraria;
- fedeltà ai fatti;
- credibilità psicologica;
- originalità della voce;
- efficacia drammatica;
- coerenza con le memorie precedenti;
- adeguatezza all'inserimento nel romanzo.

DEVI scegliere A oppure B.
Non dire semplicemente che entrambe sono valide.

Penalizza invenzioni, onniscienza,
ripetizioni e immagini artificiose.

Se entrambe sono insufficienti, dillo,
ma indica quella meno problematica.

Non approvare automaticamente nulla.

Restituisci JSON valido con:
{
 "preferenza": "A",
 "motivazione": "...",
 "riserve": "...",
 "alternativa": "...",
 "pronta": false
}

Il campo pronta indica se la versione preferita
è consigliabile per l'approvazione senza revisioni.
""",
        {
            "SCENA": scene["title"],
            "PERSONAGGIO": pov,
            "TRASCRIZIONE": transcript(scene, pov),
            "RICORDI": previous_memories(scene["id"], pov),
            "A": record["A"],
            "B": record["B"]
        }
    )

    if ai_error(raw):
        return None, raw

    result = ai_json(raw)

    if not isinstance(result, dict):
        return None, "Risposta critica non strutturata."

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
        f"{'Sì' if result.get('pronta') is True else 'Richiede revisione'}"
    )

    return winner, review


# ============================================================
# ESPORTAZIONE DOCX / TXT / MARKDOWN
# ============================================================

def make_docx(title, text):
    from docx import Document

    document = Document()
    document.add_heading(title, 0)

    for paragraph in text.split("\n"):
        document.add_paragraph(paragraph)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def downloads(scene, pov, text, suffix):
    if not text.strip():
        st.caption("Testo non disponibile.")
        return

    base = f"{scene['id']}_{pov.lower()}_{suffix}"
    columns = st.columns(3)

    with columns[0]:
        st.download_button(
            "TXT",
            text.encode("utf-8"),
            file_name=base + ".txt",
            mime="text/plain",
            key="txt_" + base,
            use_container_width=True
        )

    with columns[1]:
        st.download_button(
            "MARKDOWN",
            text.encode("utf-8"),
            file_name=base + ".md",
            mime="text/markdown",
            key="md_" + base,
            use_container_width=True
        )

    with columns[2]:
        st.download_button(
            "WORD",
            make_docx(scene["title"], text),
            file_name=base + ".docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            key="doc_" + base,
            use_container_width=True
        )


# ============================================================
# OFFICINA VISIVA — PROMPT COERENTI
# ============================================================

def generate_visual_prompts(scene, pov, count):
    record = record_for(scene, pov)
    approved = record.get("approved", "")

    if not approved.strip():
        return None, "La scena non è approvata."

    raw = ask_ai(
        f"""
Sei il DIRETTORE DELLA FOTOGRAFIA
e STORYBOARD ARTIST di Turing Hotel.

Devi tradurre la scena letteraria APPROVATA
in una sequenza coerente di {count} inquadrature.

FONTE NARRATIVA VINCOLANTE:
il racconto approvato, non le bozze.

Prima costruisci una BIBBIA VISIVA della scena.

Definisci, soltanto se attestati nel racconto
o nel canone visivo:
- personaggi presenti;
- abbigliamento;
- ambiente;
- oggetti;
- illuminazione;
- posizione dei personaggi;
- atmosfera;
- continuità temporale e spaziale.

Quando un dettaglio non è determinato,
non inventarlo come fatto canonico.
Puoi formulare una scelta fotografica
coerente, distinguendola dai fatti.

Per ogni inquadratura produci:
1. titolo;
2. momento del racconto rappresentato;
3. prompt per Nano Banana;
4. prompt per un generatore video;
5. indicazione di continuità;
6. riferimento visivo necessario.

PROMPT NANO BANANA:
fotorealismo cinematografico, composizione,
inquadratura, luce, ambiente, azione.
Non inventare identità diverse.
Richiedi di usare i ritratti Noa.jpg e Ada.jpg
come reference image se il personaggio appare.

PROMPT VIDEO:
movimento di macchina, azione osservabile,
inquadratura, luce e durata suggerita.
Nessun avvenimento successivo non presente.

Tutte le inquadrature devono essere
visivamente e narrativamente coerenti.

Non trasformare pensieri interiori
in azioni letterali non presenti nel racconto.

Restituisci soltanto JSON valido:
{{
 "bible": "bibbia visiva condivisa",
 "shots": [
   {{
     "title": "titolo inquadratura",
     "moment": "momento narrativo",
     "image_prompt": "prompt Nano Banana",
     "video_prompt": "prompt video",
     "continuity": "vincoli di continuità",
     "reference": "foto/personaggi necessari"
   }}
 ]
}}
""",
        {
            "SCENA": scene["title"],
            "POV": pov,
            "RACCONTO_APPROVATO": approved,
            "CANONE_VISIVO": turing_context(),
            "IMMAGINI_PERSONAGGI": [
                "assets/Noa.jpg",
                "assets/Ada.jpg"
            ]
        }
    )

    if ai_error(raw):
        return None, raw

    result = ai_json(raw)

    if not isinstance(result, dict):
        return None, "L'agente non ha restituito JSON valido."

    shots = result.get("shots")

    if not isinstance(shots, list) or not shots:
        return None, "Sequenza di prompt non valida."

    required = {
        "title", "moment", "image_prompt",
        "video_prompt", "continuity", "reference"
    }

    for shot in shots:
        if not isinstance(shot, dict):
            return None, "Inquadratura non valida."
        if not required.issubset(shot.keys()):
            return None, "Mancano campi nelle inquadrature."
        if not all(
            isinstance(shot[k], str) for k in required
        ):
            return None, "Formato dei prompt non valido."

    if not isinstance(result.get("bible"), str):
        return None, "Bibbia visiva mancante."

    return result, ""


def visual_as_text(visual):
    lines = [
        "TURING HOTEL — OFFICINA VISIVA",
        "",
        "BIBBIA VISIVA",
        str(visual.get("bible", "")),
        ""
    ]

    for i, shot in enumerate(visual.get("prompts", []), 1):
        lines += [
            f"INQUADRATURA {i}: {shot.get('title', '')}",
            "",
            "MOMENTO:",
            shot.get("moment", ""),
            "",
            "PROMPT NANO BANANA:",
            shot.get("image_prompt", ""),
            "",
            "PROMPT VIDEO:",
            shot.get("video_prompt", ""),
            "",
            "CONTINUITÀ:",
            shot.get("continuity", ""),
            "",
            "RIFERIMENTI:",
            shot.get("reference", ""),
            "",
            "---",
            ""
        ]

    return "\n".join(lines)


def render_visual_workshop(scene, pov):
    record = record_for(scene, pov)
    approved = record.get("approved", "")

    st.markdown("---")
    st.subheader("Officina visiva")

    if not approved.strip():
        st.info(
            "Approva prima una versione letteraria "
            "per attivare la generazione dei prompt."
        )
        return

    st.caption(
        "I prompt derivano esclusivamente dal racconto "
        "approvato e dal canone visivo."
    )

    count = st.slider(
        "Numero di inquadrature",
        min_value=2,
        max_value=12,
        value=6,
        key=f"shot_count_{scene['id']}_{pov}"
    )

    if st.button(
        "GENERA PROMPT NANO BANANA + VIDEO",
        key=f"visual_generate_{scene['id']}_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        with st.spinner("Creazione della sequenza visiva..."):
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

    visual = safe_dict(record.get("visual"))
    shots = safe_list(visual.get("prompts"))

    if not shots:
        return

    if (
        visual.get("source_approved_at")
        != record.get("approved_at")
    ):
        st.warning(
            "I prompt appartengono a una versione precedente "
            "del racconto. Rigenerali per il nuovo testo approvato."
        )
        return

    with st.expander("BIBBIA VISIVA", expanded=True):
        st.write(visual.get("bible", ""))

    for i, shot in enumerate(shots, 1):
        with st.expander(
            f"{i:02d} — {shot.get('title', 'Inquadratura')}"
        ):
            st.markdown("**Momento del romanzo**")
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

    export_scene = {
        "title": "Prompt visivi",
        "id": scene["id"]
    }
    downloads(
        export_scene,
        pov,
        visual_as_text(visual),
        "prompt_visivi"
    )


# ============================================================
# EDITOR CONTESTO E CONSULENTE
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
                lambda: scene.update(author_context=notes)
            ):
                st.success("Indicazioni salvate su GitHub.")

        if st.button(
            "CREA CONTESTO",
            disabled=not bool(client),
            key=f"create_context_{scene['id']}"
        ):
            original = scene["author_context"]
            scene["author_context"] = notes

            result = create_context(scene)
            scene["author_context"] = original

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
                "Correzioni al contesto",
                value=scene["story_feedback"],
                key=f"ctx_feedback_{scene['id']}"
            )

            if st.button(
                "RISCRIVI CONTESTO",
                key=f"rewrite_ctx_{scene['id']}",
                disabled=not bool(client)
            ):
                old_feedback = scene["story_feedback"]
                scene["story_feedback"] = feedback
                result = create_context(scene)
                scene["story_feedback"] = old_feedback

                if ai_error(result):
                    st.error(result)
                elif commit_change(
                    lambda: scene.update(
                        story_feedback=feedback,
                        story_draft=result
                    )
                ):
                    st.rerun()

            if st.button(
                "RIFINISCI CON AGENTE SCRITTORE",
                key=f"refine_ctx_{scene['id']}",
                disabled=not bool(client)
            ):
                result = refine_context(scene)

                if ai_error(result):
                    st.error(result)
                elif commit_change(
                    lambda: scene.update(story_draft=result)
                ):
                    st.rerun()

            if st.button(
                "APPROVA CONTESTO",
                key=f"approve_ctx_{scene['id']}"
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


def render_advisor(scene):
    with st.expander("CONSULENTE NARRATIVO"):
        for message in scene["advisor_messages"]:
            st.markdown(
                "**Tu:**" if message.get("role") == "user"
                else "**Consulente:**"
            )
            st.write(message.get("text", ""))

        with st.form(f"advisor_form_{scene['id']}"):
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

            old_messages = scene["advisor_messages"]
            scene["advisor_messages"] = messages
            result = ask_advisor(scene)
            scene["advisor_messages"] = old_messages

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
# DIALOGHI
# ============================================================

def render_chat(scene, pov):
    st.markdown("---")
    st.subheader(f"Dialogo con {pov}")

    messages = scene["messages"][pov]

    with st.container(height=380, border=True):
        if not messages:
            st.caption("La conversazione non è ancora iniziata.")

        for message in messages:
            if not isinstance(message, dict):
                continue

            inner = message.get("kind") == "inner"

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
            css = "inner-text" if inner else "chat-text"

            st.markdown(
                f'<div class="{css}">'
                f'<strong>{speaker}</strong>'
                f'<div>{content}</div></div>',
                unsafe_allow_html=True
            )

    if st.button(
        "GO ALONE · 2 SCAMBI",
        disabled=not bool(client),
        key=f"go_{scene['id']}_{pov}",
        use_container_width=True
    ):
        with st.spinner("Noa e Ada dialogano..."):
            error = go_alone(scene)

        if error:
            st.error(error)
        else:
            st.rerun()

    if scene["id"] == "stanza" and pov == "Noa":
        st.caption(
            "Qui Noa vive il proprio dialogo interiore. "
            "Il dialogo esterno è visibile nel percorso di Ada."
        )

    other = "Noa" if pov == "Ada" else "Ada"
    options = [
        other, pov, "Elia", "Luigi",
        "Adam", "Vittoria", "Riccardo", "Altro"
    ]

    if scene["id"] == "stanza":
        options = ["Noa"]

    with st.form(f"chat_form_{scene['id']}_{pov}"):
        speaker = st.selectbox("Chi parla", options)
        message = st.text_area("Messaggio", height=100)
        send = st.form_submit_button("INVIA")

    if send and message.strip():
        mode = "inner" if speaker == pov else "external"

        turn = {
            "speaker": speaker,
            "text": message.strip(),
            "kind": mode,
            "role": "prompt"
        }

        # Il prompt viene fornito all'AI,
        # ma non resta registrato finché la risposta
        # e il salvataggio non riescono.
        scene["messages"][pov].append(turn)
        result = answer_character(scene, pov, mode)
        scene["messages"][pov].pop()

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

    with st.expander("GESTIONE CONVERSAZIONE"):
        st.warning(
            "La cancellazione non altera i racconti "
            "già approvati."
        )

        confirm = st.checkbox(
            "Confermo la cancellazione",
            key=f"confirm_delete_{scene['id']}_{pov}"
        )

        if st.button(
            "CANCELLA CONVERSAZIONE",
            disabled=not confirm,
            key=f"delete_{scene['id']}_{pov}"
        ):
            if commit_change(
                lambda: scene["messages"].update({pov: []})
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
        "Solo l'approvazione aggiorna la memoria."
    )

    st.write(f"**Stato:** {record['status']}")

    feedback = st.text_area(
        "Indicazioni per le stesure",
        value=record.get("feedback", ""),
        key=f"writing_feedback_{scene['id']}_{pov}"
    )

    if st.button(
        "GENERA VERSIONI A E B",
        disabled=not bool(client),
        key=f"write_pair_{scene['id']}_{pov}",
        use_container_width=True
    ):
        if not scene["messages"][pov]:
            st.warning("Mancano interazioni da romanzare.")
        else:
            with st.spinner("Scrittura delle due versioni..."):
                a = write_narrative(
                    scene, pov, "A", feedback
                )
                b = (
                    write_narrative(scene, pov, "B", feedback)
                    if not ai_error(a) else ""
                )

            if ai_error(a) or ai_error(b):
                st.error(
                    a if ai_error(a) else b
                )
            else:
                def change():
                    record["A"] = a
                    record["B"] = b
                    record["feedback"] = feedback
                    record["review"] = ""
                    record["recommended"] = ""
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
            downloads(scene, pov, record["A"], "A")

        with tab_b:
            st.markdown(
                '<div class="story-text">'
                + escape(record["B"])
                + '</div>',
                unsafe_allow_html=True
            )
            downloads(scene, pov, record["B"], "B")

        if st.button(
            "CHIEDI IL GIUDIZIO CRITICO",
            disabled=not bool(client),
            key=f"critic_{scene['id']}_{pov}",
            use_container_width=True
        ):
            with st.spinner("Valutazione delle versioni..."):
                winner, review = critic(scene, pov)

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
        st.markdown("### Preferenza dell'agente critico")
        st.markdown(record["review"])

    choices = ["Bozza salvata"]

    if record["A"]:
        choices.append("Versione A")
    if record["B"]:
        choices.append("Versione B")

    default = 0
    preferred = "Versione " + record.get("recommended", "")
    if preferred in choices:
        default = choices.index(preferred)

    selection = st.selectbox(
        "Versione da lavorare",
        choices,
        index=default,
        key=f"select_{scene['id']}_{pov}_"
            f"{record.get('approved_at', '')}_"
            f"{record.get('status', '')}"
    )

    selected = record["draft"]

    if selection == "Versione A":
        selected = record["A"]
    elif selection == "Versione B":
        selected = record["B"]

    editor_key = f"editor_{scene['id']}_{pov}_{selection}"

    # Evita di sovrascrivere modifiche nella casella
    # mentre Streamlit riesegue la pagina.
    edited = st.text_area(
        "Testo definitivo modificabile",
        value=selected,
        height=450,
        key=editor_key
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "SALVA BOZZA SU GITHUB",
            key=f"save_draft_{scene['id']}_{pov}",
            use_container_width=True
        ):
            if commit_change(
                lambda: record.update(
                    draft=edited,
                    status="bozza"
                )
            ):
                st.success("Bozza salvata nell'archivio privato.")

    with col2:
        if st.button(
            "APPROVA E MEMORIZZA",
            type="primary",
            key=f"approve_{scene['id']}_{pov}",
            use_container_width=True
        ):
            if not edited.strip():
                st.warning("Il racconto è vuoto.")
            else:
                def change():
                    previous = record.get("approved", "")

                    if previous.strip() and previous != edited:
                        record.setdefault("history", []).append({
                            "text": previous,
                            "replaced_at": now()
                        })

                    record["draft"] = edited
                    record["approved"] = edited
                    record["approved_at"] = now()
                    record["status"] = "approvata"
                    scene["diary"][pov] = edited

                    # I prompt vecchi restano in archivio,
                    # ma risultano obsoleti dopo la modifica.
                    if previous != edited:
                        record["visual"][
                            "source_approved_at"
                        ] = ""

                if commit_change(change):
                    st.success(
                        f"Memoria canonica di {pov} "
                        "salvata permanentemente."
                    )
                    st.rerun()

    st.markdown("**Esportazione testo in revisione**")
    downloads(scene, pov, edited, "revisione")

    approved = record.get("approved", "")

    if approved.strip():
        with st.expander(
            f"MEMORIA CANONICA DI {pov}",
            expanded=False
        ):
            st.markdown(
                '<div class="story-text">'
                + escape(approved)
                + '</div>',
                unsafe_allow_html=True
            )
            downloads(scene, pov, approved, "approvata")

            later = later_approved(scene["id"], pov)

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

    with st.expander("TRASCRIZIONE ORIGINALE"):
        original = transcript(scene, pov)
        st.text(original)
        downloads(scene, pov, original, "trascrizione")

    render_visual_workshop(scene, pov)


# ============================================================
# FINALE
# ============================================================

def render_return(scene, pov):
    st.markdown("---")
    st.subheader("La decisione finale")

    memories = previous_memories(scene["id"], pov)

    with st.expander("RICORDI PRECEDENTI"):
        for memory in memories:
            st.markdown(f"**{memory['scena']}**")
            st.write(memory["ricordo"])

    if st.button(
        f"LASCIA DECIDERE {pov.upper()}",
        key=f"decide_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        if not memories:
            st.warning("Non ci sono ricordi approvati.")
        else:
            result = ask_ai(
                character_prompt(pov, "inner")
                + """
Questa è la scena finale.

Prendi autonomamente una decisione.
Rispetta i tuoi ricordi canonici.
Non cercare di soddisfare l'autore.
Non usare pensieri privati dell'altro personaggio.
Mostra ciò che fai, dici e scegli.
""",
                {
                    "SCENA": scene["title"],
                    "CONTESTO": scene["approved_context"],
                    "RICORDI": memories,
                    "CONVERSAZIONE": scene["messages"][pov]
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

    decision = scene["decision"].get(pov, "")

    if decision:
        st.markdown("### Decisione")
        st.write(decision)
        st.caption(
            "La decisione entra nella memoria soltanto "
            "quando approvi il racconto della scena."
        )


# ============================================================
# PAGINE
# ============================================================

def page_entrance():
    if HOTEL_IMAGE.exists():
        st.image(
            str(HOTEL_IMAGE),
            use_container_width=True
        )
    else:
        st.info("Manca assets/TuringHotel.jpg")

    left, center, right = st.columns([2, 1.4, 2])

    with center:
        if st.button(
            "ENTRA AL TURING HOTEL",
            use_container_width=True
        ):
            st.session_state.page = "characters"
            st.rerun()


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

            st.markdown(f"## {pov.upper()}")

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

    scene = scene_by_id(SCENE_ORDER[index])

    st.sidebar.header(pov)

    portrait = NOA_IMAGE if pov == "Noa" else ADA_IMAGE

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

    with st.sidebar.expander("MEMORIA CANONICA"):
        memories = previous_memories(scene["id"], pov)

        if not memories:
            st.caption("Nessuna memoria precedente.")

        for memory in memories:
            st.markdown(f"**{memory['scena']}**")
            st.caption(memory["ricordo"][:350])

    with st.sidebar.expander("ARCHIVIO GITHUB"):
        st.success("Archivio privato collegato.")
        st.caption(
            f"{GH_OWNER}/{GH_REPO} — {GH_BRANCH}"
        )

        if st.button(
            "RICARICA ARCHIVIO DA GITHUB",
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

    with st.sidebar.expander("FONTI AGENTE"):
        for item in character_sources(pov):
            st.write(item["file"])

    with st.sidebar.expander("LIBRI AGENTE SCRITTORE"):
        for item in writer_books():
            st.write(item["file"])

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
        st.rerun()

    st.markdown(
        f'<div class="scene-title">'
        f'{escape(scene["title"])}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="pov-label">'
        f'STORIA DI {pov.upper()}</div>',
        unsafe_allow_html=True
    )

    covers = scene_media(scene["id"], pov, "cover")

    if covers:
        st.image(
            str(covers[0]),
            use_container_width=True
        )

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
        if index > 0 and st.button(
            "← PRECEDENTE",
            use_container_width=True
        ):
            st.session_state.scene_index -= 1
            st.rerun()

    with following:
        if index < len(SCENE_ORDER) - 1 and st.button(
            "SUCCESSIVA →",
            use_container_width=True
        ):
            st.session_state.scene_index += 1
            st.rerun()


# ============================================================
# ROUTER
# ============================================================

if st.session_state.page == "entrance":
    page_entrance()

elif st.session_state.page == "characters":
    page_characters()

elif st.session_state.page == "story":
    page_story()

else:
    st.session_state.page = "entrance"
    st.rerun()
