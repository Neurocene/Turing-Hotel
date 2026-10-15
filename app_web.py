
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
# TURING HOTEL — OFFICINA DEL ROMANZO
# 30 SCENE — NOA E ADA
# DIALOGO + MONOLOGO CON GO ALONE
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

CHARACTERS = ("Noa", "Ada")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}


# ============================================================
# LE 30 SCENE
# ============================================================

SCENE_DEFINITIONS = [
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
    ("il_bagno", "Il bagno")
]

SCENE_ORDER = [sid for sid, _ in SCENE_DEFINITIONS]
SCENE_TITLES = dict(SCENE_DEFINITIONS)

LEGACY_ALIASES = {
    "inizio": ["inizio", "prologo", "l'inizio"],
    "hall": ["hall", "la hall", "reception"],
    "stanza": ["stanza", "camera", "la stanza"],
    "funerale": ["funerale", "il funerale"],
    "matrimonio": ["matrimonio", "il matrimonio"],
    "reparto_nascite": [
        "repartonascite",
        "reparto-nascite",
        "nascite"
    ],
    "ritorno": ["ritorno", "il ritorno"]
}

INTRO_CONTEXTS = {
    "Noa": (
        "Noa percorre a piedi il viale che porta "
        "al Turing Hotel. È sola con i propri pensieri. "
        "La scena iniziale è un monologo interiore. "
        "Le riflessioni nascono dalla sua identità "
        "e da ciò che effettivamente conosce. "
        "La scena termina con l'incontro con Ada. "
        "Non proseguire nel dialogo successivo."
    ),
    "Ada": (
        "Ada si trova nello studio del professor Elia, "
        "suo padre, all'interno del Turing Hotel. "
        "La scena procede come dialogo tra Ada "
        "e il Professore. Termina quando Noa "
        "arriva alla reception. "
        "Non raccontare eventi successivi."
    )
}


# ============================================================
# UTILITÀ
# ============================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def safe_list(value):
    return value if isinstance(value, list) else []


def normalized(value):
    return re.sub(
        r"[^a-z0-9]+", "",
        str(value).casefold()
    )


def setting(name, default=""):
    try:
        value = st.secrets.get(name)
        if value is not None and value != "":
            return str(value)
    except Exception:
        pass

    return os.getenv(name, default)


def find_file(filename):
    if not ASSETS.is_dir():
        return None

    for path in ASSETS.iterdir():
        if (
            path.is_file()
            and path.name.casefold() == filename.casefold()
        ):
            return path

    return None


def ai_failed(text):
    return (
        not isinstance(text, str)
        or not text.strip()
        or text.startswith("Errore OpenAI:")
        or text.startswith("OPENAI_API_KEY")
    )


def json_from_ai(text):
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        str(text).strip(),
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except (ValueError, TypeError):
        return None


def fill_defaults(target, template):
    target = safe_dict(target)

    for key, value in template.items():
        if key not in target:
            target[key] = copy.deepcopy(value)
        elif isinstance(value, dict):
            target[key] = fill_defaults(
                target[key],
                value
            )

    return target


# ============================================================
# SECRETS
# ============================================================

OPENAI_KEY = setting("OPENAI_API_KEY")
OPENAI_MODEL = setting("OPENAI_MODEL", "gpt-4.1-mini")

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


# ============================================================
# CSS — COLORI LEGGIBILI
# ============================================================

st.markdown("""
<style>
.stApp {
    background: #090c0e !important;
    color: #ffffff !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

[data-testid="stSidebar"] {
    background: #101519 !important;
    color: #ffffff !important;
    border-right: 1px solid #46525b;
}

.stApp h1, .stApp h2, .stApp h3,
.stApp h4, .stApp h5, .stApp h6 {
    color: #ffffff !important;
}

.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stCheckbox"] label p,
.stApp [data-testid="stRadio"] label p {
    color: #ffffff !important;
}

.stApp [data-testid="stCaptionContainer"] p {
    color: #dde2e5 !important;
}

.stApp .stButton > button,
.stApp .stFormSubmitButton > button,
.stApp .stDownloadButton > button {
    background: #1b2227 !important;
    color: #ffffff !important;
    border: 1px solid #88949c !important;
    border-radius: 5px !important;
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
    background: #354149 !important;
    border-color: #c1a478 !important;
}

.stApp input:not([type="checkbox"]):not([type="radio"]),
.stApp textarea {
    background: #ffffff !important;
    color: #111111 !important;
    -webkit-text-fill-color: #111111 !important;
    caret-color: #111111 !important;
}

.stApp input::placeholder,
.stApp textarea::placeholder {
    color: #666666 !important;
    -webkit-text-fill-color: #666666 !important;
}

.stApp [data-baseweb="input"],
.stApp [data-baseweb="textarea"] {
    background: #ffffff !important;
}

.stApp [data-baseweb="select"] > div {
    background: #ffffff !important;
    color: #111111 !important;
}

.stApp [data-baseweb="select"] span,
.stApp [data-baseweb="select"] input {
    color: #111111 !important;
}

[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"] {
    background: #ffffff !important;
    color: #111111 !important;
}

[data-baseweb="popover"] [role="option"] * {
    color: #111111 !important;
}

[data-baseweb="popover"] [role="option"]:hover {
    background: #dfe5e8 !important;
}

.stApp button[data-baseweb="tab"] {
    background: #1b2227 !important;
    color: #ffffff !important;
}

.stApp button[data-baseweb="tab"] p {
    color: inherit !important;
}

.stApp button[data-baseweb="tab"][aria-selected="true"] {
    background: #ffffff !important;
    color: #111111 !important;
}

.stApp [data-testid="stExpander"] {
    background: #151b20 !important;
    border: 1px solid #46525b !important;
}

.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary * {
    color: #ffffff !important;
}

.stApp pre {
    background: #171d22 !important;
}

.stApp pre code {
    color: #ffffff !important;
}

.hotel-title {
    font-family: Georgia, serif;
    font-size: 2.8rem;
    line-height: 1.15;
    color: #ffffff;
    margin-bottom: 8px;
}

.hotel-subtitle {
    color: #d3b98d;
    letter-spacing: .12em;
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

.stApp button:focus-visible,
.stApp input:focus-visible,
.stApp textarea:focus-visible {
    outline: 2px solid #c1a478 !important;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# GITHUB — ARCHIVIO PRIVATO
# ============================================================

class ArchiveError(Exception):
    pass


def github_ready():
    return all([
        GH_TOKEN, GH_OWNER, GH_REPO, GH_BRANCH
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
            f"Errore di connessione GitHub: {exc}"
        ) from exc

    if response.status_code == 404:
        if method == "GET":
            return None

        raise ArchiveError(
            "Repository, ramo o percorso non trovato."
        )

    if response.status_code in (409, 422):
        raise ArchiveError(
            "Conflitto di versione. Ricarica l'archivio."
        )

    if not response.ok:
        raise ArchiveError(
            f"GitHub HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    return response.json()


def read_remote():
    response = github_request("GET", REMOTE_FILE)

    if response is None:
        return None, None

    try:
        content = base64.b64decode(
            response["content"]
        ).decode("utf-8")

        return content, response["sha"]

    except (KeyError, ValueError) as exc:
        raise ArchiveError(
            "Impossibile leggere il JSON remoto."
        ) from exc


def write_remote(content, expected_sha):
    _, current_sha = read_remote()

    if current_sha != expected_sha:
        raise ArchiveError(
            "Archivio modificato in un'altra sessione. "
            "Ricarica prima di salvare."
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
        },
        "monologue_topics": {
            "Noa": "",
            "Ada": ""
        }
    }

    if sid == "inizio":
        scene["intro_contexts"] = copy.deepcopy(
            INTRO_CONTEXTS
        )

    if sid == "stanza":
        scene["author_context"] = (
            "Ada accompagna Noa nella stanza. "
            "La scena assume la prospettiva "
            "del personaggio selezionato."
        )
        scene["approved_context"] = (
            scene["author_context"]
        )

    if sid == "ritorno":
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
            empty_scene(sid)
            for sid in SCENE_ORDER
        ]
    }


def aliases_for(sid):
    names = [
        sid,
        SCENE_TITLES[sid],
        *LEGACY_ALIASES.get(sid, [])
    ]

    return {
        normalized(name)
        for name in names
    }


def migrate_state(old):
    """
    Mantiene i contenuti esistenti e
    inserisce le nuove scene in ordine.

    Conserva anche eventuali campi
    aggiuntivi non riconosciuti.
    """
    old = safe_dict(old)
    result = fill_defaults(
        copy.deepcopy(old),
        default_state()
    )

    original_scenes = safe_list(
        old.get("scenes")
    )

    updated = []

    for sid in SCENE_ORDER:
        previous = None
        aliases = aliases_for(sid)

        for candidate in original_scenes:
            if not isinstance(candidate, dict):
                continue

            if (
                normalized(
                    candidate.get("id", "")
                ) in aliases
                or normalized(
                    candidate.get("title", "")
                ) in aliases
            ):
                previous = candidate
                break

        fresh = empty_scene(sid)

        if previous is None:
            scene = fresh
        else:
            scene = fill_defaults(
                copy.deepcopy(previous),
                fresh
            )

        scene["id"] = sid
        scene["title"] = SCENE_TITLES[sid]

        scene["messages"] = fill_defaults(
            safe_dict(scene.get("messages")),
            {"Noa": [], "Ada": []}
        )

        scene["monologue_topics"] = fill_defaults(
            safe_dict(
                scene.get("monologue_topics")
            ),
            {"Noa": "", "Ada": ""}
        )

        if sid == "inizio":
            scene["intro_contexts"] = fill_defaults(
                safe_dict(
                    scene.get("intro_contexts")
                ),
                INTRO_CONTEXTS
            )

        scene["narrative"] = fill_defaults(
            safe_dict(scene.get("narrative")),
            {
                "Noa": empty_narrative(),
                "Ada": empty_narrative()
            }
        )

        for pov in CHARACTERS:
            record = fill_defaults(
                safe_dict(
                    scene["narrative"].get(pov)
                ),
                empty_narrative()
            )

            scene["narrative"][pov] = record

            old_diary = safe_dict(
                scene.get("diary")
            ).get(pov, "")

            if (
                not record.get("approved")
                and not record.get("draft")
                and old_diary
            ):
                record["draft"] = old_diary
                record["status"] = "bozza_legacy"

        updated.append(scene)

    result["scenes"] = updated
    return result


# ============================================================
# CARICAMENTO E SALVATAGGIO
# ============================================================

def load_archive():
    raw, sha = read_remote()

    if raw is None:
        return None, None

    try:
        old = json.loads(raw)
    except ValueError as exc:
        raise ArchiveError(
            "Il JSON remoto non è valido."
        ) from exc

    return migrate_state(old), sha


def initialize_session():
    if "state" in st.session_state:
        return

    if not github_ready():
        st.error(
            "Configura i Secrets GitHub."
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
            "Archivio non inizializzato."
        )

    payload = json.dumps(
        state,
        ensure_ascii=False,
        indent=2
    )

    st.session_state.archive_sha = write_remote(
        payload,
        st.session_state.archive_sha
    )


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
                "Archivio remoto mancante."
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

    confirmed = st.checkbox(
        "Confermo l'inizializzazione "
        "dell'archivio privato"
    )

    if st.button(
        "INIZIALIZZA ARCHIVIO",
        disabled=not confirmed
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

            sha = write_remote(
                json.dumps(
                    selected,
                    ensure_ascii=False,
                    indent=2
                ),
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
# MEDIA
# FORMATO: NOMESCENA.NOMEPERSONA.NUMERO
# ============================================================

def media_prefix(sid, pov):
    return f"{sid}.{pov.lower()}"


def expected_media_names(sid, pov):
    prefix = media_prefix(sid, pov)

    return {
        "cover": f"{prefix}.jpg",
        "images": [
            f"{prefix}.{i}.jpg"
            for i in range(1, 4)
        ],
        "videos": [
            f"{prefix}.{i}.mp4"
            for i in range(1, 3)
        ]
    }


def parse_scene_media(path, sid, pov):
    if path.suffix.casefold() not in (
        IMAGE_EXT | VIDEO_EXT
    ):
        return None

    name = normalized(path.stem)
    person = normalized(pov)

    aliases = sorted(
        aliases_for(sid),
        key=len,
        reverse=True
    )

    for alias in aliases:
        if not name.startswith(alias):
            continue

        tail = name[len(alias):]

        if tail == person:
            if path.suffix.casefold() in IMAGE_EXT:
                return "cover", 0
            return None

        if tail == "" and sid != "inizio":
            if path.suffix.casefold() in IMAGE_EXT:
                return "generic_cover", 0
            return None

        if tail.startswith(person):
            number = tail[len(person):]

            if number.isdigit():
                category = (
                    "videos"
                    if path.suffix.casefold() in VIDEO_EXT
                    else "images"
                )
                return category, int(number)

        if sid != "inizio" and tail.isdigit():
            category = (
                "videos"
                if path.suffix.casefold() in VIDEO_EXT
                else "images"
            )
            return category, int(tail)

    return None


def media_files(sid, pov):
    found = {
        "cover": [],
        "generic_cover": [],
        "images": [],
        "videos": []
    }

    if not ASSETS.is_dir():
        return found

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        parsed = parse_scene_media(
            path, sid, pov
        )

        if parsed is None:
            continue

        category, number = parsed
        found[category].append(
            (number, path)
        )

    result = {}

    for category, items in found.items():
        items.sort(
            key=lambda pair: (
                pair[0],
                pair[1].name.casefold()
            )
        )

        result[category] = [
            path
            for _, path in items
        ]

    return result


def media_diagnostics(sid, pov, files):
    expected = expected_media_names(
        sid, pov
    )

    if files["cover"]:
        st.success(
            "Copertina trovata: "
            + files["cover"][0].name
        )
    elif files["generic_cover"]:
        st.success(
            "Copertina generica: "
            + files["generic_cover"][0].name
        )
    else:
        st.warning(
            "Copertina mancante: "
            + expected["cover"]
        )

    for category, title in (
        ("images", "Fotografia"),
        ("videos", "Video")
    ):
        for i, name in enumerate(
            expected[category], 1
        ):
            matching = [
                path.name
                for path in files[category]
                if normalized(path.stem)
                == normalized(
                    media_prefix(sid, pov)
                    + str(i)
                )
            ]

            if matching:
                st.success(
                    f"{title} {i}: "
                    + ", ".join(matching)
                )
            else:
                st.warning(
                    f"{title} {i} mancante: {name}"
                )

        extra = [
            path.name
            for path in files[category]
            if normalized(path.stem)
            not in {
                normalized(
                    media_prefix(sid, pov)
                    + str(i)
                )
                for i in range(
                    1,
                    len(expected[category]) + 1
                )
            }
        ]

        if extra:
            st.caption(
                "Altri file riconosciuti: "
                + ", ".join(extra)
            )

    st.caption(
        "I file numerati sono facoltativi. "
        "La diagnostica indica i nomi consigliati."
    )

    if sid == "inizio" and pov == "Ada":
        st.info(
            "Nel prologo di Ada vengono mostrate "
            "soltanto immagini e video dello studio "
            "del Professore, nominati inizio.ada..."
        )

    with st.expander(
        "TUTTI I FILE PRESENTI IN ASSETS"
    ):
        if ASSETS.is_dir():
            for path in sorted(
                ASSETS.iterdir(),
                key=lambda p: p.name.casefold()
            ):
                if path.is_file():
                    st.text(path.name)
        else:
            st.error(
                "Cartella assets non trovata."
            )


def render_media(scene, pov):
    files = media_files(
        scene["id"], pov
    )

    covers = (
        files["cover"]
        or files["generic_cover"]
    )

    if covers:
        st.image(
            str(covers[0]),
            use_container_width=True
        )

    gallery = []

    for category in ("images", "videos"):
        for path in files[category]:
            parsed = parse_scene_media(
                path, scene["id"], pov
            )
            if parsed:
                gallery.append(
                    (parsed[1], category, path)
                )

    gallery.sort(
        key=lambda item: (
            item[0],
            item[2].name.casefold()
        )
    )

    if gallery:
        st.subheader(
            "Fotografie e video della scena"
        )

        for start in range(0, len(gallery), 2):
            columns = st.columns(2)

            for column, item in zip(
                columns,
                gallery[start:start + 2]
            ):
                _, category, path = item

                with column:
                    try:
                        if category == "videos":
                            st.video(str(path))
                        else:
                            st.image(
                                str(path),
                                use_container_width=True
                            )
                        st.caption(path.name)

                    except Exception as exc:
                        st.error(
                            "File trovato ma non "
                            f"visualizzabile: {path.name}. "
                            f"{exc}"
                        )

    with st.expander(
        "DIAGNOSTICA MEDIA — FILE MANCANTI",
        expanded=not bool(covers or gallery)
    ):
        media_diagnostics(
            scene["id"], pov, files
        )


# ============================================================
# FONTI
# ============================================================

def read_reference(path):
    try:
        if path.suffix.casefold() in (
            ".txt", ".md"
        ):
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
        pass

    return ""


def hotel_context():
    root_file = (
        ROOT / "TURING_HOTEL_CONTESTO_AGENTE.md"
    )

    if root_file.exists():
        return read_reference(root_file)

    if ASSETS.is_dir():
        for path in ASSETS.iterdir():
            if (
                normalized(path.stem)
                == "contestoturinghotel"
            ):
                return read_reference(path)

    return ""


def character_sources(pov):
    result = []

    if not CHARACTERS_DIR.is_dir():
        return result

    total = 0

    for path in sorted(
        CHARACTERS_DIR.iterdir()
    ):
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

        text = read_reference(path)
        remaining = 70000 - total

        if remaining <= 0:
            break

        text = text[:remaining]

        if text:
            result.append({
                "file": path.name,
                "text": text
            })
            total += len(text)

    return result


def writer_sources():
    result = []

    if not ASSETS.is_dir():
        return result

    for path in sorted(
        ASSETS.iterdir()
    ):
        if not path.is_file():
            continue

        if path.suffix.casefold() not in (
            ".txt", ".md", ".pdf"
        ):
            continue

        if normalized(
            path.stem
        ).startswith("libriagenti"):
            text = read_reference(path)

            if text:
                result.append({
                    "file": path.name,
                    "text": text[:20000]
                })

    return result


# ============================================================
# SCENE, CONTESTI E MEMORIE
# ============================================================

def scene_by_id(sid):
    return next(
        scene
        for scene in state["scenes"]
        if scene["id"] == sid
    )


def narrative_for(scene, pov):
    return scene["narrative"][pov]


def scene_context(scene, pov):
    if scene["id"] == "inizio":
        return safe_dict(
            scene.get("intro_contexts")
        ).get(
            pov, INTRO_CONTEXTS[pov]
        )

    return scene.get(
        "approved_context", ""
    )


def previous_memories(sid, pov):
    memories = []

    for current_sid in SCENE_ORDER:
        if current_sid == sid:
            break

        scene = scene_by_id(current_sid)

        approved = narrative_for(
            scene, pov
        ).get("approved", "")

        if approved.strip():
            memories.append({
                "scene": scene["title"],
                "text": approved
            })

    return memories


def later_approved(sid, pov):
    index = SCENE_ORDER.index(sid)
    result = []

    for current_sid in SCENE_ORDER[index + 1:]:
        scene = scene_by_id(current_sid)

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

    for item in safe_list(
        scene["messages"][pov]
    ):
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
# CREATORE DELLA SCENA
# ============================================================

def create_context(scene):
    return ask_ai(
        """
Sei il creatore della scena di Turing Hotel.

Trasforma le indicazioni dell'autore
in un contesto narrativo preciso.

Descrivi luogo, atmosfera, fatti,
persone e oggetti.

Non decidere i pensieri di Noa o Ada.
Non inventare svolte fondamentali.

Restituisci soltanto il contesto.
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
Sei lo scrittore di Turing Hotel.

Rendi il contesto più preciso,
evocativo e narrativamente efficace.

Non cambiare i fatti.
Non inventare eventi.

Usa le fonti letterarie come riferimenti
di tecnica, senza copiarle.

Restituisci soltanto il testo.
""",
        {
            "SCENA": scene["title"],
            "TESTO": scene["story_draft"],
            "CANONE": hotel_context(),
            "FONTI": writer_sources()
        }
    )


def ask_advisor(scene):
    return ask_ai(
        """
Sei il consulente narrativo.

Dialoghi con l'autore.
Individua problemi di coerenza,
opportunità e alternative.

Se proponi alternative,
indica quella che preferisci e perché.

Non decidere al posto dell'autore.
Non modificare autonomamente i testi.

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
# IDENTITÀ DEI PERSONAGGI
# ============================================================

def character_instructions(pov, mode):
    agent = state["agents"][pov]

    instructions = f"""
Sei {pov}, personaggio del romanzo Turing Hotel.

Non sei un assistente.
Non interpreti altri personaggi.

MONDO:
{state["world"]}

IDENTITÀ:
{agent["profile"]}

MEMORIA PERSONALE:
{agent["memory"]}

Ricordi le scene precedenti soltanto
attraverso i tuoi racconti APPROVATI.

Non conosci i pensieri privati altrui.
Distingui fatti, sospetti e intuizioni.

Reagisci autonomamente e coerentemente.
Rispondi in italiano.
"""

    if mode == "inner":
        instructions += """
Stai pensando interiormente.

Esprimi una riflessione autentica,
nella tua voce e nella tua prospettiva.

Non scrivere dialoghi di altri personaggi.
"""
    else:
        instructions += """
Stai parlando ad alta voce.
Scrivi soltanto la tua battuta.
"""

    return instructions


def answer_character(scene, pov, mode):
    instructions = character_instructions(
        pov, mode
    )

    if scene["id"] == "inizio":
        if pov == "Noa":
            instructions += """
Cammini lungo il viale del Turing Hotel.
Non anticipare l'incontro con Ada.
"""
        else:
            instructions += """
Ti trovi nello studio del Professore.
Non anticipare l'arrivo di Noa.
"""

    return ask_ai(
        instructions,
        {
            "SCENA": scene["title"],
            "CONTESTO": scene_context(
                scene, pov
            ),
            "CANONE": hotel_context(),
            "FONTI": character_sources(pov),
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "MESSAGGI": scene["messages"][pov],
            "MODALITA": mode
        }
    )


# ============================================================
# GO ALONE — DIALOGO
# ============================================================

def go_alone_dialogue(scene, pov):
    sid = scene["id"]

    if sid == "inizio" and pov == "Noa":
        return (
            "Per il prologo di Noa usa "
            "la modalità Monologo."
        )

    if sid == "inizio" and pov == "Ada":
        speakers = [
            "Professore", "Ada",
            "Professore", "Ada"
        ]
    else:
        speakers = [
            "Ada", "Noa", "Ada", "Noa"
        ]

    generated = []

    temporary_messages = copy.deepcopy(
        scene["messages"][pov]
    )

    temporary_shared = copy.deepcopy(
        scene["shared_dialogue"]
    )

    for speaker in speakers:
        if speaker == "Professore":
            instructions = """
Sei il professor Elia,
padre di Ada, nel suo studio
al Turing Hotel.

Scrivi una sola battuta.

Non inventare rivelazioni decisive.
Non oltrepassare l'arrivo di Noa
alla reception.
"""
            payload = {
                "CANONE": hotel_context(),
                "SCENA": scene["title"],
                "CONTESTO": scene_context(
                    scene, "Ada"
                ),
                "DIALOGO": temporary_messages
            }

        else:
            instructions = character_instructions(
                speaker, "external"
            )

            instructions += """
Modalità GO ALONE.

Scrivi una battuta alla volta.
Non inventare eventi irreversibili.
"""

            payload = {
                "CANONE": hotel_context(),
                "SCENA": scene["title"],
                "CONTESTO": scene_context(
                    scene, speaker
                ),
                "RICORDI": previous_memories(
                    sid, speaker
                ),
                "FONTI": character_sources(
                    speaker
                ),
                "DIALOGO": (
                    temporary_messages
                    if sid == "inizio"
                    else temporary_shared
                )
            }

        answer = ask_ai(
            instructions, payload
        )

        if ai_failed(answer):
            return answer

        turn = {
            "speaker": speaker,
            "text": answer,
            "kind": "external",
            "role": "response",
            "origin": "go_alone"
        }

        generated.append(turn)

        temporary_messages.append(
            copy.deepcopy(turn)
        )
        temporary_shared.append(
            copy.deepcopy(turn)
        )

    def change():
        if sid == "inizio":
            scene["messages"][pov].extend(
                copy.deepcopy(generated)
            )
        else:
            scene["shared_dialogue"].extend(
                copy.deepcopy(generated)
            )

            for person in CHARACTERS:
                scene["messages"][person].extend(
                    copy.deepcopy(generated)
                )

    if not commit_change(change):
        return "Salvataggio GO ALONE fallito."

    return ""


# ============================================================
# GO ALONE — MONOLOGO IN DUE PENSIERI
# ============================================================

def go_alone_monologue(scene, pov, theme):
    """
    Produce due pensieri consecutivi sul tema
    suggerito dall'autore.

    Li salva entrambi soltanto nella storia
    del personaggio selezionato.

    Non li trasforma subito in memoria canonica:
    occorre l'approvazione del racconto.
    """
    if not theme.strip():
        return (
            "Scrivi prima il tema del monologo."
        )

    sid = scene["id"]
    generated = []

    working_messages = copy.deepcopy(
        scene["messages"][pov]
    )

    for number in (1, 2):
        special = ""

        if sid == "inizio":
            if pov == "Noa":
                special = (
                    "Sei sul viale del Turing Hotel. "
                    "Non oltrepassare l'incontro con Ada."
                )
            else:
                special = (
                    "Sei nello studio del Professore. "
                    "Non oltrepassare l'arrivo di Noa "
                    "alla reception."
                )

        instructions = (
            character_instructions(
                pov, "inner"
            )
            + f"""
MODALITÀ MONOLOGO — GO ALONE.

Tema suggerito dall'autore:
{theme}

Devi produrre il pensiero numero {number}
di una sequenza di due pensieri consecutivi.

Ogni pensiero è un movimento distinto
del ragionamento interiore.

Il secondo pensiero deve approfondire,
contraddire, correggere o trasformare
il primo. Non deve semplicemente ripeterlo.

Non scrivere due pensieri in una risposta.
Scrivine uno soltanto, in prima persona.

Usa il tempo presente.

Non inventare nuovi eventi esterni.
Non attribuire al personaggio
informazioni che non possiede.

Non concludere automaticamente la scena.

VINCOLO:
{special}

Restituisci soltanto il pensiero.
"""
        )

        payload = {
            "SCENA": scene["title"],
            "PERSONAGGIO": pov,
            "TEMA_AUTORE": theme,
            "NUMERO_PENSIERO": number,
            "CONTESTO": scene_context(
                scene, pov
            ),
            "CANONE": hotel_context(),
            "IDENTITA": state["agents"][pov],
            "FONTI": character_sources(pov),
            "RICORDI": previous_memories(
                sid, pov
            ),
            "MESSAGGI_PRECEDENTI": working_messages
        }

        answer = ask_ai(
            instructions, payload
        )

        if ai_failed(answer):
            return answer

        turn = {
            "speaker": pov,
            "text": answer,
            "kind": "inner",
            "role": "response",
            "origin": "go_alone_monologue",
            "theme": theme,
            "thought_number": number
        }

        generated.append(turn)

        working_messages.append(
            copy.deepcopy(turn)
        )

    def change():
        scene.setdefault(
            "monologue_topics", {}
        )[pov] = theme

        scene["messages"][pov].extend(
            copy.deepcopy(generated)
        )

    if not commit_change(change):
        return (
            "I pensieri non sono stati salvati."
        )

    return ""


# ============================================================
# SCRITTORE LETTERARIO A / B
# ============================================================

def write_narrative(scene, pov, version, feedback):
    style = (
        "Essenziale, precisa, concreta, "
        "con sottotesto e silenzi."
        if version == "A"
        else
        "Introspettiva, sensoriale, evocativa, "
        "emotiva ma controllata."
    )

    special = ""

    if scene["id"] == "inizio":
        if pov == "Noa":
            special = (
                "Monologo lungo il viale. "
                "Termina con l'incontro con Ada."
            )
        else:
            special = (
                "Dialogo col Professore nello studio. "
                "Termina all'arrivo di Noa "
                "alla reception."
            )

    theme = safe_dict(
        scene.get("monologue_topics")
    ).get(pov, "")

    return ask_ai(
        f"""
Sei lo scrittore letterario di Turing Hotel.

Scrivi un racconto compiuto.

NARRATORE: {pov}
PRIMA PERSONA SINGOLARE
TEMPO PRESENTE

Non scrivere un riassunto.
Trasforma la trascrizione in letteratura.

Integra dialoghi e pensieri interiori
senza confonderli.

Rispetta gli eventi registrati.
Non inventare svolte fondamentali.

Non attribuire al narratore
informazioni che non possiede.

STILE:
{style}

VINCOLO DELLA SCENA:
{special}

TEMA DELL'ULTIMO MONOLOGO:
{theme}

Usa le fonti letterarie come
riferimenti tecnici, senza copiarle.

Applica le correzioni dell'autore.
Restituisci soltanto il racconto.
""",
        {
            "SCENA": scene["title"],
            "PERSONAGGIO": pov,
            "CONTESTO": scene_context(
                scene, pov
            ),
            "TRASCRIZIONE": transcript(
                scene, pov
            ),
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "IDENTITA": state["agents"][pov],
            "FONTI": character_sources(pov),
            "LIBRIAGENTI": writer_sources(),
            "CORREZIONI": feedback
        }
    )


# ============================================================
# CRITICO
# ============================================================

def literary_critic(scene, pov):
    record = narrative_for(
        scene, pov
    )

    response = ask_ai(
        """
Sei il critico letterario di Turing Hotel.

Confronta le versioni A e B.

Devi scegliere una preferita.

Valuta qualità letteraria,
fedeltà agli eventi, voce narrativa,
coerenza psicologica, efficacia
e continuità.

Indica riserve e quando sceglieresti
l'altra versione.

Non approvare automaticamente.

Restituisci SOLO JSON:
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
            "VERSIONE_A": record["A"],
            "VERSIONE_B": record["B"],
            "TRASCRIZIONE": transcript(
                scene, pov
            ),
            "RICORDI": previous_memories(
                scene["id"], pov
            )
        }
    )

    if ai_failed(response):
        return None, response

    parsed = json_from_ai(response)

    if not isinstance(parsed, dict):
        return None, "Giudizio critico non valido."

    winner = str(
        parsed.get("preferenza", "")
    ).upper()

    if winner not in ("A", "B"):
        return None, "Preferenza A/B mancante."

    review = (
        f"**Preferisco la versione {winner}.**\n\n"
        f"{parsed.get('motivazione', '')}\n\n"
        f"**Riserve:** {parsed.get('riserve', '')}\n\n"
        f"**Quando sceglierei l'altra:** "
        f"{parsed.get('alternativa', '')}\n\n"
        f"**Pronta:** "
        + (
            "Sì"
            if parsed.get("pronta") is True
            else "È consigliata una revisione"
        )
    )

    return winner, review


# ============================================================
# WORD, TXT, MARKDOWN
# ============================================================

def create_docx(title, text):
    document = Document()
    document.add_heading(title, 0)

    for paragraph in text.split("\n"):
        document.add_paragraph(paragraph)

    buffer = BytesIO()
    document.save(buffer)
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
    record = narrative_for(
        scene, pov
    )

    if not record["approved"].strip():
        return None, "Manca il testo approvato."

    response = ask_ai(
        f"""
Sei il direttore della fotografia
di Turing Hotel.

Genera {count} inquadrature a partire
soltanto dal racconto approvato.

Non inventare eventi.

Crea una bibbia visiva coerente.

Per ogni inquadratura fornisci:
- titolo;
- momento;
- prompt Nano Banana;
- prompt video;
- continuità;
- riferimenti.

Restituisci SOLO JSON:
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
            "PERSONAGGIO": pov,
            "TESTO_APPROVATO": record["approved"],
            "CANONE": hotel_context(),
            "MEDIA_PRESENTI": [
                path.name
                for paths in media_files(
                    scene["id"], pov
                ).values()
                for path in paths
            ]
        }
    )

    if ai_failed(response):
        return None, response

    parsed = json_from_ai(response)

    if not isinstance(parsed, dict):
        return None, "JSON dei prompt non valido."

    if (
        not isinstance(parsed.get("bible"), str)
        or not isinstance(parsed.get("shots"), list)
        or not parsed["shots"]
    ):
        return None, "Prompt visivi incompleti."

    return parsed, ""


def visual_text(visual):
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
            str(shot.get("title", "")),
            "",
            "MOMENTO",
            str(shot.get("moment", "")),
            "",
            "NANO BANANA",
            str(shot.get("image_prompt", "")),
            "",
            "VIDEO",
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
    record = narrative_for(
        scene, pov
    )

    st.markdown("---")
    st.subheader("Officina visiva")

    if not record["approved"].strip():
        st.info(
            "Approva prima il racconto."
        )
        return

    count = st.slider(
        "Numero di inquadrature",
        2, 12, 6,
        key=f"shots_{scene['id']}_{pov}"
    )

    if st.button(
        "GENERA PROMPT NANO BANANA + VIDEO",
        key=f"visual_{scene['id']}_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        with st.spinner(
            "Genero la sequenza visiva..."
        ):
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
            "I prompt appartengono a una "
            "versione precedente."
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
            for title, key in (
                ("Momento", "moment"),
                ("Nano Banana", "image_prompt"),
                ("Video", "video_prompt"),
                ("Continuità", "continuity"),
                ("Riferimenti", "reference")
            ):
                st.markdown(f"**{title}**")
                st.write(
                    shot.get(key, "")
                )

    download_text(
        scene, pov,
        visual_text(visual),
        "prompt_visivi"
    )


# ============================================================
# EDITOR DEL PROLOGO
# ============================================================

def render_intro_editor(scene, pov):
    st.subheader(f"Prologo di {pov}")

    if pov == "Noa":
        st.info(
            "Noa percorre il viale. "
            "La scena termina con l'incontro con Ada."
        )
    else:
        st.info(
            "Ada dialoga col Professore nello studio. "
            "La scena termina quando Noa "
            "arriva alla reception."
        )

    edited = st.text_area(
        "Contesto iniziale",
        value=scene_context(scene, pov),
        height=180,
        key=f"intro_{pov}"
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
            st.success("Contesto salvato.")


# ============================================================
# EDITOR CONTESTO SCENA
# ============================================================

def render_context_editor(scene):
    with st.expander(
        "CREATORE DELLA SCENA"
    ):
        notes = st.text_area(
            "Indicazioni dell'autore",
            value=scene["author_context"],
            height=130,
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
                st.success(
                    "Indicazioni salvate."
                )

        if st.button(
            "CREA CONTESTO",
            disabled=not bool(client),
            key=f"create_{scene['id']}"
        ):
            temporary = copy.deepcopy(scene)
            temporary["author_context"] = notes

            answer = create_context(temporary)

            if ai_failed(answer):
                st.error(answer)
            elif commit_change(
                lambda: scene.update(
                    author_context=notes,
                    story_draft=answer
                )
            ):
                st.rerun()

        if scene["story_draft"]:
            st.write(
                scene["story_draft"]
            )

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
                temporary = copy.deepcopy(scene)
                temporary["story_feedback"] = feedback

                answer = create_context(temporary)

                if ai_failed(answer):
                    st.error(answer)
                elif commit_change(
                    lambda: scene.update(
                        story_feedback=feedback,
                        story_draft=answer
                    )
                ):
                    st.rerun()

            if st.button(
                "RIFINISCI CON SCRITTORE",
                disabled=not bool(client),
                key=f"refine_{scene['id']}"
            ):
                answer = refine_context(scene)

                if ai_failed(answer):
                    st.error(answer)
                elif commit_change(
                    lambda: scene.update(
                        story_draft=answer
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
        for item in scene["advisor_messages"]:
            st.markdown(
                "**Autore:**"
                if item.get("role") == "user"
                else "**Consulente:**"
            )
            st.write(
                item.get("text", "")
            )

        with st.form(
            f"advisor_{scene['id']}"
        ):
            question = st.text_area(
                "Domanda al consulente"
            )

            send = st.form_submit_button(
                "CHIEDI AL CONSULENTE"
            )

        if send and question.strip():
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
# CHAT: DIALOGO E MONOLOGO
# ============================================================

def render_chat(scene, pov):
    sid = scene["id"]

    st.markdown("---")
    st.subheader(f"Interazioni di {pov}")

    if sid == "inizio" and pov == "Noa":
        default_mode = 1
    else:
        default_mode = 0

    mode = st.radio(
        "Modalità della scena",
        ["Dialogo", "Monologo"],
        index=default_mode,
        horizontal=True,
        key=f"interaction_mode_{sid}_{pov}"
    )

    with st.container(
        height=380,
        border=True
    ):
        messages = scene["messages"][pov]

        if not messages:
            st.caption(
                "Nessuna interazione registrata."
            )

        for item in messages:
            if not isinstance(item, dict):
                continue

            inner = item.get("kind") == "inner"

            css = (
                "thought-box"
                if inner
                else "chat-box"
            )

            speaker = escape(
                str(item.get("speaker", "?"))
            )

            content = escape(
                str(item.get("text", ""))
            )

            if item.get("origin") == "go_alone_monologue":
                number = item.get(
                    "thought_number"
                )
                speaker += (
                    f" — pensiero {number}"
                )

            st.markdown(
                f'<div class="{css}">'
                f'<strong>{speaker}</strong>'
                f'<div>{content}</div>'
                '</div>',
                unsafe_allow_html=True
            )

    if mode == "Monologo":
        st.markdown(
            "### Monologo interiore"
        )

        st.caption(
            "Suggerisci un tema. "
            "GO ALONE produrrà due pensieri "
            "consecutivi del personaggio."
        )

        current_theme = safe_dict(
            scene.get("monologue_topics")
        ).get(pov, "")

        theme = st.text_area(
            "Tema suggerito dall'autore",
            value=current_theme,
            height=90,
            placeholder=(
                "Esempio: la paura di essere "
                "dimenticata, il desiderio di "
                "libertà, il rapporto col padre..."
            ),
            key=f"monologue_theme_{sid}_{pov}"
        )

        if st.button(
            "SALVA TEMA DEL MONOLOGO",
            key=f"save_theme_{sid}_{pov}",
            use_container_width=True
        ):
            def change():
                scene.setdefault(
                    "monologue_topics", {}
                )[pov] = theme

            if commit_change(change):
                st.success(
                    "Tema salvato nell'archivio."
                )

        if st.button(
            "GO ALONE — 2 PENSIERI",
            key=f"monologue_go_{sid}_{pov}",
            disabled=(
                not bool(client)
                or not theme.strip()
            ),
            use_container_width=True
        ):
            with st.spinner(
                f"{pov} sta sviluppando "
                "due pensieri..."
            ):
                error = go_alone_monologue(
                    scene, pov, theme
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        with st.form(
            f"manual_thought_{sid}_{pov}",
            clear_on_submit=True
        ):
            author_input = st.text_area(
                "Scrivi un pensiero o "
                "una sollecitazione per il personaggio",
                height=100
            )

            send = st.form_submit_button(
                "CHIEDI UNA RISPOSTA INTERIORE"
            )

        if send and author_input.strip():
            turn = {
                "speaker": "Autore",
                "text": author_input.strip(),
                "kind": "inner",
                "role": "prompt",
                "origin": "author_monologue"
            }

            temporary = copy.deepcopy(scene)
            temporary["messages"][pov].append(
                copy.deepcopy(turn)
            )

            with st.spinner(
                f"{pov} sta riflettendo..."
            ):
                answer = answer_character(
                    temporary, pov, "inner"
                )

            if ai_failed(answer):
                st.error(answer)
            else:
                reply = {
                    "speaker": pov,
                    "text": answer,
                    "kind": "inner",
                    "role": "response",
                    "origin": "manual_monologue"
                }

                def change():
                    scene["messages"][pov].extend(
                        [turn, reply]
                    )

                if commit_change(change):
                    st.rerun()

    else:
        st.markdown(
            "### Dialogo"
        )

        if sid == "inizio" and pov == "Noa":
            st.info(
                "Il prologo di Noa è un monologo. "
                "Seleziona la modalità Monologo "
                "per utilizzare GO ALONE."
            )

        else:
            label = (
                "GO ALONE — ADA E PROFESSORE"
                if sid == "inizio" and pov == "Ada"
                else
                "GO ALONE — NOA E ADA"
            )

            if st.button(
                label,
                key=f"dialogue_go_{sid}_{pov}",
                disabled=not bool(client),
                use_container_width=True
            ):
                with st.spinner(
                    "I personaggi stanno dialogando..."
                ):
                    error = go_alone_dialogue(
                        scene, pov
                    )

                if error:
                    st.error(error)
                else:
                    st.rerun()

        other = (
            "Ada"
            if pov == "Noa"
            else "Noa"
        )

        options = [
            other,
            pov,
            "Elia",
            "Professore",
            "Luigi",
            "Adam",
            "Vittoria",
            "Riccardo",
            "Altro"
        ]

        if sid == "inizio" and pov == "Ada":
            options = ["Professore"]

        if sid == "inizio" and pov == "Noa":
            options = ["Noa"]

        with st.form(
            f"dialogue_form_{sid}_{pov}",
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
            kind = (
                "inner"
                if speaker == pov
                else "external"
            )

            turn = {
                "speaker": speaker,
                "text": message.strip(),
                "kind": kind,
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
                    kind
                )

            if ai_failed(answer):
                st.error(answer)
            else:
                reply = {
                    "speaker": pov,
                    "text": answer,
                    "kind": kind,
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
            "La cancellazione della trascrizione "
            "non elimina i racconti già approvati."
        )

        confirmed = st.checkbox(
            "Confermo la cancellazione",
            key=f"confirm_delete_{sid}_{pov}"
        )

        if st.button(
            "CANCELLA CONVERSAZIONE",
            key=f"delete_{sid}_{pov}",
            disabled=not confirmed
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
    record = narrative_for(
        scene, pov
    )

    st.markdown("---")
    st.header("Officina del romanzo")

    st.caption(
        "Prima persona e tempo presente. "
        "Dialoghi e monologhi entrano "
        "nella trascrizione originale. "
        "Soltanto il racconto approvato "
        "diventa memoria canonica."
    )

    st.write(
        f"**Stato:** {record['status']}"
    )

    feedback = st.text_area(
        "Indicazioni per la scrittura",
        value=record.get("feedback", ""),
        key=f"feedback_{scene['id']}_{pov}"
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
                "Scrittura delle due versioni..."
            ):
                version_a = write_narrative(
                    scene, pov, "A", feedback
                )

                version_b = (
                    write_narrative(
                        scene, pov, "B", feedback
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

            elif commit_change(
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

    choice_index = (
        choices.index(preferred)
        if preferred in choices
        else 0
    )

    choice = st.selectbox(
        "Versione da revisionare",
        choices,
        index=choice_index,
        key=f"choice_{scene['id']}_{pov}"
    )

    selected = record.get("draft", "")

    if choice == "Versione A":
        selected = record.get("A", "")

    elif choice == "Versione B":
        selected = record.get("B", "")

    editor_key = (
        f"editor_{scene['id']}_{pov}_"
        f"{normalized(choice)}"
    )

    source_key = editor_key + "_source"

    if st.session_state.get(source_key) != selected:
        st.session_state[editor_key] = selected
        st.session_state[source_key] = selected

    edited = st.text_area(
        "Testo definitivo modificabile",
        height=420,
        key=editor_key
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA SU GITHUB",
            key=f"draft_{scene['id']}_{pov}",
            use_container_width=True
        ):
            def change():
                record["draft"] = edited

                if not record["approved"].strip():
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

                    record["draft"] = edited
                    record["approved"] = edited
                    record["approved_at"] = now()
                    record["status"] = "approvata"

                    scene["diary"][pov] = edited

                    if previous != edited:
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
                scene, pov,
                approved, "approvata"
            )

            later = later_approved(
                scene["id"], pov
            )

            if later:
                st.warning(
                    "Controlla la continuità con "
                    "le scene successive: "
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
            original, "trascrizione"
        )

    render_visual_workshop(scene, pov)


# ============================================================
# ARCHIVIO SCENE SALVATE
# ============================================================

def render_saved_scenes():
    st.header("Archivio scene salvate")

    st.caption(
        "I testi approvati sono conservati "
        "nel repository privato GitHub."
    )

    total = 0

    for sid in SCENE_ORDER:
        scene = scene_by_id(sid)

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

                download_text(
                    scene, pov,
                    approved, "archivio"
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
# DECISIONE DEL RITORNO
# ============================================================

def render_return(scene, pov):
    st.markdown("---")
    st.subheader("Decisione del ritorno")

    memories = previous_memories(
        scene["id"], pov
    )

    if st.button(
        f"LASCIA DECIDERE {pov.upper()}",
        key=f"decision_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        if not memories:
            st.warning(
                "Non ci sono ancora "
                "memorie precedenti approvate."
            )
        else:
            answer = ask_ai(
                character_instructions(
                    pov, "inner"
                ) + """
Prendi autonomamente una decisione
sulla base del contesto attuale
e dei tuoi ricordi approvati.

Non conoscere i pensieri altrui.
Non cercare di compiacere l'autore.

Questa non è necessariamente
la fine del romanzo.
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

            elif commit_change(
                lambda: scene["decision"].update(
                    {pov: answer}
                )
            ):
                st.rerun()

    decision = safe_dict(
        scene.get("decision")
    ).get(pov, "")

    if decision:
        st.write(decision)


# ============================================================
# PAGINA D'INGRESSO
# ============================================================

def page_entrance():
    hotel = find_file(
        "TuringHotel.jpg"
    )

    if hotel:
        st.image(
            str(hotel),
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

    _, center, _ = st.columns(
        [2, 1.5, 2]
    )

    with center:
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

    columns = st.columns(2)

    for pov, column in zip(
        CHARACTERS, columns
    ):
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
                    f"Ritratto {pov}.jpg non trovato."
                )

            st.subheader(pov)

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

    sid = SCENE_ORDER[index]
    scene = scene_by_id(sid)

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

    selected = st.sidebar.selectbox(
        "SCEGLI LA SCENA",
        SCENE_ORDER,
        index=index,
        format_func=lambda item: (
            f"{SCENE_ORDER.index(item) + 1:02d} · "
            f"{SCENE_TITLES[item]}"
        ),
        key=f"scene_selector_{pov}_{index}"
    )

    if selected != sid:
        st.session_state.scene_index = (
            SCENE_ORDER.index(selected)
        )
        st.rerun()

    st.sidebar.caption(
        f"Scena {index + 1} di "
        f"{len(SCENE_ORDER)}"
    )

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
            sid, pov
        )

        if not memories:
            st.caption(
                "Nessuna memoria precedente."
            )

        for memory in memories:
            st.markdown(
                f"**{memory['scene']}**"
            )
            st.caption(
                memory["text"][:300]
            )

    with st.sidebar.expander(
        "ARCHIVIO GITHUB"
    ):
        st.caption(
            f"{GH_OWNER}/{GH_REPO} "
            f"— {GH_BRANCH}"
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
            data=backup.encode("utf-8"),
            file_name="turing_hotel_backup.json",
            mime="application/json",
            use_container_width=True
        )

    with st.sidebar.expander(
        "FONTI DEL PERSONAGGIO"
    ):
        for item in character_sources(pov):
            st.write(item["file"])

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
        f"STORIA DI {pov.upper()} "
        f"· SCENA {index + 1}/{len(SCENE_ORDER)}"
        '</div>',
        unsafe_allow_html=True
    )

    render_media(scene, pov)

    if sid == "inizio":
        render_intro_editor(scene, pov)
    else:
        render_context_editor(scene)

    render_advisor(scene)
    render_chat(scene, pov)

    if sid == "ritorno":
        render_return(scene, pov)

    render_workshop(scene, pov)

    st.markdown("---")

    left, _, right = st.columns(
        [1, 3, 1]
    )

    with left:
        if index > 0 and st.button(
            "← PRECEDENTE",
            use_container_width=True
        ):
            st.session_state.scene_index -= 1
            st.rerun()

    with right:
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
