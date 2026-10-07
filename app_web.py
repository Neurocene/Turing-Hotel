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
DATA_DIR = BASE_DIR / "data_web"

DATA_FILE = DATA_DIR / "romanzo_web.json"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
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


client = OpenAI(
    api_key=openai_key
) if openai_key else None


try:

    OPENAI_MODEL = st.secrets.get(
        "OPENAI_MODEL",
        "gpt-5.6-sol"
    )

except Exception:

    OPENAI_MODEL = os.environ.get(
        "OPENAI_MODEL",
        "gpt-5.6-sol"
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


/* BUTTON */

div.stButton > button {
    width: 100%;
    min-height: 50px;
    background: #1b2227;
    color: #f4efe7;
    border: 1px solid #4e575e;
    border-radius: 3px;
    font-weight: 600;
    letter-spacing: .04em;
}

div.stButton > button:hover {
    background: #29343b;
    border-color: #af9872;
}


/* CHARACTER */

.character-name {
    text-align: center;
    font-family: Georgia, serif;
    font-size: 2.6rem;
    margin-top: .5rem;
}

.character-description {
    text-align: center;
    color: #989fa3;
    margin-bottom: 1rem;
}


/* SCENE */

.scene-number {
    color: #81878b;
    letter-spacing: .18em;
    font-size: .75rem;
    text-transform: uppercase;
}

.scene-title {
    font-family: Georgia, serif;
    font-size: 3.3rem;
    line-height: 1.05;
    margin-top: .3rem;
}

.scene-location {
    color: #92999e;
    margin-top: .5rem;
    margin-bottom: 1.8rem;
}

.pov {
    color: #b79c72;
    font-size: .75rem;
    letter-spacing: .15em;
    text-transform: uppercase;
}


/* CHAT */

[data-testid="stChatMessage"] {
    background: #13181c;
    border: 1px solid #282f34;
    border-radius: 6px;
}


/* DIARY */

.diary {
    font-family: Georgia, serif;
    line-height: 1.7;
    padding: 22px;
    background: #111518;
    border-left: 2px solid #8e7654;
}


/* RETURN */

.return-box {
    padding: 25px;
    background: #111518;
    border: 1px solid #675943;
    margin-bottom: 20px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# DEFAULT STATE
# ============================================================

DEFAULT_STATE = {

    "world": """
Il Turing Hotel è un antico albergo cinque stelle
sul mare Adriatico.

Un tempo era prestigioso e mondano.
Oggi vive una lenta decadenza.

Fuori stagione mantiene ancora
le tracce del proprio lusso:
legno, ottone, velluti,
grandi finestre,
vecchie fotografie,
stanze troppo grandi
e una veranda affacciata sul mare d'inverno.

La storia viene vissuta attraverso
due protagoniste: Noa e Ada.
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

Non vuole necessariamente diventare umana.

Sta cercando di capire
quanto valore possano avere
esperienze e sentimenti
quando sai che potrebbero essere
copiati, modificati o cancellati.
""",

            "memory": ""
        },

        "Ada": {

            "profile": """
Ada è la figlia del professor Elia.

È una donna italiana
poco più che trentenne.

È cresciuta intorno al Turing Hotel
e ora lo gestisce insieme al padre.

È intelligente,
pratica,
riservata
e molto osservatrice.

Conosce ogni rumore,
corridoio e problema dell'albergo.

Non è certa di aver scelto di restare.
Forse ha soltanto rimandato
per molti anni il momento di andarsene.
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
            "id": "nascite",
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

            "decision": {
                "Noa": "",
                "Ada": ""
            }
        }
    ]
}


# ============================================================
# LOAD DATA
# ============================================================

if "state" not in st.session_state:

    if DATA_FILE.exists():

        try:

            st.session_state.state = json.loads(
                DATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            st.session_state.state = copy.deepcopy(
                DEFAULT_STATE
            )

    else:

        st.session_state.state = copy.deepcopy(
            DEFAULT_STATE
        )


state = st.session_state.state


# ============================================================
# MIGRATION / RESET STRUCTURE
# ============================================================

if "world" not in state:
    state["world"] = DEFAULT_STATE["world"]

if "agents" not in state:
    state["agents"] = copy.deepcopy(
        DEFAULT_STATE["agents"]
    )


for person in ["Noa", "Ada"]:

    if person not in state["agents"]:
        state["agents"][person] = copy.deepcopy(
            DEFAULT_STATE["agents"][person]
        )


# garantiamo le quattro scene

scene_ids = {
    scene.get("id")
    for scene in state.get("scenes", [])
}


for default_scene in DEFAULT_STATE["scenes"]:

    if default_scene["id"] not in scene_ids:

        state.setdefault(
            "scenes",
            []
        ).append(
            copy.deepcopy(default_scene)
        )


for scene in state["scenes"]:

    if "messages" not in scene:
        scene["messages"] = {
            "Noa": [],
            "Ada": []
        }

    for person in ["Noa", "Ada"]:

        if person not in scene["messages"]:
            scene["messages"][person] = []

    if scene["id"] != "ritorno":

        if "diary" not in scene:

            scene["diary"] = {
                "Noa": "",
                "Ada": ""
            }

        for person in ["Noa", "Ada"]:

            if person not in scene["diary"]:
                scene["diary"][person] = ""

    else:

        if "decision" not in scene:

            scene["decision"] = {
                "Noa": "",
                "Ada": ""
            }


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

        return f"Errore OpenAI: {e}"


# ============================================================
# ASSET HELPERS
# ============================================================

IMAGE_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
]

VIDEO_EXTENSIONS = [
    ".mp4",
    ".mov",
    ".webm",
    ".m4v"
]


def natural_number(filename):

    numbers = re.findall(
        r"\d+",
        filename
    )

    if numbers:
        return int(numbers[-1])

    return 0


def sorted_assets(paths):

    return sorted(
        paths,
        key=lambda x: (
            natural_number(x.name),
            x.name.lower()
        )
    )


# ============================================================
# CHARACTER VIDEOS
# ============================================================

def character_videos(character):

    character = character.lower()

    results = []

    patterns = [

        rf"^{character}\.video(\d+)\.mp4$",

        rf"^{character}_video(\d+)\.mp4$",

        rf"^{character}\.video\.(\d+)\.mp4$"
    ]

    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue

        name = path.name.lower()

        for pattern in patterns:

            if re.match(pattern, name):

                results.append(path)

                break

    return sorted_assets(results)


# ============================================================
# GENERIC SCENE ASSETS
# ============================================================

def find_scene_assets(
    scene_id,
    pov,
    media_type
):

    pov = pov.lower()

    results = []


    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue


        filename = path.name.lower()

        suffix = path.suffix.lower()


        if media_type == "image":

            if suffix not in IMAGE_EXTENSIONS:
                continue

        else:

            if suffix not in VIDEO_EXTENSIONS:
                continue


        # ----------------------------------------------------
        # HALL
        # hall1.jpg
        # hall2.jpg
        # hall.video1.mp4
        # hall1.mp4
        # ----------------------------------------------------

        if scene_id == "hall":

            valid = [

                rf"^hall\d+\{suffix}$",

                rf"^hall\.video\d+\{suffix}$",

                rf"^hall\.{pov}\.\d+\{suffix}$",

                rf"^hall\.{pov}\.video\d+\{suffix}$"
            ]


        # ----------------------------------------------------
        # FUNERALE
        # funerale.noa.1.jpg
        # funerale.ada.2.mp4
        # ----------------------------------------------------

        elif scene_id == "funerale":

            valid = [

                rf"^funerale\.{pov}\.\d+\{suffix}$",

                rf"^funerale\.{pov}\.video\d+\{suffix}$",

                rf"^funerale_{pov}_\d+\{suffix}$"
            ]


        # ----------------------------------------------------
        # NASCITE
        # nascite.noa.1.jpg
        # nascite.ada.1.mp4
        #
        # accetta anche:
        # reparto.nascite.noa.1.jpg
        # ----------------------------------------------------

        elif scene_id == "nascite":

            valid = [

                rf"^nascite\.{pov}\.\d+\{suffix}$",

                rf"^nascite\.{pov}\.video\d+\{suffix}$",

                rf"^reparto\.nascite\.{pov}\.\d+\{suffix}$",

                rf"^reparto_nascite_{pov}_\d+\{suffix}$"
            ]


        # ----------------------------------------------------
        # RITORNO
        # ----------------------------------------------------

        else:

            valid = [

                rf"^ritorno\.{pov}\.\d+\{suffix}$",

                rf"^ritorno\.{pov}\.video\d+\{suffix}$"
            ]


        for pattern in valid:

            if re.match(
                pattern,
                filename
            ):

                results.append(
                    path
                )

                break


    return sorted_assets(
        results
    )


# ============================================================
# BOOKS FOR WRITER AGENT
# ============================================================

def load_writer_books():

    books = []


    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue


        name = path.stem.lower()


        if not name.startswith(
            "libriagenti"
        ):
            continue


        suffix = path.suffix.lower()


        # TXT / MD

        if suffix in [
            ".txt",
            ".md"
        ]:

            try:

                content = path.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

                books.append(
                    (
                        path.name,
                        content
                    )
                )

            except Exception:

                pass


        # PDF

        elif suffix == ".pdf":

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

                books.append(
                    (
                        path.name,
                        "\n".join(pages)
                    )
                )

            except Exception:

                pass


    books.sort(
        key=lambda x: natural_number(
            x[0]
        )
    )


    # evitiamo prompt giganteschi

    MAX_TOTAL_CHARS = 30000

    result = []

    used = 0


    for filename, content in books:

        remaining = (
            MAX_TOTAL_CHARS
            - used
        )

        if remaining <= 0:
            break


        excerpt = content[
            :remaining
        ]


        result.append({

            "file":
                filename,

            "testo":
                excerpt
        })


        used += len(
            excerpt
        )


    return result


# ============================================================
# CHARACTER PROMPT
# ============================================================

def character_prompt(character):

    agent = state[
        "agents"
    ][character]

    return f"""
SEI {character}.

Sei un personaggio del romanzo TURING HOTEL.

Non sei un assistente.

MONDO:

{state["world"]}


PERSONAGGIO:

{agent["profile"]}


MEMORIA PERSONALE:

{agent["memory"]}


REGOLE:

Interpreta soltanto {character}.

Non scrivere ciò che dicono
gli altri personaggi.

Non spiegare la teoria.

Non anticipare il futuro.

Non cercare di essere utile
come un assistente.

Vivi quello che accade.

Puoi:

- parlare;
- agire;
- sbagliare;
- dubitare;
- mentire;
- restare in silenzio;
- cambiare idea.

Scrivi in italiano naturale,
contemporaneo,
credibile.
"""


# ============================================================
# DIARY WRITER
# ============================================================

def write_scene_diary(
    scene,
    pov
):

    books = load_writer_books()


    instructions = """
Sei l'agente scrittore del romanzo
Turing Hotel.

Devi redigere il DIARIO DELLA SCENA.

Il diario non è un riassunto tecnico.

È una registrazione narrativa
di ciò che il personaggio ha vissuto.

Deve contenere soltanto:

- ciò che è realmente accaduto;
- ciò che il personaggio può ricordare;
- impressioni rilevanti;
- emozioni;
- dubbi;
- cambiamenti nei rapporti;
- dettagli che potrebbero influenzare
  decisioni future.

I libri forniti sono riferimenti
per ritmo, atmosfera,
densità e tecnica narrativa.

NON copiare frasi dai libri.
NON citare i libri.
NON imitare letteralmente un autore.

Usa i riferimenti soltanto
per costruire una voce narrativa
coerente e letteraria.

Scrivi il diario in prima persona.
"""


    data = {

        "personaggio":
            pov,

        "scena":
            scene["title"],

        "conversazione":
            scene["messages"][pov],

        "profilo":
            state["agents"][pov]["profile"],

        "diario_precedente":
            scene["diary"][pov],

        "riferimenti_letterari":
            books
    }


    return query_openai(
        instructions,
        data
    )


# ============================================================
# PAGE 1 — ENTRANCE
# ============================================================

def page_entrance():

    if HOTEL_IMAGE.exists():

        st.image(
            str(HOTEL_IMAGE),
            use_container_width=True
        )

    else:

        st.info(
            "Carica assets/TuringHotel.jpg"
        )


    c1, c2, c3 = st.columns(
        [2, 1.2, 2]
    )


    with c2:

        if st.button(
            "ENTRA AL TURING HOTEL",
            type="primary"
        ):

            st.session_state.page = (
                "characters"
            )

            st.rerun()


# ============================================================
# CHARACTER CHOICE
# ============================================================

def page_characters():

    col_noa, gap, col_ada = (
        st.columns(
            [1, .08, 1]
        )
    )


    # --------------------------------------------------------
    # NOA
    # --------------------------------------------------------

    with col_noa:

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


        for video in character_videos(
            "noa"
        ):

            st.video(
                str(video)
            )


        if st.button(
            "SEGUI NOA",
            key="select_noa"
        ):

            st.session_state.pov = "Noa"

            st.session_state.scene_index = 0

            st.session_state.page = "story"

            st.rerun()


    # --------------------------------------------------------
    # ADA
    # --------------------------------------------------------

    with col_ada:

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


        for video in character_videos(
            "ada"
        ):

            st.video(
                str(video)
            )


        if st.button(
            "SEGUI ADA",
            key="select_ada"
        ):

            st.session_state.pov = "Ada"

            st.session_state.scene_index = 0

            st.session_state.page = "story"

            st.rerun()


# ============================================================
# RESET CHAT
# ============================================================

def reset_scene_chat(
    scene,
    pov
):

    scene[
        "messages"
    ][pov] = []

    if scene["id"] != "ritorno":

        scene[
            "diary"
        ][pov] = ""

    save_state()


# ============================================================
# CHAT
# ============================================================

def render_chat(
    scene,
    pov
):

    messages = scene[
        "messages"
    ][pov]


    for message in messages:

        speaker = message[
            "speaker"
        ]

        with st.chat_message(
            "assistant"
            if speaker == pov
            else "user"
        ):

            st.markdown(
                f"**{speaker}**"
            )

            st.write(
                message[
                    "text"
                ]
            )


    col_clear, blank = st.columns(
        [1, 3]
    )


    with col_clear:

        if st.button(
            "🗑 CANCELLA CONVERSAZIONE",
            key=f"clear_{scene['id']}_{pov}"
        ):

            reset_scene_chat(
                scene,
                pov
            )

            st.rerun()


    speaker = st.selectbox(

        "Chi interviene?",

        [
            "Luigi",
            "Elia",
            "Noa",
            "Ada",
            "Adam",
            "Vittoria",
            "Riccardo",
            "Altro"
        ],

        key=f"speaker_{scene['id']}_{pov}"
    )


    user_text = st.chat_input(
        f"Interagisci con {pov}..."
    )


    if user_text:

        messages.append({

            "speaker":
                speaker,

            "text":
                user_text
        })


        reply = query_openai(

            character_prompt(
                pov
            ),

            {
                "scena":
                    scene["title"],

                "conversazione":
                    messages
            }
        )


        messages.append({

            "speaker":
                pov,

            "text":
                reply
        })


        save_state()

        st.rerun()


# ============================================================
# STANDARD SCENE
# ============================================================

def render_standard_scene(
    scene,
    index
):

    pov = st.session_state.pov


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
        f'Punto di vista · {pov}'
        f'</div>',
        unsafe_allow_html=True
    )


    # ========================================================
    # VIDEO SOPRA LA CHAT
    # ========================================================

    videos = find_scene_assets(
        scene["id"],
        pov,
        "video"
    )


    for video in videos:

        st.video(
            str(video)
        )


    # ========================================================
    # CHAT
    # ========================================================

    render_chat(
        scene,
        pov
    )


    # ========================================================
    # IMMAGINI SOTTO LA CHAT
    # ========================================================

    images = find_scene_assets(
        scene["id"],
        pov,
        "image"
    )


    if images:

        st.markdown("---")


        for image in images:

            st.image(
                str(image),
                use_container_width=True
            )


    # ========================================================
    # DIARIO
    # ========================================================

    st.markdown("---")


    if st.button(
        "SCRIVI IL DIARIO DELLA SCENA",
        key=f"diary_{scene['id']}_{pov}"
    ):

        with st.spinner(
            "L'agente scrittore sta redigendo il diario..."
        ):

            scene[
                "diary"
            ][pov] = write_scene_diary(
                scene,
                pov
            )


        save_state()

        st.rerun()


    diary = scene[
        "diary"
    ][pov]


    if diary:

        with st.expander(
            "DIARIO DELLA SCENA",
            expanded=False
        ):

            st.markdown(
                f'<div class="diary">'
                f'{diary}'
                f'</div>',
                unsafe_allow_html=True
            )


# ============================================================
# THE RETURN
# ============================================================

def render_return():

    pov = st.session_state.pov


    scene = next(
        scene
        for scene in state["scenes"]
        if scene["id"] == "ritorno"
    )


    st.markdown(
        '<div class="scene-number">'
        'Sequenza 4'
        '</div>',
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
        f'Punto di vista · {pov}'
        f'</div>',
        unsafe_allow_html=True
    )


    videos = find_scene_assets(
        "ritorno",
        pov,
        "video"
    )


    for video in videos:

        st.video(
            str(video)
        )


    # ========================================================
    # RACCOGLIAMO I DIARI
    # ========================================================

    previous_diaries = []


    for previous_scene in state[
        "scenes"
    ]:

        if previous_scene[
            "id"
        ] not in [
            "hall",
            "funerale",
            "nascite"
        ]:
            continue


        diary = previous_scene[
            "diary"
        ][pov]


        if diary:

            previous_diaries.append({

                "scena":
                    previous_scene["title"],

                "diario":
                    diary
            })


    st.markdown(
        """
<div class="return-box">

Nel ritorno l'autore non decide
come la protagonista deve reagire.

La decisione viene presa
in base a ciò che ha vissuto
nelle scene precedenti.

</div>
""",
        unsafe_allow_html=True
    )


    if not previous_diaries:

        st.warning(
            "Non ci sono ancora diari delle scene precedenti."
        )


    if st.button(
        f"LASCIA DECIDERE {pov.upper()}",
        type="primary"
    ):

        with st.spinner(
            f"{pov} sta ricordando..."
        ):

            decision = query_openai(

                character_prompt(
                    pov
                )
                +
                """

QUESTA È LA SCENA DEL RITORNO.

Non chiedere all'autore cosa fare.

Leggi i tuoi diari.

Considera ciò che hai vissuto.

Considera:

- persone incontrate;
- emozioni;
- delusioni;
- paure;
- affetti;
- promesse;
- contraddizioni;
- scelte precedenti.

Ora decidi autonomamente
che cosa vuoi fare.

Non cercare il finale migliore.

Compi la scelta che questo personaggio
farebbe davvero in questo momento.

Scrivi la scena in prima persona.
""",

                {
                    "diari":
                        previous_diaries,

                    "scena":
                        "Il ritorno"
                }
            )


            scene[
                "decision"
            ][pov] = decision


        save_state()

        st.rerun()


    decision = scene[
        "decision"
    ].get(
        pov,
        ""
    )


    if decision:

        st.markdown("---")

        st.markdown(
            decision
        )


    images = find_scene_assets(
        "ritorno",
        pov,
        "image"
    )


    for image in images:

        st.image(
            str(image),
            use_container_width=True
        )


# ============================================================
# STORY NAVIGATION
# ============================================================

def page_story():

    pov = st.session_state.pov


    if not pov:

        st.session_state.page = (
            "characters"
        )

        st.rerun()


    ordered_ids = [

        "hall",
        "funerale",
        "nascite",
        "ritorno"
    ]


    scenes = {

        scene["id"]:
            scene

        for scene in state["scenes"]
    }


    index = st.session_state.scene_index


    scene_id = ordered_ids[
        index
    ]


    if scene_id == "ritorno":

        render_return()

    else:

        render_standard_scene(

            scenes[
                scene_id
            ],

            index
        )


    st.markdown("---")


    prev_col, center, next_col = (
        st.columns(
            [1, 3, 1]
        )
    )


    with prev_col:

        if index > 0:

            if st.button(
                "← PRECEDENTE"
            ):

                st.session_state.scene_index -= 1

                st.rerun()


    with next_col:

        if index < 3:

            if st.button(
                "SUCCESSIVA →"
            ):

                # ------------------------------------------------
                # PRIMA DI USCIRE DALLA SCENA:
                # se il diario manca, lo creiamo automaticamente
                # ------------------------------------------------

                current_scene = scenes[
                    scene_id
                ]


                if (
                    scene_id != "ritorno"
                    and
                    not current_scene[
                        "diary"
                    ][pov]
                    and
                    current_scene[
                        "messages"
                    ][pov]
                ):

                    with st.spinner(
                        "Salvataggio del diario..."
                    ):

                        current_scene[
                            "diary"
                        ][pov] = (
                            write_scene_diary(
                                current_scene,
                                pov
                            )
                        )


                    save_state()


                st.session_state.scene_index += 1

                st.rerun()


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
        ordered_ids
    ):

        title = {

            "hall":
                "La Hall",

            "funerale":
                "Il Funerale",

            "nascite":
                "Il reparto nascite",

            "ritorno":
                "Il ritorno"

        }[sid]


        if st.sidebar.button(
            title,
            key=f"nav_{sid}"
        ):

            st.session_state.scene_index = i

            st.rerun()


    st.sidebar.markdown("---")


    if st.sidebar.button(
        "CAMBIA PROTAGONISTA"
    ):

        st.session_state.page = (
            "characters"
        )

        st.rerun()


    if st.sidebar.button(
        "TORNA ALL'INGRESSO"
    ):

        st.session_state.page = (
            "entrance"
        )

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
