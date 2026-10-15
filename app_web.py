
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
# VERSIONE 31 SCENE — INCLUSO "IL TRIO"
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

CHARACTERS = ("Noa", "Ada")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}


# ============================================================
# LE 31 SCENE DEL ROMANZO
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
    ("il_bagno", "Il bagno")
]

SCENE_ORDER = [sid for sid, _ in SCENE_DEFINITIONS]
SCENE_TITLES = dict(SCENE_DEFINITIONS)

LEGACY_ALIASES = {
    "inizio": ["inizio", "prologo"],
    "hall": ["hall", "reception"],
    "stanza": ["stanza", "camera"],
    "funerale": ["funerale"],
    "matrimonio": ["matrimonio"],
    "reparto_nascite": [
        "repartonascite",
        "reparto-nascite",
        "nascite"
    ],
    "ritorno": ["ritorno"],
    "il_trio": ["iltrio", "trio"]
}

INTRO_CONTEXTS = {
    "Noa": (
        "Noa cammina lungo il viale che conduce "
        "al Turing Hotel. La scena è un monologo "
        "interiore e termina quando incontra Ada. "
        "Non raccontare il dialogo successivo."
    ),
    "Ada": (
        "Ada si trova nello studio del professor "
        "Elia, suo padre. La scena è un dialogo "
        "tra Ada e il Professore e termina "
        "quando Noa arriva alla reception."
    )
}


# ============================================================
# FUNZIONI GENERALI
# ============================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def safe_list(value):
    return value if isinstance(value, list) else []


def normalized(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
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


def fill_defaults(value, template):
    value = safe_dict(value)
    for key, default in template.items():
        if key not in value:
            value[key] = copy.deepcopy(default)
        elif isinstance(default, dict):
            value[key] = fill_defaults(
                value[key], default
            )
    return value


def find_file(filename):
    if not ASSETS.is_dir():
        return None
    for path in ASSETS.iterdir():
        if path.is_file() and (
            path.name.casefold() == filename.casefold()
        ):
            return path
    return None


def aliases_for(sid):
    values = [
        sid,
        SCENE_TITLES[sid],
        *LEGACY_ALIASES.get(sid, [])
    ]
    return {
        normalized(value)
        for value in values
    }


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


def ai_json(text):
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        str(text).strip(),
        flags=re.I
    )
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except (ValueError, TypeError):
        return None


# ============================================================
# STILE — CONTRASTO
# ============================================================

st.markdown("""
<style>
.stApp {
    background: #090c0e !important;
    color: #ffffff !important;
}
[data-testid="stSidebar"] {
    background: #101519 !important;
    color: #ffffff !important;
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
.stApp .stButton button,
.stApp .stFormSubmitButton button,
.stApp .stDownloadButton button {
    background: #1b2227 !important;
    color: #ffffff !important;
    border: 1px solid #88949c !important;
    min-height: 42px;
}
.stApp .stButton button *,
.stApp .stFormSubmitButton button *,
.stApp .stDownloadButton button * {
    color: #ffffff !important;
}
.stApp .stButton button:hover,
.stApp .stFormSubmitButton button:hover,
.stApp .stDownloadButton button:hover {
    background: #354149 !important;
    border-color: #c1a478 !important;
}
.stApp input:not([type="checkbox"]):not([type="radio"]),
.stApp textarea {
    background: #ffffff !important;
    color: #111111 !important;
    -webkit-text-fill-color: #111111 !important;
}
.stApp input::placeholder,
.stApp textarea::placeholder {
    color: #666666 !important;
    -webkit-text-fill-color: #666666 !important;
}
.stApp [data-baseweb="select"] > div,
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"] {
    background: #ffffff !important;
    color: #111111 !important;
}
.stApp [data-baseweb="select"] span,
.stApp [data-baseweb="select"] input,
[data-baseweb="popover"] [role="option"] * {
    color: #111111 !important;
}
.stApp button[data-baseweb="tab"] {
    background: #1b2227 !important;
    color: #ffffff !important;
}
.stApp button[data-baseweb="tab"][aria-selected="true"] {
    background: #ffffff !important;
    color: #111111 !important;
}
.stApp button[data-baseweb="tab"] p {
    color: inherit !important;
}
.stApp [data-testid="stExpander"] {
    background: #151b20 !important;
    border: 1px solid #46525b !important;
}
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary * {
    color: #ffffff !important;
}
.hotel-title {
    font-family: Georgia, serif;
    color: #ffffff;
    font-size: 2.8rem;
}
.hotel-subtitle {
    color: #d3b98d;
    letter-spacing: .12em;
    margin: 12px 0 20px;
}
.story-text {
    background: #171c20;
    color: #ffffff;
    border-left: 3px solid #c1a478;
    padding: 22px;
    font-family: Georgia, serif;
    font-size: 1.07rem;
    line-height: 1.8;
    white-space: pre-wrap;
}
.chat-box {
    background: #1c242a;
    color: #ffffff;
    padding: 14px;
    margin: 8px 0;
    border-left: 3px solid #8b9da8;
    white-space: pre-wrap;
}
.thought-box {
    background: #29221e;
    color: #ffffff;
    padding: 14px;
    margin: 8px 0;
    border-left: 3px solid #c1a478;
    white-space: pre-wrap;
}
.stApp pre {
    background: #171d22 !important;
}
.stApp pre code {
    color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# ARCHIVIO GITHUB PRIVATO
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
        raise ArchiveError(str(exc)) from exc

    if response.status_code == 404:
        if method == "GET":
            return None
        raise ArchiveError(
            "Repository o ramo non trovato."
        )

    if response.status_code in (409, 422):
        raise ArchiveError(
            "Archivio modificato da un'altra sessione. "
            "Ricarica e riprova."
        )

    if not response.ok:
        raise ArchiveError(
            f"GitHub HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    return response.json()


def read_remote():
    response = github_request(
        "GET", REMOTE_FILE
    )

    if response is None:
        return None, None

    try:
        content = base64.b64decode(
            response["content"]
        ).decode("utf-8")
        return content, response["sha"]
    except (KeyError, ValueError) as exc:
        raise ArchiveError(
            "Archivio GitHub non leggibile."
        ) from exc


def write_remote(content, expected_sha):
    _, current_sha = read_remote()

    if current_sha != expected_sha:
        raise ArchiveError(
            "Conflitto di versione. "
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
        "PUT", REMOTE_FILE, payload
    )

    sha = safe_dict(
        response.get("content")
    ).get("sha")

    if not sha:
        raise ArchiveError(
            "Salvataggio non confermato da GitHub."
        )

    return sha


# ============================================================
# STRUTTURA DEI DATI
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
        "messages": {"Noa": [], "Ada": []},
        "diary": {"Noa": "", "Ada": ""},
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
            "Il racconto segue la prospettiva "
            "del personaggio selezionato."
        )
        scene["approved_context"] = (
            scene["author_context"]
        )

    if sid == "ritorno":
        scene["decision"] = {
            "Noa": "", "Ada": ""
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


def migrate_state(old):
    """
    Aggiunge Il trio senza cancellare
    i contenuti delle altre scene.
    """
    old = safe_dict(old)
    result = fill_defaults(
        copy.deepcopy(old),
        default_state()
    )

    originals = safe_list(
        old.get("scenes")
    )

    scenes = []

    for sid in SCENE_ORDER:
        previous = None
        aliases = aliases_for(sid)

        for candidate in originals:
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

        template = empty_scene(sid)

        if previous is None:
            scene = template
        else:
            scene = fill_defaults(
                copy.deepcopy(previous),
                template
            )

        scene["id"] = sid
        scene["title"] = SCENE_TITLES[sid]

        for pov in CHARACTERS:
            scene["narrative"][pov] = fill_defaults(
                safe_dict(
                    scene["narrative"].get(pov)
                ),
                empty_narrative()
            )

        scenes.append(scene)

    result["scenes"] = scenes
    return result


def load_archive():
    raw, sha = read_remote()

    if raw is None:
        return None, None

    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise ArchiveError(
            "Il JSON remoto non è valido."
        ) from exc

    return migrate_state(parsed), sha


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
    content = json.dumps(
        state,
        ensure_ascii=False,
        indent=2
    )

    st.session_state.archive_sha = write_remote(
        content,
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
            f"Salvataggio fallito: {exc}"
        )
        return False


def refresh_archive():
    try:
        loaded, sha = load_archive()

        if loaded is None:
            st.error("Archivio non trovato.")
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

    confirmed = st.checkbox(
        "Confermo l'inizializzazione"
    )

    if st.button(
        "INIZIALIZZA ARCHIVIO",
        disabled=not confirmed
    ):
        try:
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
            st.error(str(exc))

    st.stop()


initialize_archive_if_needed()


# ============================================================
# MEDIA DELLE SCENE
# ============================================================

def media_prefix(sid, pov):
    return f"{sid}.{pov.lower()}"


def parse_media(path, sid, pov):
    ext = path.suffix.casefold()

    if ext not in IMAGE_EXT | VIDEO_EXT:
        return None

    name = normalized(path.stem)
    person = normalized(pov)

    for alias in sorted(
        aliases_for(sid),
        key=len,
        reverse=True
    ):
        if not name.startswith(alias):
            continue

        tail = name[len(alias):]

        if tail == person and ext in IMAGE_EXT:
            return "cover", 0

        if tail == "" and sid != "inizio":
            if ext in IMAGE_EXT:
                return "generic_cover", 0

        if tail.startswith(person):
            number = tail[len(person):]
            if number.isdigit():
                kind = (
                    "videos"
                    if ext in VIDEO_EXT
                    else "images"
                )
                return kind, int(number)

        if sid != "inizio" and tail.isdigit():
            kind = (
                "videos"
                if ext in VIDEO_EXT
                else "images"
            )
            return kind, int(tail)

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

        parsed = parse_media(
            path, sid, pov
        )

        if parsed:
            category, number = parsed
            found[category].append(
                (number, path)
            )

    return {
        category: [
            path
            for _, path in sorted(
                values,
                key=lambda item: (
                    item[0],
                    item[1].name.casefold()
                )
            )
        ]
        for category, values in found.items()
    }


def render_media(scene, pov):
    sid = scene["id"]
    files = media_files(sid, pov)

    cover = (
        files["cover"]
        or files["generic_cover"]
    )

    if cover:
        st.image(
            str(cover[0]),
            use_container_width=True
        )

    gallery = []

    for category in ("images", "videos"):
        for path in files[category]:
            parsed = parse_media(
                path, sid, pov
            )
            if parsed:
                gallery.append((
                    parsed[1],
                    category,
                    path
                ))

    gallery.sort(
        key=lambda item: (
            item[0],
            item[2].name.casefold()
        )
    )

    if gallery:
        st.subheader(
            "Fotografie e video"
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
                            f"Media non visualizzabile: "
                            f"{path.name}: {exc}"
                        )

    with st.expander(
        "DIAGNOSTICA MEDIA — FILE MANCANTI",
        expanded=not bool(cover or gallery)
    ):
        prefix = media_prefix(sid, pov)

        if cover:
            st.success(
                "Copertina trovata: "
                + cover[0].name
            )
        else:
            st.warning(
                "Copertina mancante: "
                + prefix + ".jpg"
            )

        for category, extension, title, count in (
            ("images", "jpg", "Fotografia", 3),
            ("videos", "mp4", "Video", 2)
        ):
            for number in range(1, count + 1):
                found = [
                    path.name
                    for path in files[category]
                    if normalized(path.stem)
                    == normalized(
                        prefix + str(number)
                    )
                ]

                if found:
                    st.success(
                        f"{title} {number}: "
                        + ", ".join(found)
                    )
                else:
                    st.warning(
                        f"{title} {number} mancante: "
                        f"{prefix}.{number}.{extension}"
                    )

        st.caption(
            "I file segnalati sono facoltativi. "
            "Puoi aggiungere altri numeri progressivi."
        )

        if sid == "inizio" and pov == "Ada":
            st.info(
                "Il prologo di Ada utilizza "
                "esclusivamente i media dello "
                "studio del Professore, "
                "con prefisso inizio.ada."
            )


# ============================================================
# FONTI E PROFILI
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
    filename = (
        ROOT / "TURING_HOTEL_CONTESTO_AGENTE.md"
    )

    if filename.exists():
        return read_reference(filename)

    return ""


def character_sources(pov):
    result = []

    if not CHARACTERS_DIR.is_dir():
        return result

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

        if name.startswith(
            pov.casefold()
        ) or name.startswith("shared"):
            text = read_reference(path)
            if text:
                result.append({
                    "file": path.name,
                    "text": text[:30000]
                })

    return result


def writer_sources():
    result = []

    if ASSETS.is_dir():
        for path in ASSETS.iterdir():
            if (
                path.is_file()
                and path.suffix.casefold() in (
                    ".txt", ".md", ".pdf"
                )
                and normalized(path.stem).startswith(
                    "libriagenti"
                )
            ):
                text = read_reference(path)
                if text:
                    result.append({
                        "file": path.name,
                        "text": text[:15000]
                    })

    return result


# ============================================================
# MEMORIE CANONICHE
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
            pov,
            INTRO_CONTEXTS[pov]
        )

    return scene.get(
        "approved_context", ""
    )


def previous_memories(sid, pov):
    result = []

    for current in SCENE_ORDER:
        if current == sid:
            break

        scene = scene_by_id(current)
        text = narrative_for(
            scene, pov
        ).get("approved", "")

        if text.strip():
            result.append({
                "scene": scene["title"],
                "text": text
            })

    return result


def transcript(scene, pov):
    lines = [
        f"TURING HOTEL — {scene['title']}",
        f"PERSONAGGIO: {pov}",
        "",
        "TRASCRIZIONE ORIGINALE",
        ""
    ]

    for item in scene["messages"][pov]:
        if not isinstance(item, dict):
            continue

        speaker = item.get("speaker", "?")
        if item.get("kind") == "inner":
            speaker += " (pensiero)"

        lines.append(
            f"{speaker}: "
            f"{item.get('text', '')}"
        )
        lines.append("")

    return "\n".join(lines)


# ============================================================
# AGENTI DELLA STORIA
# ============================================================

def character_instructions(pov, inner=False):
    agent = state["agents"][pov]

    return f"""
Sei {pov}, personaggio di Turing Hotel.

Non sei un assistente.
Non interpreti altri personaggi.

MONDO:
{state["world"]}

PROFILO:
{agent["profile"]}

MEMORIA PERSONALE:
{agent["memory"]}

Ricordi soltanto i tuoi testi letterari
APPROVATI delle scene precedenti.

Non conosci i pensieri privati altrui.
Distingui fatti e supposizioni.

{"Produci un pensiero interiore." if inner
else "Produci soltanto la tua battuta parlata."}

Rispondi in italiano.
"""


def answer_character(scene, pov, inner):
    return ask_ai(
        character_instructions(pov, inner),
        {
            "SCENA": scene["title"],
            "CONTESTO": scene_context(scene, pov),
            "CANONE": hotel_context(),
            "FONTI": character_sources(pov),
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "MESSAGGI": scene["messages"][pov]
        }
    )


def go_alone_dialogue(scene, pov):
    if scene["id"] == "inizio" and pov == "Noa":
        return "Usa il Monologo per Noa."

    if scene["id"] == "inizio":
        speakers = [
            "Professore", "Ada",
            "Professore", "Ada"
        ]
    else:
        speakers = [
            "Ada", "Noa", "Ada", "Noa"
        ]

    generated = []
    history = copy.deepcopy(
        scene["messages"][pov]
        if scene["id"] == "inizio"
        else scene["shared_dialogue"]
    )

    for speaker in speakers:
        if speaker == "Professore":
            instructions = """
Sei il professor Elia, padre di Ada.
Ti trovi nel tuo studio.

Scrivi una sola battuta.
Non inventare fatti decisivi.
La scena finisce con l'arrivo
di Noa alla reception.
"""
            memories = []
        else:
            instructions = character_instructions(
                speaker
            )
            memories = previous_memories(
                scene["id"], speaker
            )

        answer = ask_ai(
            instructions,
            {
                "SCENA": scene["title"],
                "CONTESTO": scene_context(
                    scene,
                    "Ada" if speaker == "Professore"
                    else speaker
                ),
                "CANONE": hotel_context(),
                "RICORDI": memories,
                "DIALOGO": history
            }
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
        history.append(turn)

    def change():
        if scene["id"] == "inizio":
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

    return (
        ""
        if commit_change(change)
        else "Salvataggio fallito."
    )


def go_alone_monologue(scene, pov, theme):
    if not theme.strip():
        return "Scrivi il tema del monologo."

    generated = []
    history = copy.deepcopy(
        scene["messages"][pov]
    )

    for number in (1, 2):
        answer = ask_ai(
            character_instructions(pov, True)
            + f"""
Monologo autonomo, pensiero {number} di 2.

Tema dell'autore:
{theme}

Scrivi un solo pensiero, in prima persona
e al tempo presente.

Il secondo deve approfondire o trasformare
il primo, senza ripeterlo.

Non introdurre eventi esterni nuovi.
Non terminare automaticamente la scena.
""",
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
                "MESSAGGI": history,
                "TEMA": theme
            }
        )

        if ai_failed(answer):
            return answer

        turn = {
            "speaker": pov,
            "text": answer,
            "kind": "inner",
            "role": "response",
            "origin": "go_alone_monologue",
            "thought_number": number,
            "theme": theme
        }

        generated.append(turn)
        history.append(turn)

    def change():
        scene["monologue_topics"][pov] = theme
        scene["messages"][pov].extend(
            copy.deepcopy(generated)
        )

    return (
        ""
        if commit_change(change)
        else "Salvataggio fallito."
    )


# ============================================================
# CREATORE E CONSULENTE
# ============================================================

def create_context(scene):
    return ask_ai(
        """
Sei il creatore della scena di Turing Hotel.

Trasforma le indicazioni dell'autore
in un contesto narrativo preciso.

Non decidere i pensieri dei personaggi.
Non inventare eventi fondamentali.
""",
        {
            "SCENA": scene["title"],
            "CANONE": hotel_context(),
            "INDICAZIONI": scene["author_context"],
            "BOZZA": scene["story_draft"],
            "CORREZIONI": scene["story_feedback"]
        }
    )


def refine_context(scene):
    return ask_ai(
        """
Sei lo scrittore del Turing Hotel.

Rifinisci il contesto senza cambiare
i fatti. Usa le fonti letterarie
come riferimenti tecnici senza copiarle.
""",
        {
            "SCENA": scene["title"],
            "TESTO": scene["story_draft"],
            "FONTI": writer_sources()
        }
    )


def ask_advisor(scene):
    return ask_ai(
        """
Sei il consulente narrativo.

Rispondi all'autore, segnala problemi
e proponi alternative.

Se presenti alternative, indica
quale preferisci e spiega perché.

Non modificare autonomamente nulla.
""",
        {
            "CANONE": hotel_context(),
            "SCENA": scene["title"],
            "CONTESTO": scene["approved_context"],
            "CONVERSAZIONE": scene["advisor_messages"]
        }
    )


# ============================================================
# AGENTE SCRITTORE A/B
# ============================================================

def write_narrative(scene, pov, version, feedback):
    style = (
        "Essenziale, sobrio, concreto."
        if version == "A"
        else "Introspettivo, sensoriale, evocativo."
    )

    final_rule = ""

    if scene["id"] == "inizio":
        final_rule = (
            "Termina con l'incontro con Ada."
            if pov == "Noa"
            else "Termina con l'arrivo "
                 "di Noa alla reception."
        )

    return ask_ai(
        f"""
Sei lo scrittore letterario di Turing Hotel.

NARRATORE: {pov}.
PRIMA PERSONA SINGOLARE.
TEMPO PRESENTE.

Scrivi una scena narrativa compiuta,
non un riassunto.

STILE:
{style}

Non inventare svolte fondamentali.
Non attribuire conoscenze improprie.
Integra pensieri e dialoghi registrati.

{final_rule}

Restituisci soltanto il racconto.
""",
        {
            "SCENA": scene["title"],
            "CONTESTO": scene_context(scene, pov),
            "TRASCRIZIONE": transcript(scene, pov),
            "RICORDI": previous_memories(
                scene["id"], pov
            ),
            "FONTI": character_sources(pov),
            "LIBRIAGENTI": writer_sources(),
            "CORREZIONI": feedback
        }
    )


def literary_critic(scene, pov):
    record = narrative_for(scene, pov)

    answer = ask_ai(
        """
Sei il critico letterario di Turing Hotel.

Confronta A e B e scegli una preferita.
Motiva la scelta, indica le riserve
e quando sceglieresti l'altra.

Non approvare automaticamente.

Restituisci JSON valido:
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
            "A": record["A"],
            "B": record["B"],
            "RICORDI": previous_memories(
                scene["id"], pov
            )
        }
    )

    if ai_failed(answer):
        return None, answer

    result = ai_json(answer)

    if not isinstance(result, dict):
        return None, "Giudizio non valido."

    winner = str(
        result.get("preferenza", "")
    ).upper()

    if winner not in ("A", "B"):
        return None, "Preferenza mancante."

    review = (
        f"**Preferisco {winner}.**\n\n"
        f"{result.get('motivazione', '')}\n\n"
        f"**Riserve:** {result.get('riserve', '')}\n\n"
        f"**Alternativa:** "
        f"{result.get('alternativa', '')}\n\n"
        f"**Pronta:** "
        + (
            "Sì"
            if result.get("pronta") is True
            else "Da rivedere"
        )
    )

    return winner, review


# ============================================================
# ESPORTAZIONI
# ============================================================

def docx_bytes(title, text):
    document = Document()
    document.add_heading(title, 0)

    for paragraph in text.split("\n"):
        document.add_paragraph(paragraph)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def downloads(scene, pov, text, suffix):
    if not text.strip():
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
            docx_bytes(scene["title"], text),
            file_name=base + ".docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            key="doc_" + base,
            use_container_width=True
        )


# ============================================================
# OFFICINA VISIVA
# ============================================================

def generate_visuals(scene, pov, count):
    record = narrative_for(scene, pov)

    response = ask_ai(
        f"""
Sei il direttore della fotografia.

Usa soltanto il racconto APPROVATO.
Genera {count} inquadrature coerenti.

Crea una bibbia visiva e prompt
per Nano Banana e video.

Non inventare eventi.

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
            "MEDIA": [
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

    parsed = ai_json(response)

    if not isinstance(parsed, dict):
        return None, "Risposta non valida."

    if not (
        isinstance(parsed.get("bible"), str)
        and isinstance(parsed.get("shots"), list)
        and parsed["shots"]
    ):
        return None, "Prompt incompleti."

    return parsed, ""


def render_visuals(scene, pov):
    record = narrative_for(scene, pov)

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
        with st.spinner("Creo i prompt..."):
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

    visual = safe_dict(record.get("visual"))

    if (
        visual.get("source_approved_at")
        != record.get("approved_at")
    ):
        return

    prompts = safe_list(
        visual.get("prompts")
    )

    if not prompts:
        return

    with st.expander(
        "BIBBIA VISIVA",
        expanded=True
    ):
        st.write(visual.get("bible", ""))

    lines = [
        "BIBBIA VISIVA",
        visual.get("bible", "")
    ]

    for i, shot in enumerate(prompts, 1):
        with st.expander(
            f"{i:02d} — {shot.get('title', '')}"
        ):
            for label, key in (
                ("Momento", "moment"),
                ("Nano Banana", "image_prompt"),
                ("Video", "video_prompt"),
                ("Continuità", "continuity"),
                ("Riferimenti", "reference")
            ):
                st.markdown(f"**{label}**")
                st.write(shot.get(key, ""))

        lines.extend([
            "",
            f"INQUADRATURA {i}",
            str(shot.get("title", "")),
            str(shot.get("moment", "")),
            str(shot.get("image_prompt", "")),
            str(shot.get("video_prompt", "")),
            str(shot.get("continuity", "")),
            str(shot.get("reference", ""))
        ])

    downloads(
        scene, pov,
        "\n".join(lines),
        "prompt_visivi"
    )


# ============================================================
# CONTEXT EDITOR
# ============================================================

def render_context_editor(scene, pov):
    if scene["id"] == "inizio":
        st.subheader(f"Prologo di {pov}")

        current = scene_context(scene, pov)

        edited = st.text_area(
            "Contesto iniziale",
            value=current,
            height=170,
            key=f"intro_{pov}"
        )

        if st.button(
            "SALVA CONTESTO INIZIALE",
            key=f"save_intro_{pov}"
        ):
            def change():
                scene["intro_contexts"][pov] = edited

            if commit_change(change):
                st.success("Contesto salvato.")

        return

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
                st.success("Indicazioni salvate.")

        if st.button(
            "CREA CONTESTO",
            key=f"create_{scene['id']}",
            disabled=not bool(client)
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
            st.write(scene["story_draft"])

            feedback = st.text_area(
                "Correzioni",
                value=scene["story_feedback"],
                key=f"context_feedback_{scene['id']}"
            )

            if st.button(
                "RISCRIVI CONTESTO",
                key=f"rewrite_{scene['id']}",
                disabled=not bool(client)
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
                key=f"refine_{scene['id']}",
                disabled=not bool(client)
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
            st.markdown("**Contesto approvato**")
            st.write(scene["approved_context"])


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
            st.write(item.get("text", ""))

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
# DIALOGO E MONOLOGO
# ============================================================

def render_chat(scene, pov):
    sid = scene["id"]

    st.markdown("---")
    st.subheader(f"Interazioni di {pov}")

    mode = st.radio(
        "Modalità",
        ["Dialogo", "Monologo"],
        index=(
            1 if sid == "inizio" and pov == "Noa"
            else 0
        ),
        horizontal=True,
        key=f"mode_{sid}_{pov}"
    )

    with st.container(
        height=370,
        border=True
    ):
        if not scene["messages"][pov]:
            st.caption(
                "Nessuna interazione."
            )

        for item in scene["messages"][pov]:
            if not isinstance(item, dict):
                continue

            inner = (
                item.get("kind") == "inner"
            )

            css = (
                "thought-box"
                if inner else "chat-box"
            )

            name = escape(
                str(item.get("speaker", "?"))
            )

            text = escape(
                str(item.get("text", ""))
            )

            st.markdown(
                f'<div class="{css}">'
                f'<strong>{name}</strong>'
                f'<div>{text}</div>'
                '</div>',
                unsafe_allow_html=True
            )

    if mode == "Monologo":
        theme = st.text_area(
            "Tema suggerito dall'autore",
            value=scene["monologue_topics"][pov],
            key=f"theme_{sid}_{pov}",
            height=90
        )

        if st.button(
            "GO ALONE — 2 PENSIERI",
            key=f"mono_go_{sid}_{pov}",
            disabled=(
                not bool(client)
                or not theme.strip()
            ),
            use_container_width=True
        ):
            with st.spinner(
                "Il personaggio riflette..."
            ):
                error = go_alone_monologue(
                    scene, pov, theme
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        with st.form(
            f"thought_form_{sid}_{pov}",
            clear_on_submit=True
        ):
            prompt = st.text_area(
                "Sollecitazione al personaggio"
            )
            send = st.form_submit_button(
                "CHIEDI UNA RISPOSTA INTERIORE"
            )

        if send and prompt.strip():
            turn = {
                "speaker": "Autore",
                "text": prompt,
                "kind": "inner",
                "role": "prompt"
            }

            temporary = copy.deepcopy(scene)
            temporary["messages"][pov].append(turn)

            answer = answer_character(
                temporary, pov, True
            )

            if ai_failed(answer):
                st.error(answer)
            else:
                reply = {
                    "speaker": pov,
                    "text": answer,
                    "kind": "inner",
                    "role": "response"
                }

                if commit_change(
                    lambda: scene["messages"][pov].extend(
                        [turn, reply]
                    )
                ):
                    st.rerun()

    else:
        if sid == "inizio" and pov == "Noa":
            st.info(
                "Per l'inizio di Noa usa "
                "il Monologo."
            )
        else:
            label = (
                "GO ALONE — ADA E PROFESSORE"
                if sid == "inizio" and pov == "Ada"
                else "GO ALONE — NOA E ADA"
            )

            if st.button(
                label,
                key=f"dialog_go_{sid}_{pov}",
                disabled=not bool(client),
                use_container_width=True
            ):
                with st.spinner(
                    "I personaggi dialogano..."
                ):
                    error = go_alone_dialogue(
                        scene, pov
                    )

                if error:
                    st.error(error)
                else:
                    st.rerun()

        options = [
            "Ada" if pov == "Noa" else "Noa",
            pov,
            "Professore",
            "Elia",
            "Luigi",
            "Adam",
            "Vittoria",
            "Riccardo",
            "Altro"
        ]

        if sid == "inizio":
            options = (
                ["Professore"]
                if pov == "Ada"
                else ["Noa"]
            )

        with st.form(
            f"dialog_form_{sid}_{pov}",
            clear_on_submit=True
        ):
            speaker = st.selectbox(
                "Chi parla", options
            )
            message = st.text_area(
                "Messaggio"
            )
            send = st.form_submit_button("INVIA")

        if send and message.strip():
            inner = speaker == pov

            turn = {
                "speaker": speaker,
                "text": message,
                "kind": (
                    "inner" if inner else "external"
                ),
                "role": "prompt"
            }

            temporary = copy.deepcopy(scene)
            temporary["messages"][pov].append(turn)

            answer = answer_character(
                temporary, pov, inner
            )

            if ai_failed(answer):
                st.error(answer)
            else:
                reply = {
                    "speaker": pov,
                    "text": answer,
                    "kind": (
                        "inner" if inner else "external"
                    ),
                    "role": "response"
                }

                if commit_change(
                    lambda: scene["messages"][pov].extend(
                        [turn, reply]
                    )
                ):
                    st.rerun()

    with st.expander(
        "GESTIONE CONVERSAZIONE"
    ):
        confirmed = st.checkbox(
            "Confermo la cancellazione",
            key=f"delete_confirm_{sid}_{pov}"
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
    record = narrative_for(scene, pov)

    st.markdown("---")
    st.header("Officina del romanzo")

    st.caption(
        "Le versioni approvate diventano "
        "memoria canonica indipendente."
    )

    st.write(
        f"**Stato:** {record['status']}"
    )

    feedback = st.text_area(
        "Indicazioni letterarie",
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
                "Crea prima un'interazione."
            )
        else:
            with st.spinner(
                "Scrivo le due versioni..."
            ):
                a = write_narrative(
                    scene, pov, "A", feedback
                )
                b = (
                    write_narrative(
                        scene, pov, "B", feedback
                    )
                    if not ai_failed(a)
                    else ""
                )

            if ai_failed(a):
                st.error(a)
            elif ai_failed(b):
                st.error(b)
            else:
                def change():
                    record["A"] = a
                    record["B"] = b
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
            "CHIEDI GIUDIZIO CRITICO",
            key=f"critic_{scene['id']}_{pov}",
            disabled=not bool(client),
            use_container_width=True
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

    choice = st.selectbox(
        "Testo da revisionare",
        choices,
        index=(
            choices.index(preferred)
            if preferred in choices
            else 0
        ),
        key=f"choice_{scene['id']}_{pov}"
    )

    selected = record.get("draft", "")

    if choice == "Versione A":
        selected = record.get("A", "")
    elif choice == "Versione B":
        selected = record.get("B", "")

    key = (
        f"editor_{scene['id']}_{pov}_"
        f"{normalized(choice)}"
    )
    source_key = key + "_source"

    if st.session_state.get(source_key) != selected:
        st.session_state[key] = selected
        st.session_state[source_key] = selected

    edited = st.text_area(
        "Testo definitivo",
        height=400,
        key=key
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA",
            key=f"draft_{scene['id']}_{pov}",
            use_container_width=True
        ):
            def change():
                record["draft"] = edited
                if not record["approved"]:
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
                st.warning("Testo vuoto.")
            else:
                def change():
                    old = record.get("approved", "")

                    if old.strip() and old != edited:
                        record.setdefault(
                            "history", []
                        ).append({
                            "text": old,
                            "replaced_at": now()
                        })

                    record["draft"] = edited
                    record["approved"] = edited
                    record["approved_at"] = now()
                    record["status"] = "approvata"
                    scene["diary"][pov] = edited

                    if old != edited:
                        record["visual"][
                            "source_approved_at"
                        ] = ""

                if commit_change(change):
                    st.rerun()

    downloads(
        scene, pov, edited, "revisione"
    )

    if record.get("approved"):
        with st.expander(
            f"MEMORIA CANONICA DI {pov}"
        ):
            st.markdown(
                '<div class="story-text">'
                + escape(record["approved"])
                + '</div>',
                unsafe_allow_html=True
            )
            downloads(
                scene, pov,
                record["approved"],
                "approvata"
            )

    with st.expander(
        "TRASCRIZIONE ORIGINALE"
    ):
        original = transcript(scene, pov)
        st.text(original)
        downloads(
            scene, pov,
            original,
            "trascrizione"
        )

    render_visuals(scene, pov)


# ============================================================
# ARCHIVIO SCENE SALVATE
# ============================================================

def render_archive():
    st.header("Archivio scene salvate")

    total = 0

    for sid in SCENE_ORDER:
        scene = scene_by_id(sid)

        for pov in CHARACTERS:
            record = narrative_for(scene, pov)

            if not record.get("approved", "").strip():
                continue

            total += 1

            with st.expander(
                f"{scene['title']} — {pov}"
            ):
                st.caption(
                    record.get("approved_at", "")
                )
                st.markdown(
                    '<div class="story-text">'
                    + escape(record["approved"])
                    + '</div>',
                    unsafe_allow_html=True
                )
                downloads(
                    scene, pov,
                    record["approved"],
                    "archivio"
                )

    if not total:
        st.info(
            "Nessuna scena ancora approvata."
        )
    else:
        st.success(
            f"Scene archiviate: {total}"
        )


# ============================================================
# PAGINE
# ============================================================

def page_entrance():
    hotel = find_file("TuringHotel.jpg")

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

    if st.button(
        "ENTRA AL TURING HOTEL",
        use_container_width=True
    ):
        st.session_state.page = "characters"
        st.rerun()


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

    portrait = find_file(pov + ".jpg")
    if portrait:
        st.sidebar.image(
            str(portrait),
            use_container_width=True
        )

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
        f"Scena {index + 1} di 31"
    )

    if st.sidebar.button(
        "ARCHIVIO SCENE SALVATE",
        use_container_width=True
    ):
        st.session_state.page = "archive"
        st.rerun()

    with st.sidebar.expander(
        "MEMORIA CANONICA"
    ):
        for memory in previous_memories(sid, pov):
            st.markdown(
                f"**{memory['scene']}**"
            )
            st.caption(memory["text"][:300])

    with st.sidebar.expander(
        "ARCHIVIO GITHUB"
    ):
        st.caption(
            f"{GH_OWNER}/{GH_REPO}"
        )

        if st.button(
            "RICARICA ARCHIVIO"
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
            mime="application/json"
        )

    if st.sidebar.button(
        "CAMBIA PERSONAGGIO"
    ):
        st.session_state.page = "characters"
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
        f"— SCENA {index + 1}/31"
        '</div>',
        unsafe_allow_html=True
    )

    render_media(scene, pov)
    render_context_editor(scene, pov)
    render_advisor(scene)
    render_chat(scene, pov)
    render_workshop(scene, pov)

    st.markdown("---")

    left, _, right = st.columns(
        [1, 3, 1]
    )

    with left:
        if index > 0 and st.button(
            "← PRECEDENTE"
        ):
            st.session_state.scene_index -= 1
            st.rerun()

    with right:
        if index < len(SCENE_ORDER) - 1:
            if st.button(
                "SUCCESSIVA →"
            ):
                st.session_state.scene_index += 1
                st.rerun()


def page_archive():
    if st.button(
        "← TORNA AL ROMANZO"
    ):
        st.session_state.page = "story"
        st.rerun()

    render_archive()


# ============================================================
# AVVIO
# ============================================================

if not st.session_state.archive_ready:
    initialize_archive_if_needed()

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
