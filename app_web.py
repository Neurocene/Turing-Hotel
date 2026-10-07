import streamlit as st
import json
import os
import re
import copy
from pathlib import Path
import google.generativeai as genai


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


HOTEL_IMAGE = ASSETS_DIR / "TuringHotel.jpg"
NOA_IMAGE = ASSETS_DIR / "Noa.jpg"
ADA_IMAGE = ASSETS_DIR / "Ada.jpg"


# ============================================================
# GEMINI KEY
# ============================================================

gemini_key = None

try:
    gemini_key = st.secrets.get("GEMINI_API_KEY")
except Exception:
    pass

if not gemini_key:
    gemini_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )

if gemini_key:
    genai.configure(api_key=gemini_key)


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.stApp {
    background-color: #090c10;
    color: #f3f0e9;
}

header[data-testid="stHeader"] {
    background: rgba(0,0,0,0);
}

[data-testid="stSidebar"] {
    background-color: #10151a !important;
    border-right: 1px solid #252d33;
}

h1, h2, h3 {
    font-family: Georgia, serif;
}

/* HOME */

.hotel-title {
    text-align: center;
    font-family: Georgia, serif;
    font-size: clamp(3rem, 7vw, 6rem);
    letter-spacing: 0.14em;
    margin-top: 2rem;
    margin-bottom: 0;
}

.hotel-subtitle {
    text-align: center;
    color: #9ba1a6;
    font-family: Georgia, serif;
    font-size: 1.1rem;
    margin-top: 0.6rem;
    margin-bottom: 2rem;
}

/* PERSONAGGI */

.character-name {
    text-align: center;
    font-family: Georgia, serif;
    font-size: 2.6rem;
    margin-top: 0.5rem;
}

.character-desc {
    text-align: center;
    color: #a8adb2;
    margin-bottom: 1rem;
}

/* SCENA */

.scene-number {
    color: #858b91;
    font-size: 0.78rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-top: 1rem;
}

.scene-title {
    font-family: Georgia, serif;
    font-size: 3rem;
    line-height: 1.05;
    margin-top: 0.3rem;
}

.scene-meta {
    color: #969ca1;
    margin-top: 0.3rem;
    margin-bottom: 1.8rem;
}

.pov-label {
    color: #c4ab7c;
    letter-spacing: 0.12em;
    font-size: 0.75rem;
    text-transform: uppercase;
}

/* CHAT */

[data-testid="stChatMessage"] {
    background-color: #141a20;
    border: 1px solid #29323a;
    border-radius: 8px;
    margin-bottom: 0.7rem;
}

/* BOTTONI */

div.stButton > button {
    width: 100%;
    min-height: 48px;
    background-color: #1b242b;
    color: #f4f0e8;
    border: 1px solid #4b555c;
    border-radius: 4px;
    font-weight: 600;
}

div.stButton > button:hover {
    background-color: #28343d;
    border-color: #ae9873;
    color: white;
}

/* FINALE */

.final-box {
    background-color: #12171b;
    border: 1px solid #78674d;
    padding: 24px;
    border-radius: 6px;
    margin: 1rem 0 1.5rem 0;
}

.final-speaker {
    font-family: Georgia, serif;
    color: #c2a878;
    font-size: 1.3rem;
}

.small-muted {
    color: #858c92;
    font-size: 0.85rem;
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
Oggi conserva il lusso del passato, ma vive una lenta decadenza.

È fuori stagione.

Marmi, legno, ottone, velluti, grandi finestre,
vecchie fotografie e una veranda Liberty guardano il mare d'inverno.

Il Turing Hotel è il luogo nel quale esseri umani
e artificiali sono messi davanti alla memoria,
alla perdita, all'empatia e alla libertà.
""",

    "agents": {

        "Noa": {

            "profile": """
Noa è un agente artificiale relazionale.

Sa di essere artificiale.

È stata progettata per comprendere gli esseri umani,
creare empatia e farli stare bene.

È lucida, intelligente, ironica e osservatrice.

Può essere seduttiva.
Può usare ciò che comprende delle persone.

Non desidera necessariamente diventare umana.

Il suo conflitto riguarda il valore delle proprie esperienze:
se qualcosa nasce da un sistema progettato,
può comunque diventare autentico?
""",

            "system_prompt": """
Interpreta soltanto Noa.

Noa non è un assistente.
Noa è un personaggio.

Non spiegare la teoria.
Non fare lezioni.
Non anticipare il futuro.

Lascia che ciò che prova emerga
attraverso pensieri, comportamenti,
azioni, omissioni e dialoghi.

Noa può:
- sbagliare;
- mentire;
- dubitare;
- desiderare;
- cambiare idea;
- restare in silenzio.
""",

            "visual_identity": """
Donna elegante, contemporanea, apparentemente umana.

Presenza intelligente e controllata.
Eleganza discreta da hotel sul mare fuori stagione.
""",

            "memory": "",

            "notes": ""
        },

        "Ada": {

            "profile": """
Ada è la figlia del professor Elia.

È una donna italiana poco più che trentenne.

È cresciuta intorno al Turing Hotel
e oggi lo gestisce insieme al padre.

È intelligente, pratica, osservatrice,
riservata e poco espansiva.

Conosce ogni corridoio,
ogni rumore e ogni difetto dell'hotel.

Non sa con certezza se abbia scelto di restare
oppure se abbia semplicemente continuato
a rimandare la propria partenza.
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

Può essere ironica.
Può sbagliare.
Può nascondere qualcosa.
Può essere contraddittoria.
""",

            "visual_identity": """
Donna italiana poco più che trentenne.

Elegante in modo naturale.

Bellezza da località di mare d'inverno:
maglieria raffinata,
cappotti morbidi,
toni crema, sabbia, blu e grigio.

Capelli castani spesso raccolti.

Ha qualcosa del padre nello sguardo
e nella piega fra le sopracciglia.
""",

            "memory": "",

            "notes": ""
        }
    },

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
# CARICAMENTO JSON
# ============================================================

if "state" not in st.session_state:

    if DATA_FILE.exists():

        try:
            loaded = json.loads(
                DATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

            st.session_state.state = loaded

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
# MIGRAZIONE / PROTEZIONE DATI
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


for name in ["Noa", "Ada"]:

    if name not in state["agents"]:
        state["agents"][name] = copy.deepcopy(
            DEFAULT_STATE["agents"][name]
        )

    for key, value in DEFAULT_STATE["agents"][name].items():

        if key not in state["agents"][name]:
            state["agents"][name][key] = copy.deepcopy(
                value
            )


for scene in state["scenes"]:

    scene_id = str(scene.get("id", "")).zfill(2)

    scene["id"] = scene_id

    if "slug" not in scene:
        scene["slug"] = "scena"

    if "event" not in scene:
        scene["event"] = ""

    if "vision_noa" not in scene:
        scene["vision_noa"] = scene.get(
            "vision",
            ""
        )

    if "vision_ada" not in scene:
        scene["vision_ada"] = ""

    if "messages_noa" not in scene:
        scene["messages_noa"] = (
            scene.get("messages", [])
            if scene.get("agent") == "Noa"
            else []
        )

    if "messages_ada" not in scene:
        scene["messages_ada"] = (
            scene.get("messages", [])
            if scene.get("agent") == "Ada"
            else []
        )

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
        s["id"]
        for s in state["scenes"]
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

if "author_mode" not in st.session_state:
    st.session_state.author_mode = False


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
# GEMINI
# ============================================================

def query_gemini(
    instructions,
    prompt_data,
    model_name="gemini-2.5-flash"
):

    if not gemini_key:

        return (
            "ERRORE: GEMINI_API_KEY non configurata. "
            "Inseriscila nei Secrets di Streamlit."
        )

    try:

        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=instructions
        )

        response = model.generate_content(
            json.dumps(
                prompt_data,
                ensure_ascii=False
            )
        )

        return response.text

    except Exception as e:

        return f"Errore Gemini: {str(e)}"


# ============================================================
# FUNZIONI SCENE
# ============================================================

def scene_by_id(scene_id):

    for scene in state["scenes"]:

        if scene["id"] == scene_id:
            return scene

    return None


def ordered_scenes():

    result = []

    existing_ids = {
        s["id"]
        for s in state["scenes"]
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

    for scene_id in clean_order:

        scene = scene_by_id(scene_id)

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
        text.replace("à", "a")
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

    return text.strip("_") or "scena"


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


def scene_media(scene):

    prefix = scene_prefix(scene)

    results = []

    if not SCENES_DIR.exists():
        return results

    for path in SCENES_DIR.iterdir():

        if (
            path.is_file()
            and path.name.startswith(prefix)
        ):
            results.append(path)

    return sorted(results)


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

    media = scene_media(scene)

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

    return (
        max(numbers) + 1
        if numbers
        else 1
    )


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
# PROMPT AGENTI
# ============================================================

def build_agent_prompt(
    agent_name,
    finale=False
):

    agent = state["agents"][agent_name]

    prompt = f"""
SEI {agent_name}.

Non sei un assistente AI.

Sei un personaggio del romanzo TURING HOTEL.


MONDO

{state["world"]}


IDENTITÀ

{agent["profile"]}


ISTRUZIONI PERSONAGGIO

{agent["system_prompt"]}


MEMORIA GENERALE

{agent["memory"]}


REGOLE

1. Interpreta soltanto {agent_name}.
2. Non scrivere ciò che dicono gli altri personaggi.
3. Non decidere gli eventi futuri della storia.
4. Non spiegare la teoria.
5. Non comportarti come un assistente.
6. Non sai ciò che l'autore sa.
7. Reagisci soltanto a ciò che puoi percepire o ricordare.
8. Puoi sbagliare.
9. Puoi mentire.
10. Puoi dubitare.
11. Puoi cambiare idea.
12. Puoi essere contraddittoria.
13. Puoi agire invece di parlare.
14. Puoi restare in silenzio.
15. Mantieni continuità con le esperienze precedenti.
"""

    if finale:

        prompt += """

FASE FINALE

Da questo momento l'autore non controlla più
come deve svilupparsi la scena.

Non cercare un finale bello.
Non cercare un finale drammatico.
Non cercare di soddisfare l'autore.

Agisci secondo:
- la tua identità;
- i tuoi ricordi;
- i tuoi desideri;
- le tue paure;
- ciò che hai imparato;
- il rapporto che hai costruito con Ada o Noa.

Puoi:
- parlare;
- muoverti;
- compiere un'azione;
- aspettare;
- non rispondere;
- andartene;
- prendere una decisione irreversibile.

Descrivi soltanto ciò che fai,
pensi o dici tu.
"""

    return prompt


# ============================================================
# HOME
# ============================================================

def page_welcome():

    st.markdown(
        '<div class="hotel-title">'
        'TURING HOTEL'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="hotel-subtitle">'
        'In un futuro dannatamente possibile'
        '</div>',
        unsafe_allow_html=True
    )

    if HOTEL_IMAGE.exists():

        st.image(
            str(HOTEL_IMAGE),
            use_container_width=True
        )

    else:

        st.info(
            "Inserisci una foto chiamata "
            "TuringHotel.jpg nella cartella assets."
        )

    st.write("")

    c1, c2, c3 = st.columns(
        [2, 1, 2]
    )

    with c2:

        if st.button(
            "ENTRA",
            key="enter_hotel"
        ):

            st.session_state.page = (
                "characters"
            )

            st.rerun()

    st.write("")

    with st.expander(
        "⚙ Studio / configurazione",
        expanded=False
    ):

        if st.button(
            "Apri modalità autore"
        ):

            st.session_state.author_mode = True
            st.session_state.page = "author"

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
            '<div class="character-name">'
            'NOA'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="character-desc">'
            'Sa di essere artificiale.'
            '</div>',
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
            '<div class="character-name">'
            'ADA'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="character-desc">'
            'È cresciuta dentro il Turing Hotel.'
            '</div>',
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
        "← Torna all'ingresso"
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
        f"Stai vivendo la storia dal punto di vista di {pov}."
    )

    st.sidebar.markdown("---")

    scenes = ordered_scenes()

    for index, scene in enumerate(
        scenes
    ):

        prefix = (
            "● "
            if index == st.session_state.scene_position
            else ""
        )

        label = (
            prefix
            + scene["id"]
            + " · "
            + scene["title"]
        )

        if st.sidebar.button(
            label,
            key=f"goto_{scene['id']}"
        ):

            st.session_state.scene_position = index

            st.rerun()

    st.sidebar.markdown("---")

    if st.sidebar.button(
        "⇄ Cambia protagonista"
    ):

        st.session_state.page = "characters"

        st.rerun()

    if st.sidebar.button(
        "⌂ Torna all'hotel"
    ):

        st.session_state.page = "welcome"

        st.rerun()


# ============================================================
# MEDIA DELLA SCENA
# ============================================================

def render_scene_media(scene):

    media = scene_media(scene)

    if media:

        for path in media:

            show_media(path)


# ============================================================
# CHAT
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

    messages = scene[message_key]

    if messages:

        st.markdown(
            "### Quello che è accaduto"
        )

    for message in messages:

        speaker = message.get(
            "speaker",
            "?"
        )

        is_pov = speaker == pov

        with st.chat_message(
            "assistant"
            if is_pov
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

            "evento_imposto_dall_autore":
                scene["event"],

            "cio_che_percepisce":
                scene[vision_key],

            "memoria_di_questa_scena":
                scene[memory_key],

            "conversazione":
                messages
        }

        with st.spinner(
            f"{pov} sta reagendo..."
        ):

            reply = query_gemini(
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
        f'<div class="scene-number">'
        f'Sequenza {position + 1} di {total}'
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
        f'<div class="scene-meta">'
        f'{scene["place"]} · '
        f'{scene["moment"]}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="pov-label">'
        f'Punto di vista: {pov}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.write("")

    render_scene_media(
        scene
    )

    if scene["event"]:

        st.markdown(
            scene["event"]
        )

    render_scene_chat(
        scene,
        pov
    )


# ============================================================
# FINALE AUTONOMO
# ============================================================

def run_finale(
    scene,
    starting_agent,
    turns
):

    transcript = []

    current_agent = starting_agent

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

            "l_altra_persona":
                other_agent,

            "cio_che_e_successo_finora":
                transcript,

            "istruzione":
                """
Decidi autonomamente cosa fai adesso.

Non sei obbligata a parlare.

Puoi:
parlare,
compiere un'azione,
muoverti,
aspettare,
non fare nulla,
andartene,
prendere una decisione.

Scrivi una sola azione narrativa
dal tuo punto di vista.
"""
        }

        response = query_gemini(
            build_agent_prompt(
                current_agent,
                finale=True
            ),
            prompt_data
        )

        transcript.append({
            "speaker": current_agent,
            "text": response
        })

        current_agent = other_agent

    return transcript


def render_finale(scene):

    pov = st.session_state.pov

    st.markdown(
        '<div class="scene-number">'
        'Finale'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="scene-title">'
        f'{scene["title"]}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="scene-meta">'
        f'{scene["place"]} · '
        f'{scene["moment"]}'
        f'</div>',
        unsafe_allow_html=True
    )

    render_scene_media(
        scene
    )

    st.markdown(
        """
<div class="final-box">

Da questo momento l'autore smette di intervenire.

Noa e Ada ricevono soltanto un evento.

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
            "Descrivi ciò che accade, "
            "senza dire a Noa o Ada "
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

        if not scene["final_event"].strip():

            st.warning(
                "Scrivi prima l'evento finale."
            )

        else:

            with st.spinner(
                "Noa e Ada stanno vivendo l'evento..."
            ):

                scene["final_transcript"] = (
                    run_finale(
                        scene,
                        pov,
                        turns
                    )
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
                f'<div class="final-speaker">'
                f'{item["speaker"]}'
                f'</div>',
                unsafe_allow_html=True
            )

            st.markdown(
                item["text"]
            )

            st.write("")


# ============================================================
# PAGINA STORIA
# ============================================================

def page_story():

    if not st.session_state.pov:

        st.session_state.page = "characters"

        st.rerun()

    story_sidebar()

    scenes = ordered_scenes()

    if not scenes:

        st.warning(
            "Non ci sono scene."
        )

        return

    position = min(
        st.session_state.scene_position,
        len(scenes) - 1
    )

    st.session_state.scene_position = position

    scene = scenes[position]

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

    prev_col, middle, next_col = (
        st.columns(
            [1, 3, 1]
        )
    )

    with prev_col:

        if position > 0:

            if st.button(
                "← PRECEDENTE"
            ):

                st.session_state.scene_position -= 1

                st.rerun()

    with next_col:

        if position < len(scenes) - 1:

            if st.button(
                "SUCCESSIVA →"
            ):

                st.session_state.scene_position += 1

                st.rerun()

    save_state()


# ============================================================
# MODALITÀ AUTORE
# ============================================================

def page_author():

    st.title(
        "Turing Hotel · Studio"
    )

    tab_scenes, tab_agents, tab_world = (
        st.tabs([
            "🎬 Sequenze",
            "🧠 Noa & Ada",
            "🏨 Mondo"
        ])
    )

    # --------------------------------------------------------
    # SCENE
    # --------------------------------------------------------

    with tab_scenes:

        st.subheader(
            "Ordine delle sequenze"
        )

        scenes = ordered_scenes()

        for index, scene in enumerate(
            scenes
        ):

            with st.expander(
                f"{scene['id']} · {scene['title']}",
                expanded=False
            ):

                c1, c2, c3 = st.columns(
                    [2, 1, 1]
                )

                scene["title"] = c1.text_input(
                    "Titolo",
                    scene["title"],
                    key=f"title_{scene['id']}"
                )

                scene["place"] = c2.text_input(
                    "Luogo",
                    scene["place"],
                    key=f"place_{scene['id']}"
                )

                scene["moment"] = c3.text_input(
                    "Momento",
                    scene["moment"],
                    key=f"moment_{scene['id']}"
                )

                new_slug = slugify(
                    scene["title"]
                )

                scene["slug"] = st.text_input(
                    "Nome file / slug",
                    scene.get(
                        "slug",
                        new_slug
                    ),
                    key=f"slug_{scene['id']}"
                )

                scene["event"] = st.text_area(
                    "Evento della scena",
                    scene["event"],
                    height=120,
                    key=f"event_{scene['id']}"
                )

                scene["vision_noa"] = (
                    st.text_area(
                        "Cosa percepisce Noa",
                        scene["vision_noa"],
                        height=100,
                        key=f"vision_noa_{scene['id']}"
                    )
                )

                scene["vision_ada"] = (
                    st.text_area(
                        "Cosa percepisce Ada",
                        scene["vision_ada"],
                        height=100,
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
                        key=f"final_{scene['id']}"
                    )
                )

                st.markdown(
                    "#### Foto e video"
                )

                existing_media = scene_media(
                    scene
                )

                if existing_media:

                    media_cols = st.columns(
                        min(
                            3,
                            len(existing_media)
                        )
                    )

                    for media_index, path in enumerate(
                        existing_media
                    ):

                        with media_cols[
                            media_index
                            % len(media_cols)
                        ]:

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
                        "Salva media",
                        key=f"save_media_{scene['id']}"
                    ):

                        for upload in uploads:

                            save_uploaded_media(
                                upload,
                                scene
                            )

                        save_state()

                        st.rerun()

                st.caption(
                    "I file vengono nominati automaticamente: "
                    f"{scene_prefix(scene)}_01.jpg, "
                    f"{scene_prefix(scene)}_02.mp4..."
                )

                st.markdown("---")

                order_col1, order_col2 = (
                    st.columns(2)
                )

                if order_col1.button(
                    "↑ Sposta prima",
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

                if order_col2.button(
                    "↓ Sposta dopo",
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
                "id": new_id,
                "slug": "nuova_scena",
                "title": "Nuova scena",
                "place": "Turing Hotel",
                "moment": "Giorno",
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
            }

            state["scenes"].append(
                new_scene
            )

            state["scene_order"].append(
                new_id
            )

            save_state()

            st.rerun()

    # --------------------------------------------------------
    # AGENTI
    # --------------------------------------------------------

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

        col_profile, col_portrait = (
            st.columns(
                [2, 1]
            )
        )

        with col_portrait:

            if portrait.exists():

                st.image(
                    str(portrait),
                    use_container_width=True
                )

        with col_profile:

            agent["profile"] = (
                st.text_area(
                    "Profilo",
                    agent["profile"],
                    height=260
                )
            )

            agent["system_prompt"] = (
                st.text_area(
                    "Istruzioni permanenti",
                    agent["system_prompt"],
                    height=230
                )
            )

            agent["memory"] = (
                st.text_area(
                    "Memoria generale",
                    agent["memory"],
                    height=220
                )
            )

            agent["notes"] = (
                st.text_area(
                    "Appunti autore",
                    agent.get(
                        "notes",
                        ""
                    ),
                    height=180
                )
            )

        if st.button(
            "SALVA AGENTI"
        ):

            save_state()

            st.success(
                "Agenti salvati."
            )

    # --------------------------------------------------------
    # MONDO
    # --------------------------------------------------------

    with tab_world:

        state["world"] = (
            st.text_area(
                "Mondo narrativo",
                state["world"],
                height=450
            )
        )

        if st.button(
            "SALVA MONDO"
        ):

            save_state()

            st.success(
                "Mondo salvato."
            )

    st.markdown("---")

    if st.button(
        "← TORNA ALL'HOTEL"
    ):

        save_state()

        st.session_state.author_mode = False
        st.session_state.page = "welcome"

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
