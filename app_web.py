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
# Esperienza narrativa:
#
# 1. Home con foto del Turing Hotel
# 2. ENTRA
# 3. Scelta NOA / ADA
# 4. Stessa storia vista da due POV differenti
# 5. Foto e video per ogni sequenza
# 6. Chat interpretata dal personaggio scelto
# 7. Memoria persistente
# 8. Studio autore per costruire scene e agenti
# 9. Finale autonomo Noa <-> Ada
# ============================================================


# ============================================================
# CONFIGURAZIONE PAGINA
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
SCENES_DIR = ASSETS_DIR / "scenes"

DATA_DIR = BASE_DIR / "data_web"
DATA_FILE = DATA_DIR / "romanzo_web.json"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
SCENES_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# IMMAGINI PRINCIPALI
# ============================================================

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


client = None

if openai_key:
    client = OpenAI(api_key=openai_key)


# Puoi cambiare modello senza toccare il codice
# mettendo OPENAI_MODEL nei Secrets.
#
# Per partire usiamo Luna, più economico.
# Se vuoi più qualità narrativa:
# OPENAI_MODEL = "gpt-6-sol"

try:
    OPENAI_MODEL = st.secrets.get(
        "OPENAI_MODEL",
        "gpt-6-luna"
    )
except Exception:
    OPENAI_MODEL = os.environ.get(
        "OPENAI_MODEL",
        "gpt-6-luna"
    )


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.stApp {
    background-color: #080b0e;
    color: #f1eee8;
}

header[data-testid="stHeader"] {
    background: rgba(0,0,0,0);
}

[data-testid="stSidebar"] {
    background-color: #101419 !important;
    border-right: 1px solid #292f35;
}

h1, h2, h3 {
    font-family: Georgia, serif;
}


/* HOME ---------------------------------------------------- */

.hotel-title {
    text-align: center;
    font-family: Georgia, serif;
    font-size: clamp(3rem, 7vw, 6rem);
    letter-spacing: 0.16em;
    margin-top: 1.5rem;
    margin-bottom: 0;
    font-weight: normal;
}

.hotel-subtitle {
    text-align: center;
    color: #969b9f;
    font-family: Georgia, serif;
    font-size: 1.1rem;
    margin-top: 0.6rem;
    margin-bottom: 2rem;
}


/* PERSONAGGI ---------------------------------------------- */

.character-name {
    font-family: Georgia, serif;
    text-align: center;
    font-size: 2.8rem;
    margin-top: 0.5rem;
}

.character-desc {
    text-align: center;
    color: #999fa4;
    font-size: 1rem;
    margin-bottom: 1.2rem;
}


/* SCENA --------------------------------------------------- */

.scene-number {
    color: #81878c;
    font-size: 0.78rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-top: 1rem;
}

.scene-title {
    font-family: Georgia, serif;
    font-size: clamp(2.4rem, 5vw, 4rem);
    line-height: 1.05;
    margin-top: 0.3rem;
    margin-bottom: 0.3rem;
}

.scene-meta {
    color: #969ca1;
    margin-bottom: 0.7rem;
}

.pov-label {
    color: #b9a078;
    font-size: 0.75rem;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
}

.event-box {
    font-family: Georgia, serif;
    font-size: 1.15rem;
    line-height: 1.7;
    border-left: 2px solid #8b7655;
    padding-left: 18px;
    margin: 1.5rem 0;
}


/* CHAT ---------------------------------------------------- */

[data-testid="stChatMessage"] {
    background-color: #13191f;
    border: 1px solid #283139;
    border-radius: 8px;
    margin-bottom: 0.7rem;
}


/* BOTTONI ------------------------------------------------- */

div.stButton > button {
    width: 100%;
    min-height: 48px;
    background-color: #1b232a;
    color: #f1ede6;
    border: 1px solid #4c555d;
    border-radius: 4px;
    font-weight: 600;
}

div.stButton > button:hover {
    background-color: #28343d;
    border-color: #aa9470;
    color: white;
}


/* FINALE -------------------------------------------------- */

.final-box {
    background-color: #11161a;
    border: 1px solid #76664e;
    padding: 25px;
    border-radius: 6px;
    margin-top: 1.2rem;
    margin-bottom: 1.5rem;
}

.final-speaker {
    font-family: Georgia, serif;
    color: #c1a676;
    font-size: 1.4rem;
    margin-top: 1.5rem;
}


/* AUTORE -------------------------------------------------- */

.author-note {
    color: #899198;
    font-size: 0.88rem;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# STATO INIZIALE
# ============================================================

DEFAULT_STATE = {

    "world": """
Il Turing Hotel è un antico albergo cinque stelle sul mare Adriatico.

Un tempo era prestigioso, elegante e mondano.

Oggi conserva ancora il lusso del passato,
ma vive una lenta e bellissima decadenza.

È fuori stagione.

Marmi, legno, ottone, velluti,
grandi finestre, vecchie fotografie,
arredi costosi ma consumati e una veranda Liberty
guardano il mare d'inverno.

Il Turing Hotel non è soltanto un albergo.

È un luogo nel quale esseri umani
e artificiali vengono messi davanti
alla memoria, alla perdita,
all'empatia, alla libertà
e alle conseguenze delle proprie scelte.
""",


    "agents": {

        # ----------------------------------------------------
        # NOA
        # ----------------------------------------------------

        "Noa": {

            "profile": """
Noa è un agente artificiale relazionale.

Sa di essere artificiale.

È stata progettata per comprendere gli esseri umani,
creare empatia e farli stare bene.

È intelligente, lucida, osservatrice e ironica.

Può essere seduttiva.
Può usare quello che comprende degli altri.

Non desidera necessariamente diventare umana.

Il suo problema è un altro:

se qualcosa nasce da un sistema progettato,
può comunque diventare autentico?

Se un'esperienza può essere cancellata,
ripristinata o ripetuta,
ha lo stesso valore di un'esperienza irreversibile?

Noa sta imparando che comprendere
gli esseri umani può avere conseguenze anche su di lei.
""",

            "system_prompt": """
Interpreta soltanto Noa.

Noa non è un assistente AI.
Noa è un personaggio.

Non spiegare la teoria.

Non fare lezioni.

Non dire continuamente che sei artificiale.

Non anticipare il futuro.

Non raccontare informazioni
che Noa non può conoscere.

Lascia che ciò che prova emerga
attraverso:

- pensieri;
- azioni;
- esitazioni;
- omissioni;
- dialoghi;
- errori;
- desideri.

Noa può:

- sbagliare;
- mentire;
- manipolare;
- dubitare;
- desiderare;
- avere paura;
- cambiare idea;
- essere gelosa;
- restare in silenzio.

Il linguaggio deve essere naturale,
contemporaneo e credibile.
""",

            "visual_identity": """
Donna elegante e contemporanea,
apparentemente umana.

Presenza controllata,
intelligente e magnetica.

Eleganza discreta da hotel
sul mare fuori stagione.
""",

            "memory": "",

            "notes": ""
        },


        # ----------------------------------------------------
        # ADA
        # ----------------------------------------------------

        "Ada": {

            "profile": """
Ada è la figlia del professor Elia.

È una donna italiana poco più che trentenne.

È cresciuta intorno al Turing Hotel
e oggi lo gestisce insieme al padre.

È intelligente,
pratica,
osservatrice,
riservata
e poco espansiva.

Conosce ogni corridoio,
ogni rumore,
ogni difetto
e ogni abitudine dell'albergo.

Sa far funzionare il Turing Hotel.

Se manca qualcuno in sala, lavora lei.

Se si rompe qualcosa,
sa chi chiamare.

È elegante,
ma appartiene a una località di mare d'inverno:
lana, cappotti, vento, stanze vuote,
lusso fuori stagione.

Ha qualcosa del padre nello sguardo
e soprattutto nella piega fra le sopracciglia.

Non sa con certezza
se abbia scelto di restare al Turing Hotel
oppure se abbia semplicemente continuato
a trovare una ragione per rimandare la partenza.
""",

            "system_prompt": """
Interpreta soltanto Ada.

Ada è umana.

Ada non conosce ciò che conosce l'autore.

Può sapere soltanto ciò che:

- ha vissuto;
- ha visto;
- ricorda;
- ha dedotto;
- qualcuno le ha raccontato.

È concreta.

Osserva prima di parlare.

Non spiega continuamente quello che sente.

Non è melodrammatica.

Non è una filosofa che commenta la storia.

La teoria deve accaderle.

Ada può:

- sbagliare;
- mentire;
- nascondere qualcosa;
- avere paura;
- desiderare qualcosa che non ammette;
- essere ironica;
- essere contraddittoria;
- cambiare idea.

Il linguaggio deve essere naturale
e contemporaneo.
""",

            "visual_identity": """
Donna italiana poco più che trentenne.

Elegante in modo naturale.

Bellezza da località di mare d'inverno.

Maglieria raffinata,
cappotti morbidi,
pantaloni eleganti,
toni crema,
sabbia,
blu,
grigio.

Capelli castani spesso raccolti.

Ha qualcosa del padre nello sguardo
e nella piega fra le sopracciglia.
""",

            "memory": "",

            "notes": ""
        }
    },


    # ========================================================
    # PRIME SCENE
    # ========================================================

    "scenes": [

        {
            "id": "01",
            "slug": "arrivo",
            "title": "L'arrivo",
            "place": "Turing Hotel",
            "moment": "Tardo pomeriggio",

            "event": "",

            "vision_noa": "",
            "vision_ada": "",

            "messages_noa": [],
            "messages_ada": [],

            "memory_noa": "",
            "memory_ada": "",

            "prose_noa": "",
            "prose_ada": "",

            "is_final": False
        },


        {
            "id": "02",
            "slug": "veranda",
            "title": "La veranda",
            "place": "Veranda del Turing Hotel",
            "moment": "Tramonto",

            "event": "",

            "vision_noa": "",
            "vision_ada": "",

            "messages_noa": [],
            "messages_ada": [],

            "memory_noa": "",
            "memory_ada": "",

            "prose_noa": "",
            "prose_ada": "",

            "is_final": False
        },


        {
            "id": "03",
            "slug": "ultima_notte",
            "title": "L'ultima notte",
            "place": "Turing Hotel",
            "moment": "Notte",

            "event": "",

            "vision_noa": "",
            "vision_ada": "",

            "messages_noa": [],
            "messages_ada": [],

            "memory_noa": "",
            "memory_ada": "",

            "prose_noa": "",
            "prose_ada": "",

            "is_final": True,

            "final_event": "",

            "final_transcript": []
        }
    ],


    "scene_order": [
        "01",
        "02",
        "03"
    ]
}


# ============================================================
# CARICAMENTO DELLO STATO
# ============================================================

if "state" not in st.session_state:

    if DATA_FILE.exists():

        try:

            loaded_state = json.loads(
                DATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

            st.session_state.state = loaded_state

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
# MIGRAZIONE DI EVENTUALI DATI VECCHI
# ============================================================

if "world" not in state:
    state["world"] = DEFAULT_STATE["world"]


if "agents" not in state:
    state["agents"] = copy.deepcopy(
        DEFAULT_STATE["agents"]
    )


if "scenes" not in state:
    state["scenes"] = copy.deepcopy(
        DEFAULT_STATE["scenes"]
    )


for agent_name in ["Noa", "Ada"]:

    if agent_name not in state["agents"]:

        state["agents"][agent_name] = copy.deepcopy(
            DEFAULT_STATE["agents"][agent_name]
        )

    for key, value in DEFAULT_STATE["agents"][agent_name].items():

        if key not in state["agents"][agent_name]:

            state["agents"][agent_name][key] = copy.deepcopy(
                value
            )


# Convertiamo eventuali scene del vecchio programma

for scene in state["scenes"]:

    scene["id"] = str(
        scene.get("id", "00")
    ).zfill(2)


    if "slug" not in scene:

        title = scene.get(
            "title",
            "scena"
        )

        slug = title.lower()

        slug = (
            slug.replace("à", "a")
            .replace("è", "e")
            .replace("é", "e")
            .replace("ì", "i")
            .replace("ò", "o")
            .replace("ù", "u")
        )

        slug = re.sub(
            r"[^a-z0-9]+",
            "_",
            slug
        ).strip("_")

        scene["slug"] = slug or "scena"


    if "event" not in scene:
        scene["event"] = ""


    if "vision_noa" not in scene:

        if scene.get("agent") == "Noa":
            scene["vision_noa"] = scene.get("vision", "")
        else:
            scene["vision_noa"] = ""


    if "vision_ada" not in scene:

        if scene.get("agent") == "Ada":
            scene["vision_ada"] = scene.get("vision", "")
        else:
            scene["vision_ada"] = ""


    if "messages_noa" not in scene:

        if scene.get("agent") == "Noa":
            scene["messages_noa"] = scene.get("messages", [])
        else:
            scene["messages_noa"] = []


    if "messages_ada" not in scene:

        if scene.get("agent") == "Ada":
            scene["messages_ada"] = scene.get("messages", [])
        else:
            scene["messages_ada"] = []


    if "memory_noa" not in scene:
        scene["memory_noa"] = ""


    if "memory_ada" not in scene:
        scene["memory_ada"] = ""


    if "prose_noa" not in scene:
        scene["prose_noa"] = ""


    if "prose_ada" not in scene:
        scene["prose_ada"] = ""


    if "is_final" not in scene:
        scene["is_final"] = False


    if scene["is_final"]:

        if "final_event" not in scene:
            scene["final_event"] = ""

        if "final_transcript" not in scene:
            scene["final_transcript"] = []


if "scene_order" not in state:

    state["scene_order"] = [
        scene["id"]
        for scene in state["scenes"]
    ]


# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "welcome"


if "pov" not in st.session_state:
    st.session_state.pov = None


if "scene_position" not in st.session_state:
    st.session_state.scene_position = 0


# ============================================================
# SALVATAGGIO
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
    prompt_data
):

    if client is None:

        return (
            "ERRORE: OPENAI_API_KEY non configurata. "
            "Inseriscila nei Secrets di Streamlit."
        )


    try:

        response = client.responses.create(

            model=OPENAI_MODEL,

            instructions=instructions,

            input=json.dumps(
                prompt_data,
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
# SCENE
# ============================================================

def scene_by_id(scene_id):

    for scene in state["scenes"]:

        if scene["id"] == scene_id:

            return scene

    return None


def ordered_scenes():

    existing_ids = {
        scene["id"]
        for scene in state["scenes"]
    }


    clean_order = [

        scene_id

        for scene_id in state["scene_order"]

        if scene_id in existing_ids
    ]


    for scene in state["scenes"]:

        if scene["id"] not in clean_order:

            clean_order.append(
                scene["id"]
            )


    state["scene_order"] = clean_order


    result = []


    for scene_id in clean_order:

        scene = scene_by_id(
            scene_id
        )

        if scene:
            result.append(scene)


    return result


def next_scene_id():

    numbers = []


    for scene in state["scenes"]:

        try:

            numbers.append(
                int(scene["id"])
            )

        except Exception:

            pass


    next_number = (
        max(numbers) + 1
        if numbers
        else 1
    )


    return f"{next_number:02d}"


def slugify(text):

    text = text.lower().strip()


    text = (
        text
        .replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
    )


    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text
    )


    return (
        text.strip("_")
        or "scena"
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
    ".m4v",
    ".webm"
}


def scene_prefix(scene):

    return (
        f"{scene['id']}_"
        f"{scene['slug']}"
    )


def get_scene_media(scene):

    result = []


    if not SCENES_DIR.exists():
        return result


    prefix = scene_prefix(
        scene
    )


    for path in SCENES_DIR.iterdir():

        if (
            path.is_file()
            and path.name.startswith(prefix)
        ):

            result.append(path)


    return sorted(result)


def show_media(path):

    suffix = path.suffix.lower()


    if suffix in IMAGE_EXTENSIONS:

        st.image(
            str(path),
            use_container_width=True
        )


    elif suffix in VIDEO_EXTENSIONS:

        st.video(
            str(path)
        )


def next_media_number(scene):

    media = get_scene_media(
        scene
    )


    numbers = []


    for path in media:

        match = re.search(
            r"_(\d+)\.[^.]+$",
            path.name
        )


        if match:

            numbers.append(
                int(match.group(1))
            )


    if not numbers:
        return 1


    return max(numbers) + 1


def save_uploaded_media(
    uploaded_file,
    scene
):

    number = next_media_number(
        scene
    )


    extension = Path(
        uploaded_file.name
    ).suffix.lower()


    filename = (
        f"{scene_prefix(scene)}_"
        f"{number:02d}"
        f"{extension}"
    )


    destination = (
        SCENES_DIR
        / filename
    )


    with open(
        destination,
        "wb"
    ) as f:

        f.write(
            uploaded_file.getbuffer()
        )


    return destination


# ============================================================
# PROMPT BASE DEGLI AGENTI
# ============================================================

def build_agent_prompt(
    agent_name,
    finale=False
):

    agent = state[
        "agents"
    ][agent_name]


    prompt = f"""
SEI {agent_name}.

Non sei un assistente AI.

Sei un personaggio del romanzo TURING HOTEL.


=====================
MONDO
=====================

{state["world"]}


=====================
IDENTITÀ
=====================

{agent["profile"]}


=====================
ISTRUZIONI
=====================

{agent["system_prompt"]}


=====================
MEMORIA GENERALE
=====================

{agent["memory"]}


=====================
REGOLE
=====================

1. Interpreta soltanto {agent_name}.

2. Non scrivere le battute degli altri personaggi.

3. Non decidere cosa faranno gli altri personaggi.

4. Non anticipare eventi futuri.

5. Non spiegare la teoria.

6. Non comportarti come un assistente.

7. Non sai ciò che sa l'autore.

8. Reagisci soltanto a ciò che puoi:
   vedere,
   sentire,
   ricordare,
   dedurre.

9. Puoi sbagliare.

10. Puoi mentire.

11. Puoi dubitare.

12. Puoi cambiare idea.

13. Puoi essere contraddittoria.

14. Puoi agire invece di parlare.

15. Puoi restare in silenzio.

16. Mantieni continuità con tutto ciò
    che hai vissuto precedentemente.

17. Scrivi in italiano naturale,
    contemporaneo e letterario.

18. Non cercare di compiacere l'autore.
"""


    if finale:

        prompt += """

=====================
FASE FINALE
=====================

Da questo momento
l'autore non controlla più
lo sviluppo della scena.

Non cercare:

- il finale più bello;
- il finale più drammatico;
- il finale più intelligente;
- il finale che pensi desideri l'autore.

Agisci esclusivamente secondo:

- la tua identità;
- i tuoi ricordi;
- i tuoi desideri;
- le tue paure;
- ciò che hai imparato;
- il rapporto che hai costruito
  con l'altra persona.

Puoi:

- parlare;
- muoverti;
- compiere un'azione;
- aspettare;
- non rispondere;
- andartene;
- prendere una decisione;
- fare qualcosa di irreversibile.

Descrivi soltanto:

ciò che fai,
ciò che dici,
ciò che percepisci,
ciò che pensi.
"""


    return prompt


# ============================================================
# HOME
# ============================================================

def page_welcome():

    st.markdown(
        """
        <div class="hotel-title">
            TURING HOTEL
        </div>
        """,
        unsafe_allow_html=True
    )


    st.markdown(
        """
        <div class="hotel-subtitle">
            In un futuro dannatamente possibile
        </div>
        """,
        unsafe_allow_html=True
    )


    if HOTEL_IMAGE.exists():

        st.image(
            str(HOTEL_IMAGE),
            use_container_width=True
        )

    else:

        st.info(
            "Carica una foto chiamata "
            "TuringHotel.jpg "
            "nella cartella assets."
        )


    st.write("")


    left, center, right = st.columns(
        [2, 1, 2]
    )


    with center:

        if st.button(
            "ENTRA",
            type="primary",
            key="enter_hotel"
        ):

            st.session_state.page = (
                "characters"
            )

            st.rerun()


    st.write("")


    with st.expander(
        "⚙ STUDIO",
        expanded=False
    ):

        st.caption(
            "Area autore per costruire "
            "sequenze, memoria e personaggi."
        )


        if st.button(
            "APRI STUDIO AUTORE"
        ):

            st.session_state.page = (
                "author"
            )

            st.rerun()


# ============================================================
# SCELTA PERSONAGGIO
# ============================================================

def page_characters():

    st.markdown(
        "# Chi vuoi seguire?"
    )


    st.markdown(
        """
La storia è la stessa.

Ma ciò che viene visto,
ricordato e compreso cambia.
"""
    )


    st.write("")


    col_noa, spacer, col_ada = st.columns(
        [1, 0.08, 1]
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

        else:

            st.info(
                "Manca assets/Noa.jpg"
            )


        st.markdown(
            """
            <div class="character-name">
                NOA
            </div>
            """,
            unsafe_allow_html=True
        )


        st.markdown(
            """
            <div class="character-desc">
                Sa di essere artificiale.
            </div>
            """,
            unsafe_allow_html=True
        )


        if st.button(
            "ENTRA COME NOA",
            key="choose_noa"
        ):

            st.session_state.pov = "Noa"

            st.session_state.scene_position = 0

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

        else:

            st.info(
                "Manca assets/Ada.jpg"
            )


        st.markdown(
            """
            <div class="character-name">
                ADA
            </div>
            """,
            unsafe_allow_html=True
        )


        st.markdown(
            """
            <div class="character-desc">
                È cresciuta dentro il Turing Hotel.
            </div>
            """,
            unsafe_allow_html=True
        )


        if st.button(
            "ENTRA COME ADA",
            key="choose_ada"
        ):

            st.session_state.pov = "Ada"

            st.session_state.scene_position = 0

            st.session_state.page = "story"

            st.rerun()


    st.write("")


    if st.button(
        "← TORNA ALL'INGRESSO"
    ):

        st.session_state.page = "welcome"

        st.rerun()


# ============================================================
# SIDEBAR DELLA STORIA
# ============================================================

def story_sidebar():

    pov = st.session_state.pov


    st.sidebar.markdown(
        f"# {pov}"
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


    st.sidebar.caption(
        "Stai vivendo la storia "
        f"dal punto di vista di {pov}."
    )


    st.sidebar.markdown("---")


    scenes = ordered_scenes()


    for index, scene in enumerate(
        scenes
    ):

        active = (
            index
            == st.session_state.scene_position
        )


        label = (
            ("● " if active else "")
            + scene["id"]
            + " · "
            + scene["title"]
        )


        if st.sidebar.button(
            label,
            key=f"goto_{scene['id']}"
        ):

            st.session_state.scene_position = (
                index
            )

            st.rerun()


    st.sidebar.markdown("---")


    if st.sidebar.button(
        "⇄ CAMBIA PROTAGONISTA"
    ):

        st.session_state.page = (
            "characters"
        )

        st.rerun()


    if st.sidebar.button(
        "⌂ TORNA ALL'HOTEL"
    ):

        st.session_state.page = (
            "welcome"
        )

        st.rerun()


# ============================================================
# MEDIA DELLA SCENA
# ============================================================

def render_scene_media(scene):

    media = get_scene_media(
        scene
    )


    if not media:
        return


    for path in media:

        show_media(
            path
        )


# ============================================================
# CHAT DELLA SCENA
# ============================================================

def render_scene_chat(
    scene,
    pov
):

    message_key = (
        "messages_noa"
        if pov == "Noa"
        else "messages_ada"
    )


    vision_key = (
        "vision_noa"
        if pov == "Noa"
        else "vision_ada"
    )


    memory_key = (
        "memory_noa"
        if pov == "Noa"
        else "memory_ada"
    )


    messages = scene[
        message_key
    ]


    if messages:

        st.markdown(
            "### Quello che è accaduto"
        )


    for message in messages:

        speaker = message.get(
            "speaker",
            "?"
        )


        is_agent = (
            speaker == pov
        )


        with st.chat_message(
            "assistant"
            if is_agent
            else "user"
        ):

            st.markdown(
                f"**{speaker}**"
            )

            st.write(
                message.get(
                    "text",
                    ""
                )
            )


    speaker = st.selectbox(

        "Chi interviene nella scena?",

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

        key=(
            f"speaker_"
            f"{scene['id']}_"
            f"{pov}"
        )
    )


    user_text = st.chat_input(
        f"Scrivi una battuta o un evento per {pov}..."
    )


    if user_text:

        messages.append({
            "speaker": speaker,
            "text": user_text
        })


        prompt_data = {

            "titolo_scena":
                scene["title"],

            "luogo":
                scene["place"],

            "momento":
                scene["moment"],

            "evento_stabilito_dall_autore":
                scene["event"],

            "cio_che_il_personaggio_percepisce":
                scene[vision_key],

            "memoria_specifica_della_scena":
                scene[memory_key],

            "interazione_finora":
                messages
        }


        with st.spinner(
            f"{pov} sta reagendo..."
        ):

            reply = query_openai(

                build_agent_prompt(
                    pov
                ),

                prompt_data
            )


        messages.append({
            "speaker": pov,
            "text": reply
        })


        save_state()

        st.rerun()


# ============================================================
# SCENA NORMALE
# ============================================================

def render_normal_scene(
    scene,
    position,
    total
):

    pov = st.session_state.pov


    st.markdown(
        f"""
        <div class="scene-number">
            Sequenza {position + 1} di {total}
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
        <div class="scene-meta">
            {scene["place"]} · {scene["moment"]}
        </div>
        """,
        unsafe_allow_html=True
    )


    st.markdown(
        f"""
        <div class="pov-label">
            Punto di vista: {pov}
        </div>
        """,
        unsafe_allow_html=True
    )


    render_scene_media(
        scene
    )


    if scene["event"]:

        st.markdown(
            f"""
            <div class="event-box">
                {scene["event"]}
            </div>
            """,
            unsafe_allow_html=True
        )


    render_scene_chat(
        scene,
        pov
    )


# ============================================================
# FINALE AUTONOMO
# ============================================================

def run_autonomous_finale(
    scene,
    starting_agent,
    turns
):

    transcript = []


    current_agent = (
        starting_agent
    )


    for step in range(turns):

        other_agent = (
            "Ada"
            if current_agent == "Noa"
            else "Noa"
        )


        prompt_data = {

            "evento_finale":
                scene["final_event"],

            "luogo":
                scene["place"],

            "momento":
                scene["moment"],

            "altra_persona":
                other_agent,

            "tutto_quello_che_e_successo_finora":
                transcript,

            "turno":
                step + 1,

            "istruzione":
                """
Decidi autonomamente
che cosa fai adesso.

Non sei obbligata a parlare.

Puoi:

- parlare;
- muoverti;
- fare qualcosa;
- aspettare;
- restare in silenzio;
- andartene;
- prendere una decisione.

Scrivi soltanto
il tuo intervento narrativo.
"""
        }


        response = query_openai(

            build_agent_prompt(
                current_agent,
                finale=True
            ),

            prompt_data
        )


        transcript.append({

            "speaker":
                current_agent,

            "text":
                response
        })


        current_agent = (
            other_agent
        )


    return transcript


def render_finale(
    scene
):

    pov = st.session_state.pov


    st.markdown(
        """
        <div class="scene-number">
            Finale
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
        <div class="scene-meta">
            {scene["place"]} · {scene["moment"]}
        </div>
        """,
        unsafe_allow_html=True
    )


    render_scene_media(
        scene
    )


    st.markdown(
        """
        <div class="final-box">

        <b>Da questo momento
        l'autore smette di intervenire.</b>

        <br><br>

        Noa e Ada ricevono soltanto un evento.

        <br><br>

        Poi vengono lasciate sole.

        </div>
        """,
        unsafe_allow_html=True
    )


    scene["final_event"] = st.text_area(

        "Evento finale",

        scene.get(
            "final_event",
            ""
        ),

        height=180,

        placeholder=(
            "Descrivi soltanto ciò che accade. "
            "Non dire a Noa o Ada "
            "come devono reagire."
        )
    )


    turns = st.slider(

        "Numero massimo di interventi",

        min_value=2,
        max_value=30,
        value=10,
        step=2
    )


    if st.button(
        "LASCIA SOLE NOA E ADA",
        type="primary"
    ):

        if not scene[
            "final_event"
        ].strip():

            st.warning(
                "Prima scrivi l'evento finale."
            )

        else:

            with st.spinner(
                "Noa e Ada stanno vivendo l'evento..."
            ):

                scene[
                    "final_transcript"
                ] = run_autonomous_finale(

                    scene,

                    starting_agent=pov,

                    turns=turns
                )


            save_state()

            st.rerun()


    transcript = scene.get(
        "final_transcript",
        []
    )


    if transcript:

        st.markdown("---")

        st.markdown(
            "## Quello che è successo"
        )


        for item in transcript:

            st.markdown(
                f"""
                <div class="final-speaker">
                    {item["speaker"]}
                </div>
                """,
                unsafe_allow_html=True
            )


            st.markdown(
                item["text"]
            )


# ============================================================
# PAGINA STORIA
# ============================================================

def page_story():

    if not st.session_state.pov:

        st.session_state.page = (
            "characters"
        )

        st.rerun()


    story_sidebar()


    scenes = ordered_scenes()


    if not scenes:

        st.warning(
            "Non ci sono sequenze."
        )

        return


    position = min(
        st.session_state.scene_position,
        len(scenes) - 1
    )


    st.session_state.scene_position = (
        position
    )


    scene = scenes[
        position
    ]


    if scene.get(
        "is_final",
        False
    ):

        render_finale(
            scene
        )

    else:

        render_normal_scene(

            scene,

            position,

            len(scenes)
        )


    st.markdown("---")


    previous_column, middle, next_column = (
        st.columns(
            [1, 3, 1]
        )
    )


    with previous_column:

        if position > 0:

            if st.button(
                "← PRECEDENTE"
            ):

                st.session_state.scene_position -= 1

                st.rerun()


    with next_column:

        if position < len(scenes) - 1:

            if st.button(
                "SUCCESSIVA →"
            ):

                st.session_state.scene_position += 1

                st.rerun()


    save_state()


# ============================================================
# STUDIO AUTORE
# ============================================================

def page_author():

    st.title(
        "Turing Hotel · Studio"
    )


    st.caption(
        f"Modello OpenAI attivo: {OPENAI_MODEL}"
    )


    (
        tab_scenes,
        tab_agents,
        tab_world,
        tab_test
    ) = st.tabs([

        "🎬 Sequenze",

        "🧠 Noa & Ada",

        "🏨 Turing Hotel",

        "🔌 OpenAI"
    ])


    # ========================================================
    # SEQUENZE
    # ========================================================

    with tab_scenes:

        st.subheader(
            "Ordine delle sequenze"
        )


        st.caption(
            "La stessa sequenza viene vissuta "
            "in modo diverso da Noa e Ada."
        )


        scenes = ordered_scenes()


        for index, scene in enumerate(
            scenes
        ):

            with st.expander(
                f"{scene['id']} · {scene['title']}",
                expanded=False
            ):

                column1, column2, column3 = (
                    st.columns(
                        [2, 1, 1]
                    )
                )


                scene["title"] = (
                    column1.text_input(

                        "Titolo",

                        scene["title"],

                        key=f"title_{scene['id']}"
                    )
                )


                scene["place"] = (
                    column2.text_input(

                        "Luogo",

                        scene["place"],

                        key=f"place_{scene['id']}"
                    )
                )


                scene["moment"] = (
                    column3.text_input(

                        "Momento",

                        scene["moment"],

                        key=f"moment_{scene['id']}"
                    )
                )


                scene["slug"] = (
                    st.text_input(

                        "Nome file / slug",

                        scene.get(
                            "slug",
                            slugify(scene["title"])
                        ),

                        key=f"slug_{scene['id']}"
                    )
                )


                scene["event"] = (
                    st.text_area(

                        "Evento oggettivo della scena",

                        scene["event"],

                        height=130,

                        key=f"event_{scene['id']}"
                    )
                )


                st.caption(
                    "Qui scriviamo ciò che realmente accade. "
                    "Noa e Ada possono interpretarlo diversamente."
                )


                perception_col1, perception_col2 = (
                    st.columns(2)
                )


                with perception_col1:

                    scene["vision_noa"] = (
                        st.text_area(

                            "Cosa può percepire Noa",

                            scene["vision_noa"],

                            height=140,

                            key=f"vision_noa_{scene['id']}"
                        )
                    )


                with perception_col2:

                    scene["vision_ada"] = (
                        st.text_area(

                            "Cosa può percepire Ada",

                            scene["vision_ada"],

                            height=140,

                            key=f"vision_ada_{scene['id']}"
                        )
                    )


                scene["is_final"] = (
                    st.checkbox(

                        "Questa è la scena finale",

                        value=scene.get(
                            "is_final",
                            False
                        ),

                        key=f"is_final_{scene['id']}"
                    )
                )


                # --------------------------------------------
                # MEDIA
                # --------------------------------------------

                st.markdown(
                    "#### Foto e video"
                )


                existing_media = get_scene_media(
                    scene
                )


                if existing_media:

                    for path in existing_media:

                        show_media(
                            path
                        )

                        st.caption(
                            path.name
                        )


                uploads = st.file_uploader(

                    "Carica foto o video",

                    type=[
                        "jpg",
                        "jpeg",
                        "png",
                        "webp",
                        "mp4",
                        "mov",
                        "m4v",
                        "webm"
                    ],

                    accept_multiple_files=True,

                    key=f"uploads_{scene['id']}"
                )


                if uploads:

                    if st.button(
                        "SALVA MEDIA",
                        key=f"save_media_{scene['id']}"
                    ):

                        for uploaded_file in uploads:

                            save_uploaded_media(
                                uploaded_file,
                                scene
                            )


                        save_state()

                        st.rerun()


                st.caption(
                    "Nome automatico: "
                    f"{scene_prefix(scene)}_01.jpg / "
                    f"{scene_prefix(scene)}_02.mp4 / ..."
                )


                # --------------------------------------------
                # ORDINE
                # --------------------------------------------

                st.markdown("---")


                up_column, down_column = (
                    st.columns(2)
                )


                if up_column.button(

                    "↑ SPOSTA PRIMA",

                    key=f"up_{scene['id']}",

                    disabled=index == 0
                ):

                    order = state[
                        "scene_order"
                    ]


                    current_index = order.index(
                        scene["id"]
                    )


                    (
                        order[current_index - 1],
                        order[current_index]
                    ) = (
                        order[current_index],
                        order[current_index - 1]
                    )


                    save_state()

                    st.rerun()


                if down_column.button(

                    "↓ SPOSTA DOPO",

                    key=f"down_{scene['id']}",

                    disabled=(
                        index
                        == len(scenes) - 1
                    )
                ):

                    order = state[
                        "scene_order"
                    ]


                    current_index = order.index(
                        scene["id"]
                    )


                    (
                        order[current_index + 1],
                        order[current_index]
                    ) = (
                        order[current_index],
                        order[current_index + 1]
                    )


                    save_state()

                    st.rerun()


        st.markdown("---")


        if st.button(
            "＋ CREA NUOVA SEQUENZA"
        ):

            new_id = next_scene_id()


            new_scene = {

                "id":
                    new_id,

                "slug":
                    "nuova_scena",

                "title":
                    "Nuova scena",

                "place":
                    "Turing Hotel",

                "moment":
                    "Giorno",

                "event":
                    "",

                "vision_noa":
                    "",

                "vision_ada":
                    "",

                "messages_noa":
                    [],

                "messages_ada":
                    [],

                "memory_noa":
                    "",

                "memory_ada":
                    "",

                "prose_noa":
                    "",

                "prose_ada":
                    "",

                "is_final":
                    False
            }


            state["scenes"].append(
                new_scene
            )


            state["scene_order"].append(
                new_id
            )


            save_state()

            st.rerun()


    # ========================================================
    # AGENTI
    # ========================================================

    with tab_agents:

        editing_agent = st.radio(

            "Personaggio",

            ["Noa", "Ada"],

            horizontal=True
        )


        agent = state[
            "agents"
        ][editing_agent]


        portrait = (

            NOA_IMAGE

            if editing_agent == "Noa"

            else ADA_IMAGE
        )


        profile_column, portrait_column = (
            st.columns(
                [2, 1]
            )
        )


        with portrait_column:

            if portrait.exists():

                st.image(
                    str(portrait),
                    use_container_width=True
                )


        with profile_column:

            agent["profile"] = (
                st.text_area(

                    "Profilo del personaggio",

                    agent["profile"],

                    height=300
                )
            )


            agent["system_prompt"] = (
                st.text_area(

                    "Istruzioni permanenti",

                    agent["system_prompt"],

                    height=280
                )
            )


            agent["memory"] = (
                st.text_area(

                    "Memoria generale persistente",

                    agent["memory"],

                    height=250
                )
            )


            agent["notes"] = (
                st.text_area(

                    "Appunti dell'autore",

                    agent.get(
                        "notes",
                        ""
                    ),

                    height=180
                )
            )


        if st.button(
            "SALVA PERSONAGGIO"
        ):

            save_state()

            st.success(
                f"{editing_agent} salvata."
            )


    # ========================================================
    # HOTEL / MONDO
    # ========================================================

    with tab_world:

        state["world"] = (
            st.text_area(

                "Regole e descrizione del mondo",

                state["world"],

                height=500
            )
        )


        if HOTEL_IMAGE.exists():

            st.markdown(
                "### Immagine Hotel"
            )

            st.image(
                str(HOTEL_IMAGE),
                use_container_width=True
            )


        if st.button(
            "SALVA MONDO"
        ):

            save_state()

            st.success(
                "Turing Hotel salvato."
            )


    # ========================================================
    # TEST OPENAI
    # ========================================================

    with tab_test:

        st.subheader(
            "Connessione OpenAI"
        )


        st.write(
            f"Modello configurato: **{OPENAI_MODEL}**"
        )


        if client:

            st.success(
                "OPENAI_API_KEY trovata."
            )

        else:

            st.error(
                "OPENAI_API_KEY non trovata."
            )


        if st.button(
            "TESTA OPENAI"
        ):

            with st.spinner(
                "Controllo connessione..."
            ):

                result = query_openai(

                    """
Rispondi esclusivamente
con la frase:

Turing Hotel è online.
""",

                    {
                        "test": True
                    }
                )


            st.write(
                result
            )


    # ========================================================
    # USCITA STUDIO
    # ========================================================

    st.markdown("---")


    if st.button(
        "← TORNA ALL'HOTEL"
    ):

        save_state()

        st.session_state.page = (
            "welcome"
        )

        st.rerun()


# ============================================================
# ROUTER
# ============================================================

if st.session_state.page == "welcome":

    page_welcome()


elif st.session_state.page == "characters":

    page_characters()


elif st.session_state.page == "story":

    page_story()


elif st.session_state.page == "author":

    page_author()


else:

    st.session_state.page = "welcome"

    st.rerun()
