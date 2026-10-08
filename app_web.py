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

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

HOTEL_IMAGE = ASSETS_DIR / "TuringHotel.jpg"
NOA_IMAGE = ASSETS_DIR / "Noa.jpg"
ADA_IMAGE = ASSETS_DIR / "Ada.jpg"


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

.chat-title {
    font-family: Georgia, serif;
    font-size: 1.4rem;
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

.return-box {
    padding: 25px;
    background: #111518;
    border: 1px solid #675943;
    margin-bottom: 20px;
}

.media-caption {
    color: #747b80;
    font-size: .68rem;
    margin-top: .2rem;
    margin-bottom: 1.4rem;
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
# STATO BASE
# ============================================================

DEFAULT_STATE = {

    "world": """
Il Turing Hotel è un antico albergo cinque stelle
sul mare Adriatico.

Un tempo era prestigioso e mondano.
Oggi vive una lenta decadenza.

Fuori stagione mantiene ancora
le tracce del proprio lusso.

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
e molto osservatrice.
""",

            "memory": ""
        }
    },

    "scenes": [

        {
            "id": "hall",
            "title": "La Hall",

            "messages": {
                "Noa": [],
                "Ada": []
            },

            "diary": {
                "Noa": "",
                "Ada": ""
            }
        },

        {
            "id": "funerale",
            "title": "Il Funerale",

            "messages": {
                "Noa": [],
                "Ada": []
            },

            "diary": {
                "Noa": "",
                "Ada": ""
            }
        },

        {
            "id": "matrimonio",
            "title": "Il Matrimonio",

            "messages": {
                "Noa": [],
                "Ada": []
            },

            "diary": {
                "Noa": "",
                "Ada": ""
            }
        },

        {
            "id": "reparto_nascite",
            "title": "Il reparto nascite",

            "messages": {
                "Noa": [],
                "Ada": []
            },

            "diary": {
                "Noa": "",
                "Ada": ""
            }
        },

        {
            "id": "ritorno",
            "title": "Il ritorno",

            "messages": {
                "Noa": [],
                "Ada": []
            },

            "diary": {
                "Noa": "",
                "Ada": ""
            },

            "decision": {
                "Noa": "",
                "Ada": ""
            }
        }
    ]
}


# ============================================================
# UTILITY
# ============================================================

def safe_list(value):
    return value if isinstance(value, list) else []


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def number_from_filename(filename):

    matches = re.findall(
        r"\.(\d+)\.[^.]+$",
        filename.lower()
    )

    if matches:
        return int(matches[-1])

    matches = re.findall(
        r"\d+",
        filename
    )

    if matches:
        return int(matches[-1])

    return 0


# ============================================================
# LETTURA FILE
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

            reader = PdfReader(
                str(path)
            )

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

        remaining = (
            max_chars - used
        )

        if remaining <= 0:
            break

        excerpt = text[:remaining]

        results.append({

            "file":
                path.name,

            "contenuto":
                excerpt
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

        if not path.stem.lower().startswith(
            "libriagenti"
        ):
            continue

        if path.suffix.lower() not in [
            ".txt",
            ".md",
            ".pdf"
        ]:
            continue

        text = read_reference_file(path)

        if text:

            results.append({

                "file":
                    path.name,

                "testo":
                    text[:15000]
            })

    return sorted(
        results,
        key=lambda x:
        number_from_filename(
            x["file"]
        )
    )


# ============================================================
# MIGRAZIONE
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

    aliases = SCENE_FILE_ALIASES.get(
        scene_id,
        [scene_id]
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


def migrate_messages(
    old_scene
):

    result = {
        "Noa": [],
        "Ada": []
    }

    if not old_scene:
        return result

    old_messages = old_scene.get(
        "messages",
        {}
    )

    if isinstance(
        old_messages,
        dict
    ):

        result["Noa"] = safe_list(
            old_messages.get(
                "Noa",
                []
            )
        )

        result["Ada"] = safe_list(
            old_messages.get(
                "Ada",
                []
            )
        )

    elif isinstance(
        old_messages,
        list
    ):

        agent = old_scene.get(
            "agent",
            "Noa"
        )

        if agent == "Ada":

            result["Ada"] = (
                old_messages
            )

        else:

            result["Noa"] = (
                old_messages
            )

    return result


def migrate_diary(
    old_scene
):

    result = {
        "Noa": "",
        "Ada": ""
    }

    if not old_scene:
        return result

    diary = old_scene.get(
        "diary",
        {}
    )

    if isinstance(
        diary,
        dict
    ):

        result["Noa"] = str(
            diary.get(
                "Noa",
                ""
            )
        )

        result["Ada"] = str(
            diary.get(
                "Ada",
                ""
            )
        )

    return result


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

    old_scenes = old_state.get(
        "scenes",
        []
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

        new_scene[
            "messages"
        ] = migrate_messages(
            old_scene
        )

        new_scene[
            "diary"
        ] = migrate_diary(
            old_scene
        )

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

            old_state = json.loads(
                DATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

            st.session_state.state = (
                migrate_state(
                    old_state
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


# ============================================================
# SESSION
# ============================================================

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
# PULIZIA RISPOSTA
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

                value = data.get(
                    key
                )

                if isinstance(
                    value,
                    str
                ) and value.strip():

                    return value.strip()

    except Exception:
        pass

    return text


# ============================================================
# RICORDI PRECEDENTI
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
# PROMPT PERSONAGGIO
# ============================================================

def character_prompt(
    character,
    scene,
    interaction_mode="external"
):

    agent = state[
        "agents"
    ][character]

    base = f"""
SEI {character}.

Sei un personaggio
del romanzo TURING HOTEL.

NON sei un assistente.

Devi lavorare soltanto
con le informazioni realmente
disponibili al personaggio.

I tuoi dati sono:

- file del personaggio;
- file condivisi;
- profilo;
- memoria;
- ricordi delle scene precedenti;
- conversazione corrente.

Se non conosci qualcosa,
non inventarla come fatto.

Puoi:

- non sapere;
- dubitare;
- sospettare;
- sbagliare;
- mentire;
- ricordare male.

MONDO:

{state["world"]}

PROFILO:

{agent["profile"]}

MEMORIA:

{agent["memory"]}

REGOLE:

Interpreta soltanto {character}.

Non scrivere battute
degli altri personaggi.

Non raccontare
i loro pensieri.

Non anticipare il futuro.

Non spiegare la teoria.

Non restituire JSON.

Non mostrare
note tecniche o stato interno
in forma strutturata.

Mostra soltanto
ciò che {character}
dice, pensa o fa,
a seconda del tipo
di interazione.

I dati servono
per rendere coerente
il comportamento.

Non devi recitare
tutto quello che sai.

Se un'informazione
non è pertinente,
non usarla.

Lingua italiana naturale,
credibile e contemporanea.
"""

    if interaction_mode == "inner":

        base += f"""

MODALITÀ:
DIALOGO INTERIORE DI {character.upper()}.

Il testo ricevuto non viene
pronunciato da un'altra persona.

È un pensiero,
una domanda interiore,
un dubbio oppure una riflessione
che {character} rivolge
a se stessa.

Rispondi come prosecuzione
del pensiero interiore.

Puoi:

- contraddirti;
- esitare;
- ricordare;
- associare;
- avere paura;
- razionalizzare;
- negare qualcosa;
- riconoscere qualcosa;
- interrompere il pensiero.

Non parlare
come se avessi davanti
un interlocutore esterno.

Non usare formule
da chatbot.

Non spiegare
che si tratta di
un dialogo interiore.

Scrivi direttamente
la riflessione.
"""

    else:

        base += """

MODALITÀ:
DIALOGO CON UN ALTRO PERSONAGGIO.

Reagisci alla persona
che sta parlando con te.

Non trasformare la risposta
in un monologo esplicativo.

Rispondi come una persona
presente nella scena.
"""

    return base


# ============================================================
# RISPOSTA PERSONAGGIO
# ============================================================

def answer_as_character(
    character,
    scene,
    interaction_mode="external"
):

    sources = (
        load_character_sources(
            character
        )
    )

    memories = (
        get_previous_memories(
            scene["id"],
            character
        )
    )

    raw = query_openai(

        character_prompt(
            character,
            scene,
            interaction_mode
        ),

        {
            "personaggio":
                character,

            "scena":
                scene[
                    "title"
                ],

            "modalita_interazione":
                interaction_mode,

            "dati_personaggio":
                sources,

            "ricordi":
                memories,

            "conversazione":
                scene[
                    "messages"
                ][character]
        }
    )

    return clean_character_response(
        raw
    )


# ============================================================
# AGENTE SCRITTORE
# ============================================================

def create_scene_memory(
    scene,
    pov,
    extra_event=""
):

    instructions = """
Sei l'agente scrittore
del Turing Hotel.

Devi creare il ricordo
autobiografico della scena
dal punto di vista
del personaggio.

Usa esclusivamente
le informazioni fornite.

Non aggiungere fatti.

Non trasformare supposizioni
in certezze.

Scrivi in prima persona.

Il ricordo deve includere
anche pensieri e riflessioni
interiori avvenuti
durante la scena,
se presenti.

Registra soprattutto:

- eventi;
- persone;
- emozioni;
- dubbi;
- desideri;
- paure;
- conflitti;
- promesse;
- decisioni;
- cambiamenti nei rapporti;
- riflessioni che possono
  influenzare il futuro.

Il ricordo deve essere utile
al personaggio
nelle scene successive.

I libri forniti
sono riferimenti narrativi,
non contenuto da copiare.
"""

    return query_openai(

        instructions,

        {
            "personaggio":
                pov,

            "scena":
                scene[
                    "title"
                ],

            "conversazione":
                scene[
                    "messages"
                ][pov],

            "evento_aggiuntivo":
                extra_event,

            "ricordi_precedenti":
                get_previous_memories(
                    scene["id"],
                    pov
                ),

            "dati_personaggio":
                load_character_sources(
                    pov
                ),

            "riferimenti_scrittura":
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

    character = character.lower()

    aliases = (
        SCENE_FILE_ALIASES[
            scene_id
        ]
    )

    results = []

    if not ASSETS_DIR.exists():
        return results

    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue

        suffix = (
            path.suffix.lower()
        )

        if (
            suffix not in IMAGE_EXTENSIONS
            and
            suffix not in VIDEO_EXTENSIONS
        ):
            continue

        filename = (
            path.name.lower()
        )

        matched = False

        for location in aliases:

            escaped_location = (
                re.escape(
                    location
                )
            )

            pattern = (
                rf"^{escaped_location}\."
                rf"{character}\."
                rf"(\d+)\."
                rf"(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$"
            )

            if re.match(
                pattern,
                filename
            ):

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


def character_intro_videos(
    character
):

    character = character.lower()

    results = []

    if not ASSETS_DIR.exists():
        return results

    for path in ASSETS_DIR.iterdir():

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


def render_scene_media(
    scene_id,
    pov
):

    media = find_scene_media(
        scene_id,
        pov
    )

    if not media:
        return

    for index, path in enumerate(
        media
    ):

        suffix = (
            path.suffix.lower()
        )

        if suffix in VIDEO_EXTENSIONS:

            st.video(
                str(path)
            )

        elif suffix in IMAGE_EXTENSIONS:

            st.image(
                str(path),
                use_container_width=True
            )

        st.markdown(
            f'<div class="media-caption">'
            f'{index + 1}'
            f'</div>',
            unsafe_allow_html=True
        )


# ============================================================
# HOME
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
# SCELTA STORIA
# ============================================================

def page_characters():

    noa_col, gap, ada_col = (
        st.columns(
            [1, .08, 1]
        )
    )

    with noa_col:

        if NOA_IMAGE.exists():

            st.image(
                str(NOA_IMAGE),
                use_container_width=True
            )

        st.markdown(
            '<div class="character-name">'
            'NOA'
            '</div>',
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

    with ada_col:

        if ADA_IMAGE.exists():

            st.image(
                str(ADA_IMAGE),
                use_container_width=True
            )

        st.markdown(
            '<div class="character-name">'
            'ADA'
            '</div>',
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
# CANCELLA SOLO LA CHAT
# ============================================================

def reset_scene_chat(
    scene,
    pov
):

    # Il ricordo già creato resta.
    # Si azzera soltanto la conversazione.

    scene[
        "messages"
    ][pov] = []

    save_state()


# ============================================================
# CREA RICORDO
# ============================================================

def make_memory(
    scene,
    pov,
    extra_event=""
):

    if (
        not scene[
            "messages"
        ][pov]
        and
        not extra_event
    ):

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
# INTERFACCIA CHAT COMPATTA
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

    # Preset:
    # percorso Noa -> Ada
    # percorso Ada -> Noa

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
            f'<div class="chat-title">'
            f'Dialogo con {pov}'
            f'</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="chat-subtitle">'
            'Conversazione e pensieri della scena'
            '</div>',
            unsafe_allow_html=True
        )

        # ====================================================
        # CRONOLOGIA IN FINESTRA SCORREVOLE
        # ====================================================

        history = st.container(
            height=390,
            border=False
        )

        with history:

            if not messages:

                st.caption(
                    "La conversazione non è ancora iniziata."
                )

            for message in messages:

                if not isinstance(
                    message,
                    dict
                ):
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

                # --------------------------------------------
                # DIALOGO INTERIORE
                # --------------------------------------------

                if kind == "inner":

                    if role == "prompt":

                        label = (
                            f"Pensiero di {pov}"
                        )

                    else:

                        label = (
                            f"Riflessione di {pov}"
                        )

                    st.markdown(
                        f"""
<div class="inner-message">
<div class="message-name">{label}</div>
{text}
</div>
""",
                        unsafe_allow_html=True
                    )

                # --------------------------------------------
                # RISPOSTA AGENTE
                # --------------------------------------------

                elif speaker == pov:

                    st.markdown(
                        f"""
<div class="agent-message">
<div class="message-name">{pov}</div>
{text}
</div>
""",
                        unsafe_allow_html=True
                    )

                # --------------------------------------------
                # INTERLOCUTORE
                # --------------------------------------------

                else:

                    st.markdown(
                        f"""
<div class="human-message">
<div class="message-name">{speaker}</div>
{text}
</div>
""",
                        unsafe_allow_html=True
                    )

        # ====================================================
        # DUE PULSANTI AFFIANCATI
        # ====================================================

        memory_col, clear_col = (
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

                if (
                    not messages
                    and
                    not extra_event
                ):

                    st.warning(
                        "Non c'è ancora nulla "
                        "da trasformare in ricordo."
                    )

                else:

                    with st.spinner(
                        "Creazione del ricordo..."
                    ):

                        make_memory(
                            scene,
                            pov,
                            extra_event
                        )

                    st.rerun()

        with clear_col:

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
        # RICORDO GIÀ CREATO
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
                    f'<div class="diary">'
                    f'{memory}'
                    f'</div>',
                    unsafe_allow_html=True
                )

        st.markdown("---")

        # ====================================================
        # COMPOSER
        # ====================================================

        with st.form(
            key=(
                f"chat_form_"
                f"{scene['id']}_"
                f"{pov}"
            ),
            clear_on_submit=True
        ):

            # Selectbox più corto e vicino
            # alla finestra di testo

            select_col, info_col = (
                st.columns(
                    [1.15, 2.85]
                )
            )

            with select_col:

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
                        f"Dialogo interiore di {pov}: "
                        "ciò che scrivi viene trattato "
                        "come un pensiero rivolto a se stessa."
                    )

                else:

                    st.caption(
                        f"{speaker} sta parlando con {pov}."
                    )

            user_text = st.text_area(
                "Scrivi",
                height=90,
                placeholder=(
                    "Scrivi una battuta, una domanda "
                    "o un pensiero..."
                ),
                label_visibility="collapsed"
            )

            send = st.form_submit_button(
                "INVIA",
                use_container_width=True
            )

        # ====================================================
        # INVIO
        # ====================================================

        if send and user_text.strip():

            is_inner = (
                speaker == pov
            )

            if is_inner:

                interaction_mode = (
                    "inner"
                )

                messages.append({

                    "speaker":
                        pov,

                    "text":
                        user_text.strip(),

                    "kind":
                        "inner",

                    "role":
                        "prompt"
                })

            else:

                interaction_mode = (
                    "external"
                )

                messages.append({

                    "speaker":
                        speaker,

                    "text":
                        user_text.strip(),

                    "kind":
                        "external",

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
                        interaction_mode
                    )
                )

            if is_inner:

                messages.append({

                    "speaker":
                        pov,

                    "text":
                        reply,

                    "kind":
                        "inner",

                    "role":
                        "response"
                })

            else:

                messages.append({

                    "speaker":
                        pov,

                    "text":
                        reply,

                    "kind":
                        "external",

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
        f'<div class="scene-number">'
        f'Sequenza {index + 1}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="scene-title">'
        f'{scene["title"]}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="pov">'
        f'Storia di {pov}'
        f'</div>',
        unsafe_allow_html=True
    )

    # Media specifici del personaggio

    render_scene_media(
        scene[
            "id"
        ],
        pov
    )

    # Chat compatta

    render_chat_panel(
        scene,
        pov
    )


# ============================================================
# IL RITORNO
# ============================================================

def render_return(
    scene,
    index
):

    pov = (
        st.session_state.pov
    )

    st.markdown(
        f'<div class="scene-number">'
        f'Sequenza {index + 1}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="scene-title">'
        'Il ritorno'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="pov">'
        f'Storia di {pov}'
        f'</div>',
        unsafe_allow_html=True
    )

    render_scene_media(
        "ritorno",
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
dei propri dati e dei ricordi
costruiti durante le scene precedenti.
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

    else:

        st.warning(
            "Non esistono ancora ricordi."
        )

    # Anche nel ritorno si può dialogare

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
        f"LASCIA DECIDERE {pov.upper()}",
        type="primary"
    ):

        if not memories:

            st.warning(
                "Il personaggio non ha "
                "ancora ricordi sufficienti."
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

QUESTA È LA SCENA
DEL RITORNO.

Ora devi prendere
autonomamente una decisione.

Usa soltanto:

- la tua personalità;
- i tuoi dati;
- le tue esperienze;
- i tuoi ricordi.

Non cercare
il finale migliore.

Non cercare
il finale più drammatico.

Non cercare di capire
cosa vuole l'autore.

Non spiegare
come hai preso
la decisione.

Mostra ciò che fai,
dici oppure decidi.
""",

                    {
                        "dati_personaggio":
                            load_character_sources(
                                pov
                            ),

                        "ricordi":
                            memories,

                        "conversazione_attuale":
                            scene[
                                "messages"
                            ][pov],

                        "scena":
                            "Il ritorno"
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

        st.markdown("---")

        st.markdown(
            "### Decisione"
        )

        st.markdown(
            decision
        )


# ============================================================
# HOME
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
# SCELTA PERCORSO
# ============================================================

def page_characters():

    noa_col, gap, ada_col = (
        st.columns(
            [1, .08, 1]
        )
    )

    with noa_col:

        if NOA_IMAGE.exists():

            st.image(
                str(NOA_IMAGE),
                use_container_width=True
            )

        st.markdown(
            '<div class="character-name">'
            'NOA'
            '</div>',
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

    with ada_col:

        if ADA_IMAGE.exists():

            st.image(
                str(ADA_IMAGE),
                use_container_width=True
            )

        st.markdown(
            '<div class="character-name">'
            'ADA'
            '</div>',
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
            str(portrait),
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

        if index < len(
            SCENE_ORDER
        ) - 1:

            if st.button(
                "SUCCESSIVA →"
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
