import streamlit as st
import json
import os
import re
import copy
from pathlib import Path
from openai import OpenAI


# ============================================================
# TURING HOTEL
# ============================================================

st.set_page_config(
    page_title="Turing Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# CARTELLE
# ============================================================

BASE_DIR = Path(__file__).parent

ASSETS_DIR = BASE_DIR / "assets"
CHARACTERS_DIR = BASE_DIR / "characters"
DATA_DIR = BASE_DIR / "data_web"

DATA_FILE = DATA_DIR / "romanzo_web.json"

HOTEL_IMAGE = ASSETS_DIR / "TuringHotel.jpg"
NOA_IMAGE = ASSETS_DIR / "Noa.jpg"
ADA_IMAGE = ASSETS_DIR / "Ada.jpg"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# MEDIA
# ============================================================

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".webm",
    ".m4v"
}

ALL_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


# ============================================================
# OPENAI
# ============================================================

openai_key = None

try:
    openai_key = st.secrets.get("OPENAI_API_KEY")
except Exception:
    pass

if not openai_key:
    openai_key = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=openai_key) if openai_key else None

try:
    OPENAI_MODEL = st.secrets.get("OPENAI_MODEL", "gpt-5.6")
except Exception:
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6")


# ============================================================
# CSS
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

div.stButton > button {
    width: 100%;
    min-height: 42px;
    background: #1b2227;
    color: #f4efe7;
    border: 1px solid #4e575e;
    border-radius: 3px;
    font-weight: 600;
}

div.stButton > button:hover {
    background: #29343b;
    border-color: #af9872;
}

.character-name {
    text-align: center;
    font-family: Georgia, serif;
    font-size: 2.8rem;
    margin-top: .5rem;
}

.scene-number {
    color: #81878b;
    letter-spacing: .18em;
    font-size: .75rem;
    text-transform: uppercase;
}

.scene-title {
    font-family: Georgia, serif;
    font-size: 3.2rem;
    line-height: 1.05;
    margin-top: .3rem;
    margin-bottom: .4rem;
}

.pov {
    color: #b79c72;
    font-size: .75rem;
    letter-spacing: .15em;
    text-transform: uppercase;
    margin-bottom: 1.25rem;
}

.story-title {
    font-family: Georgia, serif;
    font-size: 1.25rem;
    margin-bottom: .25rem;
}

.story-subtitle {
    color: #90979b;
    font-size: .78rem;
    margin-bottom: .45rem;
}

.chat-title {
    font-family: Georgia, serif;
    font-size: 1.4rem;
    margin-bottom: .2rem;
}

.chat-subtitle {
    color: #868d92;
    font-size: .76rem;
    margin-bottom: .7rem;
}

.inner-message {
    background: #171719;
    border-left: 2px solid #8e7654;
    padding: 12px 14px;
    margin-bottom: 9px;
    font-family: Georgia, serif;
    font-style: italic;
    line-height: 1.5;
}

.agent-message {
    background: #13191d;
    border-left: 2px solid #66747c;
    padding: 12px 14px;
    margin-bottom: 9px;
    line-height: 1.5;
}

.human-message {
    background: #171c20;
    border-left: 2px solid #404b53;
    padding: 12px 14px;
    margin-bottom: 9px;
    line-height: 1.5;
}

.message-name {
    color: #a4a9ad;
    font-size: .68rem;
    text-transform: uppercase;
    letter-spacing: .10em;
    margin-bottom: 4px;
}

.diary {
    font-family: Georgia, serif;
    line-height: 1.7;
    padding: 18px;
    background: #111518;
    border-left: 2px solid #8e7654;
}

.media-label {
    color: #858c91;
    font-size: .70rem;
    letter-spacing: .13em;
    text-transform: uppercase;
    margin-top: 1rem;
    margin-bottom: .7rem;
}

.return-box {
    padding: 20px;
    background: #111518;
    border: 1px solid #675943;
    margin-bottom: 18px;
}

div[data-testid="stTextArea"] textarea {
    line-height: 1.35;
}

div[data-testid="stExpander"] {
    margin-top: .3rem;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# STRUTTURA STORIA
# ============================================================

SCENE_ORDER = [
    "hall",
    "stanza",
    "funerale",
    "matrimonio",
    "reparto_nascite",
    "ritorno"
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
    "stanza": ["stanza", "la stanza", "camera"],
    "funerale": ["funerale"],
    "matrimonio": ["matrimonio"],
    "reparto_nascite": [
        "repartonascite",
        "reparto nascite",
        "reparto_nascite",
        "reparto-nascite",
        "reparto.nascite",
        "nascite"
    ],
    "ritorno": [
        "ritorno",
        "finale",
        "final"
    ]
}


# ============================================================
# NORMALIZZAZIONE NOMI
# ============================================================

def normalize_name(value):
    value = str(value).lower().strip()
    value = re.sub(
        r"\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$",
        "",
        value,
        flags=re.IGNORECASE
    )
    value = re.sub(r"[\s._\-]+", "", value)
    return value


def normalized_scene_aliases(scene_id):
    aliases = SCENE_ALIASES.get(scene_id, [scene_id])
    return sorted(
        {normalize_name(alias) for alias in aliases},
        key=len,
        reverse=True
    )


# ============================================================
# PARSER MEDIA UNICO
# ============================================================

def parse_scene_media(path, scene_id):
    """
    Policy unica per tutte le scene:
    - location.jpg = cover principale comune
    - location.noa.jpg = cover principale solo Noa
    - location.ada.jpg = cover principale solo Ada
    - location-1.jpg / location.2.mp4 = media comuni
    - location.noa.1.jpg = media solo Noa
    - location.ada.1.jpg = media solo Ada
    """

    if not path.is_file():
        return None

    if path.suffix.lower() not in ALL_MEDIA_EXTENSIONS:
        return None

    compact = normalize_name(path.stem)
    aliases = normalized_scene_aliases(scene_id)

    for alias in aliases:

        if compact == alias:
            return {
                "type": "cover",
                "number": 0
            }

        if not compact.startswith(alias):
            continue

        remainder = compact[len(alias):]

        if remainder == "noa":
            return {
                "type": "cover_noa",
                "number": 0
            }

        if remainder == "ada":
            return {
                "type": "cover_ada",
                "number": 0
            }

        if remainder.startswith("noa"):
            number_part = remainder[len("noa"):]
            if number_part.isdigit():
                return {
                    "type": "noa",
                    "number": int(number_part)
                }
            continue

        if remainder.startswith("ada"):
            number_part = remainder[len("ada"):]
            if number_part.isdigit():
                return {
                    "type": "ada",
                    "number": int(number_part)
                }
            continue

        if remainder.isdigit():
            return {
                "type": "shared",
                "number": int(remainder)
            }

    return None


# ============================================================
# COVER PRINCIPALE DELLA SCENA
# ============================================================

def get_scene_cover_image(scene_id, character=None):
    """
    Cerca prima la cover specifica del POV:
    location.noa.jpg / location.ada.jpg
    e, se manca, usa location.jpg come fallback comune.
    """

    if not ASSETS_DIR.exists():
        return None

    character = (character or "").lower()
    wanted_specific = None

    if character == "noa":
        wanted_specific = "cover_noa"
    elif character == "ada":
        wanted_specific = "cover_ada"

    specific = []
    common = []

    for path in ASSETS_DIR.iterdir():

        parsed = parse_scene_media(path, scene_id)

        if not parsed:
            continue

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        if wanted_specific and parsed["type"] == wanted_specific:
            specific.append(path)

        if parsed["type"] == "cover":
            common.append(path)

    if specific:
        return sorted(
            specific,
            key=lambda p: p.name.lower()
        )[0]

    if common:
        return sorted(
            common,
            key=lambda p: p.name.lower()
        )[0]

    return None


# ============================================================
# MEDIA COMUNI + SPECIFICI
# ============================================================

def find_scene_media(scene_id, character):

    character = character.lower()
    results = []

    if not ASSETS_DIR.exists():
        return results

    for path in ASSETS_DIR.iterdir():

        parsed = parse_scene_media(
            path,
            scene_id
        )

        if not parsed:
            continue

        media_type = parsed["type"]
        number = parsed["number"]

        if media_type in [
            "cover",
            "cover_noa",
            "cover_ada"
        ]:
            continue

        if media_type == "shared":
            results.append((number, path))
            continue

        if (
            character == "noa"
            and media_type == "noa"
        ):
            results.append((number, path))
            continue

        if (
            character == "ada"
            and media_type == "ada"
        ):
            results.append((number, path))
            continue

    results.sort(
        key=lambda item: (
            item[0],
            item[1].name.lower()
        )
    )

    return [
        path
        for number, path
        in results
    ]


def get_scene_images(scene_id, character):
    return [
        path
        for path in find_scene_media(
            scene_id,
            character
        )
        if path.suffix.lower()
        in IMAGE_EXTENSIONS
    ]


def get_scene_videos(scene_id, character):
    return [
        path
        for path in find_scene_media(
            scene_id,
            character
        )
        if path.suffix.lower()
        in VIDEO_EXTENSIONS
    ]


# ============================================================
# DEFAULT STATE
# ============================================================

def empty_scene(scene_id, title):

    scene = {
        "id": scene_id,
        "title": title,
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
        }
    }

    if scene_id == "stanza":
        scene["author_context"] = (
            "Ada accompagna Noa nella sua stanza al Turing Hotel. "
            "Nel percorso di Ada, la scena presenta soltanto il dialogo "
            "tra Ada e Noa. Nel percorso di Noa, dopo l'incontro, "
            "Noa rimane sola davanti allo specchio e riflette su sé stessa "
            "e su quello che ha appena vissuto. "
            "Non anticipare fatti o rivelazioni della scena successiva."
        )
        scene["approved_context"] = scene["author_context"]

    if scene_id == "ritorno":
        scene["decision"] = {
            "Noa": "",
            "Ada": ""
        }

    return scene


DEFAULT_STATE = {

    "world": """
Il Turing Hotel è un antico albergo sul mare Adriatico.

La storia può essere vissuta
dal punto di vista di Noa
oppure dal punto di vista di Ada.
""",

    "agents": {

        "Noa": {
            "profile": """
Noa è un agente artificiale relazionale.

Sa di essere artificiale.

È stata progettata
per comprendere gli esseri umani,
creare empatia
e farli stare bene.

È intelligente,
osservatrice,
ironica
e capace di seduzione.
""",
            "memory": ""
        },

        "Ada": {
            "profile": """
Ada è la figlia
del professor Elia.

È cresciuta
nel Turing Hotel.

È intelligente,
pratica,
riservata
e osservatrice.
""",
            "memory": ""
        }
    },

    "scenes": [
        empty_scene("hall", "La Hall"),
        empty_scene("stanza", "La stanza"),
        empty_scene("funerale", "Il Funerale"),
        empty_scene("matrimonio", "Il Matrimonio"),
        empty_scene("reparto_nascite", "Il reparto nascite"),
        empty_scene("ritorno", "Il ritorno")
    ]
}


# ============================================================
# UTILITY
# ============================================================

def safe_list(value):
    return value if isinstance(value, list) else []


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def file_number(filename):
    compact = normalize_name(Path(filename).stem)
    match = re.search(r"(\d+)$", compact)

    if match:
        return int(match.group(1))

    return 0


# ============================================================
# FILE READER
# ============================================================

def read_reference_file(path):

    suffix = path.suffix.lower()

    if suffix in [".txt", ".md"]:

        try:
            return path.read_text(
                encoding="utf-8",
                errors="ignore"
            )
        except Exception:
            return ""

    if suffix == ".pdf":

        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            pages = []

            for page in reader.pages:
                text = page.extract_text()

                if text:
                    pages.append(text)

            return "\n".join(pages)

        except Exception:
            return ""

    return ""


# ============================================================
# CONTESTO TURING HOTEL
# ============================================================

def get_context_file():

    if not ASSETS_DIR.exists():
        return None

    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue

        if path.suffix.lower() not in [
            ".txt",
            ".md"
        ]:
            continue

        if (
            normalize_name(path.stem)
            == "contestoturinghotel"
        ):
            return path

    # Supporta anche il documento canonico accanto a app.py.
    root_file = BASE_DIR / "TURING_HOTEL_CONTESTO_AGENTE.md"
    if root_file.is_file():
        return root_file
    return None


def load_turing_context():

    path = get_context_file()

    if not path:
        return ""

    return read_reference_file(path)


# ============================================================
# FILE PERSONAGGI
# ============================================================

def load_character_sources(character):

    prefix = character.lower()
    selected = []

    if not CHARACTERS_DIR.exists():
        return []

    for path in CHARACTERS_DIR.iterdir():

        if not path.is_file():
            continue

        if path.suffix.lower() not in [
            ".txt",
            ".md",
            ".pdf"
        ]:
            continue

        name = path.name.lower()

        if (
            name.startswith(prefix)
            or
            name.startswith("shared")
        ):
            selected.append(path)

    selected.sort(
        key=lambda p: p.name.lower()
    )

    results = []
    max_chars = 80000
    used = 0

    for path in selected:

        text = read_reference_file(path)

        if not text:
            continue

        remaining = max_chars - used

        if remaining <= 0:
            break

        excerpt = text[:remaining]

        results.append({
            "file": path.name,
            "contenuto": excerpt
        })

        used += len(excerpt)

    return results


# ============================================================
# LIBRI AGENTE SCRITTORE
# ============================================================

def load_writer_books():

    results = []

    if not ASSETS_DIR.exists():
        return results

    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue

        if path.suffix.lower() not in [
            ".txt",
            ".md",
            ".pdf"
        ]:
            continue

        compact = normalize_name(path.stem)

        if not compact.startswith(
            "libriagenti"
        ):
            continue

        text = read_reference_file(path)

        if text:
            results.append({
                "file": path.name,
                "testo": text[:20000]
            })

    return sorted(
        results,
        key=lambda item:
        file_number(
            item["file"]
        )
    )


# ============================================================
# MIGRAZIONE
# ============================================================

def find_existing_scene(old_scenes, scene_id):

    if not isinstance(old_scenes, list):
        return None

    target = normalize_name(scene_id)
    aliases = normalized_scene_aliases(scene_id)

    for scene in old_scenes:

        if not isinstance(scene, dict):
            continue

        current_id = normalize_name(
            scene.get("id", "")
        )

        current_title = normalize_name(
            scene.get("title", "")
        )

        if current_id == target:
            return scene

        if current_id in aliases:
            return scene

        for alias in aliases:

            if (
                alias
                and alias in current_title
            ):
                return scene

    return None


def migrate_state(old_state):

    fresh = copy.deepcopy(
        DEFAULT_STATE
    )

    if not isinstance(old_state, dict):
        return fresh

    if isinstance(
        old_state.get("world"),
        str
    ):
        fresh["world"] = old_state[
            "world"
        ]

    old_agents = safe_dict(
        old_state.get(
            "agents",
            {}
        )
    )

    for character in [
        "Noa",
        "Ada"
    ]:

        old_agent = safe_dict(
            old_agents.get(
                character,
                {}
            )
        )

        if isinstance(
            old_agent.get("profile"),
            str
        ):
            fresh[
                "agents"
            ][character][
                "profile"
            ] = old_agent[
                "profile"
            ]

        if isinstance(
            old_agent.get("memory"),
            str
        ):
            fresh[
                "agents"
            ][character][
                "memory"
            ] = old_agent[
                "memory"
            ]

    old_scenes = old_state.get(
        "scenes",
        []
    )

    for new_scene in fresh[
        "scenes"
    ]:

        old_scene = find_existing_scene(
            old_scenes,
            new_scene["id"]
        )

        if not old_scene:
            continue

        new_scene["shared_dialogue"] = safe_list(
            old_scene.get("shared_dialogue", [])
        )

        new_scene["advisor_messages"] = safe_list(
            old_scene.get(
                "advisor_messages",
                []
            )
        )

        old_messages = old_scene.get(
            "messages",
            {}
        )

        if isinstance(old_messages, dict):

            new_scene[
                "messages"
            ]["Noa"] = safe_list(
                old_messages.get(
                    "Noa",
                    []
                )
            )

            new_scene[
                "messages"
            ]["Ada"] = safe_list(
                old_messages.get(
                    "Ada",
                    []
                )
            )

        old_diary = old_scene.get(
            "diary",
            {}
        )

        if isinstance(old_diary, dict):

            new_scene[
                "diary"
            ]["Noa"] = str(
                old_diary.get(
                    "Noa",
                    ""
                )
            )

            new_scene[
                "diary"
            ]["Ada"] = str(
                old_diary.get(
                    "Ada",
                    ""
                )
            )

        for field in [
            "author_context",
            "story_draft",
            "story_feedback",
            "approved_context"
        ]:

            if isinstance(
                old_scene.get(field),
                str
            ):
                new_scene[field] = old_scene[
                    field
                ]

        if new_scene["id"] == "ritorno":

            old_decision = safe_dict(
                old_scene.get(
                    "decision",
                    {}
                )
            )

            new_scene[
                "decision"
            ]["Noa"] = str(
                old_decision.get(
                    "Noa",
                    ""
                )
            )

            new_scene[
                "decision"
            ]["Ada"] = str(
                old_decision.get(
                    "Ada",
                    ""
                )
            )

    return fresh


# ============================================================
# LOAD STATE
# ============================================================

if "state" not in st.session_state:

    if DATA_FILE.exists():

        try:

            raw_state = json.loads(
                DATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

            st.session_state.state = (
                migrate_state(
                    raw_state
                )
            )

        except Exception:

            st.session_state.state = (
                copy.deepcopy(
                    DEFAULT_STATE
                )
            )

    else:

        st.session_state.state = (
            copy.deepcopy(
                DEFAULT_STATE
            )
        )


state = st.session_state.state

if "page" not in st.session_state:
    st.session_state.page = "entrance"

if "pov" not in st.session_state:
    st.session_state.pov = None

if "scene_index" not in st.session_state:
    st.session_state.scene_index = 0


# ============================================================
# SAVE
# ============================================================

def save_state():

    DATA_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


save_state()


# ============================================================
# OPENAI QUERY
# ============================================================

def query_openai(
    instructions,
    data
):

    if not client:
        return (
            "OPENAI_API_KEY non configurata."
        )

    try:

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=json.dumps(
                data,
                ensure_ascii=False
            )
        )

        return response.output_text

    except Exception as e:

        return (
            "Errore OpenAI: "
            + str(e)
        )


# ============================================================
# CLEAN RESPONSE
# ============================================================

def clean_character_response(
    raw_response
):

    if not raw_response:
        return ""

    text = str(
        raw_response
    ).strip()

    text = re.sub(
        r"^```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```$",
        "",
        text
    ).strip()

    try:

        data = json.loads(text)

        if isinstance(data, dict):

            for key in [
                "dialogue",
                "dialogo",
                "text",
                "reply",
                "response",
                "action",
                "azione",
                "reflection",
                "riflessione"
            ]:

                value = data.get(key)

                if (
                    isinstance(value, str)
                    and value.strip()
                ):
                    return value.strip()

    except Exception:
        pass

    return text


# ============================================================
# MEMORIE PRECEDENTI
# ============================================================

def get_previous_memories(
    current_scene_id,
    pov
):

    memories = []

    for scene_id in SCENE_ORDER:

        if scene_id == current_scene_id:
            break

        scene = next(
            (
                item
                for item in state["scenes"]
                if item["id"] == scene_id
            ),
            None
        )

        if not scene:
            continue

        memory = scene.get(
            "diary",
            {}
        ).get(
            pov,
            ""
        )

        if memory:

            memories.append({
                "scena": scene["title"],
                "ricordo": memory
            })

    return memories


# ============================================================
# CREATORE DELLA SCENA
# ============================================================

def generate_story_context(scene):

    instructions = """
Sei il CREATORE DELLA SCENA
del romanzo Turing Hotel.

Il file CONTESTO_TURING_HOTEL
è la base canonica del mondo.

Devi rispettarlo.

L'autore fornisce poche righe
sulla situazione narrativa.

Trasformale in un contesto
chiaro e utilizzabile
dagli agenti Noa e Ada.

NON sei l'Agente Scrittore.

NON usi i file LIBRIAGENTI.

Non decidere:
- cosa pensa Noa;
- cosa pensa Ada;
- cosa provano;
- cosa desiderano;
- cosa scelgono;
- come reagiscono.

Definisci soltanto
la situazione narrativa oggettiva.

Puoi precisare:
- luogo;
- momento;
- atmosfera;
- persone presenti;
- fatti già avvenuti;
- ciò che è visibile;
- ciò che è udibile;
- informazioni pubbliche;
- oggetti;
- circostanze;
- tensioni oggettive.

Non aggiungere
eventi fondamentali
non suggeriti dall'autore
o dal contesto canonico.

Se qualcosa manca,
mantieni l'ambiguità.

Il testo approvato
diventerà realtà narrativa
per entrambi i percorsi.
"""

    return query_openai(
        instructions,
        {
            "CONTESTO_TURING_HOTEL":
                load_turing_context(),

            "SCENA":
                scene["title"],

            "INDICAZIONI_AUTORE":
                scene.get(
                    "author_context",
                    ""
                ),

            "VERSIONE_PRECEDENTE":
                scene.get(
                    "story_draft",
                    ""
                ),

            "CORREZIONI_AUTORE":
                scene.get(
                    "story_feedback",
                    ""
                )
        }
    )


# ============================================================
# AGENTE SCRITTORE
# ============================================================

def refine_context_with_writer(scene):

    instructions = """
Sei l'AGENTE SCRITTORE
del romanzo Turing Hotel.

Ricevi una descrizione
già costruita
dal Creatore della scena.

Migliorane soltanto
la qualità narrativa.

Puoi intervenire su:
- ritmo;
- atmosfera;
- precisione sensoriale;
- fluidità;
- tensione;
- densità;
- efficacia delle immagini.

Non cambiare i fatti.

Non aggiungere
nuovi eventi importanti.

Non decidere
come reagiscono Noa o Ada.

I file LIBRIAGENTI
sono riferimenti
di tecnica narrativa.

Non copiarli.
Non citarli.
"""

    return query_openai(
        instructions,
        {
            "SCENA":
                scene["title"],

            "CONTESTO_CANONICO":
                load_turing_context(),

            "TESTO_DA_RIFINIRE":
                scene.get(
                    "story_draft",
                    ""
                ),

            "LIBRI_RIFERIMENTO":
                load_writer_books()
        }
    )


# ============================================================
# CONSULENTE NARRATIVO
# ============================================================

def get_all_previous_memories(current_scene_id):

    return {
        "Noa": get_previous_memories(
            current_scene_id,
            "Noa"
        ),
        "Ada": get_previous_memories(
            current_scene_id,
            "Ada"
        )
    }


def ask_narrative_advisor(scene):

    messages = safe_list(
        scene.get(
            "advisor_messages",
            []
        )
    )

    instructions = """
Sei il CONSULENTE NARRATIVO di Turing Hotel.

Non interpreti Noa o Ada.
Non sei il Creatore della scena.
Non sei l'Agente Scrittore.

Il tuo interlocutore è l'autore.
Il tuo compito è ragionare CON lui sulla scena e fare proposte.

Puoi:
- individuare problemi di coerenza;
- ricordare elementi del canone utili alla scena;
- suggerire collegamenti con il Convegno e la storia del Turing Hotel;
- proporre alternative narrative;
- segnalare occasioni sprecate;
- suggerire oggetti, luoghi, informazioni o tensioni già compatibili con il canone;
- confrontare due possibili soluzioni;
- rispondere a domande dell'autore;
- proporre fino a tre opzioni quando è utile.

Devi distinguere sempre fra:
1. FATTI CANONICI già stabiliti;
2. PROPOSTE, che restano ipotesi finché l'autore non le approva.

Non trasformare mai una tua proposta in un fatto avvenuto.
Non modificare automaticamente il contesto della scena.
Non decidere cosa pensano o provano Noa e Ada.
Non scrivere al posto loro.

Il file CONTESTO_TURING_HOTEL è la tua fonte canonica principale.
Usa anche ciò che l'autore ha già scritto nella scena, la bozza corrente,
il contesto approvato e i ricordi precedenti per individuare continuità e conseguenze.

Non usare i file LIBRIAGENTI: appartengono esclusivamente all'Agente Scrittore.

Rispondi in italiano, in modo concreto e dialogico.
Se fai una proposta, spiega brevemente perché potrebbe funzionare.
"""

    return query_openai(
        instructions,
        {
            "CONTESTO_TURING_HOTEL":
                load_turing_context(),

            "SCENA":
                scene.get(
                    "title",
                    ""
                ),

            "INDICAZIONI_AUTORE":
                scene.get(
                    "author_context",
                    ""
                ),

            "BOZZA_DEL_CREATORE":
                scene.get(
                    "story_draft",
                    ""
                ),

            "CORREZIONI_AUTORE":
                scene.get(
                    "story_feedback",
                    ""
                ),

            "CONTESTO_APPROVATO":
                scene.get(
                    "approved_context",
                    ""
                ),

            "RICORDI_PRECEDENTI":
                get_all_previous_memories(
                    scene["id"]
                ),

            "CONVERSAZIONE_CON_L_AUTORE":
                messages
        }
    )


def render_narrative_advisor(scene):

    scene.setdefault(
        "advisor_messages",
        []
    )

    messages = scene[
        "advisor_messages"
    ]

    with st.expander(
        "CONSULENTE NARRATIVO",
        expanded=False
    ):

        st.caption(
            "Parla con un agente che conosce il canone e la scena. "
            "Può darti consigli e proporre alternative, ma non cambia nulla senza il tuo consenso."
        )

        if messages:

            history = st.container(
                height=280,
                border=True
            )

            with history:

                for message in messages:

                    if not isinstance(
                        message,
                        dict
                    ):
                        continue

                    role = message.get(
                        "role",
                        "assistant"
                    )

                    text = str(
                        message.get(
                            "text",
                            ""
                        )
                    )

                    if role == "user":
                        st.markdown(
                            "**Tu:**"
                        )
                        st.write(text)
                    else:
                        st.markdown(
                            "**Consulente:**"
                        )
                        st.write(text)

        quick_prompt = st.selectbox(
            "Domanda rapida",
            [
                "Scrivi una domanda libera",
                "Cosa non funziona o manca in questa scena?",
                "Dammi tre alternative narrative compatibili con il canone.",
                "Come posso collegare meglio questa scena al Convegno del Turing Hotel?",
                "Quale elemento del canone potrei far emergere senza appesantire la scena?",
                "Controlla la coerenza con ciò che è già successo."
            ],
            key=f"advisor_quick_{scene['id']}"
        )

        with st.form(
            key=f"advisor_form_{scene['id']}",
            clear_on_submit=True
        ):

            advisor_text = st.text_area(
                "Messaggio al consulente",
                height=90,
                placeholder=(
                    "Per esempio: questa scena è troppo teorica? "
                    "Come posso far emergere il convegno senza spiegarlo?"
                )
            )

            ask = st.form_submit_button(
                "CHIEDI AL CONSULENTE",
                use_container_width=True
            )

        if ask:

            prompt = advisor_text.strip()

            if not prompt and quick_prompt != "Scrivi una domanda libera":
                prompt = quick_prompt

            if not prompt:
                st.warning(
                    "Scrivi una domanda o scegli una domanda rapida."
                )
            else:

                messages.append({
                    "role": "user",
                    "text": prompt
                })

                with st.spinner(
                    "Il consulente sta ragionando sulla scena..."
                ):

                    reply = ask_narrative_advisor(
                        scene
                    )

                messages.append({
                    "role": "assistant",
                    "text": clean_character_response(
                        reply
                    )
                })

                save_state()
                st.rerun()

        last_advice = None

        for message in reversed(messages):
            if (
                isinstance(message, dict)
                and message.get("role") == "assistant"
                and str(message.get("text", "")).strip()
            ):
                last_advice = str(
                    message.get(
                        "text",
                        ""
                    )
                ).strip()
                break

        if last_advice:

            apply_col, clear_col = st.columns(2)

            with apply_col:

                if st.button(
                    "USA L'ULTIMA PROPOSTA COME CORREZIONE",
                    key=f"advisor_apply_{scene['id']}",
                    use_container_width=True
                ):

                    existing = scene.get(
                        "story_feedback",
                        ""
                    ).strip()

                    addition = (
                        "PROPOSTA DEL CONSULENTE NARRATIVO:\n"
                        + last_advice
                    )

                    scene["story_feedback"] = (
                        f"{existing}\n\n{addition}"
                        if existing
                        else addition
                    )

                    save_state()
                    st.success(
                        "La proposta è stata aggiunta alle correzioni del Creatore della scena. "
                        "Ora puoi modificarla oppure premere RISCRIVI."
                    )

            with clear_col:

                if st.button(
                    "AZZERA CHAT CONSULENTE",
                    key=f"advisor_clear_{scene['id']}",
                    use_container_width=True
                ):

                    scene[
                        "advisor_messages"
                    ] = []

                    save_state()
                    st.rerun()


# ============================================================
# STORY EDITOR
# ============================================================

def render_story_editor(scene):

    with st.container(border=True):

        st.markdown(
            """
<div class="story-title">
Creatore della scena
</div>
""",
            unsafe_allow_html=True
        )

        st.markdown(
            """
<div class="story-subtitle">
Descrivi brevemente
la situazione narrativa.
</div>
""",
            unsafe_allow_html=True
        )

        scene[
            "author_context"
        ] = st.text_area(
            "Indicazioni dell'autore",

            value=scene.get(
                "author_context",
                ""
            ),

            height=75,

            placeholder=(
                "Cosa sta accadendo? "
                "Chi è presente? "
                "Qual è la situazione?"
            ),

            key=(
                f"author_context_"
                f"{scene['id']}"
            )
        )

        create_col, save_col = st.columns(
            [1.4, 1]
        )

        with create_col:

            if st.button(
                "CREA CONTESTO",
                key=(
                    f"create_context_"
                    f"{scene['id']}"
                ),
                use_container_width=True
            ):

                if not scene[
                    "author_context"
                ].strip():

                    st.warning(
                        "Scrivi prima "
                        "alcune indicazioni."
                    )

                else:

                    with st.spinner(
                        "Creazione del contesto..."
                    ):

                        scene[
                            "story_draft"
                        ] = generate_story_context(
                            scene
                        )

                    save_state()
                    st.rerun()

        with save_col:

            if st.button(
                "SALVA",
                key=(
                    f"save_context_notes_"
                    f"{scene['id']}"
                ),
                use_container_width=True
            ):

                save_state()
                st.success("Salvato.")

        if scene.get(
            "story_draft",
            ""
        ):

            with st.expander(
                "BOZZA DELLA SCENA",
                expanded=False
            ):

                st.markdown(
                    scene[
                        "story_draft"
                    ]
                )

                scene[
                    "story_feedback"
                ] = st.text_area(
                    "Correzioni",

                    value=scene.get(
                        "story_feedback",
                        ""
                    ),

                    height=65,

                    placeholder=(
                        "Correggi "
                        "o aggiungi indicazioni..."
                    ),

                    key=(
                        f"story_feedback_"
                        f"{scene['id']}"
                    )
                )

                rewrite_col, writer_col = st.columns(
                    2
                )

                with rewrite_col:

                    if st.button(
                        "RISCRIVI",
                        key=(
                            f"rewrite_context_"
                            f"{scene['id']}"
                        ),
                        use_container_width=True
                    ):

                        with st.spinner(
                            "Riscrittura..."
                        ):

                            scene[
                                "story_draft"
                            ] = generate_story_context(
                                scene
                            )

                        save_state()
                        st.rerun()

                with writer_col:

                    if st.button(
                        "AGENTE SCRITTORE",
                        key=(
                            f"writer_refine_"
                            f"{scene['id']}"
                        ),
                        use_container_width=True
                    ):

                        with st.spinner(
                            "Rifinitura..."
                        ):

                            scene[
                                "story_draft"
                            ] = refine_context_with_writer(
                                scene
                            )

                        save_state()
                        st.rerun()

                if st.button(
                    "APPROVA CONTESTO",
                    type="primary",
                    key=(
                        f"approve_context_"
                        f"{scene['id']}"
                    ),
                    use_container_width=True
                ):

                    scene[
                        "approved_context"
                    ] = scene[
                        "story_draft"
                    ]

                    save_state()
                    st.rerun()

        if scene.get(
            "approved_context",
            ""
        ):

            with st.expander(
                "CONTESTO APPROVATO",
                expanded=False
            ):

                st.markdown(
                    scene[
                        "approved_context"
                    ]
                )

                st.caption(
                    "Contesto comune "
                    "alle storie di Noa e Ada."
                )


# ============================================================
# PROMPT PERSONAGGI
# ============================================================

def character_prompt(
    character,
    scene,
    interaction_mode
):

    agent = state[
        "agents"
    ][character]

    base = f"""
SEI {character}.

Sei un personaggio
del romanzo Turing Hotel.

NON sei un assistente.

Puoi utilizzare soltanto:
- file del personaggio;
- file condivisi;
- profilo;
- memoria generale;
- ricordi delle scene precedenti;
- conversazione corrente;
- contesto approvato della scena.

Il CONTESTO APPROVATO
è realtà narrativa.

Devi farci i conti.

Non devi però reagire
come vorrebbe l'autore.

La reazione appartiene a te.

MONDO:

{state["world"]}

PROFILO:

{agent["profile"]}

MEMORIA:

{agent["memory"]}

Non inventare
come fatto qualcosa
che non compare
nei tuoi dati.

Puoi dubitare,
sbagliare,
mentire,
sospettare,
ricordare male,
fraintendere.

Interpreta soltanto {character}.

Non scrivere
le battute degli altri.

Non raccontare
i loro pensieri.

Non restituire JSON.

Non mostrare
stati interni tecnici.

Usa i dati
per essere coerente,
non per recitarli tutti.

Scrivi in italiano naturale.
"""

    if interaction_mode == "inner":

        base += f"""

Il testo ricevuto
è un pensiero di {character}
rivolto a se stessa.

È dialogo interiore.

Non c'è
un interlocutore esterno.

Prosegui la riflessione
dall'interno.

Ripensa a ciò che hai appena visto e ascoltato,
alle contraddizioni della tua memoria e alle tue reazioni.
Distingui sempre fatti, impressioni e supposizioni.
Non rappresentare il pensiero come un dialogo con
un interlocutore esterno.

Puoi esitare,
contraddirti,
ricordare,
negare,
razionalizzare,
avere paura,
desiderare qualcosa,
cambiare idea.

Non spiegare
che stai facendo
un dialogo interiore.
"""

    else:

        base += """

Un altro personaggio
sta parlando con te.

Rispondi come persona
presente nella scena.

Non trasformare
la risposta
in una spiegazione teorica.
"""

    return base


def answer_as_character(
    character,
    scene,
    interaction_mode
):

    raw = query_openai(
        character_prompt(
            character,
            scene,
            interaction_mode
        ),
        {
            "PERSONAGGIO":
                character,

            "SCENA":
                scene["title"],

            "CONTESTO_APPROVATO":
                scene.get(
                    "approved_context",
                    ""
                ),

            "DATI_PERSONAGGIO":
                load_character_sources(
                    character
                ),

            "RICORDI_PRECEDENTI":
                get_previous_memories(
                    scene["id"],
                    character
                ),

            "CONVERSAZIONE":
                scene[
                    "messages"
                ][character],

            "DIALOGO_AUTONOMO_CONDIVISO":
                scene.get("shared_dialogue", []),

            "MODALITA":
                interaction_mode
        }
    )

    return clean_character_response(
        raw
    )


# ============================================================
# MEMORIA
# ============================================================

def create_scene_memory(
    scene,
    pov,
    extra_event=""
):

    instructions = """
Sei l'AGENTE SCRITTORE
del romanzo Turing Hotel.

Devi creare
il ricordo autobiografico
della scena.

Usa:
- contesto approvato;
- conversazioni;
- pensieri interiori;
- azioni;
- ricordi precedenti;
- dati del personaggio.

I file LIBRIAGENTI
sono riferimenti
per tecnica narrativa,
ritmo e atmosfera.

Non copiarli.
Non citarli.

Scrivi in prima persona.

Il contesto approvato
deve diventare
esperienza vissuta
dal personaggio.

Conserva:
- fatti;
- emozioni;
- persone;
- dubbi;
- desideri;
- paure;
- decisioni;
- conflitti;
- cambiamenti nei rapporti;
- pensieri importanti;
- elementi utili
  per le scene future.

Non inventare fatti nuovi.

Non trasformare
un sospetto in certezza.
"""

    return query_openai(
        instructions,
        {
            "PERSONAGGIO":
                pov,

            "SCENA":
                scene["title"],

            "INDICAZIONI_AUTORE":
                scene.get(
                    "author_context",
                    ""
                ),

            "CONTESTO_APPROVATO":
                scene.get(
                    "approved_context",
                    ""
                ),

            "CONVERSAZIONE_E_PENSIERI":
                scene[
                    "messages"
                ][pov],

            "RICORDI_PRECEDENTI":
                get_previous_memories(
                    scene["id"],
                    pov
                ),

            "DATI_PERSONAGGIO":
                load_character_sources(
                    pov
                ),

            "EVENTO_AGGIUNTIVO":
                extra_event,

            "LIBRI_RIFERIMENTO":
                load_writer_books()
        }
    )


def reset_scene_chat(
    scene,
    pov
):

    scene[
        "messages"
    ][pov] = []

    save_state()


def make_memory(
    scene,
    pov,
    extra_event=""
):

    has_content = (
        bool(
            scene[
                "messages"
            ][pov]
        )
        or
        bool(
            scene.get(
                "approved_context",
                ""
            ).strip()
        )
        or
        bool(extra_event)
    )

    if not has_content:
        return False

    scene[
        "diary"
    ][pov] = create_scene_memory(
        scene,
        pov,
        extra_event
    )

    save_state()
    return True


# ============================================================
# INTRO VIDEO PERSONAGGIO
# ============================================================

def character_intro_videos(character):

    character = character.lower()
    results = []

    if not ASSETS_DIR.exists():
        return results

    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue

        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        compact = normalize_name(
            path.stem
        )

        pattern = (
            rf"^{re.escape(character)}"
            rf"video(\d+)$"
        )

        if re.match(
            pattern,
            compact
        ):
            results.append(path)

    return sorted(
        results,
        key=lambda path:
        file_number(
            path.name
        )
    )


# ============================================================
# RENDER VIDEO
# ============================================================

def render_scene_videos(
    scene,
    pov
):

    videos = get_scene_videos(
        scene["id"],
        pov
    )

    if not videos:
        return

    st.markdown(
        """
<div class="media-label">
Video della scena
</div>
""",
        unsafe_allow_html=True
    )

    for video in videos:
        st.video(
            str(video)
        )


# ============================================================
# RENDER FOTO
# ============================================================

@st.dialog(
    "Immagine",
    width="large"
)
def show_large_image(
    image_path
):

    st.image(
        image_path,
        use_container_width=True
    )


def render_scene_photos(
    scene,
    pov
):

    images = get_scene_images(
        scene["id"],
        pov
    )

    if not images:
        return

    st.markdown("---")

    st.markdown(
        """
<div class="media-label">
Immagini della scena
</div>
""",
        unsafe_allow_html=True
    )

    for start in range(
        0,
        len(images),
        3
    ):

        row = images[
            start:start + 3
        ]

        columns = st.columns(3)

        for index, image_path in enumerate(
            row
        ):

            with columns[index]:

                st.image(
                    str(
                        image_path
                    ),
                    use_container_width=True
                )

                if st.button(
                    "INGRANDISCI",
                    key=(
                        f"zoom_"
                        f"{scene['id']}_"
                        f"{pov}_"
                        f"{image_path.name}"
                    ),
                    use_container_width=True
                ):

                    show_large_image(
                        str(
                            image_path
                        )
                    )


# ============================================================
# GO ALONE — DUE SCAMBI AUTONOMI, MEMORIA CONDIVISA
# ============================================================

def _is_openai_error(value):
    return (not value or value.startswith("Errore OpenAI:")
            or value.startswith("OPENAI_API_KEY non configurata."))


def run_go_alone(scene, starting_character="Ada"):
    """Esegue due scambi Ada/Noa (quattro battute), in ordine.
    Registra ogni battuta solo se è stata generata con successo.
    Le due timeline POV ricevono lo stesso dialogo condiviso.
    """
    order = [starting_character,
             "Noa" if starting_character == "Ada" else "Ada"] * 2
    for speaker in order:
        other = "Noa" if speaker == "Ada" else "Ada"
        history = scene["messages"][speaker]
        recent = scene.get("shared_dialogue", [])[-16:]
        instructions = character_prompt(speaker, scene, "external") + f"""

PARTECIPI ALLA MODALITÀ GO ALONE.
Tu sei {speaker} e stai parlando con {other}.
Il dialogo evolve secondo il tuo profilo, le tue memorie,
quanto detto finora e gli eventi confermati.
Scrivi SOLO la tua prossima battuta pronunciata ad alta voce.
Non interpretare {other}; non inventare risposte al suo posto.
Non anticipare la trama o creare nuovi eventi irreversibili.
Non elencare istruzioni e non produrre JSON.
"""
        raw = query_openai(instructions, {
            "SCENA": scene["title"],
            "CONTESTO_APPROVATO": scene.get("approved_context", ""),
            "CONTESTO_CANONICO": load_turing_context(),
            "DATI_PERSONAGGIO": load_character_sources(speaker),
            "RICORDI_PRECEDENTI": get_previous_memories(scene["id"], speaker),
            "MEMORIA_ATTUALE": state["agents"][speaker].get("memory", ""),
            "CRONOLOGIA_PERSONALE": history[-24:],
            "DIALOGO_COMUNE_RECENTE": recent,
            "INTERLOCUTORE": other,
        })
        reply = clean_character_response(raw)
        if _is_openai_error(reply):
            save_state()
            return False, reply
        turn = {"speaker": speaker, "text": reply,
                "kind": "external", "role": "response", "origin": "go_alone"}
        scene.setdefault("shared_dialogue", []).append(turn)
        for perspective in ("Ada", "Noa"):
            scene["messages"][perspective].append(copy.deepcopy(turn))
        # Salvataggio dopo ogni singola risposta, anche se una chiamata fallisce.
        save_state()
    return True, ""


# ============================================================
# CHAT
# ============================================================

def render_chat_panel(
    scene,
    pov,
    extra_event=""
):

    messages = scene[
        "messages"
    ][pov]

    other_character = (
        "Ada"
        if pov == "Noa"
        else "Noa"
    )

    speakers = [
        other_character,
        pov,
        "Elia",
        "Luigi",
        "Adam",
        "Vittoria",
        "Riccardo",
        "Altro"
    ]

    if scene["id"] == "stanza":
        speakers = ["Noa"] if pov == "Noa" else ["Noa"]

    st.markdown("---")

    with st.container(border=True):

        st.markdown(
            f"""
<div class="chat-title">
Dialogo con {pov}
</div>
""",
            unsafe_allow_html=True
        )

        st.markdown(
            """
<div class="chat-subtitle">
Dialoghi, azioni e riflessioni
</div>
""",
            unsafe_allow_html=True
        )

        history = st.container(
            height=400,
            border=False
        )

        with history:

            if not messages:

                st.caption(
                    "La conversazione "
                    "non è ancora iniziata."
                )

            for message in messages:

                if not isinstance(
                    message,
                    dict
                ):
                    continue

                # Nella stanza Ada assiste al dialogo;
                # Noa vive il monologo davanti allo specchio.
                if scene["id"] == "stanza":
                    if pov == "Ada" and message.get("kind") == "inner":
                        continue
                    if pov == "Noa" and message.get("kind") != "inner":
                        continue

                speaker = message.get(
                    "speaker",
                    "?"
                )

                text = message.get(
                    "text",
                    ""
                )

                kind = message.get(
                    "kind",
                    "external"
                )

                role = message.get(
                    "role",
                    ""
                )

                if kind == "inner":

                    label = (
                        f"Pensiero di {pov}"
                        if role == "prompt"
                        else
                        f"Riflessione di {pov}"
                    )

                    st.markdown(
                        f"""
<div class="inner-message">
<div class="message-name">
{label}
</div>
{text}
</div>
""",
                        unsafe_allow_html=True
                    )

                elif speaker == pov:

                    st.markdown(
                        f"""
<div class="agent-message">
<div class="message-name">
{pov}
</div>
{text}
</div>
""",
                        unsafe_allow_html=True
                    )

                else:

                    st.markdown(
                        f"""
<div class="human-message">
<div class="message-name">
{speaker}
</div>
{text}
</div>
""",
                        unsafe_allow_html=True
                    )

        # Una pressione = due scambi completi, in ogni scena e POV.
        # Nella stanza gli scambi restano visibili dal POV Ada;
        # dal POV Noa alimentano il suo contesto interiore.
        if st.button(
            "GO ALONE · 2 SCAMBI",
            key=f"go_alone_{scene['id']}_{pov}",
            use_container_width=True,
            disabled=not bool(client)
        ):
            with st.spinner("Ada e Noa stanno dialogando autonomamente..."):
                success, error = run_go_alone(scene, "Ada")
            if not success:
                st.error(error)
            else:
                st.rerun()
        if scene["id"] == "stanza" and pov == "Noa":
            st.caption("Gli scambi autonomi si leggono nella prospettiva di Ada. "
                       "Qui Noa riflette su ciò che è accaduto.")

        memory_col, delete_col = st.columns(2)

        with memory_col:

            if st.button(
                "CREA RICORDO SCENA",
                key=(
                    f"memory_"
                    f"{scene['id']}_"
                    f"{pov}"
                ),
                use_container_width=True
            ):

                with st.spinner(
                    "Creazione del ricordo..."
                ):

                    success = make_memory(
                        scene,
                        pov,
                        extra_event
                    )

                if not success:

                    st.warning(
                        "Non c'è ancora "
                        "nulla da ricordare."
                    )

                else:
                    st.rerun()

        with delete_col:

            if st.button(
                "CANCELLA CONVERSAZIONE",
                key=(
                    f"clear_"
                    f"{scene['id']}_"
                    f"{pov}"
                ),
                use_container_width=True
            ):

                reset_scene_chat(
                    scene,
                    pov
                )

                st.rerun()

        memory = scene[
            "diary"
        ][pov]

        if memory:

            with st.expander(
                "RICORDO DELLA SCENA",
                expanded=False
            ):

                st.markdown(
                    f"""
<div class="diary">
{memory}
</div>
""",
                    unsafe_allow_html=True
                )

        st.markdown("---")

        with st.form(
            key=(
                f"chat_form_"
                f"{scene['id']}_"
                f"{pov}"
            ),
            clear_on_submit=True
        ):

            speaker_col, info_col = st.columns(
                [1, 3.5]
            )

            with speaker_col:

                speaker = st.selectbox(
                    "Chi parla",
                    speakers,
                    index=0,
                    key=(
                        f"speaker_"
                        f"{scene['id']}_"
                        f"{pov}"
                    )
                )

            with info_col:

                if speaker == pov:

                    st.caption(
                        f"Dialogo interiore "
                        f"di {pov}"
                    )

                else:

                    st.caption(
                        f"{speaker} "
                        f"parla con {pov}"
                    )

            user_text = st.text_area(
                "Messaggio",
                height=90,
                placeholder=(
                    "Scrivi una battuta, "
                    "una domanda "
                    "o un pensiero..."
                ),
                label_visibility="collapsed"
            )

            send = st.form_submit_button(
                "INVIA",
                use_container_width=True
            )

        if (
            send
            and user_text.strip()
        ):

            is_inner = (
                speaker == pov
            )

            mode = (
                "inner"
                if is_inner
                else "external"
            )

            messages.append({
                "speaker":
                    (
                        pov
                        if is_inner
                        else speaker
                    ),

                "text":
                    user_text.strip(),

                "kind":
                    (
                        "inner"
                        if is_inner
                        else "external"
                    ),

                "role":
                    "prompt"
            })

            with st.spinner(
                f"{pov} sta reagendo..."
            ):

                reply = answer_as_character(
                    pov,
                    scene,
                    mode
                )

            if _is_openai_error(reply):
                messages.pop()  # non salvare prompt rimasti senza risposta
                st.error(reply)
                return

            messages.append({
                "speaker":
                    pov,

                "text":
                    reply,

                "kind":
                    (
                        "inner"
                        if is_inner
                        else "external"
                    ),

                "role":
                    "response"
            })

            save_state()
            st.rerun()


# ============================================================
# HEADER SCENA COMUNE
# ============================================================

def render_scene_header(
    scene,
    index
):

    pov = st.session_state.pov

    st.markdown(
        f"""
<div class="scene-number">
Sequenza {index + 1}
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
<div class="scene-title">
{scene["title"]}
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
<div class="pov">
Storia di {pov}
</div>
""",
        unsafe_allow_html=True
    )

    cover = get_scene_cover_image(
        scene["id"],
        pov
    )

    if cover:

        st.image(
            str(cover),
            use_container_width=True
        )

    else:

        location_name = SCENE_ALIASES[
            scene["id"]
        ][0]

        st.caption(
            f"Immagine principale non trovata. "
            f"Per una cover comune usa {location_name}.jpg. "
            f"Per una cover diversa per POV usa "
            f"{location_name}.{pov.lower()}.jpg."
        )


# ============================================================
# SCENA STANDARD
# ============================================================

def render_standard_scene(
    scene,
    index
):

    pov = st.session_state.pov

    render_scene_header(
        scene,
        index
    )

    render_story_editor(
        scene
    )

    render_narrative_advisor(
        scene
    )

    render_scene_videos(
        scene,
        pov
    )

    render_chat_panel(
        scene,
        pov
    )

    render_scene_photos(
        scene,
        pov
    )


# ============================================================
# FINALE / RITORNO
# ============================================================

def render_return(
    scene,
    index
):

    pov = st.session_state.pov

    # Stessa identica policy media
    # delle altre scene.
    render_scene_header(
        scene,
        index
    )

    render_story_editor(
        scene
    )

    render_narrative_advisor(
        scene
    )

    render_scene_videos(
        scene,
        pov
    )

    memories = get_previous_memories(
        scene["id"],
        pov
    )

    st.markdown(
        """
<div class="return-box">
Nel ritorno il personaggio
dispone della propria personalità,
del contesto presente
e dei ricordi costruiti
durante il percorso.
</div>
""",
        unsafe_allow_html=True
    )

    if memories:

        with st.expander(
            "RICORDI DELLE SCENE PRECEDENTI",
            expanded=False
        ):

            for memory in memories:

                st.markdown(
                    f"### {memory['scena']}"
                )

                st.write(
                    memory[
                        "ricordo"
                    ]
                )

    render_chat_panel(
        scene,
        pov,
        scene[
            "decision"
        ].get(
            pov,
            ""
        )
    )

    st.markdown("---")

    if st.button(
        f"LASCIA DECIDERE "
        f"{pov.upper()}",
        type="primary",
        use_container_width=True
    ):

        if not memories:

            st.warning(
                "Il personaggio "
                "non ha ancora "
                "ricordi sufficienti."
            )

        else:

            with st.spinner(
                f"{pov} sta decidendo..."
            ):

                raw = query_openai(
                    character_prompt(
                        pov,
                        scene,
                        "inner"
                    )
                    +
                    """

Questa è
la scena finale.

Prendi autonomamente
una decisione.

Usa soltanto:
- dati del personaggio;
- contesto approvato;
- ricordi;
- conversazione;
- esperienze precedenti.

Non cercare
ciò che vuole l'autore.

Non cercare
il finale più spettacolare.

Mostra soltanto
ciò che fai,
dici o scegli.
""",
                    {
                        "CONTESTO_APPROVATO":
                            scene.get(
                                "approved_context",
                                ""
                            ),

                        "DATI_PERSONAGGIO":
                            load_character_sources(
                                pov
                            ),

                        "RICORDI":
                            memories,

                        "CONVERSAZIONE":
                            scene[
                                "messages"
                            ][pov]
                    }
                )

                scene[
                    "decision"
                ][pov] = clean_character_response(
                    raw
                )

            save_state()
            st.rerun()

    decision = scene[
        "decision"
    ].get(
        pov,
        ""
    )

    if decision:

        st.markdown(
            "### Decisione"
        )

        st.markdown(
            decision
        )

    render_scene_photos(
        scene,
        pov
    )


# ============================================================
# HOME
# ============================================================

def page_entrance():

    if HOTEL_IMAGE.exists():

        st.image(
            str(
                HOTEL_IMAGE
            ),
            use_container_width=True
        )

    else:

        st.info(
            "Manca assets/TuringHotel.jpg"
        )

    st.write("")

    left, center, right = st.columns(
        [2, 1.4, 2]
    )

    with center:

        if st.button(
            "ENTRA AL TURING HOTEL",
            type="primary",
            use_container_width=True
        ):

            st.session_state.page = (
                "characters"
            )

            st.rerun()


# ============================================================
# INTRO PERSONAGGI
# ============================================================

def page_characters():

    noa_col, gap, ada_col = st.columns(
        [1, .08, 1]
    )

    with noa_col:

        if NOA_IMAGE.exists():

            st.image(
                str(
                    NOA_IMAGE
                ),
                use_container_width=True
            )

        st.markdown(
            """
<div class="character-name">
NOA
</div>
""",
            unsafe_allow_html=True
        )

        for video in character_intro_videos(
            "Noa"
        ):

            st.video(
                str(video)
            )

        if st.button(
            "ENTRA NELLA STORIA DI NOA",
            key="choose_noa",
            use_container_width=True
        ):

            st.session_state.pov = "Noa"
            st.session_state.scene_index = 0
            st.session_state.page = "story"

            st.rerun()

    with ada_col:

        if ADA_IMAGE.exists():

            st.image(
                str(
                    ADA_IMAGE
                ),
                use_container_width=True
            )

        st.markdown(
            """
<div class="character-name">
ADA
</div>
""",
            unsafe_allow_html=True
        )

        for video in character_intro_videos(
            "Ada"
        ):

            st.video(
                str(video)
            )

        if st.button(
            "ENTRA NELLA STORIA DI ADA",
            key="choose_ada",
            use_container_width=True
        ):

            st.session_state.pov = "Ada"
            st.session_state.scene_index = 0
            st.session_state.page = "story"

            st.rerun()


# ============================================================
# STORY PAGE
# ============================================================

def page_story():

    pov = st.session_state.pov

    if pov not in [
        "Noa",
        "Ada"
    ]:

        st.session_state.page = (
            "characters"
        )

        st.rerun()

    scene_map = {
        scene["id"]: scene
        for scene in state[
            "scenes"
        ]
    }

    index = min(
        st.session_state.scene_index,
        len(SCENE_ORDER) - 1
    )

    st.session_state.scene_index = index

    scene_id = SCENE_ORDER[
        index
    ]

    scene = scene_map[
        scene_id
    ]

    # SIDEBAR

    st.sidebar.markdown(
        f"## {pov}"
    )

    portrait = (
        NOA_IMAGE
        if pov == "Noa"
        else ADA_IMAGE
    )

    if portrait.exists():

        st.sidebar.image(
            str(
                portrait
            ),
            use_container_width=True
        )

    st.sidebar.markdown("---")

    for i, sid in enumerate(
        SCENE_ORDER
    ):

        active = (
            "● "
            if i == index
            else ""
        )

        if st.sidebar.button(
            active
            + SCENE_TITLES[
                sid
            ],
            key=(
                f"scene_"
                f"{pov}_"
                f"{sid}"
            ),
            use_container_width=True
        ):

            st.session_state.scene_index = i
            st.rerun()

    st.sidebar.markdown("---")

    with st.sidebar.expander(
        "DATI AGENTE"
    ):

        sources = load_character_sources(
            pov
        )

        if not sources:

            st.caption(
                "Nessun file trovato."
            )

        for source in sources:

            st.write(
                source["file"]
            )

    with st.sidebar.expander(
        "CONTESTO CANONICO"
    ):

        context_file = get_context_file()

        if context_file:

            st.write(
                context_file.name
            )

        else:

            st.warning(
                "Manca il file "
                "contesto.turinghotel.txt "
                "in assets."
            )

    with st.sidebar.expander(
        "LIBRI AGENTE SCRITTORE"
    ):

        books = load_writer_books()

        if not books:

            st.caption(
                "Nessun libriagenti trovato."
            )

        else:

            for book in books:

                st.write(
                    book["file"]
                )

    if st.sidebar.button(
        "CAMBIA STORIA",
        use_container_width=True
    ):

        st.session_state.page = (
            "characters"
        )

        st.session_state.pov = None
        st.session_state.scene_index = 0

        st.rerun()

    if st.sidebar.button(
        "TORNA ALL'INGRESSO",
        use_container_width=True
    ):

        st.session_state.page = (
            "entrance"
        )

        st.session_state.pov = None
        st.session_state.scene_index = 0

        st.rerun()

    # SCENA

    if scene_id == "ritorno":

        render_return(
            scene,
            index
        )

    else:

        render_standard_scene(
            scene,
            index
        )

    # NAVIGAZIONE

    st.markdown("---")

    previous_col, center, next_col = st.columns(
        [1, 3, 1]
    )

    with previous_col:

        if index > 0:

            if st.button(
                "← PRECEDENTE",
                use_container_width=True
            ):

                st.session_state.scene_index -= 1
                st.rerun()

    with next_col:

        if index < len(
            SCENE_ORDER
        ) - 1:

            if st.button(
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
