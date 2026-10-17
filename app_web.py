
import os
import re
import json
import copy
import base64
import hashlib
import difflib
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

import streamlit as st
import requests
from openai import OpenAI
from docx import Document


# =========================================================
# TURING HOTEL - OFFICINA NARRATIVA
#
# VERSIONE:
# - RITRATTO DEL PERSONAGGIO IN ALTO A SINISTRA
# - FILONE PRINCIPALE: SFONDO BLU NOTTE
# - ADA ALONE: SFONDO VIOLA SCURO
# - SCRITTA ADA ALONE SOTTO IL RITRATTO
# - ARCHIVIO PERSONAGGI CON RITRATTO
# - 31 SCENE
# - CONSULENTE NARRATIVO CON 3 PROPOSTE
# - RISPONDI: UNA BATTUTA
# - GO ALONE: QUATTRO BATTUTE
# - MONOLOGO: DUE PENSIERI
# - OFFICINA LETTERARIA
# - CONOSCENZE SEPARATE
# - FOTO / VIDEO ASSOCIATI ALLA LINEA
# - ARCHIVIO PRIVATO GITHUB
# =========================================================

st.set_page_config(
    page_title="Turing Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"

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

SCENE_IDS = [x[0] for x in SCENES]
SCENE_NAMES = dict(SCENES)
ADA_START = SCENE_IDS.index("il_professore")

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
        "Indaga la libertà, la bellezza, "
        "l'identità e le relazioni umane."
    ),
    "Ada": (
        "Figlia del professor Elia Ferrante. "
        "Lavora al Turing Hotel. "
        "Ha una propria storia e una "
        "personalità indipendente."
    ),
    "Elia": (
        "Professor Elia Ferrante, padre di Ada, "
        "legato alla storia scientifica "
        "del Turing Hotel."
    ),
    "Luigi": (
        "Regista giunto al Turing Hotel "
        "per preparare un documentario "
        "sugli idrovolanti."
    ),
    "Adam": (
        "Personaggio coinvolto nelle vicende "
        "di Riccardo e Vittoria."
    ),
    "Riccardo": (
        "Marito di Vittoria. "
        "Il rapporto con Adam è complesso."
    ),
    "Vittoria": (
        "Moglie di Riccardo, coinvolta "
        "in una vicenda complessa con Adam."
    ),
}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}
MAX_UPLOAD = 20 * 1024 * 1024

ARCHIVE_PATH = "romanzo_web.json"
REFERENCE_PATH = (
    "references/TURING_HOTEL_ROMANZO_REFERENCE.txt"
)


# =========================================================
# CONFIGURAZIONE
# =========================================================

def secret(name, default=""):
    try:
        value = st.secrets.get(name)

        if value is not None and str(value).strip():
            return str(value)

    except Exception:
        pass

    return os.environ.get(name, default)


GH_TOKEN = secret("GITHUB_TOKEN")
GH_OWNER = secret("GITHUB_OWNER", "Neurocene")
GH_REPO = secret(
    "GITHUB_REPO", "turing-hotel-archivio"
)
GH_BRANCH = secret("GITHUB_BRANCH", "main")

MEDIA_TOKEN = secret(
    "GITHUB_MEDIA_TOKEN", GH_TOKEN
)
MEDIA_OWNER = secret(
    "GITHUB_MEDIA_OWNER", "Neurocene"
)
MEDIA_REPO = secret(
    "GITHUB_MEDIA_REPO", "Turing-Hotel"
)
MEDIA_BRANCH = secret(
    "GITHUB_MEDIA_BRANCH", "main"
)

OPENAI_KEY = secret("OPENAI_API_KEY")
OPENAI_MODEL = secret(
    "OPENAI_MODEL", "gpt-4.1-mini"
)

AI = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None


# =========================================================
# UTILITÀ
# =========================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def as_dict(x):
    return x if isinstance(x, dict) else {}


def as_list(x):
    return x if isinstance(x, list) else []


def merge_defaults(value, template):
    if not isinstance(value, dict):
        value = {}

    for key, default in template.items():
        if key not in value:
            value[key] = copy.deepcopy(default)

        elif isinstance(default, dict):
            value[key] = merge_defaults(
                value[key], default
            )

    return value


def json_text(x):
    return json.dumps(
        x, ensure_ascii=False, indent=2
    )


def parse_json(value):
    text = str(value).strip()
    text = re.sub(
        r"^```(?:json)?\s*", "",
        text, flags=re.IGNORECASE
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


def normalize(x):
    return re.sub(
        r"[^a-z0-9]+", "", str(x).casefold()
    )


def scene_number(sid):
    return SCENE_IDS.index(sid)


def text_diff(before, after):
    lines = difflib.unified_diff(
        str(before).splitlines(),
        str(after).splitlines(),
        fromfile="Precedente",
        tofile="Nuovo",
        lineterm="",
    )
    return "\n".join(lines) or "Nessuna differenza."


def ask_ai(instructions, payload):
    if AI is None:
        return "OPENAI_API_KEY non configurata."

    try:
        result = AI.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=json_text(payload),
        )
        return (result.output_text or "").strip()

    except Exception as exc:
        return "Errore OpenAI: " + str(exc)


# =========================================================
# GITHUB
# =========================================================

class GitHubError(Exception):
    pass


def github_api(
    method, owner, repo, branch,
    token, path, payload=None
):
    if not token:
        raise GitHubError(
            "Token GitHub non configurato."
        )

    url = (
        "https://api.github.com/repos/"
        + quote(owner, safe="")
        + "/"
        + quote(repo, safe="")
        + "/contents/"
        + quote(path, safe="/")
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            params=(
                {"ref": branch}
                if method == "GET" else None
            ),
            json=payload,
            timeout=90,
        )

    except requests.RequestException as exc:
        raise GitHubError(str(exc)) from exc

    if method == "GET" and response.status_code == 404:
        return None

    if not response.ok:
        raise GitHubError(
            f"GitHub HTTP {response.status_code}: "
            + response.text[:350]
        )

    return response.json()


def github_get(
    owner, repo, branch, token, path
):
    result = github_api(
        "GET", owner, repo,
        branch, token, path
    )

    if result is None:
        return None, None

    if result.get("encoding") != "base64":
        raise GitHubError(
            "File non leggibile via GitHub API."
        )

    return (
        base64.b64decode(result["content"]),
        result["sha"],
    )


def github_put(
    owner, repo, branch, token,
    path, raw, sha=None,
    message="Turing Hotel update"
):
    payload = {
        "message": message,
        "branch": branch,
        "content": base64.b64encode(
            raw
        ).decode("ascii"),
    }

    if sha:
        payload["sha"] = sha

    result = github_api(
        "PUT", owner, repo,
        branch, token, path, payload
    )

    new_sha = as_dict(
        result.get("content")
    ).get("sha")

    if not new_sha:
        raise GitHubError(
            "GitHub non ha confermato il salvataggio."
        )

    return new_sha


def read_archive():
    raw, sha = github_get(
        GH_OWNER, GH_REPO,
        GH_BRANCH, GH_TOKEN,
        ARCHIVE_PATH,
    )

    if raw is None:
        return None, None

    return json.loads(raw.decode("utf-8-sig")), sha


def write_archive(data, expected_sha):
    _, current_sha = github_get(
        GH_OWNER, GH_REPO,
        GH_BRANCH, GH_TOKEN,
        ARCHIVE_PATH,
    )

    if current_sha != expected_sha:
        raise GitHubError(
            "L'archivio è cambiato. "
            "Ricarica prima di salvare."
        )

    return github_put(
        GH_OWNER, GH_REPO,
        GH_BRANCH, GH_TOKEN,
        ARCHIVE_PATH,
        json_text(data).encode("utf-8"),
        sha=current_sha,
        message="Turing Hotel - archivio narrativo",
    )


# =========================================================
# DATI
# =========================================================

def empty_direction():
    return {
        "proposals": [],
        "active": None,
        "history": [],
        "evaluations": [],
        "last_question": "",
    }


def empty_narrative():
    return {
        "A": "",
        "B": "",
        "draft": "",
        "approved": "",
        "feedback": "",
        "review": "",
        "recommended": "",
        "approved_at": "",
        "status": "da_scrivere",
        "history": [],
        "visual": {
            "bible": "",
            "prompts": [],
            "source_approved_at": "",
        },
    }


def empty_parallel():
    return {
        "title": "",
        "location": "",
        "context": "",
        "context_approved": "",
        "cast": ["Ada"],
        "messages": [],
        "inner_messages": {},
        "monologue_topics": {},
        "direction": empty_direction(),
        "narrative": empty_narrative(),
        "knowledge_events": [],
    }


def empty_scene(sid):
    return {
        "id": sid,
        "title": SCENE_NAMES[sid],
        "author_context": "",
        "approved_context": "",
        "story_draft": "",
        "cast": copy.deepcopy(
            DEFAULT_CAST.get(sid, ["Noa", "Ada"])
        ),
        "ensemble_messages": [],
        "messages": {
            "Noa": [],
            "Ada": [],
        },
        "monologue_topics": {},
        "intro_contexts": {
            "Noa": (
                "Noa giunge al Turing Hotel "
                "e riflette sulla propria identità."
            ),
            "Ada": (
                "Ada parla con il professor Elia "
                "nel suo studio."
            ),
        },
        "narrative": {
            person: empty_narrative()
            for person in PEOPLE
        },
        "direction": empty_direction(),
        "knowledge_events": [],
        "ada_parallel": empty_parallel(),
    }


def default_state():
    return {
        "world": (
            "Turing Hotel: un albergo sul mare "
            "in cui si intrecciano intelligenze "
            "artificiali e vite umane."
        ),
        "agents": {
            p: {
                "profile": PROFILES[p],
                "memory": "",
                "profile_history": [],
            }
            for p in PEOPLE
        },
        "scenes": [
            empty_scene(sid)
            for sid in SCENE_IDS
        ],
        "ada_branch": {
            "enabled": False,
            "start_scene": None,
            "end_scene": None,
            "reunions": [],
        },
        "editorial_log": [],
        "editorial_proposals": [],
    }


def migrate_state(original):
    original = as_dict(original)
    result = merge_defaults(
        copy.deepcopy(original),
        default_state(),
    )

    previous_scenes = as_list(
        original.get("scenes")
    )

    rebuilt = []

    legacy = {
        "inizio": ["prologo"],
        "hall": ["reception"],
        "stanza": ["camera"],
        "reparto_nascite": ["nascite"],
    }

    for sid in SCENE_IDS:
        aliases = {
            normalize(x)
            for x in (
                [sid, SCENE_NAMES[sid]]
                + legacy.get(sid, [])
            )
        }

        found = None

        for old in previous_scenes:
            if not isinstance(old, dict):
                continue

            if (
                normalize(old.get("id", "")) in aliases
                or normalize(old.get("title", "")) in aliases
            ):
                found = old
                break

        scene = merge_defaults(
            copy.deepcopy(found) if found else {},
            empty_scene(sid),
        )

        scene["id"] = sid
        scene["title"] = SCENE_NAMES[sid]

        scene["direction"] = merge_defaults(
            as_dict(scene.get("direction")),
            empty_direction(),
        )

        scene["ada_parallel"] = merge_defaults(
            as_dict(scene.get("ada_parallel")),
            empty_parallel(),
        )

        parallel = scene["ada_parallel"]

        parallel["direction"] = merge_defaults(
            as_dict(parallel.get("direction")),
            empty_direction(),
        )

        parallel["narrative"] = merge_defaults(
            as_dict(parallel.get("narrative")),
            empty_narrative(),
        )

        parallel["cast"] = [
            p for p in as_list(parallel.get("cast"))
            if p in PEOPLE and p != "Noa"
        ]

        if "Ada" not in parallel["cast"]:
            parallel["cast"].insert(0, "Ada")

        scene["cast"] = [
            p for p in as_list(scene.get("cast"))
            if p in PEOPLE
        ]

        for person in PEOPLE:
            scene["narrative"][person] = (
                merge_defaults(
                    as_dict(
                        scene["narrative"].get(person)
                    ),
                    empty_narrative(),
                )
            )
            scene["messages"].setdefault(person, [])

        rebuilt.append(scene)

    result["scenes"] = rebuilt

    for person in PEOPLE:
        result["agents"][person] = merge_defaults(
            as_dict(result["agents"].get(person)),
            {
                "profile": PROFILES[person],
                "memory": "",
                "profile_history": [],
            },
        )

    return result


# =========================================================
# SESSIONE
# =========================================================

def initialize():
    if "book" in st.session_state:
        return

    try:
        loaded, sha = read_archive()

    except Exception as exc:
        st.error(str(exc))
        st.stop()

    st.session_state.book = (
        migrate_state(loaded)
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
    st.session_state.reference_text = ""
    st.session_state.reference_error = ""


initialize()
book = st.session_state.book


def save(change):
    backup = copy.deepcopy(book)

    try:
        change()

        if not st.session_state.archive_exists:
            raise GitHubError(
                "Archivio non inizializzato."
            )

        sha = write_archive(
            book, st.session_state.archive_sha
        )

        st.session_state.archive_sha = sha
        return True

    except Exception as exc:
        book.clear()
        book.update(backup)
        st.error("Salvataggio fallito: " + str(exc))
        return False


def reload_book():
    try:
        loaded, sha = read_archive()

        if loaded is None:
            st.error("Archivio non trovato.")
            return False

        book.clear()
        book.update(migrate_state(loaded))
        st.session_state.archive_sha = sha
        return True

    except Exception as exc:
        st.error(str(exc))
        return False


def scene_for(sid):
    return next(
        s for s in book["scenes"]
        if s["id"] == sid
    )


def log_change(
    category, subject,
    before, after,
    reason="", sid=""
):
    book["editorial_log"].append({
        "date": now(),
        "category": category,
        "subject": subject,
        "before": before,
        "after": after,
        "reason": reason,
        "scene_id": sid,
    })


# =========================================================
# IMMAGINI PERSONAGGI E STILI DEI FILONI
# =========================================================

def find_asset(filename):
    if not ASSETS.is_dir():
        return None

    direct = ASSETS / filename

    if direct.is_file():
        return direct

    for path in ASSETS.iterdir():
        if (
            path.is_file()
            and path.name.casefold() == filename.casefold()
        ):
            return path

    return None


def portrait_path(character):
    """
    Cerca l'immagine reale del personaggio.

    Nomi accettati:
    assets/Ada.jpg
    assets/ada.png
    assets/Elia.webp
    oppure:
    assets/characters/Ada.jpg
    characters/Ada.jpg

    Nessuna immagine estranea
    viene associata automaticamente.
    """

    folders = [
        ASSETS,
        ASSETS / "characters",
        ROOT / "characters",
    ]

    for folder in folders:
        if not folder.is_dir():
            continue

        for extension in (
            ".jpg", ".jpeg", ".png", ".webp"
        ):
            for path in folder.iterdir():
                if (
                    path.is_file()
                    and path.stem.casefold()
                    == character.casefold()
                    and path.suffix.casefold()
                    == extension
                ):
                    return path

    return None


def apply_theme(ada_alone=False):
    background = (
        "#171020"
        if ada_alone
        else "#0b1115"
    )

    sidebar = (
        "#21172d"
        if ada_alone
        else "#15212a"
    )

    card = (
        "#281d35"
        if ada_alone
        else "#1b2831"
    )

    accent = (
        "#c6a1f1"
        if ada_alone
        else "#cfaa80"
    )

    st.markdown(
        f"""
<style>
.stApp {{
    background: {background} !important;
    color: #ffffff !important;
}}

[data-testid="stSidebar"] {{
    background: {sidebar} !important;
}}

.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4 {{
    color: white !important;
}}

.stApp .stButton button,
.stApp .stFormSubmitButton button,
.stApp .stDownloadButton button {{
    background: {card} !important;
    color: white !important;
    border: 1px solid {accent} !important;
    min-height: 40px;
}}

.stApp .stButton button *,
.stApp .stFormSubmitButton button *,
.stApp .stDownloadButton button * {{
    color: white !important;
}}

.stApp input:not([type="checkbox"]):not([type="radio"]),
.stApp textarea {{
    background: #ffffff !important;
    color: #111111 !important;
    -webkit-text-fill-color: #111111 !important;
    caret-color: #111111 !important;
}}

.stApp [data-baseweb="select"] > div {{
    background: white !important;
    color: #111 !important;
}}

.stApp [data-baseweb="select"] span,
.stApp [data-baseweb="select"] input {{
    color: #111 !important;
}}

[data-baseweb="popover"] [role="option"],
[data-baseweb="popover"] [role="listbox"] {{
    background: white !important;
    color: #111 !important;
}}

.stApp [data-testid="stExpander"] {{
    background: {card} !important;
    border: 1px solid {accent}55 !important;
}}

.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary * {{
    color: white !important;
}}

.stApp [data-testid="stWidgetLabel"] p {{
    color: white !important;
}}

.stApp button[data-baseweb="tab"] p {{
    color: white !important;
}}

.stApp button[data-baseweb="tab"][aria-selected="true"] {{
    background: #eeeeee !important;
}}

.stApp button[data-baseweb="tab"][aria-selected="true"] p {{
    color: #111 !important;
}}

.story {{
    background: {card};
    padding: 20px;
    border-left: 3px solid {accent};
    font-family: Georgia, serif;
    line-height: 1.75;
    white-space: pre-wrap;
}}

.dialogue {{
    background: {card};
    padding: 13px;
    margin: 8px 0;
    border-left: 3px solid #91a5b5;
    white-space: pre-wrap;
}}

.reply {{
    background: #20382d;
    padding: 13px;
    margin: 8px 0;
    border-left: 3px solid #a8d0ae;
    white-space: pre-wrap;
}}

.portrait-label {{
    text-align: center;
    font-weight: 800;
    font-size: 0.88rem;
    letter-spacing: 0.14em;
    color: {accent};
    padding: 8px 2px;
}}

.ada-label {{
    text-align: center;
    background: #38234b;
    border: 1px solid #bc91e5;
    color: #e7ceff;
    border-radius: 6px;
    padding: 10px 5px;
    margin-top: 7px;
    font-size: 0.87rem;
    font-weight: 800;
    letter-spacing: 0.17em;
}}

.scene-banner {{
    padding: 14px;
    background: {card};
    border-left: 4px solid {accent};
    margin: 8px 0 20px 0;
}}

</style>
""",
        unsafe_allow_html=True,
    )


def render_character_header(
    character,
    title="",
    ada_alone=False,
    subtitle="",
):
    """
    Foto in alto a sinistra,
    titolo della pagina sulla destra.

    Se ADA ALONE:
    scritta immediatamente
    sotto la fotografia.
    """

    left, right = st.columns(
        [1, 4],
        gap="medium",
        vertical_alignment="top",
    )

    with left:
        portrait = portrait_path(character)

        if portrait:
            st.image(
                str(portrait),
                use_container_width=True,
            )

        else:
            st.markdown(
                '<div class="portrait-label">'
                + escape(character.upper())
                + "</div>",
                unsafe_allow_html=True,
            )

        if ada_alone:
            st.markdown(
                '<div class="ada-label">'
                "ADA ALONE"
                "</div>",
                unsafe_allow_html=True,
            )

        else:
            st.markdown(
                '<div class="portrait-label">'
                + escape(character.upper())
                + "</div>",
                unsafe_allow_html=True,
            )

    with right:
        st.title(title or character)

        if subtitle:
            st.caption(subtitle)

        if ada_alone:
            st.markdown(
                '<div class="scene-banner">'
                "<strong>FILONE PARALLELO DI ADA</strong>"
                "<p>La scena si svolge nello stesso "
                "intervallo di quella di Noa, "
                "ma in un luogo differente. "
                "Noa non è presente.</p>"
                "</div>",
                unsafe_allow_html=True,
            )


def render_story_text(text):
    st.markdown(
        '<div class="story">'
        + escape(str(text or ""))
        + "</div>",
        unsafe_allow_html=True,
    )


# =========================================================
# ROMANZO ORIGINALE
# =========================================================

def load_reference(force=False):
    if (
        st.session_state.reference_loaded
        and not force
    ):
        return

    try:
        raw, _ = github_get(
            GH_OWNER, GH_REPO,
            GH_BRANCH, GH_TOKEN,
            REFERENCE_PATH,
        )

        if raw:
            st.session_state.reference_text = (
                raw.decode("utf-8-sig")
            )
            st.session_state.reference_error = ""
        else:
            st.session_state.reference_text = ""
            st.session_state.reference_error = (
                "Prima bozza non trovata."
            )

    except Exception as exc:
        st.session_state.reference_text = ""
        st.session_state.reference_error = str(exc)

    st.session_state.reference_loaded = True


def reference_passages(
    characters, title="", limit=3
):
    load_reference()

    text = st.session_state.reference_text

    if not text:
        return []

    chunks = [
        text[i:i + 2500]
        for i in range(0, len(text), 2250)
    ]

    terms = [
        word.casefold()
        for word in characters
    ]

    terms.extend(
        word.casefold()
        for word in re.findall(
            r"[A-Za-zÀ-ÿ]{4,}", title
        )
    )

    ranked = []

    for index, chunk in enumerate(chunks):
        lower = chunk.casefold()
        score = sum(
            lower.count(word)
            for word in terms
        )

        if score:
            ranked.append(
                (score, index, chunk)
            )

    ranked.sort(
        key=lambda item: (-item[0], item[1])
    )

    return [
        item[2]
        for item in ranked[:limit]
    ]


# =========================================================
# FILONI NARRATIVI
# =========================================================

def ada_alone_at(sid):
    branch = book["ada_branch"]
    start = branch.get("start_scene")

    if start not in SCENE_IDS:
        return False

    if scene_number(sid) < scene_number(start):
        return False

    end = branch.get("end_scene")

    if (
        end in SCENE_IDS
        and scene_number(sid) >= scene_number(end)
    ):
        return False

    return True


def lane_for(scene, pov):
    if (
        pov == "Ada"
        and ada_alone_at(scene["id"])
    ):
        return "ada_alone"

    return "shared"


def lane_data(scene, lane):
    return (
        scene["ada_parallel"]
        if lane == "ada_alone"
        else scene
    )


def lane_cast(scene, lane):
    if lane == "ada_alone":
        cast = [
            p for p in as_list(
                scene["ada_parallel"].get("cast")
            )
            if p in PEOPLE and p != "Noa"
        ]

        if "Ada" not in cast:
            cast.insert(0, "Ada")

        return list(dict.fromkeys(cast))

    cast = [
        p for p in as_list(scene.get("cast"))
        if p in PEOPLE
    ]

    if ada_alone_at(scene["id"]):
        cast = [
            p for p in cast if p != "Ada"
        ]

        reserved = [
            p for p in lane_cast(
                scene, "ada_alone"
            )
            if p != "Ada"
        ]

        cast = [
            p for p in cast
            if p not in reserved
        ]

    return list(dict.fromkeys(cast))


def lane_messages(scene, lane):
    key = (
        "messages"
        if lane == "ada_alone"
        else "ensemble_messages"
    )

    return as_list(
        lane_data(scene, lane).get(key)
    )


def lane_context(scene, lane, narrator):
    if lane == "ada_alone":
        data = scene["ada_parallel"]

        return (
            data.get("context_approved")
            or data.get("context")
            or ""
        )

    if scene["id"] == "inizio":
        return scene["intro_contexts"].get(
            narrator, ""
        )

    return scene.get("approved_context", "")


def direction_data(scene, lane):
    data = lane_data(scene, lane)

    direction = merge_defaults(
        as_dict(data.get("direction")),
        empty_direction(),
    )

    data["direction"] = direction
    return direction


def active_direction(scene, lane):
    current = direction_data(
        scene, lane
    ).get("active")

    return (
        current
        if isinstance(current, dict)
        else None
    )


def start_ada_alone(sid):
    branch = book["ada_branch"]

    if branch.get("start_scene"):
        return False

    if scene_number(sid) < ADA_START:
        return False

    def change():
        branch["enabled"] = True
        branch["start_scene"] = sid
        branch["end_scene"] = None

        for next_sid in SCENE_IDS[
            scene_number(sid):
        ]:
            scene = scene_for(next_sid)
            parallel = scene["ada_parallel"]

            parallel["cast"] = [
                p for p in as_list(parallel.get("cast"))
                if p in PEOPLE and p != "Noa"
            ]

            if "Ada" not in parallel["cast"]:
                parallel["cast"].insert(0, "Ada")

            if not parallel.get("location"):
                parallel["location"] = (
                    "Luogo differente da quello di Noa."
                )

        log_change(
            "separazione narrativa",
            "ADA ALONE",
            "Storia condivisa",
            "Separazione dalla scena "
            + SCENE_NAMES[sid],
            "Approvazione autore",
            sid,
        )

    return save(change)


def reunite_ada(sid, description):
    branch = book["ada_branch"]
    start = branch.get("start_scene")

    if start not in SCENE_IDS:
        return False

    if scene_number(sid) <= scene_number(start):
        return False

    if branch.get("end_scene"):
        return False

    def change():
        branch["enabled"] = False
        branch["end_scene"] = sid
        branch["reunions"].append({
            "scene_id": sid,
            "description": description,
            "created_at": now(),
        })

        log_change(
            "ricongiungimento",
            "Ada e Noa",
            "Storie separate",
            "Storie ricongiunte",
            description,
            sid,
        )

    return save(change)


# =========================================================
# MEMORIA DEI PERSONAGGI
# =========================================================

def prior_knowledge(sid, character):
    result = []

    for prior_sid in SCENE_IDS:
        if prior_sid == sid:
            break

        scene = scene_for(prior_sid)

        if character in lane_cast(
            scene, "shared"
        ):
            record = as_dict(
                scene["narrative"].get(character)
            )

            approved = record.get(
                "approved", ""
            )

            if approved:
                result.append({
                    "scene": scene["title"],
                    "source": "shared",
                    "text": approved,
                })

        if ada_alone_at(prior_sid):
            if character in lane_cast(
                scene, "ada_alone"
            ):
                approved = scene[
                    "ada_parallel"
                ]["narrative"].get(
                    "approved", ""
                )

                if approved:
                    result.append({
                        "scene": scene["title"],
                        "source": "ada_alone",
                        "text": approved,
                    })

        for data in (
            scene,
            scene["ada_parallel"],
        ):
            for event in as_list(
                data.get("knowledge_events")
            ):
                if character in as_list(
                    event.get("recipients")
                ):
                    result.append({
                        "scene": scene["title"],
                        "source": "communication",
                        "text": event.get("content", ""),
                    })

    return result[-18:]


def agent_instructions(character):
    profile = book["agents"][character]

    return f"""
Sei {character}, personaggio di Turing Hotel.

PROFILO CANONICO:
{profile.get("profile", "")}

MEMORIA APPROVATA:
{profile.get("memory", "")}

REGOLE:
- Sei un personaggio, non un assistente.
- Non conosci automaticamente il futuro.
- Non leggi il pensiero altrui.
- Non conosci scene parallele non vissute.
- Noa non partecipa ad ADA ALONE.
- Non far apparire Noa in ADA ALONE.
- Un personaggio non può essere
  in due luoghi contemporaneamente.
- Il ricongiungimento non comunica
  automaticamente le esperienze di Ada.
- Il consulente narrativo orienta
  le circostanze, non prescrive le battute.
- La prima bozza è un riferimento.
- Il nuovo canone approvato prevale.
- Un dialogo generato non è
  automaticamente parte del canone.
"""


def agent_payload(
    scene, lane, character,
    request="", history=None
):
    if history is None:
        history = lane_messages(scene, lane)

    return {
        "scene": scene["title"],
        "timeline": scene_number(scene["id"]) + 1,
        "lane": lane,
        "character": character,
        "cast": lane_cast(scene, lane),
        "location": (
            scene["ada_parallel"].get("location", "")
            if lane == "ada_alone"
            else "Luogo della scena principale"
        ),
        "context": lane_context(
            scene, lane, character
        ),
        "direction": active_direction(
            scene, lane
        ),
        "request": request,
        "current_dialogue": history[-24:],
        "approved_knowledge": prior_knowledge(
            scene["id"], character
        ),
        "knowledge_rule": (
            "Le note editoriali non sono "
            "ricordi personali. Non importare "
            "informazioni dalla linea parallela "
            "a cui non hai partecipato."
        ),
    }


# =========================================================
# RISPOSTA SINGOLA E GO ALONE
# =========================================================

def generate_single_reply(
    scene, lane, character, prompt
):
    return ask_ai(
        agent_instructions(character)
        + """
MODALITÀ RISPONDI.

Pronuncia UNA SOLA battuta,
preferibilmente una o due frasi.

Nessun nome iniziale.
Nessuna didascalia.
Nessuna seconda battuta.
Nessuna prosecuzione autonoma.
""",
        agent_payload(
            scene, lane, character,
            request=prompt
        ),
    )


def append_dialogue(scene, lane, additions):
    key = (
        "messages"
        if lane == "ada_alone"
        else "ensemble_messages"
    )

    return save(
        lambda: lane_data(scene, lane)[key].extend(
            additions
        )
    )


def generate_go_turn(
    scene, lane, character, history
):
    return ask_ai(
        agent_instructions(character)
        + """
MODALITÀ GO ALONE.

Produci UNA SOLA battuta.
Non parlare al posto degli altri.
Non introdurre personaggi assenti.
Non imporre l'esito desiderato.
Nessuna didascalia.
""",
        agent_payload(
            scene, lane, character,
            history=history
        ),
    )


def run_go_alone(scene, lane, turns=4):
    cast = lane_cast(scene, lane)

    if len(cast) < 2:
        return (
            "GO ALONE richiede almeno "
            "due personaggi presenti."
        )

    history = copy.deepcopy(
        lane_messages(scene, lane)
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

    for number in range(turns):
        character = cast[
            (start + number) % len(cast)
        ]

        answer = generate_go_turn(
            scene, lane, character, history
        )

        if ai_failed(answer):
            return answer

        item = {
            "speaker": character,
            "text": answer,
            "origin": "go_alone",
            "created_at": now(),
        }

        generated.append(item)
        history.append(item)

    if append_dialogue(
        scene, lane, generated
    ):
        return ""

    return "Dialogo non salvato."


def generate_monologue(
    scene, lane, character, theme
):
    data = lane_data(scene, lane)

    if lane == "ada_alone":
        previous = as_list(
            data["inner_messages"].get(
                character, []
            )
        )
    else:
        previous = as_list(
            scene["messages"].get(
                character, []
            )
        )

    history = copy.deepcopy(previous)
    generated = []

    for number in (1, 2):
        response = ask_ai(
            agent_instructions(character)
            + f"""
MONOLOGO: PENSIERO {number} DI 2.

Scrivi un solo pensiero interiore
in prima persona e al presente.

Tema: {theme}

Il secondo approfondisce il primo.
Niente titoli, nomi o didascalie.
""",
            {
                "context": agent_payload(
                    scene, lane, character
                ),
                "previous_thoughts": history,
            },
        )

        if ai_failed(response):
            return response

        item = {
            "speaker": character,
            "text": response,
            "origin": "monologue",
            "created_at": now(),
        }

        history.append(item)
        generated.append(item)

    def change():
        data["monologue_topics"][character] = theme

        if lane == "ada_alone":
            data["inner_messages"].setdefault(
                character, []
            ).extend(generated)
        else:
            scene["messages"].setdefault(
                character, []
            ).extend(generated)

    if save(change):
        return ""

    return "Monologo non salvato."


# =========================================================
# CONSULENTE NARRATIVO
# =========================================================

DIRECTION_FIELDS = [
    "title",
    "situation",
    "tension",
    "opportunities",
    "limits",
    "dramatic_question",
]


def propose_directions(scene, lane, question):
    cast = lane_cast(scene, lane)

    return ask_ai(
        """
Sei il consulente narrativo di Turing Hotel.

Proponi esattamente TRE DIREZIONI
drammaturgiche differenti.

Ogni direzione deve descrivere:
- title
- situation
- tension
- opportunities
- limits
- dramatic_question

Le direzioni modificano le circostanze,
non obbligano i personaggi
a pronunciare specifiche battute.

Gli agenti conservano autonomia.

Se la linea è ADA ALONE:
- Noa è assente;
- la scena si svolge altrove;
- il tempo è parallelo alla scena di Noa;
- non trasferire conoscenze a Noa.

Restituisci soltanto JSON:

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
""",
        {
            "scene": scene["title"],
            "lane": lane,
            "cast": cast,
            "profiles": {
                p: book["agents"][p]["profile"]
                for p in cast
            },
            "question": question,
            "context": lane_context(
                scene, lane,
                "Ada" if lane == "ada_alone"
                else "Noa"
            ),
            "current_direction": active_direction(
                scene, lane
            ),
            "reference": reference_passages(
                cast, scene["title"]
            ),
        },
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

        cleaned = {
            field: str(
                item.get(field, "")
            ).strip()
            for field in DIRECTION_FIELDS
        }

        if not all(cleaned.values()):
            return None

        result.append(cleaned)

    return result


def approve_direction(
    scene, lane, proposal, reason
):
    storage = direction_data(scene, lane)
    previous = storage.get("active")

    approved = copy.deepcopy(proposal)
    approved["approved_at"] = now()
    approved["approved_reason"] = reason
    approved["start_turn"] = len(
        lane_messages(scene, lane)
    )

    def change():
        if previous:
            storage["history"].append(
                copy.deepcopy(previous)
            )

        storage["active"] = approved

        log_change(
            "direzione narrativa",
            scene["title"] + "/" + lane,
            json_text(previous) if previous else "",
            json_text(approved),
            reason,
            scene["id"],
        )

    return save(change)


def evaluate_direction(scene, lane):
    active = active_direction(scene, lane)

    if not active:
        return "Nessuna direzione attiva."

    start = active.get("start_turn", 0)

    if not isinstance(start, int):
        start = 0

    history = lane_messages(
        scene, lane
    )[start:]

    if not history:
        return (
            "Non ci sono conversazioni "
            "successive all'approvazione."
        )

    return ask_ai(
        """
Valuta come la conversazione
si è sviluppata rispetto
alla direzione narrativa approvata.

Analizza:
1. Che cosa è avvenuto.
2. Direzione seguita o trasformata.
3. Autonomia dei personaggi.
4. Eventuali contraddizioni.
5. Due possibili sviluppi.

Non modificare il canone.
""",
        {
            "scene": scene["title"],
            "lane": lane,
            "direction": active,
            "dialogue": history,
        },
    )


# =========================================================
# MEDIA DELLE SCENE
# =========================================================

def media_tag(pov, lane):
    return (
        "ada_alone"
        if lane == "ada_alone"
        else pov.lower()
    )


def media_prefix(scene, pov, lane):
    return (
        scene["id"] + "."
        + media_tag(pov, lane)
    )


def parse_media_name(filename, prefix):
    path = Path(filename)
    ext = path.suffix.casefold()

    if ext not in IMAGE_EXT | VIDEO_EXT:
        return None

    stem = path.stem.casefold()
    prefix = prefix.casefold()

    if stem == prefix and ext in IMAGE_EXT:
        return ("cover", 0)

    if not stem.startswith(prefix):
        return None

    tail = stem[len(prefix):]

    if not tail.isdigit():
        return None

    number = int(tail)

    if number < 1:
        return None

    return (
        (
            "video"
            if ext in VIDEO_EXT
            else "image"
        ),
        number,
    )


def local_media(scene, pov, lane):
    result = {
        "cover": [],
        "image": [],
        "video": [],
    }

    if not ASSETS.is_dir():
        return result

    prefix = media_prefix(
        scene, pov, lane
    )

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        parsed = parse_media_name(
            path.name, prefix
        )

        if parsed:
            kind, number = parsed
            result[kind].append((number, path))

    for kind in result:
        result[kind].sort(
            key=lambda item: (
                item[0],
                item[1].name.casefold(),
            )
        )

        result[kind] = [
            path for _, path in result[kind]
        ]

    return result


def remote_media_names():
    response = github_api(
        "GET",
        MEDIA_OWNER,
        MEDIA_REPO,
        MEDIA_BRANCH,
        MEDIA_TOKEN,
        "assets",
    )

    if not isinstance(response, list):
        return []

    return [
        x.get("name", "")
        for x in response
        if x.get("type") == "file"
    ]


def next_media_name(
    scene, pov, lane,
    extension, cover
):
    prefix = media_prefix(
        scene, pov, lane
    )

    existing = remote_media_names()

    if cover:
        filename = prefix + extension

        if any(
            name.casefold() == filename.casefold()
            for name in existing
        ):
            raise GitHubError(
                "La copertina esiste già. "
                "Non viene sovrascritta."
            )

        return filename

    kind = (
        "video"
        if extension in VIDEO_EXT
        else "image"
    )

    occupied = set()

    for filename in existing:
        parsed = parse_media_name(
            filename, prefix
        )

        if parsed and parsed[0] == kind:
            occupied.add(parsed[1])

    number = 1

    while number in occupied:
        number += 1

    return (
        prefix + str(number) + extension
    )


def upload_media(filename, raw):
    if len(raw) > MAX_UPLOAD:
        raise GitHubError(
            "File oltre 20 MiB. "
            "Usa GitHub manualmente "
            "o un archivio video esterno."
        )

    path = "assets/" + filename

    _, sha = github_get(
        MEDIA_OWNER,
        MEDIA_REPO,
        MEDIA_BRANCH,
        MEDIA_TOKEN,
        path,
    )

    if sha:
        raise GitHubError(
            "Il file esiste già "
            "e non sarà sovrascritto."
        )

    return github_put(
        MEDIA_OWNER,
        MEDIA_REPO,
        MEDIA_BRANCH,
        MEDIA_TOKEN,
        path,
        raw,
        message="Turing Hotel media: " + filename,
    )


def render_media(scene, pov, lane):
    st.markdown("---")
    st.subheader("Media della scena")

    prefix = media_prefix(
        scene, pov, lane
    )

    st.caption(
        "Prefisso media: " + prefix
    )

    media = local_media(
        scene, pov, lane
    )

    if media["cover"]:
        st.image(
            str(media["cover"][0]),
            use_container_width=True,
        )

        st.caption(
            "Copertina: "
            + media["cover"][0].name
        )

    entries = []

    for kind in ("image", "video"):
        for path in media[kind]:
            parsed = parse_media_name(
                path.name, prefix
            )

            if parsed:
                entries.append(
                    (parsed[1], kind, path)
                )

    entries.sort(
        key=lambda x: (
            x[0], x[2].name.casefold()
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
                if kind == "image":
                    st.image(
                        str(path),
                        use_container_width=True,
                    )
                else:
                    st.video(str(path))

                st.caption(path.name)

    with st.expander("CARICA FOTO O VIDEO"):
        st.warning(
            "I media caricati direttamente "
            "saranno pubblicati nel repository "
            f"{MEDIA_OWNER}/{MEDIA_REPO}. "
            "Non caricare materiale riservato."
        )

        uploaded = st.file_uploader(
            "Seleziona una foto o un video",
            type=[
                "jpg", "jpeg", "png", "webp",
                "mp4", "mov", "webm", "m4v",
            ],
            key=f"upload_{scene['id']}_{prefix}",
        )

        role = st.radio(
            "Associazione",
            ["Copertina", "Media aggiuntivo"],
            horizontal=True,
            key=f"role_{scene['id']}_{prefix}",
        )

        if uploaded is not None:
            extension = Path(
                uploaded.name
            ).suffix.casefold()

            cover = role == "Copertina"

            if cover and extension in VIDEO_EXT:
                st.warning(
                    "La copertina deve essere "
                    "un'immagine."
                )

            elif uploaded.size > MAX_UPLOAD:
                st.error(
                    "Il file supera 20 MiB."
                )

            else:
                try:
                    filename = next_media_name(
                        scene,
                        pov,
                        lane,
                        extension,
                        cover,
                    )

                    st.code(
                        "assets/" + filename
                    )

                    if st.button(
                        "ASSOCIA E CARICA SU GITHUB",
                        key=f"send_{scene['id']}_{prefix}",
                    ):
                        with st.spinner(
                            "Caricamento..."
                        ):
                            upload_media(
                                filename,
                                uploaded.getvalue(),
                            )

                        st.success(
                            "Media caricato. "
                            "Comparirà dopo il "
                            "riavvio della distribuzione."
                        )

                except Exception as exc:
                    st.error(str(exc))

    with st.expander("DIAGNOSTICA MEDIA"):
        st.code(prefix + ".jpg")

        for n in range(1, 4):
            st.write(
                "Foto: "
                + prefix + f"{n}.jpg"
            )

        for n in range(1, 3):
            st.write(
                "Video: "
                + prefix + f"{n}.mp4"
            )


# =========================================================
# ADA ALONE - PULSANTI
# =========================================================

def render_ada_control(scene, pov):
    if pov != "Ada":
        return

    sid = scene["id"]

    if scene_number(sid) < ADA_START:
        return

    branch = book["ada_branch"]
    start = branch.get("start_scene")
    end = branch.get("end_scene")

    st.markdown("---")
    st.subheader("Percorso narrativo di Ada")

    if not start:
        st.info(
            "Ada segue la storia condivisa. "
            "Puoi creare una linea parallela."
        )

        if st.button(
            "ADA ALONE — AVVIA STORIA PARALLELA",
            key=f"start_ada_{sid}",
            use_container_width=True,
        ):
            if start_ada_alone(sid):
                st.rerun()

    elif ada_alone_at(sid):
        st.success(
            "ADA ALONE ATTIVO. "
            "Noa non partecipa e "
            "non conosce questi eventi."
        )

        if sid != start and not end:
            with st.form(
                f"reunion_{sid}"
            ):
                description = st.text_area(
                    "Circostanze del ricongiungimento"
                )

                submitted = st.form_submit_button(
                    "RICONGIUNGI ADA E NOA"
                )

            if submitted:
                if not description.strip():
                    st.warning(
                        "Descrivi il ricongiungimento."
                    )

                elif reunite_ada(
                    sid, description
                ):
                    st.rerun()

    elif end in SCENE_IDS:
        if scene_number(sid) >= scene_number(end):
            st.info(
                "Ada è tornata nel filone "
                "condiviso da "
                + SCENE_NAMES[end]
                + "."
            )


# =========================================================
# CONTESTO DELLA SCENA
# =========================================================

def render_context(scene, lane, pov):
    sid = scene["id"]

    if lane == "ada_alone":
        data = scene["ada_parallel"]

        st.subheader("Contesto di ADA ALONE")

        title = st.text_input(
            "Titolo della scena parallela",
            value=data.get("title", ""),
            key=f"ada_title_{sid}",
        )

        location = st.text_input(
            "Luogo in cui si trova Ada",
            value=data.get("location", ""),
            key=f"ada_location_{sid}",
        )

        context = st.text_area(
            "Circostanze della scena",
            value=data.get("context", ""),
            height=160,
            key=f"ada_context_{sid}",
        )

        if st.button(
            "APPROVA CONTESTO ADA ALONE",
            key=f"approve_ada_context_{sid}",
        ):
            def change():
                previous = data.get(
                    "context_approved", ""
                )

                data["title"] = title
                data["location"] = location
                data["context"] = context
                data["context_approved"] = context

                if previous != context:
                    log_change(
                        "contesto ADA ALONE",
                        scene["title"],
                        previous,
                        context,
                        "Approvazione autore",
                        sid,
                    )

            if save(change):
                st.rerun()

        return

    if sid == "inizio":
        value = scene[
            "intro_contexts"
        ].get(pov, "")

        edited = st.text_area(
            "Contesto iniziale",
            value=value,
            key=f"intro_{pov}",
        )

        if st.button(
            "SALVA CONTESTO",
            key=f"save_intro_{pov}",
        ):
            if save(
                lambda: scene[
                    "intro_contexts"
                ].update({pov: edited})
            ):
                st.rerun()

    else:
        with st.expander(
            "CONTESTO DELLA SCENA CONDIVISA"
        ):
            text = st.text_area(
                "Contesto narrativo",
                value=scene.get(
                    "approved_context", ""
                ),
                height=160,
                key=f"context_{sid}",
            )

            if st.button(
                "APPROVA CONTESTO",
                key=f"approve_context_{sid}",
            ):
                def change():
                    previous = scene.get(
                        "approved_context", ""
                    )

                    scene["approved_context"] = text

                    if previous != text:
                        log_change(
                            "contesto condiviso",
                            scene["title"],
                            previous,
                            text,
                            "Approvazione autore",
                            sid,
                        )

                if save(change):
                    st.rerun()


# =========================================================
# CONSULENTE - INTERFACCIA
# =========================================================

def render_advisor(scene, lane):
    sid = scene["id"]
    direction = direction_data(scene, lane)
    active = active_direction(scene, lane)

    with st.expander(
        "CONSULENTE NARRATIVO E REGIA"
    ):
        if active:
            st.success(
                "DIREZIONE ATTIVA: "
                + active.get("title", "")
            )

            st.write(
                active.get("situation", "")
            )

        else:
            st.info("Nessuna direzione attiva.")

        question = st.text_area(
            "Quale sviluppo vuoi esplorare?",
            value=direction.get(
                "last_question", ""
            ),
            key=f"question_{sid}_{lane}",
        )

        if st.button(
            "PROPONI TRE DIREZIONI",
            key=f"propose_{sid}_{lane}",
            disabled=AI is None,
        ):
            with st.spinner(
                "Il consulente studia tre strade..."
            ):
                response = propose_directions(
                    scene, lane, question
                )

            if ai_failed(response):
                st.error(response)

            else:
                options = validate_directions(
                    parse_json(response)
                )

                if options is None:
                    st.error(
                        "Le direzioni non sono "
                        "in formato valido. Riprova."
                    )

                else:
                    def change():
                        direction["proposals"] = options
                        direction["last_question"] = question

                    if save(change):
                        st.rerun()

        proposals = as_list(
            direction.get("proposals")
        )

        if proposals:
            selected = st.radio(
                "Scegli una direzione",
                range(len(proposals)),
                format_func=lambda i: (
                    str(i + 1)
                    + ". "
                    + proposals[i]["title"]
                ),
                key=f"selection_{sid}_{lane}",
            )

            proposal = proposals[selected]

            signature = hashlib.sha256(
                json_text(proposal).encode("utf-8")
            ).hexdigest()[:12]

            with st.form(
                f"direction_{sid}_{lane}_"
                f"{selected}_{signature}"
            ):
                title = st.text_input(
                    "Titolo",
                    value=proposal["title"],
                )

                situation = st.text_area(
                    "Situazione",
                    value=proposal["situation"],
                )

                tension = st.text_area(
                    "Tensione",
                    value=proposal["tension"],
                )

                opportunities = st.text_area(
                    "Opportunità",
                    value=proposal["opportunities"],
                )

                limits = st.text_area(
                    "Limiti",
                    value=proposal["limits"],
                )

                dramatic_question = st.text_area(
                    "Domanda drammatica",
                    value=proposal["dramatic_question"],
                )

                reason = st.text_input(
                    "Motivazione"
                )

                approved = st.form_submit_button(
                    "APPROVA E ATTIVA DIREZIONE"
                )

            if approved:
                modified = {
                    "title": title.strip(),
                    "situation": situation.strip(),
                    "tension": tension.strip(),
                    "opportunities":
                        opportunities.strip(),
                    "limits": limits.strip(),
                    "dramatic_question":
                        dramatic_question.strip(),
                }

                if not all(modified.values()):
                    st.warning(
                        "Completa tutti i campi."
                    )

                elif approve_direction(
                    scene, lane, modified, reason
                ):
                    st.rerun()

        if active:
            st.markdown("---")

            if st.button(
                "VALUTA EVOLUZIONE",
                key=f"evaluate_{sid}_{lane}",
                disabled=AI is None,
            ):
                with st.spinner(
                    "Analisi della conversazione..."
                ):
                    review = evaluate_direction(
                        scene, lane
                    )

                if ai_failed(review):
                    st.error(review)

                else:
                    if save(
                        lambda: direction[
                            "evaluations"
                        ].append({
                            "date": now(),
                            "text": review,
                        })
                    ):
                        st.rerun()

            with st.expander(
                "DISATTIVA DIREZIONE"
            ):
                if st.button(
                    "DISATTIVA REGIA",
                    key=f"deactivate_{sid}_{lane}",
                ):
                    def change():
                        direction["history"].append(
                            copy.deepcopy(active)
                        )
                        direction["active"] = None

                        log_change(
                            "disattivazione regia",
                            scene["title"] + "/" + lane,
                            json_text(active),
                            "Nessuna direzione attiva",
                            "Scelta autore",
                            sid,
                        )

                    if save(change):
                        st.rerun()

        for item in reversed(
            as_list(direction.get("evaluations"))
        ):
            with st.expander(
                "Valutazione "
                + item.get("date", "")[:16]
            ):
                st.write(item.get("text", ""))


# =========================================================
# DIALOGHI
# =========================================================

def render_dialogues(scene, lane):
    sid = scene["id"]
    data = lane_data(scene, lane)
    current_cast = lane_cast(scene, lane)

    st.markdown("---")
    st.header("Personaggi e conversazioni")

    if lane == "ada_alone":
        st.info(
            "Questa conversazione appartiene "
            "soltanto al filone ADA ALONE. "
            "Noa non è presente."
        )

        shared_cast = [
            p for p in lane_cast(
                scene, "shared"
            )
            if p != "Ada"
        ]

        selectable = [
            p for p in PEOPLE
            if p != "Noa"
            and (
                p not in shared_cast
                or p in current_cast
            )
        ]

    else:
        selectable = PEOPLE.copy()

        if ada_alone_at(sid):
            reserved = lane_cast(
                scene, "ada_alone"
            )

            selectable = [
                p for p in selectable
                if p not in reserved
            ]

    selected_cast = st.multiselect(
        "PERSONAGGI PRESENTI",
        selectable,
        default=[
            p for p in current_cast
            if p in selectable
        ],
        key=f"cast_{sid}_{lane}",
    )

    if st.button(
        "SALVA PERSONAGGI PRESENTI",
        key=f"save_cast_{sid}_{lane}",
    ):
        if (
            lane == "ada_alone"
            and "Ada" not in selected_cast
        ):
            st.warning(
                "Ada deve essere presente "
                "nelle scene ADA ALONE."
            )

        else:
            def change():
                previous = current_cast.copy()
                data["cast"] = selected_cast

                log_change(
                    "personaggi presenti",
                    scene["title"] + "/" + lane,
                    ", ".join(previous),
                    ", ".join(selected_cast),
                    "Scelta dell'autore",
                    sid,
                )

            if save(change):
                st.rerun()

    cast = lane_cast(scene, lane)

    if not cast:
        st.warning(
            "Seleziona almeno un personaggio."
        )
        return

    mode = st.radio(
        "Modalità",
        ["Dialogo", "Monologo"],
        horizontal=True,
        key=f"mode_{sid}_{lane}",
    )

    if mode == "Dialogo":
        for entry in lane_messages(scene, lane):
            css = (
                "reply"
                if entry.get("origin") == "single_reply"
                else "dialogue"
            )

            st.markdown(
                f'<div class="{css}">'
                "<strong>"
                + escape(entry.get("speaker", "?"))
                + "</strong><div>"
                + escape(entry.get("text", ""))
                + "</div></div>",
                unsafe_allow_html=True,
            )

        st.markdown("### RISPONDI")

        with st.form(
            f"reply_form_{sid}_{lane}",
            clear_on_submit=True,
        ):
            speaking_as = st.selectbox(
                "Chi formula la domanda?",
                ["Autore", *cast],
            )

            responder = st.selectbox(
                "Chi risponde?",
                cast,
            )

            prompt = st.text_area(
                "Battuta o domanda"
            )

            submitted = st.form_submit_button(
                "RISPONDI — UNA BATTUTA",
                disabled=AI is None,
            )

        if submitted:
            if not prompt.strip():
                st.warning(
                    "Scrivi una domanda."
                )

            else:
                with st.spinner(
                    responder + " risponde..."
                ):
                    response = generate_single_reply(
                        scene,
                        lane,
                        responder,
                        prompt,
                    )

                if ai_failed(response):
                    st.error(response)

                else:
                    additions = [
                        {
                            "speaker": speaking_as,
                            "text": prompt.strip(),
                            "origin": "manual_prompt",
                            "created_at": now(),
                        },
                        {
                            "speaker": responder,
                            "text": response,
                            "origin": "single_reply",
                            "created_at": now(),
                        },
                    ]

                    if append_dialogue(
                        scene, lane, additions
                    ):
                        st.rerun()

        st.markdown("---")
        st.markdown("### GO ALONE")

        if st.button(
            "GO ALONE — QUATTRO BATTUTE",
            key=f"go_{sid}_{lane}",
            disabled=AI is None,
            use_container_width=True,
        ):
            with st.spinner(
                "I personaggi conversano..."
            ):
                result = run_go_alone(
                    scene, lane, 4
                )

            if result:
                st.error(result)
            else:
                st.rerun()

        with st.form(
            f"manual_{sid}_{lane}",
            clear_on_submit=True,
        ):
            speaker = st.selectbox(
                "Personaggio che parla",
                cast,
            )

            manual = st.text_area(
                "Battuta manuale"
            )

            add = st.form_submit_button(
                "AGGIUNGI BATTUTA"
            )

        if add and manual.strip():
            if append_dialogue(
                scene, lane,
                [{
                    "speaker": speaker,
                    "text": manual,
                    "origin": "manual",
                    "created_at": now(),
                }],
            ):
                st.rerun()

    else:
        character = st.selectbox(
            "Personaggio",
            cast,
            key=f"inner_{sid}_{lane}",
        )

        theme = st.text_area(
            "Tema del monologo",
            value=as_dict(
                data.get("monologue_topics")
            ).get(character, ""),
            key=f"theme_{sid}_{lane}_{character}",
        )

        if st.button(
            "GO ALONE — DUE PENSIERI",
            key=f"monologue_{sid}_{lane}_{character}",
            disabled=(
                AI is None or not theme.strip()
            ),
        ):
            with st.spinner(
                "Il personaggio riflette..."
            ):
                error = generate_monologue(
                    scene, lane, character, theme
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        thoughts = (
            data["inner_messages"].get(
                character, []
            )
            if lane == "ada_alone"
            else scene["messages"].get(
                character, []
            )
        )

        for entry in thoughts:
            render_story_text(
                entry.get("text", "")
            )

    with st.expander(
        "GESTIONE CONVERSAZIONE"
    ):
        confirm = st.checkbox(
            "Confermo la cancellazione",
            key=f"clear_confirm_{sid}_{lane}",
        )

        if st.button(
            "CANCELLA DIALOGO CORRENTE",
            key=f"clear_{sid}_{lane}",
            disabled=not confirm,
        ):
            field = (
                "messages"
                if lane == "ada_alone"
                else "ensemble_messages"
            )

            if save(
                lambda: data.update({field: []})
            ):
                st.rerun()


# =========================================================
# COMUNICAZIONI E CONOSCENZE
# =========================================================

def render_knowledge(scene, lane):
    sid = scene["id"]

    with st.expander(
        "COMUNICAZIONI E CONOSCENZE"
    ):
        st.caption(
            "Registra le informazioni "
            "effettivamente comunicate. "
            "Il ricongiungimento non basta."
        )

        with st.form(
            f"knowledge_{sid}_{lane}",
            clear_on_submit=True,
        ):
            content = st.text_area(
                "Informazione comunicata"
            )

            recipients = st.multiselect(
                "Chi la apprende?",
                lane_cast(scene, lane),
            )

            submitted = st.form_submit_button(
                "APPROVA COMUNICAZIONE"
            )

        if submitted:
            if not content.strip() or not recipients:
                st.warning(
                    "Indica informazione e destinatari."
                )

            else:
                event = {
                    "content": content.strip(),
                    "recipients": recipients,
                    "created_at": now(),
                }

                def change():
                    lane_data(
                        scene, lane
                    ).setdefault(
                        "knowledge_events", []
                    ).append(event)

                    log_change(
                        "comunicazione",
                        scene["title"] + "/" + lane,
                        "",
                        json_text(event),
                        "Approvazione autore",
                        sid,
                    )

                if save(change):
                    st.rerun()


# =========================================================
# OFFICINA LETTERARIA
# =========================================================

def narrative_record(scene, lane, narrator):
    if lane == "ada_alone":
        return scene[
            "ada_parallel"
        ]["narrative"]

    return scene["narrative"][narrator]


def transcript(scene, lane):
    return "\n\n".join(
        item.get("speaker", "?")
        + ": "
        + item.get("text", "")
        for item in lane_messages(scene, lane)
    )


def write_narrative(
    scene, lane, narrator,
    version, notes
):
    style = (
        "Essenziale, controllato, preciso."
        if version == "A"
        else
        "Evocativo, introspettivo, sensoriale."
    )

    return ask_ai(
        f"""
Sei uno scrittore letterario.

Scrivi una scena compiuta di Turing Hotel.

Narratore: {narrator}
Versione: {version}
Stile: {style}

Prima persona singolare.
Tempo presente.

Non scrivere un riassunto.
Rispetta contesto, dialoghi,
conoscenze consentite e canone.

Non attribuire a Noa eventi ADA ALONE
che non le sono stati comunicati.

La direzione narrativa orienta
il contesto, non obbliga il risultato.

Restituisci soltanto il racconto.
""",
        {
            "scene": scene["title"],
            "lane": lane,
            "narrator": narrator,
            "context": lane_context(
                scene, lane, narrator
            ),
            "direction": active_direction(
                scene, lane
            ),
            "dialogue": transcript(
                scene, lane
            ),
            "knowledge": prior_knowledge(
                scene["id"], narrator
            ),
            "notes": notes,
        },
    )


def critic_review(record):
    response = ask_ai(
        """
Confronta le versioni A e B
come critico letterario.

Scegli la migliore, motiva
e indica possibili revisioni.

Non approvare alcun testo.

Rispondi soltanto JSON:

{
 "preferenza": "A",
 "motivazione": "...",
 "riserve": "...",
 "alternativa": "..."
}
""",
        {
            "A": record["A"],
            "B": record["B"],
        },
    )

    if ai_failed(response):
        return None, response

    value = parse_json(response)

    if not isinstance(value, dict):
        return None, "Giudizio non valido."

    winner = str(
        value.get("preferenza", "")
    ).upper()

    if winner not in ("A", "B"):
        return None, "Preferenza non valida."

    report = (
        f"**Preferenza {winner}**\n\n"
        + str(value.get("motivazione", ""))
        + "\n\n**Riserve:** "
        + str(value.get("riserve", ""))
        + "\n\n**Revisione:** "
        + str(value.get("alternativa", ""))
    )

    return winner, report


def generate_visuals(record):
    answer = ask_ai(
        """
Sei un direttore della fotografia.

Dal testo approvato genera:
- una bibbia visiva;
- sei inquadrature;
- un prompt immagine ciascuna;
- un prompt video ciascuna.

Non inventare nuovi eventi.

Restituisci solo JSON:

{
 "bible": "...",
 "shots": [
  {
   "title": "...",
   "image_prompt": "...",
   "video_prompt": "..."
  }
 ]
}
""",
        {
            "text": record["approved"]
        },
    )

    if ai_failed(answer):
        return None

    return parse_json(answer)


def docx_bytes(title, content):
    document = Document()
    document.add_heading(title, 0)

    for paragraph in content.split("\n"):
        document.add_paragraph(paragraph)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def export_buttons(
    title, filename, content, key
):
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


def render_workshop(scene, lane, narrator):
    sid = scene["id"]
    record = narrative_record(
        scene, lane, narrator
    )

    st.markdown("---")
    st.header("Officina del romanzo")

    st.caption(
        "Narratore: "
        + narrator
        + " | "
        + (
            "ADA ALONE"
            if lane == "ada_alone"
            else "FILONE PRINCIPALE"
        )
    )

    notes = st.text_area(
        "Indicazioni letterarie",
        value=record.get("feedback", ""),
        key=f"writer_notes_{sid}_{lane}_{narrator}",
    )

    if st.button(
        "GENERA VERSIONI A E B",
        key=f"generate_{sid}_{lane}_{narrator}",
        disabled=AI is None,
    ):
        if not lane_messages(scene, lane):
            st.warning(
                "Registra prima una conversazione."
            )

        else:
            with st.spinner(
                "Scrittura delle versioni..."
            ):
                a = write_narrative(
                    scene, lane, narrator, "A", notes
                )

                b = (
                    write_narrative(
                        scene, lane, narrator, "B", notes
                    )
                    if not ai_failed(a) else ""
                )

            if ai_failed(a):
                st.error(a)
            elif ai_failed(b):
                st.error(b)
            else:
                def change():
                    record["A"] = a
                    record["B"] = b
                    record["feedback"] = notes
                    record["review"] = ""
                    record["recommended"] = ""

                if save(change):
                    st.rerun()

    if record["A"] or record["B"]:
        tab_a, tab_b = st.tabs([
            "VERSIONE A",
            "VERSIONE B",
        ])

        with tab_a:
            render_story_text(record["A"])

        with tab_b:
            render_story_text(record["B"])

        if st.button(
            "CHIEDI GIUDIZIO CRITICO",
            key=f"critic_{sid}_{lane}_{narrator}",
            disabled=AI is None,
        ):
            with st.spinner(
                "Valutazione letteraria..."
            ):
                winner, review = critic_review(
                    record
                )

            if not winner:
                st.error(review)
            elif save(
                lambda: record.update(
                    recommended=winner,
                    review=review,
                )
            ):
                st.rerun()

    if record.get("review"):
        st.markdown(record["review"])

    options = ["Bozza salvata"]

    if record["A"]:
        options.append("Versione A")

    if record["B"]:
        options.append("Versione B")

    selected = st.selectbox(
        "Testo da revisionare",
        options,
        key=f"version_{sid}_{lane}_{narrator}",
    )

    initial = (
        record["A"]
        if selected == "Versione A"
        else record["B"]
        if selected == "Versione B"
        else record["draft"]
    )

    editor_key = (
        f"editor_{sid}_{lane}_"
        f"{narrator}_{normalize(selected)}"
    )

    source_key = editor_key + "_source"

    if st.session_state.get(source_key) != initial:
        st.session_state[editor_key] = initial
        st.session_state[source_key] = initial

    edited = st.text_area(
        "Racconto",
        height=350,
        key=editor_key,
    )

    reason = st.text_input(
        "Motivazione",
        key=f"reason_{sid}_{lane}_{narrator}",
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA",
            key=f"draft_{sid}_{lane}_{narrator}",
        ):
            if save(
                lambda: record.update(
                    draft=edited,
                    status="bozza",
                )
            ):
                st.success("Bozza salvata.")

    with right:
        if st.button(
            "APPROVA E MEMORIZZA",
            key=f"approve_{sid}_{lane}_{narrator}",
            disabled=not edited.strip(),
        ):
            def change():
                old = record["approved"]

                if old and old != edited:
                    record["history"].append({
                        "text": old,
                        "replaced_at": now(),
                        "reason": reason,
                    })

                record["approved"] = edited
                record["draft"] = edited
                record["approved_at"] = now()
                record["status"] = "approvata"

                if old != edited:
                    log_change(
                        "scena approvata",
                        scene["title"]
                        + "/"
                        + lane
                        + "/"
                        + narrator,
                        old,
                        edited,
                        reason,
                        sid,
                    )

                    record["visual"][
                        "source_approved_at"
                    ] = ""

            if save(change):
                st.rerun()

    export_buttons(
        scene["title"],
        f"{sid}_{lane}_{narrator.lower()}",
        edited,
        f"export_{sid}_{lane}_{narrator}",
    )

    if record["approved"]:
        with st.expander(
            "TESTO APPROVATO"
        ):
            render_story_text(
                record["approved"]
            )

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
                    record["approved"],
                ),
                language="diff",
            )

    with st.expander(
        "TRASCRIZIONE"
    ):
        st.text(transcript(scene, lane))

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
                key=f"visual_{sid}_{lane}_{narrator}",
                disabled=AI is None,
            ):
                with st.spinner(
                    "Preparazione inquadrature..."
                ):
                    result = generate_visuals(
                        record
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

                    if save(change):
                        st.rerun()

            visual = record["visual"]

            if (
                visual.get("source_approved_at")
                == record["approved_at"]
            ):
                st.write(
                    visual.get("bible", "")
                )

                for i, shot in enumerate(
                    as_list(
                        visual.get("prompts")
                    ), 1
                ):
                    st.markdown(
                        f"**Inquadratura {i}**"
                    )

                    st.write(
                        shot.get("title", "")
                    )

                    st.code(
                        shot.get("image_prompt", "")
                    )

                    st.code(
                        shot.get("video_prompt", "")
                    )


# =========================================================
# ARCHIVIO PERSONAGGI CON FOTO IN ALTO
# =========================================================

def page_people():
    person = st.selectbox(
        "Seleziona personaggio",
        PEOPLE,
    )

    # Foto in alto a sinistra
    # su ogni profilo.
    apply_theme(False)

    render_character_header(
        person,
        title="Profilo di " + person,
        subtitle="Archivio canonico dei personaggi",
    )

    agent = book["agents"][person]

    st.markdown("---")
    st.subheader("Profilo approvato")

    st.write(agent["profile"])

    edited = st.text_area(
        "Modifica il profilo",
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
            old = agent["profile"]

            agent["profile_history"].append({
                "profile": old,
                "replaced_at": now(),
            })

            agent["profile"] = edited

            log_change(
                "profilo",
                person,
                old,
                edited,
                reason,
            )

        if save(change):
            st.rerun()

    with st.expander(
        "PRIMA BOZZA - BRANI PERTINENTI"
    ):
        for i, passage in enumerate(
            reference_passages(
                [person], limit=4
            ), 1
        ):
            st.markdown(
                f"**Passaggio {i}**"
            )
            st.text(passage)

    with st.expander(
        "CRONOLOGIA PROFILO"
    ):
        for item in reversed(
            as_list(
                agent.get("profile_history")
            )
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


# =========================================================
# ARCHIVIO SCENE
# =========================================================

def page_archive():
    apply_theme(False)

    st.title("Archivio scene approvate")

    total = 0

    for sid in SCENE_IDS:
        scene = scene_for(sid)

        for person in PEOPLE:
            record = as_dict(
                scene["narrative"].get(person)
            )

            text = record.get(
                "approved", ""
            )

            if not text:
                continue

            total += 1

            with st.expander(
                scene["title"]
                + " / "
                + person
                + " / principale"
            ):
                render_story_text(text)

                export_buttons(
                    scene["title"],
                    f"{sid}_{person.lower()}",
                    text,
                    f"archive_{sid}_{person}",
                )

        parallel_text = scene[
            "ada_parallel"
        ]["narrative"].get(
            "approved", ""
        )

        if parallel_text:
            total += 1

            title = (
                scene["ada_parallel"].get("title")
                or scene["title"]
            )

            with st.expander(
                title + " / ADA ALONE"
            ):
                st.markdown(
                    "**ADA ALONE**"
                )

                render_story_text(
                    parallel_text
                )

                export_buttons(
                    title,
                    f"{sid}_ada_alone",
                    parallel_text,
                    f"archive_ada_{sid}",
                )

    if total == 0:
        st.info(
            "Nessuna scena approvata."
        )


# =========================================================
# REGISTRO EDITORIALE
# =========================================================

def page_editorial():
    apply_theme(False)

    st.title("Registro editoriale")

    tab_a, tab_b = st.tabs([
        "MODIFICHE APPROVATE",
        "PROPOSTE",
    ])

    with tab_a:
        for item in reversed(
            book["editorial_log"]
        ):
            with st.expander(
                item.get("date", "")[:10]
                + " / "
                + item.get("subject", "")
            ):
                st.write(
                    item.get("category", "")
                )

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

    with tab_b:
        with st.form(
            "proposal_form",
            clear_on_submit=True,
        ):
            subject = st.text_input(
                "Oggetto"
            )

            before = st.text_area(
                "Situazione precedente"
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
                book["editorial_proposals"].append({
                    "subject": subject,
                    "before": before,
                    "after": after,
                    "reason": reason,
                    "date": now(),
                    "status": "proposta",
                })

            if save(change):
                st.rerun()

        for item in reversed(
            book["editorial_proposals"]
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


# =========================================================
# INGRESSO E SCELTA DELLA STORIA
# =========================================================

def page_entrance():
    apply_theme(False)

    hotel = find_asset("TuringHotel.jpg")

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
    apply_theme(False)

    st.title("Scegli una storia")

    columns = st.columns(2)

    for column, person in zip(
        columns, PROTAGONISTS
    ):
        with column:
            portrait = portrait_path(person)

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


# =========================================================
# SIDEBAR
# =========================================================

def render_sidebar():
    index = st.session_state.scene_index
    pov = st.session_state.pov

    st.sidebar.title("TURING HOTEL")

    selected = st.sidebar.selectbox(
        "SCENA",
        SCENE_IDS,
        index=index,
        format_func=lambda sid: (
            f"{scene_number(sid) + 1:02d}"
            f" — {SCENE_NAMES[sid]}"
        ),
        key=f"scene_nav_{index}_{pov}",
    )

    if selected != SCENE_IDS[index]:
        st.session_state.scene_index = (
            scene_number(selected)
        )
        st.rerun()

    st.sidebar.caption(
        f"Scena {index + 1} di 31"
    )

    st.sidebar.markdown("---")

    for label, destination in [
        ("ARCHIVIO SCENE", "archive"),
        ("ARCHIVIO PERSONAGGI", "people"),
        ("REGISTRO EDITORIALE", "editorial"),
        ("CAMBIA STORIA", "characters"),
    ]:
        if st.sidebar.button(
            label,
            key="nav_" + destination,
            use_container_width=True,
        ):
            st.session_state.page = destination
            st.rerun()

    with st.sidebar.expander("PRIMA BOZZA"):
        load_reference()

        if st.session_state.reference_text:
            st.success(
                "Romanzo originale collegato."
            )

            st.caption(
                f"{len(st.session_state.reference_text):,}"
                " caratteri"
            )

        else:
            st.warning(
                st.session_state.reference_error
                or "Reference non disponibile."
            )

        st.code(REFERENCE_PATH)

        if st.button(
            "RICARICA ROMANZO ORIGINALE",
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
            if reload_book():
                st.rerun()

        st.download_button(
            "SCARICA BACKUP",
            json_text(book).encode("utf-8"),
            file_name="turing_hotel_backup.json",
            mime="application/json",
        )


# =========================================================
# PAGINA DELLA SCENA
# =========================================================

def page_story():
    pov = st.session_state.pov

    index = max(
        0,
        min(
            st.session_state.scene_index,
            len(SCENE_IDS) - 1,
        ),
    )

    st.session_state.scene_index = index

    sid = SCENE_IDS[index]
    scene = scene_for(sid)

    lane = (
        "ada_alone"
        if (
            pov == "Ada"
            and ada_alone_at(sid)
        )
        else "shared"
    )

    # SFONDO SPECIFICO DEL FILONE
    apply_theme(
        ada_alone=(lane == "ada_alone")
    )

    render_sidebar()

    if lane == "ada_alone":
        title = (
            scene["ada_parallel"].get("title")
            or scene["title"]
        )
    else:
        title = scene["title"]

    # FOTO DEL PERSONAGGIO
    # SEMPRE IN ALTO A SINISTRA
    # + ADA ALONE SUBITO SOTTO
    render_character_header(
        character=pov,
        title=title,
        ada_alone=(
            lane == "ada_alone"
        ),
        subtitle=(
            f"Scena {index + 1} di 31"
            + " — "
            + (
                "Filone parallelo"
                if lane == "ada_alone"
                else "Filone principale"
            )
        ),
    )

    render_ada_control(
        scene, pov
    )

    # Al primo clic su ADA ALONE
    # la pagina viene ricaricata;
    # lo sfondo diventa viola
    # automaticamente.

    render_media(
        scene, pov, lane
    )

    render_context(
        scene, lane, pov
    )

    render_advisor(
        scene, lane
    )

    render_dialogues(
        scene, lane
    )

    render_knowledge(
        scene, lane
    )

    if lane == "ada_alone":
        narrator = "Ada"

    else:
        narrators = lane_cast(
            scene, lane
        ) or [pov]

        narrator = st.selectbox(
            "PUNTO DI VISTA DEL RACCONTO",
            narrators,
            index=(
                narrators.index(pov)
                if pov in narrators
                else 0
            ),
            key=f"narrator_{sid}_{pov}",
        )

    render_workshop(
        scene, lane, narrator
    )

    st.markdown("---")

    left, _, right = st.columns(
        [1, 3, 1]
    )

    with left:
        if index > 0:
            if st.button(
                "← PRECEDENTE"
            ):
                st.session_state.scene_index -= 1
                st.rerun()

    with right:
        if index < len(SCENE_IDS) - 1:
            if st.button(
                "SUCCESSIVA →"
            ):
                st.session_state.scene_index += 1
                st.rerun()


# =========================================================
# ARCHIVIO NON TROVATO
# =========================================================

if not st.session_state.archive_exists:
    st.title("Inizializzazione archivio")

    st.warning(
        "Non è stato trovato romanzo_web.json "
        "nel repository privato. "
        "Non creare un archivio nuovo "
        "se quello originale deve già esistere."
    )

    confirmed = st.checkbox(
        "Confermo che voglio creare "
        "un archivio nuovo"
    )

    if st.button(
        "CREA ARCHIVIO",
        disabled=not confirmed,
    ):
        try:
            sha = write_archive(
                book, None
            )

            st.session_state.archive_sha = sha
            st.session_state.archive_exists = True

            st.rerun()

        except Exception as exc:
            st.error(str(exc))

    st.stop()


# =========================================================
# NAVIGAZIONE
# =========================================================

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
