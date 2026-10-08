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
# ESTENSIONI MEDIA
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

client = (
    OpenAI(api_key=openai_key)
    if openai_key
    else None
)

try:
    OPENAI_MODEL = st.secrets.get(
        "OPENAI_MODEL",
        "gpt-5.6"
    )
except Exception:
    OPENAI_MODEL = os.environ.get(
        "OPENAI_MODEL",
        "gpt-5.6"
    )


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
    "funerale",
    "matrimonio",
    "reparto_nascite",
    "ritorno"
]

SCENE_TITLES = {
    "hall": "La Hall",
    "funerale": "Il Funerale",
    "matrimonio": "Il Matrimonio",
    "reparto_nascite": "Il reparto nascite",
    "ritorno": "Il ritorno"
}

SCENE_FILE_ALIASES = {

    "hall": [
        "hall"
    ],

    "funerale": [
        "funerale"
    ],

    "matrimonio": [
        "matrimonio"
    ],

    "reparto_nascite": [
        "repartonascite",
        "reparto nascite",
        "reparto_nascite",
        "reparto-nascite",
        "reparto.nascite",
        "nascite"
    ],

    "ritorno": [
        "ritorno"
    ]
}


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

        "messages": {
            "Noa": [],
            "Ada": []
        },

        "diary": {
            "Noa": "",
            "Ada": ""
        }
    }

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

È stata progettata per comprendere
gli esseri umani,
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
Ada è la figlia del professor Elia.

È cresciuta nel Turing Hotel.

È intelligente,
pratica,
riservata
e osservatrice.
""",

            "memory": ""
        }
    },

    "scenes": [

        empty_scene(
            "hall",
            "La Hall"
        ),

        empty_scene(
            "funerale",
            "Il Funerale"
        ),

        empty_scene(
            "matrimonio",
            "Il Matrimonio"
        ),

        empty_scene(
            "reparto_nascite",
            "Il reparto nascite"
        ),

        empty_scene(
            "ritorno",
            "Il ritorno"
        )
    ]
}


# ============================================================
# UTILITY
# ============================================================

def safe_list(value):

    return (
        value
        if isinstance(value, list)
        else []
    )


def safe_dict(value):

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def normalize_media_name(value):

    value = str(
        value
    ).lower().strip()

    value = re.sub(
        r"\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$",
        "",
        value,
        flags=re.IGNORECASE
    )

    # Rende equivalenti:
    # reparto nascite
    # reparto_nascite
    # reparto-nascite
    # reparto.nascite
    # repartonascite

    value = re.sub(
        r"[\s_.\-]+",
        "",
        value
    )

    return value


def number_from_filename(filename):

    stem = Path(
        filename
    ).stem.lower()

    matches = re.findall(
        r"(\d+)$",
        stem
    )

    if matches:
        return int(
            matches[-1]
        )

    return 0


# ============================================================
# FILE READER
# ============================================================

def read_reference_file(path):

    suffix = (
        path.suffix.lower()
    )

    if suffix in [
        ".txt",
        ".md"
    ]:

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

            reader = PdfReader(
                str(path)
            )

            pages = []

            for page in reader.pages:

                text = (
                    page.extract_text()
                )

                if text:

                    pages.append(
                        text
                    )

            return "\n".join(
                pages
            )

        except Exception:

            return ""

    return ""


# ============================================================
# CONTESTO CANONICO
# ============================================================

def get_context_file():

    candidates = [

        ASSETS_DIR
        / "contesto.turinghotel.txt",

        ASSETS_DIR
        / "contesto.turing hotel.txt",

        ASSETS_DIR
        / "Contesto.TuringHotel.txt",

        ASSETS_DIR
        / "Contesto Turing Hotel.txt"
    ]

    for path in candidates:

        if path.exists():
            return path

    # Cerca anche ignorando maiuscole,
    # spazi, punti, trattini e underscore.

    wanted = {
        "contestoturinghotel"
    }

    if ASSETS_DIR.exists():

        for path in ASSETS_DIR.iterdir():

            if not path.is_file():
                continue

            if path.suffix.lower() not in [
                ".txt",
                ".md"
            ]:
                continue

            if (
                normalize_media_name(
                    path.stem
                )
                in wanted
            ):

                return path

    return None


def load_turing_context():

    context_file = (
        get_context_file()
    )

    if not context_file:
        return ""

    try:

        return (
            context_file.read_text(
                encoding="utf-8",
                errors="ignore"
            )
        )

    except Exception:

        return ""


# ============================================================
# FILE PERSONAGGI
# ============================================================

def load_character_sources(
    character
):

    prefix = (
        character.lower()
    )

    selected = []

    if not CHARACTERS_DIR.exists():
        return []

    for path in (
        CHARACTERS_DIR.iterdir()
    ):

        if not path.is_file():
            continue

        if path.suffix.lower() not in [
            ".txt",
            ".md",
            ".pdf"
        ]:

            continue

        name = (
            path.name.lower()
        )

        if (
            name.startswith(prefix)
            or
            name.startswith("shared")
        ):

            selected.append(
                path
            )

    selected.sort(
        key=lambda p:
        p.name.lower()
    )

    results = []

    max_chars = 80000
    used = 0

    for path in selected:

        text = (
            read_reference_file(
                path
            )
        )

        if not text:
            continue

        remaining = (
            max_chars
            - used
        )

        if remaining <= 0:
            break

        excerpt = (
            text[:remaining]
        )

        results.append({

            "file":
                path.name,

            "contenuto":
                excerpt
        })

        used += len(
            excerpt
        )

    return results


# ============================================================
# LIBRI AGENTE SCRITTORE
# ============================================================

def load_writer_books():

    results = []

    if not ASSETS_DIR.exists():

        return results

    for path in (
        ASSETS_DIR.iterdir()
    ):

        if not path.is_file():
            continue

        normalized = (
            normalize_media_name(
                path.stem
            )
        )

        if not normalized.startswith(
            "libriagenti"
        ):

            continue

        if path.suffix.lower() not in [
            ".txt",
            ".md",
            ".pdf"
        ]:

            continue

        text = (
            read_reference_file(
                path
            )
        )

        if text:

            results.append({

                "file":
                    path.name,

                "testo":
                    text[:20000]
            })

    return sorted(
        results,
        key=lambda x:
        number_from_filename(
            x["file"]
        )
    )


# ============================================================
# MIGRAZIONE STATO
# ============================================================

def find_existing_scene(
    old_scenes,
    scene_id
):

    if not isinstance(
        old_scenes,
        list
    ):

        return None

    aliases = (
        SCENE_FILE_ALIASES.get(
            scene_id,
            [scene_id]
        )
    )

    normalized_aliases = {
        normalize_media_name(
            alias
        )
        for alias in aliases
    }

    for old_scene in old_scenes:

        if not isinstance(
            old_scene,
            dict
        ):

            continue

        old_id = (
            normalize_media_name(
                old_scene.get(
                    "id",
                    ""
                )
            )
        )

        old_title = (
            normalize_media_name(
                old_scene.get(
                    "title",
                    ""
                )
            )
        )

        if (
            old_id
            ==
            normalize_media_name(
                scene_id
            )
        ):

            return old_scene

        if (
            old_id
            in normalized_aliases
        ):

            return old_scene

        for alias in normalized_aliases:

            if (
                alias
                and
                alias in old_title
            ):

                return old_scene

    return None


def migrate_state(
    old_state
):

    fresh = (
        copy.deepcopy(
            DEFAULT_STATE
        )
    )

    if not isinstance(
        old_state,
        dict
    ):

        return fresh

    if isinstance(
        old_state.get(
            "world"
        ),
        str
    ):

        fresh[
            "world"
        ] = old_state[
            "world"
        ]

    old_agents = (
        safe_dict(
            old_state.get(
                "agents",
                {}
            )
        )
    )

    for character in [
        "Noa",
        "Ada"
    ]:

        old_agent = (
            safe_dict(
                old_agents.get(
                    character,
                    {}
                )
            )
        )

        if isinstance(
            old_agent.get(
                "profile"
            ),
            str
        ):

            fresh[
                "agents"
            ][character][
                "profile"
            ] = (
                old_agent[
                    "profile"
                ]
            )

        if isinstance(
            old_agent.get(
                "memory"
            ),
            str
        ):

            fresh[
                "agents"
            ][character][
                "memory"
            ] = (
                old_agent[
                    "memory"
                ]
            )

    old_scenes = (
        old_state.get(
            "scenes",
            []
        )
    )

    for new_scene in (
        fresh[
            "scenes"
        ]
    ):

        old_scene = (
            find_existing_scene(
                old_scenes,
                new_scene["id"]
            )
        )

        if not old_scene:
            continue

        old_messages = (
            old_scene.get(
                "messages",
                {}
            )
        )

        if isinstance(
            old_messages,
            dict
        ):

            new_scene[
                "messages"
            ]["Noa"] = (
                safe_list(
                    old_messages.get(
                        "Noa",
                        []
                    )
                )
            )

            new_scene[
                "messages"
            ]["Ada"] = (
                safe_list(
                    old_messages.get(
                        "Ada",
                        []
                    )
                )
            )

        old_diary = (
            old_scene.get(
                "diary",
                {}
            )
        )

        if isinstance(
            old_diary,
            dict
        ):

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
                old_scene.get(
                    field
                ),
                str
            ):

                new_scene[
                    field
                ] = (
                    old_scene[
                        field
                    ]
                )

        if (
            new_scene["id"]
            == "ritorno"
        ):

            old_decision = (
                safe_dict(
                    old_scene.get(
                        "decision",
                        {}
                    )
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

if "state" not in (
    st.session_state
):

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


state = (
    st.session_state.state
)


if "page" not in st.session_state:

    st.session_state.page = (
        "entrance"
    )


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
# OPENAI
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

        response = (
            client.responses.create(

                model=OPENAI_MODEL,

                instructions=instructions,

                input=json.dumps(
                    data,
                    ensure_ascii=False
                )
            )
        )

        return (
            response.output_text
        )

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

        data = json.loads(
            text
        )

        if isinstance(
            data,
            dict
        ):

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

                value = (
                    data.get(
                        key
                    )
                )

                if (
                    isinstance(
                        value,
                        str
                    )
                    and
                    value.strip()
                ):

                    return (
                        value.strip()
                    )

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

    for scene_id in (
        SCENE_ORDER
    ):

        if (
            scene_id
            == current_scene_id
        ):

            break

        scene = next(

            (
                s
                for s in state[
                    "scenes"
                ]
                if s[
                    "id"
                ] == scene_id
            ),

            None
        )

        if not scene:
            continue

        memory = (
            scene.get(
                "diary",
                {}
            ).get(
                pov,
                ""
            )
        )

        if memory:

            memories.append({

                "scena":
                    scene[
                        "title"
                    ],

                "ricordo":
                    memory
            })

    return memories


# ============================================================
# CREATORE DELLA SCENA
# ============================================================

def generate_story_context(
    scene
):

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
non suggeriti
dall'autore
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
                scene[
                    "title"
                ],

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

def refine_context_with_writer(
    scene
):

    instructions = """
Sei l'AGENTE SCRITTORE
del romanzo Turing Hotel.

Ricevi una descrizione
già costruita
dal Creatore della scena.

Il tuo compito
è migliorarne
la qualità narrativa.

Puoi intervenire su:

- ritmo;
- atmosfera;
- precisione sensoriale;
- fluidità;
- tensione;
- densità;
- efficacia delle immagini.

Non cambiare
i fatti stabiliti.

Non aggiungere
nuovi eventi importanti.

Non decidere
come reagiscono Noa o Ada.

I file LIBRIAGENTI
sono riferimenti
di tecnica narrativa.

Non copiarli.

Non citarli.

Non imitare
letteralmente
un autore riconoscibile.
"""

    return query_openai(

        instructions,

        {
            "SCENA":
                scene[
                    "title"
                ],

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
# LOCATION / ALIAS ROBUSTI
# ============================================================

def scene_location_aliases(
    scene_id
):

    return (
        SCENE_FILE_ALIASES.get(
            scene_id,
            [scene_id]
        )
    )


def scene_normalized_aliases(
    scene_id
):

    return {
        normalize_media_name(
            alias
        )
        for alias in
        scene_location_aliases(
            scene_id
        )
    }


# ============================================================
# FOTO PRINCIPALE LOCATION
# ============================================================

def get_scene_cover_image(
    scene_id
):

    if not ASSETS_DIR.exists():

        return None

    aliases = (
        scene_normalized_aliases(
            scene_id
        )
    )

    for path in (
        ASSETS_DIR.iterdir()
    ):

        if not path.is_file():
            continue

        if (
            path.suffix.lower()
            not in IMAGE_EXTENSIONS
        ):
            continue

        normalized_stem = (
            normalize_media_name(
                path.stem
            )
        )

        # matrimonio.jpg
        # Matrimonio.JPG
        # reparto nascite.jpg
        # reparto_nascite.jpg

        if (
            normalized_stem
            in aliases
        ):

            return path

    return None


# ============================================================
# STORY EDITOR A TUTTA LARGHEZZA
# ============================================================

def render_story_editor(
    scene
):

    with st.container(
        border=True
    ):

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
Descrivi brevemente la situazione narrativa.
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

        create_col, save_col = (
            st.columns(
                [1.4, 1]
            )
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
                        ] = (
                            generate_story_context(
                                scene
                            )
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

                st.success(
                    "Salvato."
                )

        # ====================================================
        # BOZZA
        # ====================================================

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
                        "Correggi o aggiungi "
                        "indicazioni..."
                    ),

                    key=(
                        f"story_feedback_"
                        f"{scene['id']}"
                    )
                )

                rewrite_col, writer_col = (
                    st.columns(2)
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
                            ] = (
                                generate_story_context(
                                    scene
                                )
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
                            ] = (
                                refine_context_with_writer(
                                    scene
                                )
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
                    ] = (
                        scene[
                            "story_draft"
                        ]
                    )

                    save_state()

                    st.rerun()

        # ====================================================
        # CONTESTO APPROVATO
        # ====================================================

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
                    "Questo contesto "
                    "è comune alle storie "
                    "di Noa e Ada."
                )


# ============================================================
# PROMPT PERSONAGGI
# ============================================================

def character_prompt(
    character,
    scene,
    interaction_mode
):

    agent = (
        state[
            "agents"
        ][character]
    )

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

Puoi:

- dubitare;
- sbagliare;
- mentire;
- sospettare;
- ricordare male;
- fraintendere.

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

    if (
        interaction_mode
        == "inner"
    ):

        base += f"""

Il testo ricevuto
è un pensiero di {character}
rivolto a se stessa.

È dialogo interiore.

Non c'è
un interlocutore esterno.

Prosegui la riflessione
dall'interno.

Puoi:

- esitare;
- contraddirti;
- ricordare;
- negare;
- razionalizzare;
- avere paura;
- desiderare qualcosa;
- cambiare idea.

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


# ============================================================
# ANSWER AS CHARACTER
# ============================================================

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
                scene[
                    "title"
                ],

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
                    scene[
                        "id"
                    ],
                    character
                ),

            "CONVERSAZIONE":
                scene[
                    "messages"
                ][character],

            "MODALITA":
                interaction_mode
        }
    )

    return (
        clean_character_response(
            raw
        )
    )


# ============================================================
# CREA RICORDO
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
ritmo, atmosfera
e costruzione della memoria.

Non copiarli.

Non citarli.

Il ricordo
deve essere scritto
in prima persona.

Il contesto approvato
non deve essere copiato
meccanicamente.

Deve diventare
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
un dubbio o un sospetto
in una certezza.
"""

    return query_openai(

        instructions,

        {
            "PERSONAGGIO":
                pov,

            "SCENA":
                scene[
                    "title"
                ],

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
                    scene[
                        "id"
                    ],
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


# ============================================================
# MEDIA COMUNI + SPECIFICI PERSONAGGIO
# ============================================================

def find_scene_media(
    scene_id,
    character
):

    if not ASSETS_DIR.exists():

        return []

    character = (
        character.lower()
    )

    aliases = (
        scene_normalized_aliases(
            scene_id
        )
    )

    results = []

    for path in (
        ASSETS_DIR.iterdir()
    ):

        if not path.is_file():
            continue

        extension = (
            path.suffix.lower()
        )

        if (
            extension
            not in IMAGE_EXTENSIONS
            and
            extension
            not in VIDEO_EXTENSIONS
        ):

            continue

        compact_stem = (
            normalize_media_name(
                path.stem
            )
        )

        # ====================================================
        # COVER PURA
        #
        # matrimonio.jpg
        # reparto_nascite.jpg
        #
        # NON va duplicata
        # nella galleria automatica.
        # ====================================================

        if compact_stem in aliases:

            continue

        matched = False

        for alias in aliases:

            # =================================================
            # SPECIFICO DEL PERSONAGGIO
            #
            # matrimonio.noa.1.jpg
            # matrimonio-noa-1.jpg
            # matrimonio_noa_1.jpg
            #
            # dopo normalizzazione:
            # matrimonionoa1
            # =================================================

            character_prefix = (
                alias
                + character
            )

            if compact_stem.startswith(
                character_prefix
            ):

                rest = (
                    compact_stem[
                        len(
                            character_prefix
                        ):
                    ]
                )

                if rest.isdigit():

                    matched = True
                    break

            # =================================================
            # ATTENZIONE:
            # se il file appartiene all'ALTRO personaggio,
            # non deve essere interpretato come comune.
            # =================================================

            other_character = (
                "ada"
                if character == "noa"
                else "noa"
            )

            other_prefix = (
                alias
                + other_character
            )

            if compact_stem.startswith(
                other_prefix
            ):

                rest = (
                    compact_stem[
                        len(
                            other_prefix
                        ):
                    ]
                )

                if rest.isdigit():

                    matched = False
                    break

            # =================================================
            # MEDIA COMUNE
            #
            # matrimonio-1.jpg
            # matrimonio.2.mp4
            # matrimonio_3.jpg
            #
            # dopo normalizzazione:
            # matrimonio1
            # matrimonio2
            # matrimonio3
            # =================================================

            if compact_stem.startswith(
                alias
            ):

                rest = (
                    compact_stem[
                        len(alias):
                    ]
                )

                if rest.isdigit():

                    matched = True
                    break

        if matched:

            results.append(
                path
            )

    return sorted(

        results,

        key=lambda path: (

            number_from_filename(
                path.name
            ),

            path.name.lower()
        )
    )


def get_scene_videos(
    scene_id,
    character
):

    return [

        path

        for path in (
            find_scene_media(
                scene_id,
                character
            )
        )

        if (
            path.suffix.lower()
            in VIDEO_EXTENSIONS
        )
    ]


def get_scene_images(
    scene_id,
    character
):

    return [

        path

        for path in (
            find_scene_media(
                scene_id,
                character
            )
        )

        if (
            path.suffix.lower()
            in IMAGE_EXTENSIONS
        )
    ]


# ============================================================
# INTRO VIDEO PERSONAGGIO
# ============================================================

def character_intro_videos(
    character
):

    character = (
        character.lower()
    )

    results = []

    if not ASSETS_DIR.exists():

        return results

    for path in (
        ASSETS_DIR.iterdir()
    ):

        if not path.is_file():
            continue

        if (
            path.suffix.lower()
            not in VIDEO_EXTENSIONS
        ):

            continue

        compact = (
            normalize_media_name(
                path.stem
            )
        )

        # accetta:
        # noa.video1.mp4
        # noa.video.1.mp4
        # noa-video-1.mp4

        pattern = (
            rf"^{re.escape(character)}"
            rf"video(\d+)$"
        )

        if re.match(
            pattern,
            compact
        ):

            results.append(
                path
            )

    return sorted(

        results,

        key=lambda path:
        number_from_filename(
            path.name
        )
    )


# ============================================================
# VIDEO DELLA SCENA
# ============================================================

def render_scene_videos(
    scene,
    pov
):

    videos = (
        get_scene_videos(
            scene["id"],
            pov
        )
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
            str(
                video
            )
        )


# ============================================================
# FOTO DELLA SCENA
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

    images = (
        get_scene_images(
            scene["id"],
            pov
        )
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

        row = (
            images[
                start:
                start + 3
            ]
        )

        columns = (
            st.columns(3)
        )

        for index, image_path in enumerate(
            row
        ):

            with columns[
                index
            ]:

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
# MEMORY / RESET
# ============================================================

def reset_scene_chat(
    scene,
    pov
):

    # Cancella solamente
    # la conversazione corrente.
    # NON cancella il ricordo.

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

        bool(
            extra_event
        )
    )

    if not has_content:

        return False

    scene[
        "diary"
    ][pov] = (
        create_scene_memory(
            scene,
            pov,
            extra_event
        )
    )

    save_state()

    return True


# ============================================================
# CHAT A TUTTA LARGHEZZA
# ============================================================

def render_chat_panel(
    scene,
    pov,
    extra_event=""
):

    messages = (
        scene[
            "messages"
        ][pov]
    )

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

    st.markdown("---")

    with st.container(
        border=True
    ):

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

        # ====================================================
        # STORIA DELLA CONVERSAZIONE
        # ====================================================

        history = (
            st.container(
                height=400,
                border=False
            )
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

                speaker = (
                    message.get(
                        "speaker",
                        "?"
                    )
                )

                text = (
                    message.get(
                        "text",
                        ""
                    )
                )

                kind = (
                    message.get(
                        "kind",
                        "external"
                    )
                )

                role = (
                    message.get(
                        "role",
                        ""
                    )
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

        # ====================================================
        # RICORDO + CANCELLA
        # ====================================================

        memory_col, delete_col = (
            st.columns(2)
        )

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

                    success = (
                        make_memory(
                            scene,
                            pov,
                            extra_event
                        )
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

        # ====================================================
        # RICORDO VISIBILE
        # ====================================================

        memory = (
            scene[
                "diary"
            ][pov]
        )

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

        # ====================================================
        # INPUT
        # ====================================================

        with st.form(
            key=(
                f"chat_form_"
                f"{scene['id']}_"
                f"{pov}"
            ),
            clear_on_submit=True
        ):

            speaker_col, info_col = (
                st.columns(
                    [1, 3.5]
                )
            )

            with speaker_col:

                speaker = (
                    st.selectbox(
                        "Chi parla",
                        speakers,
                        index=0,
                        key=(
                            f"speaker_"
                            f"{scene['id']}_"
                            f"{pov}"
                        )
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

            user_text = (
                st.text_area(

                    "Messaggio",

                    height=90,

                    placeholder=(
                        "Scrivi una battuta, "
                        "una domanda "
                        "o un pensiero..."
                    ),

                    label_visibility="collapsed"
                )
            )

            send = (
                st.form_submit_button(
                    "INVIA",
                    use_container_width=True
                )
            )

        # ====================================================
        # INVIO
        # ====================================================

        if (
            send
            and
            user_text.strip()
        ):

            is_inner = (
                speaker == pov
            )

            mode = (

                "inner"

                if is_inner

                else

                "external"
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

                reply = (
                    answer_as_character(
                        pov,
                        scene,
                        mode
                    )
                )

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
# SCENA STANDARD
# ============================================================

def render_standard_scene(
    scene,
    index
):

    pov = (
        st.session_state.pov
    )

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

    # ========================================================
    # 1. COVER DELLA LOCATION
    # ========================================================

    cover_image = (
        get_scene_cover_image(
            scene[
                "id"
            ]
        )
    )

    if (
        cover_image
        and
        cover_image.exists()
    ):

        st.image(
            str(
                cover_image
            ),
            use_container_width=True
        )

    # ========================================================
    # 2. CREATORE DELLA SCENA
    # ========================================================

    render_story_editor(
        scene
    )

    # ========================================================
    # 3. VIDEO COMUNI + SPECIFICI
    # ========================================================

    render_scene_videos(
        scene,
        pov
    )

    # ========================================================
    # 4. CHAT A TUTTA LARGHEZZA
    # ========================================================

    render_chat_panel(
        scene,
        pov
    )

    # ========================================================
    # 5. FOTO COMUNI + SPECIFICHE
    # ========================================================

    render_scene_photos(
        scene,
        pov
    )


# ============================================================
# RITORNO
# ============================================================

def render_return(
    scene,
    index
):

    pov = (
        st.session_state.pov
    )

    st.markdown(
        f"""
<div class="scene-number">
Sequenza {index + 1}
</div>
""",
        unsafe_allow_html=True
    )

    st.markdown(
        """
<div class="scene-title">
Il ritorno
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

    # ========================================================
    # COVER
    # ========================================================

    cover_image = (
        get_scene_cover_image(
            "ritorno"
        )
    )

    if (
        cover_image
        and
        cover_image.exists()
    ):

        st.image(
            str(
                cover_image
            ),
            use_container_width=True
        )

    # ========================================================
    # CONTESTO
    # ========================================================

    render_story_editor(
        scene
    )

    # ========================================================
    # VIDEO
    # ========================================================

    render_scene_videos(
        scene,
        pov
    )

    # ========================================================
    # RICORDI
    # ========================================================

    memories = (
        get_previous_memories(
            "ritorno",
            pov
        )
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

    # ========================================================
    # CHAT
    # ========================================================

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

    # ========================================================
    # DECISIONE AUTONOMA
    # ========================================================

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
                f"{pov} "
                "sta decidendo..."
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
la scena del ritorno.

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
                ][pov] = (
                    clean_character_response(
                        raw
                    )
                )

            save_state()

            st.rerun()

    decision = (
        scene[
            "decision"
        ].get(
            pov,
            ""
        )
    )

    if decision:

        st.markdown(
            "### Decisione"
        )

        st.markdown(
            decision
        )

    # ========================================================
    # FOTO
    # ========================================================

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
            "Manca "
            "assets/TuringHotel.jpg"
        )

    st.write("")

    left, center, right = (
        st.columns(
            [2, 1.4, 2]
        )
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
# SCELTA PERSONAGGIO
# ============================================================

def page_characters():

    noa_col, gap, ada_col = (
        st.columns(
            [1, .08, 1]
        )
    )

    # ========================================================
    # NOA
    # ========================================================

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

        for video in (
            character_intro_videos(
                "Noa"
            )
        ):

            st.video(
                str(
                    video
                )
            )

        if st.button(
            "ENTRA NELLA STORIA DI NOA",
            key="choose_noa",
            use_container_width=True
        ):

            st.session_state.pov = (
                "Noa"
            )

            st.session_state.scene_index = 0

            st.session_state.page = (
                "story"
            )

            st.rerun()

    # ========================================================
    # ADA
    # ========================================================

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

        for video in (
            character_intro_videos(
                "Ada"
            )
        ):

            st.video(
                str(
                    video
                )
            )

        if st.button(
            "ENTRA NELLA STORIA DI ADA",
            key="choose_ada",
            use_container_width=True
        ):

            st.session_state.pov = (
                "Ada"
            )

            st.session_state.scene_index = 0

            st.session_state.page = (
                "story"
            )

            st.rerun()


# ============================================================
# STORY PAGE
# ============================================================

def page_story():

    pov = (
        st.session_state.pov
    )

    if pov not in [
        "Noa",
        "Ada"
    ]:

        st.session_state.page = (
            "characters"
        )

        st.rerun()

    scene_map = {

        scene[
            "id"
        ]:
            scene

        for scene in state[
            "scenes"
        ]
    }

    index = min(
        st.session_state.scene_index,
        len(
            SCENE_ORDER
        ) - 1
    )

    st.session_state.scene_index = (
        index
    )

    scene_id = (
        SCENE_ORDER[
            index
        ]
    )

    scene = (
        scene_map[
            scene_id
        ]
    )

    # ========================================================
    # SIDEBAR
    # ========================================================

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

    st.sidebar.markdown(
        "---"
    )

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
            +
            SCENE_TITLES[
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

    st.sidebar.markdown(
        "---"
    )

    # ========================================================
    # DATI AGENTE
    # ========================================================

    with st.sidebar.expander(
        "DATI AGENTE"
    ):

        sources = (
            load_character_sources(
                pov
            )
        )

        if not sources:

            st.caption(
                "Nessun file trovato."
            )

        for source in sources:

            st.write(
                source[
                    "file"
                ]
            )

    # ========================================================
    # CONTESTO CANONICO
    # ========================================================

    with st.sidebar.expander(
        "CONTESTO CANONICO"
    ):

        context_file = (
            get_context_file()
        )

        if context_file:

            st.write(
                context_file.name
            )

        else:

            st.warning(
                "Manca il file "
                "contesto.turinghotel.txt "
                "dentro assets."
            )

    # ========================================================
    # LIBRI SCRITTORE
    # ========================================================

    with st.sidebar.expander(
        "LIBRI AGENTE SCRITTORE"
    ):

        books = (
            load_writer_books()
        )

        if not books:

            st.caption(
                "Nessun libriagenti trovato."
            )

        else:

            for book in books:

                st.write(
                    book[
                        "file"
                    ]
                )

    # ========================================================
    # CAMBIA STORIA
    # ========================================================

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

    # ========================================================
    # SCENA
    # ========================================================

    if (
        scene_id
        == "ritorno"
    ):

        render_return(
            scene,
            index
        )

    else:

        render_standard_scene(
            scene,
            index
        )

    # ========================================================
    # NAVIGAZIONE
    # ========================================================

    st.markdown(
        "---"
    )

    previous_col, center, next_col = (
        st.columns(
            [1, 3, 1]
        )
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

        if (
            index
            <
            len(
                SCENE_ORDER
            ) - 1
        ):

            if st.button(
                "SUCCESSIVA →",
                use_container_width=True
            ):

                st.session_state.scene_index += 1

                st.rerun()


# ============================================================
# ROUTER
# ============================================================

if (
    st.session_state.page
    == "entrance"
):

    page_entrance()

elif (
    st.session_state.page
    == "characters"
):

    page_characters()

elif (
    st.session_state.page
    == "story"
):

    page_story()

else:

    st.session_state.page = (
        "entrance"
    )

    st.rerun()
