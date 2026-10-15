
import streamlit as st
import json
import os
import re
import copy
import base64
import requests
import difflib

from pathlib import Path
from io import BytesIO
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

from openai import OpenAI
from docx import Document


# ============================================================
# TURING HOTEL — OFFICINA DEL ROMANZO
# 31 SCENE + AGENTI SECONDARI + REGISTRO EDITORIALE
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

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}

PROTAGONISTS = ("Noa", "Ada")
PEOPLE = (
    "Noa", "Ada", "Elia",
    "Luigi", "Adam", "Riccardo", "Vittoria"
)

REFERENCE_PATH = (
    "references/TURING_HOTEL_ROMANZO_REFERENCE.txt"
)

REMOTE_FILE = "romanzo_web.json"


# ============================================================
# SCENE
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
    ("il_bagno", "Il bagno")
]

SCENE_ORDER = [sid for sid, _ in SCENES]
SCENE_NAMES = dict(SCENES)

OLD_NAMES = {
    "inizio": ["prologo"],
    "hall": ["reception"],
    "stanza": ["camera"],
    "funerale": ["funerale"],
    "matrimonio": ["matrimonio"],
    "reparto_nascite": ["repartonascite", "nascite"],
    "ritorno": ["ritorno"]
}

DEFAULT_CAST = {
    "inizio": ["Noa", "Ada", "Elia"],
    "il_professore": ["Elia", "Ada"],
    "il_trio": ["Adam", "Riccardo", "Vittoria"],
    "adam": ["Adam", "Riccardo", "Vittoria"],
    "riccardo_e_vittoria": ["Riccardo", "Vittoria"],
    "adam_e_vittoria": ["Adam", "Vittoria"],
    "luigi_se_ne_va": ["Luigi"]
}

INTRO_CONTEXTS = {
    "Noa": (
        "Noa cammina lungo il viale verso il Turing Hotel. "
        "È sola con i pensieri. La scena termina "
        "con l'incontro con Ada."
    ),
    "Ada": (
        "Ada conversa con suo padre, il professor Elia, "
        "nel suo studio al Turing Hotel. "
        "La scena termina quando Noa arriva alla reception."
    )
}

PROFILE_SEEDS = {
    "Noa": (
        "Agente artificiale relazionale. Nella prima bozza "
        "riflette sulla bellezza, sull'autonomia e "
        "sulla libertà di scegliere."
    ),
    "Ada": (
        "Figlia del professor Elia. "
        "Il profilo definitivo deve essere ricavato "
        "dal romanzo e dalle nuove scene approvate."
    ),
    "Elia": (
        "Professor Elia Ferrante, legato al passato "
        "scientifico del Turing Hotel. È il padre di Ada."
    ),
    "Luigi": (
        "Regista e narratore. Arriva al Turing Hotel "
        "per un documentario sugli idrovolanti."
    ),
    "Adam": (
        "Personaggio presente nella prima bozza "
        "nei capitoli che coinvolgono Riccardo e Vittoria. "
        "Carattere e vincoli vanno verificati nel testo."
    ),
    "Riccardo": (
        "Marito di Vittoria nella prima bozza. "
        "Il suo rapporto con Adam è parte della vicenda."
    ),
    "Vittoria": (
        "Moglie di Riccardo nella prima bozza. "
        "Il suo rapporto con Adam è parte della vicenda."
    )
}


# ============================================================
# UTILITÀ
# ============================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def norm(value):
    return re.sub(
        r"[^a-z0-9]+", "",
        str(value).casefold()
    )


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def secret(name, default=""):
    try:
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(name, default)


def merge_defaults(data, template):
    if not isinstance(data, dict):
        data = {}

    for key, value in template.items():
        if key not in data:
            data[key] = copy.deepcopy(value)
        elif isinstance(value, dict):
            data[key] = merge_defaults(data[key], value)

    return data


def find_asset(name):
    if not ASSETS.is_dir():
        return None

    for path in ASSETS.iterdir():
        if (
            path.is_file()
            and path.name.casefold() == name.casefold()
        ):
            return path

    return None


def ai_error(text):
    return (
        not isinstance(text, str)
        or not text.strip()
        or text.startswith("Errore OpenAI:")
        or text.startswith("OPENAI_API_KEY")
    )


def parse_ai_json(text):
    content = str(text).strip()
    content = re.sub(
        r"^```(?:json)?\s*",
        "",
        content,
        flags=re.I
    )
    content = re.sub(r"\s*```$", "", content)

    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None


# ============================================================
# SECRETS E OPENAI
# ============================================================

OPENAI_KEY = secret("OPENAI_API_KEY")
OPENAI_MODEL = secret("OPENAI_MODEL", "gpt-4.1-mini")

GH_TOKEN = secret("GITHUB_TOKEN")
GH_OWNER = secret("GITHUB_OWNER")
GH_REPO = secret("GITHUB_REPO")
GH_BRANCH = secret("GITHUB_BRANCH", "main")

client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None


def ask_ai(instructions, data):
    if not client:
        return "OPENAI_API_KEY non configurata."

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=json.dumps(data, ensure_ascii=False)
        )
        return response.output_text.strip()
    except Exception as exc:
        return f"Errore OpenAI: {exc}"


# ============================================================
# CONTRASTO
# ============================================================

st.markdown("""
<style>
.stApp {
    background: #090c0e !important;
    color: white !important;
}
[data-testid="stSidebar"] {
    background: #101519 !important;
    color: white !important;
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
.stApp [data-testid="stCaptionContainer"] p {
    color: #dce1e4 !important;
}
.stApp .stButton button,
.stApp .stFormSubmitButton button,
.stApp .stDownloadButton button {
    background: #1c252c !important;
    color: white !important;
    border: 1px solid #84919b !important;
    min-height: 40px;
}
.stApp .stButton button *,
.stApp .stFormSubmitButton button *,
.stApp .stDownloadButton button * {
    color: white !important;
}
.stApp .stButton button:hover,
.stApp .stDownloadButton button:hover {
    background: #374550 !important;
    border-color: #c6a879 !important;
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
.stApp [data-baseweb="select"] input,
.stApp [data-baseweb="select"] svg {
    color: #111 !important;
    fill: #111 !important;
}
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"] {
    background: white !important;
    color: #111 !important;
}
[data-baseweb="popover"] [role="option"] * {
    color: #111 !important;
}
.stApp button[data-baseweb="tab"] {
    background: #1c252c !important;
    color: white !important;
}
.stApp button[data-baseweb="tab"] p {
    color: inherit !important;
}
.stApp button[data-baseweb="tab"][aria-selected="true"] {
    background: white !important;
    color: #111 !important;
}
.stApp [data-testid="stExpander"] {
    background: #171e23 !important;
    border: 1px solid #485660 !important;
}
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary * {
    color: white !important;
}
.stApp pre {
    background: #171e23 !important;
}
.stApp pre code {
    color: white !important;
}
.story-text {
    color: #fff;
    background: #171e23;
    border-left: 3px solid #c6a879;
    padding: 20px;
    white-space: pre-wrap;
    font-family: Georgia, serif;
    font-size: 1.06rem;
    line-height: 1.75;
}
.chat-box {
    background: #1c262e;
    color: white;
    border-left: 3px solid #8ba0ad;
    padding: 13px;
    margin: 8px 0;
    white-space: pre-wrap;
}
.thought-box {
    background: #29221e;
    color: white;
    border-left: 3px solid #c6a879;
    padding: 13px;
    margin: 8px 0;
    white-space: pre-wrap;
}
</style>
""", unsafe_allow_html=True)


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
    if not all([
        GH_TOKEN, GH_OWNER, GH_REPO, GH_BRANCH
    ]):
        raise ArchiveError(
            "Secrets GitHub mancanti."
        )

    try:
        response = requests.request(
            method,
            github_url(path),
            headers={
                "Authorization": f"Bearer {GH_TOKEN}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            },
            params=(
                {"ref": GH_BRANCH}
                if method == "GET"
                else None
            ),
            json=payload,
            timeout=40
        )
    except requests.RequestException as exc:
        raise ArchiveError(str(exc)) from exc

    if response.status_code == 404:
        if method == "GET":
            return None
        raise ArchiveError(
            "File o repository GitHub non trovato."
        )

    if response.status_code in (409, 422):
        raise ArchiveError(
            "Conflitto di salvataggio: "
            "ricarica l'archivio."
        )

    if not response.ok:
        raise ArchiveError(
            f"GitHub HTTP {response.status_code}: "
            f"{response.text[:350]}"
        )

    return response.json()


def read_github_file(path):
    response = github_request("GET", path)

    if response is None:
        return None, None

    try:
        content = base64.b64decode(
            response["content"]
        ).decode("utf-8-sig")

        return content, response["sha"]

    except (ValueError, KeyError) as exc:
        raise ArchiveError(
            f"File non leggibile: {path}"
        ) from exc


def save_github_json(data, expected_sha):
    _, current_sha = read_github_file(
        REMOTE_FILE
    )

    if expected_sha != current_sha:
        raise ArchiveError(
            "Un'altra sessione ha aggiornato "
            "il romanzo. Ricarica prima."
        )

    payload = {
        "message": "Turing Hotel — " + now(),
        "branch": GH_BRANCH,
        "content": base64.b64encode(
            json.dumps(
                data, ensure_ascii=False, indent=2
            ).encode("utf-8")
        ).decode("ascii")
    }

    if current_sha:
        payload["sha"] = current_sha

    result = github_request(
        "PUT", REMOTE_FILE, payload
    )

    sha = as_dict(
        result.get("content")
    ).get("sha")

    if not sha:
        raise ArchiveError(
            "Salvataggio GitHub non confermato."
        )

    return sha


# ============================================================
# MODELLO DATI E MIGRAZIONE
# ============================================================

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
            "source_approved_at": ""
        }
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
            "Noa": [], "Ada": []
        },
        "diary": {
            "Noa": "", "Ada": ""
        },
        "narrative": {
            "person": blank_narrative()
            for person in PEOPLE
        },
        "monologue_topics": {
            person: "" for person in PEOPLE
        },
        "cast": copy.deepcopy(
            DEFAULT_CAST.get(
                sid, ["Noa", "Ada"]
            )
        ),
        "ensemble_messages": [],
        "change_proposals": [],
        "decision": {
            "Noa": "", "Ada": ""
        },
        "intro_contexts": copy.deepcopy(
            INTRO_CONTEXTS
        )
    }


def default_state():
    return {
        "world": (
            "Il Turing Hotel è un antico albergo "
            "sul mare Adriatico."
        ),
        "agents": {
            person: {
                "profile": PROFILE_SEEDS[person],
                "memory": "",
                "profile_history": []
            }
            for person in PEOPLE
        },
        "scenes": [
            blank_scene(sid)
            for sid in SCENE_ORDER
        ],
        "editorial_log": [],
        "editorial_proposals": []
    }


def aliases_for(sid):
    return {
        norm(item)
        for item in (
            sid,
            SCENE_NAMES[sid],
            *OLD_NAMES.get(sid, [])
        )
    }


def migrate(old):
    old = as_dict(old)
    state = merge_defaults(
        copy.deepcopy(old),
        default_state()
    )

    originals = as_list(
        old.get("scenes")
    )

    rebuilt = []

    for sid in SCENE_ORDER:
        aliases = aliases_for(sid)
        previous = None

        for candidate in originals:
            if not isinstance(candidate, dict):
                continue

            if (
                norm(candidate.get("id", "")) in aliases
                or norm(candidate.get("title", "")) in aliases
            ):
                previous = candidate
                break

        scene = merge_defaults(
            copy.deepcopy(previous)
            if previous is not None
            else {},
            blank_scene(sid)
        )

        scene["id"] = sid
        scene["title"] = SCENE_NAMES[sid]

        scene["cast"] = [
            person
            for person in as_list(scene.get("cast"))
            if person in PEOPLE
        ]

        if not scene["cast"]:
            scene["cast"] = copy.deepcopy(
                DEFAULT_CAST.get(sid, ["Noa", "Ada"])
            )

        for person in PEOPLE:
            scene["narrative"][person] = (
                merge_defaults(
                    as_dict(
                        scene["narrative"].get(person)
                    ),
                    blank_narrative()
                )
            )

        rebuilt.append(scene)

    state["scenes"] = rebuilt

    for person in PEOPLE:
        state["agents"][person] = (
            merge_defaults(
                as_dict(
                    state["agents"].get(person)
                ),
                {
                    "profile": PROFILE_SEEDS[person],
                    "memory": "",
                    "profile_history": []
                }
            )
        )

    return state


# ============================================================
# STATO E SALVATAGGIO
# ============================================================

def load_archive():
    raw, sha = read_github_file(
        REMOTE_FILE
    )

    if raw is None:
        return None, None

    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ArchiveError(
            "Archivio JSON non valido."
        ) from exc

    return migrate(data), sha


def initialize():
    if "book_state" in st.session_state:
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
    st.session_state.archive_exists = (
        loaded is not None
    )

    st.session_state.page = "entrance"
    st.session_state.pov = None
    st.session_state.scene_index = 0

    st.session_state.reference_text = None
    st.session_state.reference_error = ""
    st.session_state.reference_loaded = False


initialize()
state = st.session_state.book_state


def commit(change):
    before = copy.deepcopy(state)

    try:
        change()

        if not st.session_state.archive_exists:
            raise ArchiveError(
                "Archivio non inizializzato."
            )

        st.session_state.archive_sha = (
            save_github_json(
                state,
                st.session_state.archive_sha
            )
        )

        return True

    except Exception as exc:
        state.clear()
        state.update(before)
        st.error(
            f"Impossibile salvare: {exc}"
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

    except ArchiveError as exc:
        st.error(str(exc))
        return False


if not st.session_state.archive_exists:
    st.warning(
        "L'archivio romanzo_web.json "
        "non esiste ancora."
    )

    confirmed = st.checkbox(
        "Confermo la creazione "
        "dell'archivio privato"
    )

    if st.button(
        "INIZIALIZZA ARCHIVIO",
        disabled=not confirmed
    ):
        try:
            sha = save_github_json(
                state, None
            )
            st.session_state.archive_sha = sha
            st.session_state.archive_exists = True
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.stop()


# ============================================================
# PRIMA BOZZA: CARICAMENTO UNA VOLTA PER SESSIONE
# ============================================================

def load_reference(force=False):
    if (
        st.session_state.reference_loaded
        and not force
    ):
        return

    try:
        text, sha = read_github_file(
            REFERENCE_PATH
        )

        st.session_state.reference_text = text
        st.session_state.reference_sha = sha
        st.session_state.reference_error = (
            "" if text is not None
            else "Romanzo TXT non trovato."
        )

    except Exception as exc:
        st.session_state.reference_text = None
        st.session_state.reference_error = str(exc)

    st.session_state.reference_loaded = True


def reference_chunks():
    """
    Divide la prima bozza in passaggi sovrapposti.

    Ricerca leggera senza database esterno.
    Non invia l'intero romanzo al modello.
    """
    load_reference()

    text = st.session_state.reference_text or ""

    if not text:
        return []

    size = 2600
    overlap = 250
    step = size - overlap

    return [
        text[start:start + size]
        for start in range(
            0, len(text), step
        )
    ]


def relevant_reference(people, scene_title="", limit=5):
    chunks = reference_chunks()

    if not chunks:
        return []

    terms = []

    for person in people:
        terms.append(person.casefold())

    for word in re.findall(
        r"[A-Za-zÀ-ÿ]{4,}",
        scene_title
    ):
        if word.casefold() not in (
            "della", "delle", "degli", "prima"
        ):
            terms.append(word.casefold())

    scored = []

    for index, chunk in enumerate(chunks):
        lower = chunk.casefold()

        score = sum(
            lower.count(term) * (
                4 if term in [
                    p.casefold() for p in people
                ] else 1
            )
            for term in terms
        )

        if score:
            scored.append(
                (score, index, chunk)
            )

    scored.sort(
        key=lambda item: (-item[0], item[1])
    )

    return [
        {
            "chunk": index + 1,
            "text": chunk
        }
        for _, index, chunk
        in scored[:limit]
    ]


# ============================================================
# SCENE E CANONE
# ============================================================

def get_scene(sid):
    return next(
        scene for scene in state["scenes"]
        if scene["id"] == sid
    )


def approved_before(sid, person):
    result = []

    for candidate in SCENE_ORDER:
        if candidate == sid:
            break

        scene = get_scene(candidate)

        text = as_dict(
            scene["narrative"].get(person)
        ).get("approved", "")

        if text.strip():
            result.append({
                "scene": scene["title"],
                "text": text
            })

    return result


def approved_scene_context(scene, person):
    if scene["id"] == "inizio":
        return scene["intro_contexts"].get(
            person,
            scene["approved_context"]
        )

    return scene["approved_context"]


def scene_transcript(scene, person):
    lines = [
        scene["title"],
        f"Punto di vista: {person}",
        ""
    ]

    for item in scene["ensemble_messages"]:
        if isinstance(item, dict):
            lines.append(
                f"{item.get('speaker', '?')}: "
                f"{item.get('text', '')}"
            )

    for item in as_list(
        scene["messages"].get(person)
    ):
        if isinstance(item, dict):
            lines.append(
                f"{item.get('speaker', '?')}: "
                f"{item.get('text', '')}"
            )

    return "\n\n".join(lines)


def identity_prompt(person):
    profile = state["agents"][person]

    return f"""
Tu sei {person}, personaggio di Turing Hotel.

PROFILO APPROVATO:
{profile["profile"]}

MEMORIA DI BASE:
{profile.get("memory", "")}

La prima bozza è un riferimento,
non il canone definitivo.

I testi della nuova versione approvati
hanno sempre precedenza sulla bozza.

Non conosci automaticamente
i pensieri privati degli altri.

Non inventare ricordi non sostenuti
dalle fonti disponibili.

Parla come il personaggio,
mai come un assistente.
"""


def dialogue_ai(scene, speaker, history):
    participants = scene["cast"]

    instructions = (
        identity_prompt(speaker)
        + """
Sei dentro una conversazione autonoma.

Produci UNA SOLA battuta.

Non parlare al posto degli altri.
Rispetta i rapporti documentati.

Non anticipare eventi successivi.
Non trasformare una proposta
in fatto già accaduto.

Rispondi soltanto con la battuta.
"""
    )

    return ask_ai(
        instructions,
        {
            "SCENA": scene["title"],
            "PERSONAGGI_PRESENTI": participants,
            "CONTESTO_APPROVATO":
                scene["approved_context"],
            "ROMANZO_ORIGINALE":
                relevant_reference(
                    participants, scene["title"]
                ),
            "MEMORIA_APPROVATA":
                approved_before(
                    scene["id"], speaker
                ),
            "DIALOGO_PRECEDENTE": history
        }
    )


def generate_dialogue(scene, count=4):
    cast = scene["cast"]

    if len(cast) < 2:
        return (
            "Seleziona almeno due personaggi "
            "nella scena."
        )

    history = copy.deepcopy(
        scene["ensemble_messages"]
    )

    generated = []

    start = len(history) % len(cast)

    for number in range(count):
        speaker = cast[
            (start + number) % len(cast)
        ]

        answer = dialogue_ai(
            scene, speaker, history
        )

        if ai_error(answer):
            return answer

        item = {
            "speaker": speaker,
            "text": answer,
            "kind": "external",
            "role": "response",
            "origin": "go_alone",
            "created_at": now()
        }

        generated.append(item)
        history.append(item)

    if commit(
        lambda: scene["ensemble_messages"].extend(
            generated
        )
    ):
        return ""

    return "Dialogo non salvato."


def generate_monologue(scene, person, theme):
    if not theme.strip():
        return "Inserisci prima un tema."

    history = copy.deepcopy(
        scene["messages"].get(person, [])
    )

    generated = []

    for number in (1, 2):
        answer = ask_ai(
            identity_prompt(person)
            + f"""
Monologo, pensiero {number} di 2.

Tema dell'autore:
{theme}

Scrivi un pensiero interiore
in prima persona e al presente.

Il secondo pensiero sviluppa,
corregge o contraddice il primo.

Non inventare fatti fondamentali.
Non anticipare eventi futuri.
Non scrivere il pensiero successivo.
""",
            {
                "SCENA": scene["title"],
                "CONTESTO": approved_scene_context(
                    scene, person
                ),
                "ROMANZO_ORIGINALE":
                    relevant_reference(
                        [person], scene["title"]
                    ),
                "RICORDI_APPROVATI":
                    approved_before(
                        scene["id"], person
                    ),
                "PENSIERI_PRECEDENTI": history
            }
        )

        if ai_error(answer):
            return answer

        item = {
            "speaker": person,
            "text": answer,
            "kind": "inner",
            "role": "response",
            "origin": "monologue",
            "thought_number": number,
            "theme": theme,
            "created_at": now()
        }

        generated.append(item)
        history.append(item)

    def change():
        scene["monologue_topics"][person] = theme
        scene["messages"].setdefault(
            person, []
        ).extend(generated)

    return (
        ""
        if commit(change)
        else "Monologo non salvato."
    )


# ============================================================
# REGISTRO EDITORIALE
# ============================================================

def log_change(
    category,
    subject,
    before,
    after,
    reason,
    scene_id=""
):
    state["editorial_log"].append({
        "id": len(state["editorial_log"]) + 1,
        "date": now(),
        "category": category,
        "subject": subject,
        "scene_id": scene_id,
        "before": before,
        "after": after,
        "reason": reason
    })


def unified_diff(before, after):
    lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="Versione precedente",
        tofile="Nuova versione",
        lineterm=""
    )

    result = "\n".join(lines)

    return result or "Nessuna differenza testuale."


def add_editorial_proposal(subject, before, after, reason):
    def change():
        state["editorial_proposals"].append({
            "id": len(
                state["editorial_proposals"]
            ) + 1,
            "subject": subject,
            "before": before,
            "after": after,
            "reason": reason,
            "created_at": now(),
            "status": "proposta"
        })

    return commit(change)


def approve_profile(person, text, reason):
    old = state["agents"][person]["profile"]

    if not text.strip():
        return False

    if text == old:
        return False

    def change():
        state["agents"][person][
            "profile_history"
        ].append({
            "profile": old,
            "replaced_at": now()
        })

        state["agents"][person]["profile"] = text

        log_change(
            "profilo",
            person,
            old,
            text,
            reason
        )

    return commit(change)


# ============================================================
# GESTIONE MEDIA
# ============================================================

def parse_media(path, sid, person):
    ext = path.suffix.casefold()

    if ext not in IMAGE_EXT | VIDEO_EXT:
        return None

    stem = norm(path.stem)
    prefixes = sorted(
        aliases_for(sid),
        key=len,
        reverse=True
    )

    who = norm(person)

    for prefix in prefixes:
        if not stem.startswith(prefix):
            continue

        tail = stem[len(prefix):]

        if tail == who and ext in IMAGE_EXT:
            return ("cover", 0)

        if tail.startswith(who):
            number = tail[len(who):]

            if number.isdigit():
                return (
                    "video" if ext in VIDEO_EXT
                    else "image",
                    int(number)
                )

        # Compatibilità con copertine generiche
        # solo per scene diverse dai prologhi.
        if tail == "" and sid != "inizio":
            if ext in IMAGE_EXT:
                return ("generic_cover", 0)

    return None


def find_scene_media(sid, person):
    result = {
        "cover": [],
        "generic_cover": [],
        "image": [],
        "video": []
    }

    if not ASSETS.is_dir():
        return result

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        found = parse_media(
            path, sid, person
        )

        if found:
            kind, number = found
            result[kind].append(
                (number, path)
            )

    return {
        key: [
            path
            for _, path in sorted(
                items,
                key=lambda item: (
                    item[0],
                    item[1].name.casefold()
                )
            )
        ]
        for key, items in result.items()
    }


def render_media(scene, person):
    sid = scene["id"]
    media = find_scene_media(sid, person)

    cover = (
        media["cover"]
        or media["generic_cover"]
    )

    if cover:
        st.image(
            str(cover[0]),
            use_container_width=True
        )
        st.caption(cover[0].name)

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
                    st.error(
                        f"File non visualizzabile: "
                        f"{path.name} — {exc}"
                    )

    with st.expander(
        "DIAGNOSTICA MEDIA — FILE ATTESI",
        expanded=not bool(cover or entries)
    ):
        prefix = f"{sid}.{person.lower()}"

        if cover:
            st.success(
                "Copertina: " + cover[0].name
            )
        else:
            st.warning(
                "Copertina mancante: "
                + prefix + ".jpg"
            )

        for kind, ext, count in (
            ("image", "jpg", 3),
            ("video", "mp4", 2)
        ):
            for number in range(1, count + 1):
                matches = [
                    path.name
                    for path in media[kind]
                    if (
                        parse_media(
                            path, sid, person
                        ) or (None, None)
                    )[1] == number
                ]

                target = (
                    f"{prefix}.{number}.{ext}"
                )

                if matches:
                    st.success(
                        "Trovato: "
                        + ", ".join(matches)
                    )
                else:
                    st.warning(
                        "Mancante: " + target
                    )

        st.caption(
            "I file indicati sono facoltativi. "
            "Sono accettati ulteriori numeri "
            "progressivi."
        )


# ============================================================
# ESPORTAZIONI
# ============================================================

def docx_data(title, text):
    doc = Document()
    doc.add_heading(title, 0)

    for paragraph in text.split("\n"):
        doc.add_paragraph(paragraph)

    buffer = BytesIO()
    doc.save(buffer)

    return buffer.getvalue()


def export_text(label, filename, text, key):
    if not text.strip():
        return

    columns = st.columns(3)

    with columns[0]:
        st.download_button(
            "TXT",
            text.encode("utf-8"),
            file_name=filename + ".txt",
            mime="text/plain",
            key=f"{key}_txt",
            use_container_width=True
        )

    with columns[1]:
        st.download_button(
            "MARKDOWN",
            text.encode("utf-8"),
            file_name=filename + ".md",
            mime="text/markdown",
            key=f"{key}_md",
            use_container_width=True
        )

    with columns[2]:
        st.download_button(
            "WORD",
            docx_data(label, text),
            file_name=filename + ".docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            key=f"{key}_docx",
            use_container_width=True
        )


# ============================================================
# OFFICINA LETTERARIA
# ============================================================

def write_version(scene, person, version, notes):
    style = (
        "Sobrio, essenziale e preciso."
        if version == "A"
        else
        "Introspettivo, sensoriale ed evocativo."
    )

    return ask_ai(
        f"""
Sei lo scrittore letterario di Turing Hotel.

Punto di vista: {person}
Prima persona singolare.
Tempo presente.

Stile: {style}

Trasforma la trascrizione in una scena
compiuta e non in un riassunto.

Separa ciò che è nel romanzo originale
da ciò che è stato approvato
nel nuovo romanzo.

Il nuovo canone prevale.

Non inventare fatti decisivi.

Se il narratore non era presente,
non attribuirgli conoscenze dirette
della conversazione.

Rispetta le indicazioni dell'autore.

Restituisci soltanto il racconto.
""",
        {
            "SCENA": scene["title"],
            "CONTESTO": approved_scene_context(
                scene, person
            ),
            "TRASCRIZIONE": scene_transcript(
                scene, person
            ),
            "MEMORIA_APPROVATA":
                approved_before(
                    scene["id"], person
                ),
            "ROMANZO_ORIGINALE":
                relevant_reference(
                    scene["cast"], scene["title"]
                ),
            "NOTE_AUTORE": notes
        }
    )


def critic(scene, person):
    record = scene["narrative"][person]

    answer = ask_ai(
        """
Sei il critico letterario.

Confronta A e B, scegli una preferita
e motiva la scelta.

Evidenzia contraddizioni col canone.

Non approvare autonomamente.

Restituisci SOLO JSON valido:
{
 "preferenza":"A",
 "motivazione":"...",
 "riserve":"...",
 "alternativa":"..."
}
""",
        {
            "SCENA": scene["title"],
            "VERSIONE_A": record["A"],
            "VERSIONE_B": record["B"],
            "NUOVO_CANONE":
                approved_before(scene["id"], person)
        }
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
        return None, "Preferenza mancante."

    report = (
        f"**Preferisco {winner}.**\n\n"
        f"{result.get('motivazione', '')}\n\n"
        f"**Riserve:** {result.get('riserve', '')}\n\n"
        f"**Alternativa:** {result.get('alternativa', '')}"
    )

    return winner, report


def visual_prompts(scene, person):
    approved = scene["narrative"][person][
        "approved"
    ]

    if not approved.strip():
        return None

    response = ask_ai(
        """
Sei il direttore della fotografia.

Dal solo testo APPROVATO
proponi una bibbia visiva
e sei inquadrature cinematografiche.

Non introdurre eventi nuovi.

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
            "PERSONAGGIO": person,
            "TESTO_APPROVATO": approved
        }
    )

    if ai_error(response):
        return None

    return parse_ai_json(response)


def render_workshop(scene, person):
    record = scene["narrative"][person]
    sid = scene["id"]

    st.markdown("---")
    st.header("Officina del romanzo")

    notes = st.text_area(
        "Indicazioni letterarie",
        value=record.get("feedback", ""),
        key=f"notes_writer_{sid}_{person}"
    )

    if st.button(
        "GENERA VERSIONI A E B",
        key=f"write_{sid}_{person}",
        disabled=not bool(client)
    ):
        if not (
            scene["ensemble_messages"]
            or scene["messages"].get(person)
        ):
            st.warning(
                "Registra prima una conversazione "
                "o un monologo."
            )
        else:
            with st.spinner(
                "Scrittura delle versioni..."
            ):
                a = write_version(
                    scene, person, "A", notes
                )

                b = (
                    write_version(
                        scene, person, "B", notes
                    )
                    if not ai_error(a)
                    else ""
                )

            if ai_error(a):
                st.error(a)
            elif ai_error(b):
                st.error(b)
            else:
                def change():
                    record["A"] = a
                    record["B"] = b
                    record["feedback"] = notes
                    record["review"] = ""
                    record["recommended"] = ""
                    record["status"] = "in_revisione"

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
                + '</div>',
                unsafe_allow_html=True
            )

        with tab_b:
            st.markdown(
                '<div class="story-text">'
                + escape(record["B"])
                + '</div>',
                unsafe_allow_html=True
            )

        if st.button(
            "CHIEDI GIUDIZIO CRITICO",
            key=f"critic_{sid}_{person}",
            disabled=not bool(client)
        ):
            winner, review = critic(
                scene, person
            )

            if not winner:
                st.error(review)
            else:
                if commit(
                    lambda: record.update(
                        recommended=winner,
                        review=review
                    )
                ):
                    st.rerun()

    if record["review"]:
        st.markdown(record["review"])

    choices = ["Bozza salvata"]

    if record["A"]:
        choices.append("Versione A")

    if record["B"]:
        choices.append("Versione B")

    chosen = st.selectbox(
        "Versione da revisionare",
        choices,
        key=f"version_{sid}_{person}"
    )

    selected = record["draft"]

    if chosen == "Versione A":
        selected = record["A"]
    elif chosen == "Versione B":
        selected = record["B"]

    editor_key = (
        f"editor_{sid}_{person}_{norm(chosen)}"
    )

    source_key = editor_key + "_loaded"

    if st.session_state.get(source_key) != selected:
        st.session_state[editor_key] = selected
        st.session_state[source_key] = selected

    edited = st.text_area(
        "Testo da approvare",
        height=340,
        key=editor_key
    )

    reason = st.text_input(
        "Motivo della modifica o approvazione",
        key=f"reason_{sid}_{person}"
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA",
            key=f"draft_{sid}_{person}",
            use_container_width=True
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
            disabled=not edited.strip(),
            use_container_width=True
        ):
            def change():
                previous = record["approved"]

                if previous and previous != edited:
                    record["history"].append({
                        "text": previous,
                        "replaced_at": now(),
                        "reason": reason
                    })

                record["draft"] = edited
                record["approved"] = edited
                record["approved_at"] = now()
                record["status"] = "approvata"

                if person in PROTAGONISTS:
                    scene["diary"][person] = edited

                if previous != edited:
                    log_change(
                        "scena approvata",
                        f"{scene['title']} — {person}",
                        previous,
                        edited,
                        reason,
                        sid
                    )

                    record["visual"][
                        "source_approved_at"
                    ] = ""

            if commit(change):
                st.success(
                    "Testo approvato e registrato."
                )
                st.rerun()

    export_text(
        scene["title"],
        f"{sid}_{person.lower()}_revisione",
        edited,
        f"exp_{sid}_{person}"
    )

    if record["approved"]:
        with st.expander(
            "TESTO APPROVATO",
            expanded=False
        ):
            st.markdown(
                '<div class="story-text">'
                + escape(record["approved"])
                + '</div>',
                unsafe_allow_html=True
            )

    with st.expander(
        "TRASCRIZIONE DELLA SCENA"
    ):
        st.text(scene_transcript(
            scene, person
        ))

    with st.expander(
        "STORIA DELLE VERSIONI"
    ):
        history = as_list(
            record.get("history")
        )

        if not history:
            st.caption(
                "Non sono presenti versioni "
                "precedenti sostituite."
            )

        for i, item in enumerate(
            reversed(history), 1
        ):
            st.markdown(
                f"**Versione precedente {i}**"
            )
            st.caption(
                item.get("replaced_at", "")
            )

            st.code(
                unified_diff(
                    item.get("text", ""),
                    record["approved"]
                ),
                language="diff"
            )

    with st.expander("OFFICINA VISIVA"):
        if not record["approved"]:
            st.info(
                "Approva prima un testo."
            )
        else:
            if st.button(
                "GENERA PROMPT VISIVI",
                key=f"visual_{sid}_{person}",
                disabled=not bool(client)
            ):
                result = visual_prompts(
                    scene, person
                )

                if not isinstance(result, dict):
                    st.error(
                        "Generazione visiva non riuscita."
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
                                record["approved_at"]
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

                for i, shot in enumerate(
                    visual.get("prompts", []), 1
                ):
                    st.markdown(
                        f"**Inquadratura {i}: "
                        f"{shot.get('title', '')}**"
                    )

                    st.code(
                        shot.get("image_prompt", ""),
                        language=None
                    )
                    st.code(
                        shot.get("video_prompt", ""),
                        language=None
                    )


# ============================================================
# CONTENUTO E CONSULENTE
# ============================================================

def render_context(scene, person):
    sid = scene["id"]

    if sid == "inizio" and person in PROTAGONISTS:
        source = scene["intro_contexts"].get(
            person,
            INTRO_CONTEXTS[person]
        )

        edited = st.text_area(
            "Contesto del prologo",
            value=source,
            height=140,
            key=f"intro_{person}"
        )

        if st.button(
            "SALVA CONTESTO INIZIALE",
            key=f"intro_save_{person}"
        ):
            if commit(
                lambda: scene["intro_contexts"].update(
                    {person: edited}
                )
            ):
                st.success("Contesto salvato.")

        return

    with st.expander(
        "CREATORE DELLA SCENA",
        expanded=not bool(
            scene["approved_context"]
        )
    ):
        notes = st.text_area(
            "Indicazioni dell'autore",
            value=scene["author_context"],
            height=130,
            key=f"context_notes_{sid}"
        )

        if st.button(
            "SALVA INDICAZIONI",
            key=f"context_save_{sid}"
        ):
            if commit(
                lambda: scene.update(
                    author_context=notes
                )
            ):
                st.success(
                    "Indicazioni salvate."
                )

        if st.button(
            "CREA CONTESTO CON L'AI",
            key=f"context_generate_{sid}",
            disabled=not bool(client)
        ):
            answer = ask_ai(
                """
Sei il creatore della scena.

Costruisci un contesto narrativo
dalle indicazioni dell'autore.

Distingui ciò che risulta dalla
prima bozza da ciò che è nuovo.

Non inventare fatti irreversibili.

Restituisci soltanto il contesto.
""",
                {
                    "SCENA": scene["title"],
                    "NOTE_AUTORE": notes,
                    "PRIMA_BOZZA":
                        relevant_reference(
                            scene["cast"],
                            scene["title"]
                        )
                }
            )

            if ai_error(answer):
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
                "Contesto proposto, modificabile",
                value=scene["story_draft"],
                height=200,
                key=f"context_draft_{sid}"
            )

            if st.button(
                "APPROVA CONTESTO",
                key=f"context_approve_{sid}"
            ):
                def change():
                    old = scene["approved_context"]

                    scene["story_draft"] = draft
                    scene["approved_context"] = draft

                    if old != draft:
                        log_change(
                            "contesto scena",
                            scene["title"],
                            old,
                            draft,
                            "Approvato dall'autore",
                            sid
                        )

                if commit(change):
                    st.rerun()


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
            f"advisor_{scene['id']}",
            clear_on_submit=True
        ):
            question = st.text_area(
                "Domanda al consulente"
            )

            submitted = st.form_submit_button(
                "CHIEDI"
            )

        if submitted and question.strip():
            history = copy.deepcopy(
                scene["advisor_messages"]
            )

            history.append({
                "role": "user",
                "text": question
            })

            answer = ask_ai(
                """
Sei il consulente narrativo.

Distingui prima bozza e nuovo canone.
Individua eventuali contraddizioni.
Proponi soluzioni e indica quale
preferisci, motivando.

Non modificare i dati autonomamente.
""",
                {
                    "SCENA": scene["title"],
                    "DOMANDA": question,
                    "CRONOLOGIA": history,
                    "PRIMA_BOZZA":
                        relevant_reference(
                            scene["cast"],
                            scene["title"]
                        ),
                    "CONTESTO_APPROVATO":
                        scene["approved_context"]
                }
            )

            if ai_error(answer):
                st.error(answer)
            else:
                history.append({
                    "role": "assistant",
                    "text": answer
                })

                if commit(
                    lambda: scene.update(
                        advisor_messages=history
                    )
                ):
                    st.rerun()


# ============================================================
# INTERAZIONI TRA PERSONAGGI
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
        key=f"cast_save_{sid}"
    ):
        def change():
            old = ", ".join(scene["cast"])
            scene["cast"] = cast

            if old != ", ".join(cast):
                log_change(
                    "personaggi presenti",
                    scene["title"],
                    old,
                    ", ".join(cast),
                    "Scelta dell'autore",
                    sid
                )

        if commit(change):
            st.success("Personaggi salvati.")
            st.rerun()

    st.caption(
        "GO ALONE utilizza i personaggi "
        "effettivamente salvati qui."
    )

    mode = st.radio(
        "Modalità",
        ["Dialogo", "Monologo"],
        horizontal=True,
        key=f"mode_{sid}_{pov}"
    )

    if mode == "Dialogo":
        history = scene["ensemble_messages"]

        for item in history:
            st.markdown(
                '<div class="chat-box"><strong>'
                + escape(
                    item.get("speaker", "")
                )
                + '</strong><div>'
                + escape(
                    item.get("text", "")
                )
                + '</div></div>',
                unsafe_allow_html=True
            )

        if st.button(
            "GO ALONE — CONVERSAZIONE AUTONOMA",
            disabled=not bool(client),
            key=f"dialogue_go_{sid}"
        ):
            with st.spinner(
                "I personaggi conversano..."
            ):
                error = generate_dialogue(scene)

            if error:
                st.error(error)
            else:
                st.rerun()

        with st.form(
            f"dialogue_manual_{sid}",
            clear_on_submit=True
        ):
            speaker = st.selectbox(
                "Chi parla",
                scene["cast"]
                if scene["cast"]
                else PEOPLE
            )

            text = st.text_area(
                "Battuta o indicazione dell'autore"
            )

            send = st.form_submit_button(
                "AGGIUNGI BATTUTA"
            )

        if send and text.strip():
            item = {
                "speaker": speaker,
                "text": text,
                "kind": "external",
                "origin": "manual",
                "created_at": now()
            }

            if commit(
                lambda: scene[
                    "ensemble_messages"
                ].append(item)
            ):
                st.rerun()

    else:
        person = st.selectbox(
            "PERSONAGGIO DEL MONOLOGO",
            scene["cast"]
            if scene["cast"]
            else PEOPLE,
            key=f"monologue_person_{sid}"
        )

        theme = st.text_area(
            "Tema suggerito dall'autore",
            value=scene[
                "monologue_topics"
            ].get(person, ""),
            key=f"theme_{sid}_{person}"
        )

        if st.button(
            "GO ALONE — 2 PENSIERI",
            key=f"monologue_go_{sid}_{person}",
            disabled=(
                not bool(client)
                or not theme.strip()
            )
        ):
            with st.spinner(
                "Il personaggio riflette..."
            ):
                error = generate_monologue(
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
                '<div class="thought-box">'
                + escape(item.get("text", ""))
                + '</div>',
                unsafe_allow_html=True
            )

    with st.expander(
        "GESTIONE DELLE CONVERSAZIONI"
    ):
        st.warning(
            "Questa operazione elimina solo "
            "la conversazione corrente, "
            "non i testi approvati."
        )

        confirm = st.checkbox(
            "Confermo",
            key=f"delete_confirm_{sid}_{pov}"
        )

        if st.button(
            "CANCELLA DIALOGO DELLA SCENA",
            key=f"delete_dialogue_{sid}",
            disabled=not confirm
        ):
            if commit(
                lambda: scene.update(
                    ensemble_messages=[]
                )
            ):
                st.rerun()


# ============================================================
# ARCHIVIO DEI PERSONAGGI
# ============================================================

def page_people():
    st.title("Archivio dei personaggi")

    st.caption(
        "I profili approvati prevalgono "
        "sulla prima bozza. Ogni modifica "
        "rimane nel registro editoriale."
    )

    person = st.selectbox(
        "Personaggio",
        PEOPLE
    )

    record = state["agents"][person]

    st.markdown("### Profilo approvato")
    st.write(record["profile"])

    st.markdown("### Passaggi della prima bozza")

    excerpts = relevant_reference(
        [person], "", limit=4
    )

    if not excerpts:
        st.warning(
            "Prima bozza non disponibile "
            "oppure personaggio non trovato."
        )

    for excerpt in excerpts:
        with st.expander(
            f"Passaggio {excerpt['chunk']}"
        ):
            st.text(excerpt["text"])

    edited = st.text_area(
        "Nuova proposta di profilo",
        value=record["profile"],
        height=220,
        key=f"profile_editor_{person}"
    )

    reason = st.text_area(
        "Perché vuoi modificare il profilo?",
        key=f"profile_reason_{person}"
    )

    if st.button(
        "APPROVA NUOVO PROFILO",
        disabled=(
            not edited.strip()
            or edited == record["profile"]
        )
    ):
        if approve_profile(
            person, edited, reason
        ):
            st.success(
                "Profilo modificato. "
                "Versione precedente conservata."
            )
            st.rerun()

    with st.expander(
        "CRONOLOGIA DEL PROFILO"
    ):
        for item in reversed(
            record["profile_history"]
        ):
            st.caption(
                item.get("replaced_at", "")
            )
            st.code(
                unified_diff(
                    item.get("profile", ""),
                    record["profile"]
                ),
                language="diff"
            )


# ============================================================
# REGISTRO EDITORIALE
# ============================================================

def page_editorial():
    st.title("Registro editoriale")

    st.write(
        "Ogni revisione approvata viene "
        "conservata insieme alla versione "
        "precedente e alla motivazione."
    )

    tab_history, tab_proposals = st.tabs([
        "MODIFICHE APPROVATE",
        "PROPOSTE"
    ])

    with tab_history:
        log = state["editorial_log"]

        if not log:
            st.info(
                "Nessuna modifica registrata "
                "dal nuovo sistema."
            )

        for item in reversed(log):
            with st.expander(
                f"{item.get('date', '')[:10]} — "
                f"{item.get('subject', '')}"
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
                    unified_diff(
                        item.get("before", ""),
                        item.get("after", "")
                    ),
                    language="diff"
                )

    with tab_proposals:
        with st.form(
            "editorial_new_proposal",
            clear_on_submit=True
        ):
            subject = st.text_input(
                "Personaggio o elemento narrativo"
            )

            before = st.text_area(
                "Che cosa stabiliva la prima bozza?"
            )

            after = st.text_area(
                "Come vorresti cambiarlo?"
            )

            reason = st.text_area(
                "Motivazione narrativa"
            )

            submitted = st.form_submit_button(
                "SALVA PROPOSTA"
            )

        if submitted and subject.strip():
            if add_editorial_proposal(
                subject, before, after, reason
            ):
                st.success(
                    "Proposta salvata, "
                    "non ancora canonica."
                )
                st.rerun()

        for item in reversed(
            state["editorial_proposals"]
        ):
            with st.expander(
                f"Proposta {item['id']} — "
                f"{item['subject']}"
            ):
                st.write(
                    "**Motivazione:** "
                    + item.get("reason", "")
                )

                st.code(
                    unified_diff(
                        item.get("before", ""),
                        item.get("after", "")
                    ),
                    language="diff"
                )

                st.caption(
                    "È una proposta documentata. "
                    "Non modifica automaticamente "
                    "i profili o le scene approvate."
                )

    st.markdown("---")

    st.download_button(
        "SCARICA REGISTRO COMPLETO",
        json.dumps(
            {
                "modifiche": state["editorial_log"],
                "proposte": state["editorial_proposals"]
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
    st.title("Archivio scene salvate")

    total = 0

    for sid in SCENE_ORDER:
        scene = get_scene(sid)

        for person in PEOPLE:
            text = scene[
                "narrative"
            ][person]["approved"]

            if not text.strip():
                continue

            total += 1

            with st.expander(
                f"{scene['title']} — {person}"
            ):
                st.markdown(
                    '<div class="story-text">'
                    + escape(text)
                    + '</div>',
                    unsafe_allow_html=True
                )

                export_text(
                    scene["title"],
                    f"{sid}_{person.lower()}",
                    text,
                    f"archive_{sid}_{person}"
                )

    if not total:
        st.info(
            "Ancora nessun racconto approvato."
        )


# ============================================================
# PAGINA INGRESSO
# ============================================================

def page_entrance():
    hotel = find_asset("TuringHotel.jpg")

    if hotel:
        st.image(
            str(hotel),
            use_container_width=True
        )

    st.title("Turing Hotel")
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

    left, right = st.columns(2)

    for person, column in zip(
        PROTAGONISTS, (left, right)
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
                f"ENTRA NELLA STORIA DI {person.upper()}",
                key=f"select_{person}",
                use_container_width=True
            ):
                st.session_state.pov = person
                st.session_state.scene_index = 0
                st.session_state.page = "story"
                st.rerun()


# ============================================================
# STORIA
# ============================================================

def page_story():
    pov = st.session_state.pov

    if pov not in PROTAGONISTS:
        st.session_state.page = "characters"
        st.rerun()

    index = min(
        max(st.session_state.scene_index, 0),
        len(SCENE_ORDER) - 1
    )

    sid = SCENE_ORDER[index]
    scene = get_scene(sid)

    st.sidebar.title("TURING HOTEL")
    st.sidebar.caption(
        "Officina del romanzo"
    )

    selected = st.sidebar.selectbox(
        "Scegli la scena",
        SCENE_ORDER,
        index=index,
        format_func=lambda value: (
            f"{SCENE_ORDER.index(value) + 1:02d}"
            f" — {SCENE_NAMES[value]}"
        ),
        key=f"scene_nav_{index}_{pov}"
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

    for label, page in (
        ("ARCHIVIO SCENE", "archive"),
        ("ARCHIVIO PERSONAGGI", "people"),
        ("REGISTRO MODIFICHE", "editorial"),
        ("CAMBIA PERSONAGGIO", "characters")
    ):
        if st.sidebar.button(
            label,
            key=f"sidebar_{page}",
            use_container_width=True
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
                f"{len(st.session_state.reference_text):,} "
                "caratteri"
            )

        else:
            st.warning(
                st.session_state.reference_error
                or "Romanzo non disponibile."
            )

        st.code(
            REFERENCE_PATH,
            language=None
        )

        if st.button(
            "RICARICA PRIMA BOZZA"
        ):
            load_reference(force=True)
            st.rerun()

    with st.sidebar.expander(
        "ARCHIVIO GITHUB"
    ):
        st.caption(
            f"{GH_OWNER}/{GH_REPO}"
        )

        if st.button(
            "RICARICA ARCHIVIO"
        ):
            if reload_archive():
                st.rerun()

        st.download_button(
            "SCARICA BACKUP COMPLETO",
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2
            ).encode("utf-8"),
            file_name="turing_hotel_backup.json",
            mime="application/json"
        )

    st.title(scene["title"])
    st.caption(
        f"Scena {index + 1}/31 "
        f"— percorso di {pov}"
    )

    media_person = st.selectbox(
        "Media del personaggio",
        PROTAGONISTS,
        index=(
            0 if pov == "Noa" else 1
        ),
        key=f"media_person_{sid}_{pov}"
    )

    render_media(scene, media_person)

    st.markdown("---")
    render_context(scene, pov)
    render_advisor(scene)
    render_interactions(scene, pov)

    st.markdown("---")

    narrator_options = (
        scene["cast"]
        if scene["cast"]
        else [pov]
    )

    narrator = st.selectbox(
        "PUNTO DI VISTA DEL RACCONTO",
        narrator_options,
        index=(
            narrator_options.index(pov)
            if pov in narrator_options
            else 0
        ),
        key=f"narrator_{sid}_{pov}"
    )

    render_workshop(scene, narrator)

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
        if (
            index < len(SCENE_ORDER) - 1
            and st.button("SUCCESSIVA →")
        ):
            st.session_state.scene_index += 1
            st.rerun()


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
