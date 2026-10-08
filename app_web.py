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

CONTEXT_FILE = ASSETS_DIR / "contesto.turinghotel.txt"

HOTEL_IMAGE = ASSETS_DIR / "TuringHotel.jpg"
NOA_IMAGE = ASSETS_DIR / "Noa.jpg"
ADA_IMAGE = ASSETS_DIR / "Ada.jpg"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


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
    min-height: 44px;
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
    font-size: 3.4rem;
    line-height: 1.05;
    margin-top: .3rem;
    margin-bottom: .4rem;
}

.pov {
    color: #b79c72;
    font-size: .75rem;
    letter-spacing: .15em;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
}

.story-title {
    font-family: Georgia, serif;
    font-size: 1.45rem;
    margin-bottom: .2rem;
}

.story-subtitle {
    color: #90979b;
    font-size: .82rem;
    margin-bottom: 1rem;
}

.story-approved {
    background: #121816;
    border-left: 3px solid #8d9d79;
    padding: 18px 20px;
    margin-top: 15px;
    margin-bottom: 15px;
    line-height: 1.65;
}

.story-draft {
    background: #15181b;
    border-left: 3px solid #87724f;
    padding: 18px 20px;
    margin-top: 15px;
    line-height: 1.65;
}

.chat-title {
    font-family: Georgia, serif;
    font-size: 1.45rem;
    margin-bottom: .2rem;
}

.chat-subtitle {
    color: #868d92;
    font-size: .78rem;
    margin-bottom: .8rem;
}

.inner-message {
    background: #171719;
    border-left: 2px solid #8e7654;
    padding: 13px 16px;
    margin-bottom: 10px;
    font-family: Georgia, serif;
    font-style: italic;
    line-height: 1.55;
}

.agent-message {
    background: #13191d;
    border-left: 2px solid #66747c;
    padding: 13px 16px;
    margin-bottom: 10px;
    line-height: 1.55;
}

.human-message {
    background: #171c20;
    border-left: 2px solid #404b53;
    padding: 13px 16px;
    margin-bottom: 10px;
    line-height: 1.55;
}

.message-name {
    color: #a4a9ad;
    font-size: .70rem;
    text-transform: uppercase;
    letter-spacing: .10em;
    margin-bottom: 5px;
}

.diary {
    font-family: Georgia, serif;
    line-height: 1.7;
    padding: 22px;
    background: #111518;
    border-left: 2px solid #8e7654;
}

.media-label {
    color: #858c91;
    font-size: .72rem;
    letter-spacing: .13em;
    text-transform: uppercase;
    margin-top: 1rem;
    margin-bottom: .8rem;
}

.return-box {
    padding: 25px;
    background: #111518;
    border: 1px solid #675943;
    margin-bottom: 20px;
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
        "reparto.nascite",
        "reparto_nascite",
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


def number_from_filename(filename):

    matches = re.findall(
        r"\.(\d+)\.[^.]+$",
        filename.lower()
    )

    if matches:
        return int(
            matches[-1]
        )

    matches = re.findall(
        r"\d+",
        filename
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

                text = page.extract_text()

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

def load_turing_context():

    if not CONTEXT_FILE.exists():

        return ""

    try:

        return CONTEXT_FILE.read_text(
            encoding="utf-8",
            errors="ignore"
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

        text = read_reference_file(
            path
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

        name = (
            path.stem.lower()
        )

        if not name.startswith(
            "libriagenti"
        ):
            continue

        if path.suffix.lower() not in [
            ".txt",
            ".md",
            ".pdf"
        ]:

            continue

        text = read_reference_file(
            path
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

    for old_scene in old_scenes:

        if not isinstance(
            old_scene,
            dict
        ):
            continue

        old_id = str(
            old_scene.get(
                "id",
                ""
            )
        ).lower()

        old_title = str(
            old_scene.get(
                "title",
                ""
            )
        ).lower()

        if old_id == scene_id:

            return old_scene

        for alias in aliases:

            if (
                alias in old_id
                or
                alias.replace(
                    ".",
                    " "
                ) in old_title
            ):

                return old_scene

    return None


def migrate_state(
    old_state
):

    fresh = copy.deepcopy(
        DEFAULT_STATE
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
            old_agent.get(
                "profile"
            ),
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
            old_agent.get(
                "memory"
            ),
            str
        ):

            fresh[
                "agents"
            ][character][
                "memory"
            ] = old_agent[
                "memory"
            ]

    old_scenes = (
        old_state.get(
            "scenes",
            []
        )
    )

    for new_scene in fresh[
        "scenes"
    ]:

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
                ] = old_scene[
                    field
                ]

        if (
            new_scene["id"]
            == "ritorno"
        ):

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

L'autore fornisce
poche righe
sulla situazione.

Tu devi trasformarle
in un contesto narrativo
chiaro e utilizzabile
dagli agenti Noa e Ada.

NON sei l'agente scrittore.

NON usi libri di riferimento.

NON devi decidere:

- cosa pensa Noa;
- cosa pensa Ada;
- cosa provano;
- cosa desiderano;
- cosa scelgono;
- come reagiscono.

Devi definire
la situazione oggettiva.

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
diventerà realtà narrativa.
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
# AGENTE SCRITTORE - RIFINITURA CONTESTO
# ============================================================

def refine_context_with_writer(
    scene
):

    instructions = """
Sei l'AGENTE SCRITTORE
del romanzo Turing Hotel.

Ricevi una descrizione
di scena già costruita
dal Creatore della scena.

Il tuo compito
è migliorarne
la qualità narrativa.

Puoi migliorare:

- ritmo;
- atmosfera;
- precisione sensoriale;
- fluidità;
- tensione;
- densità;
- efficacia delle immagini.

NON puoi cambiare
i fatti della scena.

NON puoi aggiungere
nuovi eventi importanti.

NON puoi decidere
come reagiscono Noa o Ada.

I file LIBRIAGENTI
sono riferimenti
di tecnica narrativa.

Non copiarli.

Non citarli.

Non imitare
letteralmente
un autore riconoscibile.

Mantieni invariati
i fatti della scena.
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
# LOCATION IMAGES
# ============================================================

def scene_location_name(
    scene_id
):

    mapping = {

        "hall":
            "hall",

        "funerale":
            "funerale",

        "matrimonio":
            "matrimonio",

        "reparto_nascite":
            "repartonascite",

        "ritorno":
            "ritorno"
    }

    return mapping.get(
        scene_id,
        scene_id
    )


def find_image_by_base_name(
    base_name
):

    for extension in [

        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    ]:

        path = (
            ASSETS_DIR
            /
            f"{base_name}{extension}"
        )

        if path.exists():

            return path

    return None


def get_scene_cover_image(
    scene_id
):

    location = (
        scene_location_name(
            scene_id
        )
    )

    return find_image_by_base_name(
        location
    )


def get_scene_context_image(
    scene_id
):

    location = (
        scene_location_name(
            scene_id
        )
    )

    return find_image_by_base_name(
        f"{location}-1"
    )


def get_character_portrait(
    pov
):

    if pov == "Noa":

        return NOA_IMAGE

    return ADA_IMAGE


# ============================================================
# STORY EDITOR UI
# ============================================================

def render_story_editor(
    scene
):

    context_image = (
        get_scene_context_image(
            scene["id"]
        )
    )

    editor_col, image_col = (
        st.columns(
            [1.65, 1]
        )
    )

    # ========================================================
    # EDITOR SINISTRA
    # ========================================================

    with editor_col:

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
Descrivi in poche righe
la situazione narrativa.
Il Creatore della scena
la sviluppa usando
il contesto canonico
del Turing Hotel.
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

                height=105,

                placeholder=(
                    "Descrivi cosa sta accadendo, "
                    "chi è presente "
                    "e quale situazione "
                    "devono affrontare."
                ),

                key=(
                    f"author_context_"
                    f"{scene['id']}"
                )
            )

            create_col, save_col = (
                st.columns(2)
            )

            with create_col:

                if st.button(
                    "CREA CONTESTO",
                    key=(
                        f"create_context_"
                        f"{scene['id']}"
                    )
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
                            "Creazione "
                            "del contesto..."
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
                    "SALVA INDICAZIONI",
                    key=(
                        f"save_context_notes_"
                        f"{scene['id']}"
                    )
                ):

                    save_state()

                    st.success(
                        "Indicazioni salvate."
                    )

            # =================================================
            # DRAFT
            # =================================================

            if scene.get(
                "story_draft",
                ""
            ):

                st.markdown(
                    f"""
<div class="story-draft">
<b>BOZZA DELLA SCENA</b><br><br>
{scene["story_draft"]}
</div>
""",
                    unsafe_allow_html=True
                )

                scene[
                    "story_feedback"
                ] = st.text_area(

                    "Correzioni / indicazioni",

                    value=scene.get(
                        "story_feedback",
                        ""
                    ),

                    height=75,

                    placeholder=(
                        "Aggiungi correzioni "
                        "o nuove indicazioni."
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
                        "RISCRIVI CONTESTO",
                        key=(
                            f"rewrite_context_"
                            f"{scene['id']}"
                        )
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
                        "RIFINISCI CON SCRITTORE",
                        key=(
                            f"writer_refine_"
                            f"{scene['id']}"
                        )
                    ):

                        with st.spinner(
                            "L'agente scrittore "
                            "sta rifinendo..."
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
                    )
                ):

                    scene[
                        "approved_context"
                    ] = scene[
                        "story_draft"
                    ]

                    save_state()

                    st.rerun()

            # =================================================
            # APPROVED
            # =================================================

            if scene.get(
                "approved_context",
                ""
            ):

                st.markdown(
                    f"""
<div class="story-approved">
<b>CONTESTO APPROVATO</b><br><br>
{scene["approved_context"]}
</div>
""",
                    unsafe_allow_html=True
                )

                st.caption(
                    "Questo contesto "
                    "viene passato "
                    "sia a Noa sia ad Ada."
                )

    # ========================================================
    # FOTO LOCATION -1 A DESTRA
    # ========================================================

    with image_col:

        if (
            context_image
            and
            context_image.exists()
        ):

            st.image(
                str(
                    context_image
                ),
                use_container_width=True
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
- ricordare male.

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

Scrivi
in italiano naturale.
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
- avere paura.

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
# CREA RICORDO SCENA
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

Il ricordo
deve essere scritto
in prima persona.

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
- elementi utili
  per le scene future.

Non inventare
fatti nuovi.
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


def find_scene_media(
    scene_id,
    character
):

    character = (
        character.lower()
    )

    aliases = (
        SCENE_FILE_ALIASES[
            scene_id
        ]
    )

    results = []

    if not ASSETS_DIR.exists():

        return results

    for path in (
        ASSETS_DIR.iterdir()
    ):

        if not path.is_file():
            continue

        suffix = (
            path.suffix.lower()
        )

        if (
            suffix
            not in IMAGE_EXTENSIONS
            and
            suffix
            not in VIDEO_EXTENSIONS
        ):

            continue

        filename = (
            path.name.lower()
        )

        for location in aliases:

            pattern = (
                rf"^{re.escape(location)}\."
                rf"{character}\."
                rf"(\d+)\."
                rf"(jpg|jpeg|png|webp|"
                rf"mp4|mov|webm|m4v)$"
            )

            if re.match(
                pattern,
                filename
            ):

                results.append(
                    path
                )

                break

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
# INTRO VIDEO
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

        filename = (
            path.name.lower()
        )

        if re.match(
            rf"^{character}\.video\.?(\d+)\.mp4$",
            filename
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
# VIDEO
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
Video
</div>
""",
        unsafe_allow_html=True
    )

    for video in videos:

        st.video(
            str(video)
        )


# ============================================================
# FOTO SPECIFICHE PERCORSO
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
                    )
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

    # cancella solo la chat,
    # non il ricordo

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
# CHAT + PORTRAIT
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

    portrait = (
        get_character_portrait(
            pov
        )
    )

    st.markdown("---")

    chat_col, portrait_col = (
        st.columns(
            [2.35, 1]
        )
    )

    # ========================================================
    # CHAT SINISTRA
    # ========================================================

    with chat_col:

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

            history = (
                st.container(
                    height=380,
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

            # =================================================
            # MEMORY + DELETE
            # =================================================

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
                    )
                ):

                    with st.spinner(
                        "Creazione "
                        "del ricordo..."
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
                            "Non c'è "
                            "ancora nulla "
                            "da ricordare."
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
                    )
                ):

                    reset_scene_chat(
                        scene,
                        pov
                    )

                    st.rerun()

            # =================================================
            # MEMORY VIEW
            # =================================================

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

            # =================================================
            # INPUT
            # =================================================

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
                        [1.05, 2.95]
                    )
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
                        "INVIA"
                    )
                )

            # =================================================
            # SEND
            # =================================================

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
                    f"{pov} "
                    "sta reagendo..."
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

    # ========================================================
    # RITRATTO A DESTRA
    # ========================================================

    with portrait_col:

        if (
            portrait
            and
            portrait.exists()
        ):

            st.image(
                str(
                    portrait
                ),
                use_container_width=True
            )

            st.caption(
                pov
            )


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
    # 1. FOTO PRINCIPALE LOCATION
    # ========================================================

    cover_image = (
        get_scene_cover_image(
            scene["id"]
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
    # 2. STORY EDITOR + LOCATION-1
    # ========================================================

    render_story_editor(
        scene
    )

    # ========================================================
    # 3. VIDEO DEL PERCORSO
    # ========================================================

    render_scene_videos(
        scene,
        pov
    )

    # ========================================================
    # 4. CHAT + RITRATTO
    # ========================================================

    render_chat_panel(
        scene,
        pov
    )

    # ========================================================
    # 5. FOTO SPECIFICHE NOA / ADA
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

    # FOTO PRINCIPALE

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

    # STORY EDITOR

    render_story_editor(
        scene
    )

    # VIDEO

    render_scene_videos(
        scene,
        pov
    )

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

    # CHAT

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

    # DECISIONE AUTONOMA

    if st.button(
        f"LASCIA DECIDERE "
        f"{pov.upper()}",
        type="primary"
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

    # FOTO SPECIFICHE

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
            type="primary"
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

    # NOA

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
            key="choose_noa"
        ):

            st.session_state.pov = (
                "Noa"
            )

            st.session_state.scene_index = 0

            st.session_state.page = (
                "story"
            )

            st.rerun()

    # ADA

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
            key="choose_ada"
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
        len(SCENE_ORDER) - 1
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
            )
        ):

            st.session_state.scene_index = i

            st.rerun()

    st.sidebar.markdown("---")

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

    with st.sidebar.expander(
        "CONTESTO CANONICO"
    ):

        if CONTEXT_FILE.exists():

            st.write(
                CONTEXT_FILE.name
            )

        else:

            st.warning(
                "Manca "
                "assets/"
                "contesto.turinghotel.txt"
            )

    if st.sidebar.button(
        "CAMBIA STORIA"
    ):

        st.session_state.page = (
            "characters"
        )

        st.session_state.pov = None

        st.session_state.scene_index = 0

        st.rerun()

    if st.sidebar.button(
        "TORNA ALL'INGRESSO"
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

    # ========================================================
    # NAVIGAZIONE
    # ========================================================

    st.markdown("---")

    previous_col, center, next_col = (
        st.columns(
            [1, 3, 1]
        )
    )

    with previous_col:

        if index > 0:

            if st.button(
                "← PRECEDENTE"
            ):

                st.session_state.scene_index -= 1

                st.rerun()

    with next_col:

        if (
            index
            <
            len(SCENE_ORDER) - 1
        ):

            if st.button(
                "SUCCESSIVA →"
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
