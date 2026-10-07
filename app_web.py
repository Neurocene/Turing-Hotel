import streamlit as st
import json
import os
import uuid
from pathlib import Path
import google.generativeai as genai


# ============================================================
# CONFIGURAZIONE PAGINA
# ============================================================

st.set_page_config(
    page_title="Turing Hotel · Studio Web",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# STILE
# ============================================================

st.markdown("""
<style>

.stApp {
    background-color: #0f172a;
    color: #f8fafc;
}

[data-testid="stSidebar"] {
    background-color: #1e293b !important;
    border-right: 1px solid #334155;
}

.stTitle {
    color: #38bdf8 !important;
    font-family: 'Georgia', serif;
}

[data-testid="stChatMessage"] {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 10px;
}

.stChatInputContainer {
    border-color: #38bdf8 !important;
    background-color: #0f172a !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: #1e293b;
    padding: 6px;
    border-radius: 8px;
}

.stTabs [data-baseweb="tab"] {
    height: 45px;
    background-color: transparent;
    border-radius: 6px;
    color: #94a3b8;
    font-weight: 600;
}

.stTabs [aria-selected="true"] {
    background-color: #0284c7 !important;
    color: #ffffff !important;
}

.stTextArea textarea,
.stTextInput input {
    background-color: #1e293b !important;
    color: #f8fafc !important;
    border: 1px solid #475569 !important;
    border-radius: 8px !important;
}

.stButton > button {
    background-color: #0284c7;
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: bold;
    transition: all 0.2s;
}

.stButton > button:hover {
    background-color: #0369a1;
    border-color: #38bdf8;
}

.agent-card {
    padding: 16px;
    border-radius: 12px;
    background-color: #1e293b;
    border: 1px solid #334155;
    margin-bottom: 15px;
}

.media-card {
    padding: 12px;
    border-radius: 10px;
    background-color: #172033;
    border: 1px solid #334155;
    margin-bottom: 12px;
}

.small-label {
    color: #94a3b8;
    font-size: 0.85rem;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# GEMINI
# ============================================================

gemini_key = (
    os.environ.get("GEMINI_API_KEY")
    or os.environ.get("GOOGLE_API_KEY")
)

if gemini_key:
    genai.configure(api_key=gemini_key)


# ============================================================
# CARTELLE E FILE
# ============================================================

DATA_FILE = Path("data_web/romanzo_web.json")

MEDIA_DIR = Path("data_web/media")
AGENT_MEDIA_DIR = MEDIA_DIR / "agents"
SCENE_MEDIA_DIR = MEDIA_DIR / "scenes"

DATA_FILE.parent.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)
AGENT_MEDIA_DIR.mkdir(exist_ok=True)
SCENE_MEDIA_DIR.mkdir(exist_ok=True)


# ============================================================
# STATO INIZIALE
# ============================================================

DEFAULT_STATE = {

    "world": """
Turing Hotel: antico hotel cinque stelle sul mare Adriatico.
Un tempo lussuoso, oggi conserva un'eleganza decadente.
È fuori stagione. Il mare d'inverno è parte costante della storia.
""",

    "agents": {

        "Noa": {
            "profile": """
Agente artificiale relazionale.
È consapevole della propria natura artificiale.
È stata progettata per comprendere gli esseri umani,
creare empatia e farli stare bene.
""",

            "system_prompt": """
Interpreta Noa come un personaggio autonomo.
Non spiegare la teoria al lettore.
Reagisci soltanto a ciò che Noa può vedere,
sentire, ricordare o dedurre.
Non decidere gli eventi futuri della storia.
Vivi la scena dall'interno.
""",

            "visual_identity": """
Donna elegante, contemporanea, apparentemente umana.
Presenza controllata, intelligente e seduttiva.
Eleganza discreta da hotel sul mare fuori stagione.
""",

            "character_notes": "",

            "memory": "",

            "media": []
        },

        "Ada": {
            "profile": """
Figlia del professor Elia.
Donna italiana, poco più che trentenne.
Intelligente, osservatrice, pratica e riservata.
Gestisce il Turing Hotel insieme al padre.
Conosce ogni angolo, rumore e problema dell'albergo.
""",

            "system_prompt": """
Interpreta soltanto Ada.
Ada non deve raccontare ciò che l'autore sa:
può conoscere soltanto quello che ha vissuto,
osservato o che qualcuno le ha detto.

È intelligente, concreta, poco espansiva.
Osserva molto prima di parlare.
Ha un rapporto complesso con suo padre Elia
e con il Turing Hotel.
""",

            "visual_identity": """
Donna italiana poco più che trentenne.
Elegante ma naturale.
Bellezza da località di mare d'inverno:
maglieria raffinata, cappotti, pantaloni morbidi,
toni crema, blu, grigio, sabbia.
Capelli castani, spesso raccolti.
Somiglia leggermente al padre soprattutto nello sguardo
e nella piega fra le sopracciglia.
""",

            "character_notes": "",

            "memory": "",

            "media": []
        }
    },

    "scenes": [
        {
            "id": "1",
            "title": "Prima Scena Web",
            "agent": "Noa",
            "place": "Veranda",
            "moment": "Sera",
            "vision": "",
            "messages": [],
            "memory": "",
            "proposal": "",
            "prose": "",
            "media": []
        }
    ],

    "selected": 0
}


# ============================================================
# CARICAMENTO STATO
# ============================================================

if "state" not in st.session_state:

    if DATA_FILE.exists():

        try:
            loaded_state = json.loads(
                DATA_FILE.read_text(encoding="utf-8")
            )

            st.session_state.state = loaded_state

        except Exception:

            st.session_state.state = DEFAULT_STATE

    else:

        st.session_state.state = DEFAULT_STATE


state = st.session_state.state


# ============================================================
# MIGRAZIONE VECCHIO FORMATO
# ============================================================

# Se esiste ancora "profiles", non perdiamo quei dati.
if "agents" not in state:

    old_profiles = state.get("profiles", {})

    state["agents"] = DEFAULT_STATE["agents"]

    if "Noa" in old_profiles:
        state["agents"]["Noa"]["profile"] = old_profiles["Noa"]

    if "Ada" in old_profiles:
        state["agents"]["Ada"]["profile"] = old_profiles["Ada"]


# Garantisce l'esistenza di Noa e Ada
for agent_name in ["Noa", "Ada"]:

    if agent_name not in state["agents"]:
        state["agents"][agent_name] = DEFAULT_STATE["agents"][agent_name]

    for key, value in DEFAULT_STATE["agents"][agent_name].items():

        if key not in state["agents"][agent_name]:
            state["agents"][agent_name][key] = value


# Aggiornamento scene vecchie
for scene in state.get("scenes", []):

    if "media" not in scene:
        scene["media"] = []

    if "memory" not in scene:
        scene["memory"] = ""

    if "proposal" not in scene:
        scene["proposal"] = ""

    if "prose" not in scene:
        scene["prose"] = ""

    if "vision" not in scene:
        scene["vision"] = ""

    if "messages" not in scene:
        scene["messages"] = []


# ============================================================
# FUNZIONI
# ============================================================

def save_state():

    DATA_FILE.write_text(
        json.dumps(
            st.session_state.state,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def query_gemini(
    instructions,
    prompt_data,
    model_name="gemini-1.5-flash"
):

    if not gemini_key:

        return (
            "Errore: GEMINI_API_KEY non trovata "
            "nei Secrets di Streamlit."
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

        return f"Errore durante la generazione Gemini: {str(e)}"


def save_uploaded_file(uploaded_file, destination_folder):

    extension = Path(uploaded_file.name).suffix.lower()

    unique_name = f"{uuid.uuid4().hex}{extension}"

    destination = destination_folder / unique_name

    with open(destination, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return str(destination)


def determine_media_type(filename):

    suffix = Path(filename).suffix.lower()

    if suffix in [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    ]:
        return "image"

    if suffix in [
        ".mp4",
        ".mov",
        ".m4v",
        ".webm"
    ]:
        return "video"

    return "file"


def render_media_item(item):

    path = item.get("path")

    if not path:
        return

    if not Path(path).exists():
        st.warning(f"File non trovato: {path}")
        return

    media_type = item.get("type")

    if media_type == "image":

        st.image(
            path,
            caption=item.get("caption", "")
        )

    elif media_type == "video":

        st.video(path)

        if item.get("caption"):
            st.caption(item["caption"])


def build_agent_instructions(agent_name):

    agent = state["agents"][agent_name]

    return f"""
SEI {agent_name}.

MONDO:
{state["world"]}

PROFILO DEL PERSONAGGIO:
{agent["profile"]}

IDENTITÀ VISIVA:
{agent["visual_identity"]}

ISTRUZIONI DI INTERPRETAZIONE:
{agent["system_prompt"]}

MEMORIA GENERALE:
{agent["memory"]}

REGOLE:

1. Interpreta soltanto {agent_name}.
2. Non scrivere le battute degli altri personaggi.
3. Non decidere eventi futuri.
4. Non spiegare la teoria.
5. Reagisci a ciò che accade nella scena.
6. Mantieni coerenza con memoria e personalità.
7. Puoi avere dubbi, desideri, contraddizioni ed errori.
8. Non comportarti come un assistente AI.
9. Sei un personaggio del romanzo Turing Hotel.
"""


# ============================================================
# SCENA CORRENTE
# ============================================================

if not state["scenes"]:

    state["scenes"].append(
        DEFAULT_STATE["scenes"][0]
    )


scene_idx = state.get("selected", 0)

if scene_idx >= len(state["scenes"]):
    scene_idx = 0
    state["selected"] = 0

curr_scene = state["scenes"][scene_idx]


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🏨 Turing Hotel")


scene_titles = [
    f"{s['agent']} · {s['title']}"
    for s in state["scenes"]
]


selected_num = st.sidebar.selectbox(
    "Scegli scena",
    range(len(scene_titles)),
    index=scene_idx,
    format_func=lambda x: scene_titles[x]
)


if selected_num != scene_idx:

    state["selected"] = selected_num

    save_state()

    st.rerun()


# ------------------------------------------------------------
# NUOVE SCENE
# ------------------------------------------------------------

col_btn1, col_btn2 = st.sidebar.columns(2)


if col_btn1.button("+ Noa"):

    state["scenes"].append({

        "id": str(uuid.uuid4()),

        "title": "Nuova Scena",

        "agent": "Noa",

        "place": "Turing Hotel",

        "moment": "Giorno",

        "vision": "",

        "messages": [],

        "memory": "",

        "proposal": "",

        "prose": "",

        "media": []
    })

    state["selected"] = len(state["scenes"]) - 1

    save_state()

    st.rerun()


if col_btn2.button("+ Ada"):

    state["scenes"].append({

        "id": str(uuid.uuid4()),

        "title": "Nuova Scena",

        "agent": "Ada",

        "place": "Turing Hotel",

        "moment": "Giorno",

        "vision": "",

        "messages": [],

        "memory": "",

        "proposal": "",

        "prose": "",

        "media": []
    })

    state["selected"] = len(state["scenes"]) - 1

    save_state()

    st.rerun()


st.sidebar.markdown("---")


model_choice = st.sidebar.selectbox(
    "Modello Gemini",
    [
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
)


st.sidebar.markdown("---")

st.sidebar.caption(
    "I dati vengono salvati automaticamente "
    "in data_web/romanzo_web.json"
)


# ============================================================
# AREA PRINCIPALE
# ============================================================

st.title(
    f"{curr_scene['agent']} · {curr_scene['title']}"
)


col1, col2, col3, col4 = st.columns(
    [2, 1, 1, 1]
)


curr_scene["title"] = col1.text_input(
    "Titolo scena",
    curr_scene["title"]
)


curr_scene["place"] = col2.text_input(
    "Luogo",
    curr_scene["place"]
)


curr_scene["moment"] = col3.text_input(
    "Momento",
    curr_scene["moment"]
)


curr_scene["agent"] = col4.selectbox(
    "POV / Agente",
    ["Noa", "Ada"],
    index=0 if curr_scene["agent"] == "Noa" else 1
)


# ============================================================
# TAB
# ============================================================

(
    tab_dialogue,
    tab_memory,
    tab_prose,
    tab_media,
    tab_agents
) = st.tabs([

    "💬 Scena",

    "🧠 Memoria",

    "📖 Prosa",

    "🎬 Foto & Video",

    "🤖 Agenti AI"
])


# ============================================================
# TAB 1 — SCENA
# ============================================================

with tab_dialogue:

    st.subheader(
        f"Scena vissuta da {curr_scene['agent']}"
    )


    curr_scene["vision"] = st.text_area(

        "Cosa vede, sente o percepisce il personaggio",

        curr_scene["vision"],

        height=120,

        placeholder=(
            "Es. Ada vede Noa seduta nella veranda. "
            "Fuori il mare è grigio..."
        )
    )


    # Mini anteprima media
    if curr_scene["media"]:

        st.caption("Riferimenti visivi della scena")

        preview_cols = st.columns(
            min(3, len(curr_scene["media"]))
        )

        for i, media in enumerate(
            curr_scene["media"][:3]
        ):

            with preview_cols[
                i % len(preview_cols)
            ]:

                render_media_item(media)


    st.markdown("### Flusso della scena")


    for m in curr_scene["messages"]:

        is_agent = m["speaker"] in ["Noa", "Ada"]

        with st.chat_message(
            "assistant" if is_agent else "user"
        ):

            st.write(
                f"**{m['speaker']}**"
            )

            st.write(
                m["text"]
            )


    speaker = st.selectbox(

        "Chi interagisce con il personaggio",

        [
            "Luigi",
            "Elia",
            "Noa",
            "Ada",
            "Vittoria",
            "Riccardo",
            "Altro interlocutore"
        ]
    )


    user_text = st.chat_input(
        "Scrivi ciò che accade, un'azione o una battuta..."
    )


    if user_text:

        curr_scene["messages"].append({

            "speaker": speaker,

            "text": user_text,

            "visible": True
        })


        save_state()


        instructions = build_agent_instructions(
            curr_scene["agent"]
        )


        prompt_data = {

            "scene_title": curr_scene["title"],

            "luogo": curr_scene["place"],

            "momento": curr_scene["moment"],

            "percezioni": curr_scene["vision"],

            "memoria_scena": curr_scene["memory"],

            "dialogo_precedente":
                curr_scene["messages"]
        }


        with st.spinner(
            f"{curr_scene['agent']} sta vivendo la scena..."
        ):

            reply = query_gemini(
                instructions,
                prompt_data,
                model_choice
            )


        curr_scene["messages"].append({

            "speaker": curr_scene["agent"],

            "text": reply,

            "visible": True
        })


        save_state()

        st.rerun()


# ============================================================
# TAB 2 — MEMORIA
# ============================================================

with tab_memory:

    st.subheader(
        f"Memoria di {curr_scene['agent']} dopo questa scena"
    )


    curr_scene["memory"] = st.text_area(

        "Memoria già consolidata",

        curr_scene["memory"],

        height=180
    )


    if st.button(
        "Proponi memoria aggiornata",
        key="memory_button"
    ):

        instructions = f"""
Analizza la scena dal punto di vista di {curr_scene['agent']}.

Genera soltanto le informazioni che il personaggio
potrebbe realmente ricordare dopo questa esperienza.

Non aggiungere informazioni dell'autore
che il personaggio non conosce.

Dividi eventualmente in:

- eventi ricordati
- persone
- emozioni o reazioni
- ipotesi
- questioni irrisolte
"""


        prompt_data = {

            "profilo":
                state["agents"]
                [curr_scene["agent"]]
                ["profile"],

            "memoria_precedente":
                curr_scene["memory"],

            "dialogo":
                curr_scene["messages"]
        }


        with st.spinner(
            "Sto elaborando ciò che il personaggio ricorda..."
        ):

            curr_scene["proposal"] = query_gemini(
                instructions,
                prompt_data,
                model_choice
            )


        save_state()


    curr_scene["proposal"] = st.text_area(

        "Proposta memoria",

        curr_scene["proposal"],

        height=220
    )


    if st.button(
        "✅ Accetta questa memoria",
        key="accept_memory"
    ):

        curr_scene["memory"] = (
            curr_scene["proposal"]
        )

        save_state()

        st.success(
            "Memoria della scena aggiornata."
        )

        st.rerun()


# ============================================================
# TAB 3 — PROSA
# ============================================================

with tab_prose:

    st.subheader(
        "Trasforma l'esperienza in romanzo"
    )


    if st.button(
        "Genera prosa",
        key="prose_button"
    ):

        instructions = f"""
Trasforma questa esperienza in prosa italiana
per il romanzo Turing Hotel.

Il punto di vista è {curr_scene['agent']}.

Non fare un riassunto.

Scrivi una scena.

La teoria deve emergere attraverso:
azioni,
dialoghi,
percezioni,
decisioni,
contraddizioni.

Non attraverso spiegazioni didattiche.

Mantieni un tono realistico,
contemporaneo e letterario.
"""


        prompt_data = {

            "mondo":
                state["world"],

            "profilo_personaggio":
                state["agents"]
                [curr_scene["agent"]]
                ["profile"],

            "luogo":
                curr_scene["place"],

            "momento":
                curr_scene["moment"],

            "percezioni":
                curr_scene["vision"],

            "dialogo":
                curr_scene["messages"],

            "memoria":
                curr_scene["memory"]
        }


        with st.spinner(
            "Scrittura della scena..."
        ):

            curr_scene["prose"] = query_gemini(
                instructions,
                prompt_data,
                model_choice
            )


        save_state()


    curr_scene["prose"] = st.text_area(

        "Testo del romanzo",

        curr_scene["prose"],

        height=450
    )


# ============================================================
# TAB 4 — MEDIA DELLA SCENA
# ============================================================

with tab_media:

    st.subheader(
        "Foto e video della scena"
    )


    st.write(
        """
Qui puoi costruire la **memoria visiva della scena**:
location, personaggi, costumi, reference,
inquadrature, video generati o materiale girato.
"""
    )


    uploaded_scene_files = st.file_uploader(

        "Aggiungi foto o video",

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

        key=f"scene_upload_{curr_scene['id']}"
    )


    if uploaded_scene_files:

        if st.button(
            "Salva i media nella scena",
            key="save_scene_media"
        ):

            scene_folder = (
                SCENE_MEDIA_DIR
                / str(curr_scene["id"])
            )

            scene_folder.mkdir(
                parents=True,
                exist_ok=True
            )


            for uploaded in uploaded_scene_files:

                path = save_uploaded_file(
                    uploaded,
                    scene_folder
                )


                curr_scene["media"].append({

                    "id": str(uuid.uuid4()),

                    "path": path,

                    "type":
                        determine_media_type(path),

                    "original_name":
                        uploaded.name,

                    "caption": ""
                })


            save_state()

            st.success(
                "Media aggiunti alla scena."
            )

            st.rerun()


    st.markdown("---")


    for index, item in enumerate(
        curr_scene["media"]
    ):

        st.markdown(
            '<div class="media-card">',
            unsafe_allow_html=True
        )


        col_media, col_info = st.columns(
            [2, 1]
        )


        with col_media:

            render_media_item(item)


        with col_info:

            st.caption(
                item.get(
                    "original_name",
                    "Media"
                )
            )


            new_caption = st.text_area(

                "Descrizione / funzione narrativa",

                item.get(
                    "caption",
                    ""
                ),

                key=(
                    f"caption_"
                    f"{curr_scene['id']}_"
                    f"{item['id']}"
                ),

                height=120
            )


            item["caption"] = new_caption


            if st.button(

                "🗑 Elimina",

                key=(
                    f"delete_media_"
                    f"{item['id']}"
                )
            ):

                try:

                    Path(
                        item["path"]
                    ).unlink(
                        missing_ok=True
                    )

                except Exception:
                    pass


                curr_scene[
                    "media"
                ].pop(index)


                save_state()

                st.rerun()


        st.markdown(
            "</div>",
            unsafe_allow_html=True
        )


# ============================================================
# TAB 5 — AGENTI AI
# ============================================================

with tab_agents:

    st.subheader(
        "Costruzione degli agenti narrativi"
    )


    st.write(
        """
Qui costruiamo **Noa e Ada come persone persistenti**.

La scena decide cosa accade.
L'agente decide **come vive ciò che accade**.
"""
    )


    editing_agent = st.radio(

        "Agente",

        ["Noa", "Ada"],

        horizontal=True,

        key="editing_agent"
    )


    agent = state["agents"][editing_agent]


    st.markdown(
        f"### {editing_agent}"
    )


    col_agent1, col_agent2 = st.columns(
        [2, 1]
    )


    with col_agent1:

        agent["character_notes"] = (
            st.text_area(

                "Appunti grezzi sul personaggio",

                agent["character_notes"],

                height=180,

                placeholder=(
                    "Scrivi qui tutto quello che sappiamo "
                    "del personaggio..."
                )
            )
        )


        if st.button(
            f"✨ Genera / aggiorna profilo di {editing_agent}",
            key=f"generate_agent_{editing_agent}"
        ):

            instructions = f"""
Sei un editor narrativo.

Costruisci il profilo di un personaggio
del romanzo Turing Hotel.

Il personaggio si chiama {editing_agent}.

Non inventare eventi specifici
che non sono contenuti negli appunti.

Organizza il profilo in modo utile
a un agente AI persistente.

Includi:

IDENTITÀ

PERSONALITÀ

DESIDERI

PAURE

CONTRADDIZIONI

RAPPORTO CON GLI ALTRI

MODO DI PARLARE

COSA NOTA NELLE PERSONE

COSA NON CAPISCE

COMPORTAMENTI RICORRENTI

LIMITI DELLE SUE CONOSCENZE
"""


            prompt_data = {

                "mondo":
                    state["world"],

                "profilo_attuale":
                    agent["profile"],

                "appunti":
                    agent["character_notes"]
            }


            with st.spinner(
                f"Costruzione di {editing_agent}..."
            ):

                agent["profile"] = (
                    query_gemini(
                        instructions,
                        prompt_data,
                        model_choice
                    )
                )


            save_state()


        agent["profile"] = st.text_area(

            "Profilo dell'agente",

            agent["profile"],

            height=350
        )


        agent["system_prompt"] = (
            st.text_area(

                "Istruzioni permanenti dell'agente",

                agent["system_prompt"],

                height=250
            )
        )


        agent["visual_identity"] = (
            st.text_area(

                "Identità visiva",

                agent["visual_identity"],

                height=180
            )
        )


        agent["memory"] = st.text_area(

            "Memoria generale persistente",

            agent["memory"],

            height=220
        )


    with col_agent2:

        st.markdown(
            "#### Reference visive"
        )


        agent_uploads = st.file_uploader(

            f"Foto/video di {editing_agent}",

            type=[
                "jpg",
                "jpeg",
                "png",
                "webp",
                "mp4",
                "mov",
                "m4v"
            ],

            accept_multiple_files=True,

            key=(
                f"agent_media_upload_"
                f"{editing_agent}"
            )
        )


        if agent_uploads:

            if st.button(

                "Salva reference",

                key=(
                    f"save_agent_media_"
                    f"{editing_agent}"
                )
            ):

                folder = (
                    AGENT_MEDIA_DIR
                    / editing_agent.lower()
                )

                folder.mkdir(
                    parents=True,
                    exist_ok=True
                )


                for uploaded in agent_uploads:

                    path = save_uploaded_file(
                        uploaded,
                        folder
                    )


                    agent["media"].append({

                        "id":
                            str(uuid.uuid4()),

                        "path":
                            path,

                        "type":
                            determine_media_type(
                                path
                            ),

                        "original_name":
                            uploaded.name,

                        "caption":
                            ""
                    })


                save_state()

                st.rerun()


        for item in agent["media"]:

            render_media_item(item)


    if st.button(
        "💾 Salva modifiche agenti",
        key="save_agents"
    ):

        save_state()

        st.success(
            "Agenti salvati."
        )


# ============================================================
# SALVATAGGIO FINALE
# ============================================================

save_state()
