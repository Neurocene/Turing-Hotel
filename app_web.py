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
    min-height: 48px;
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
    font-size: 2.6rem;
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
    font-size: 3.3rem;
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

[data-testid="stChatMessage"] {
    background: #13181c;
    border: 1px solid #282f34;
    border-radius: 6px;
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

.media-title {
    color: #8f969b;
    text-transform: uppercase;
    letter-spacing: .12em;
    font-size: .72rem;
    margin-top: 1rem;
    margin-bottom: .7rem;
}

</style>
""", unsafe_allow_html=True)


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

La storia viene vissuta attraverso
Noa e Ada.
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

È una donna italiana
poco più che trentenne.

È cresciuta intorno al Turing Hotel
e ora lo gestisce insieme al padre.

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
# BASIC UTILS
# ============================================================

def safe_list(value):
    return value if isinstance(value, list) else []


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def number_from_filename(filename):

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
        key=lambda path: (
            number_from_filename(path.name),
            path.name.lower()
        )
    )


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
# FILE DEL PERSONAGGIO
# ============================================================

def load_character_sources(
    character
):

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

        filename = path.name.lower()

        if (
            filename.startswith(prefix)
            or
            filename.startswith("shared")
        ):

            selected.append(
                path
            )

    selected = sorted(
        selected,
        key=lambda p: p.name.lower()
    )

    results = []

    MAX_TOTAL_CHARS = 80000

    used = 0

    for path in selected:

        text = read_reference_file(
            path
        )

        if not text:
            continue

        remaining = (
            MAX_TOTAL_CHARS
            - used
        )

        if remaining <= 0:
            break

        excerpt = text[
            :remaining
        ]

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
# LIBRI DELL'AGENTE SCRITTORE
# ============================================================

def load_writer_books():

    books = []

    if not ASSETS_DIR.exists():
        return []

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

        content = read_reference_file(
            path
        )

        if content:

            books.append(
                (
                    path.name,
                    content
                )
            )

    books = sorted(
        books,
        key=lambda item:
        number_from_filename(
            item[0]
        )
    )

    result = []

    MAX_TOTAL_CHARS = 30000

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
# MIGRAZIONE
# ============================================================

def find_old_scene(
    old_scenes,
    new_id
):

    if not isinstance(
        old_scenes,
        list
    ):
        return None

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

        if old_id == new_id:
            return old_scene

    keywords = {

        "hall": [
            "hall"
        ],

        "funerale": [
            "funerale"
        ],

        "matrimonio": [
            "matrimonio"
        ],

        "nascite": [
            "nascite",
            "reparto nascite"
        ],

        "ritorno": [
            "ritorno"
        ]
    }

    for old_scene in old_scenes:

        if not isinstance(
            old_scene,
            dict
        ):
            continue

        title = str(
            old_scene.get(
                "title",
                ""
            )
        ).lower()

        for keyword in keywords[
            new_id
        ]:

            if keyword in title:
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

    messages = old_scene.get(
        "messages",
        []
    )

    if isinstance(
        messages,
        dict
    ):

        result["Noa"] = safe_list(
            messages.get(
                "Noa",
                []
            )
        )

        result["Ada"] = safe_list(
            messages.get(
                "Ada",
                []
            )
        )

        return result

    if isinstance(
        messages,
        list
    ):

        old_agent = old_scene.get(
            "agent",
            "Noa"
        )

        if old_agent == "Ada":

            result["Ada"] = messages

        else:

            result["Noa"] = messages

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

    for person in [
        "Noa",
        "Ada"
    ]:

        old_agent = safe_dict(
            old_agents.get(
                person,
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
            ][person][
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
            ][person][
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

        old_scene = find_old_scene(
            old_scenes,
            new_scene["id"]
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

        if new_scene[
            "id"
        ] == "ritorno":

            decision = safe_dict(
                old_scene.get(
                    "decision",
                    {}
                )
            )

            new_scene[
                "decision"
            ]["Noa"] = str(
                decision.get(
                    "Noa",
                    ""
                )
            )

            new_scene[
                "decision"
            ]["Ada"] = str(
                decision.get(
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


# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "entrance"

if "pov" not in st.session_state:
    st.session_state.pov = None

if "scene_index" not in st.session_state:
    st.session_state.scene_index = 0


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
# PULIZIA RISPOSTA PERSONAGGIO
# ============================================================

def clean_character_response(
    raw_response
):

    """
    L'interfaccia deve mostrare solo
    ciò che il personaggio dice/fa.

    Se il modello restituisce:
    {
        "dialogue": "...",
        "inner_note": "...",
        ...
    }

    mostriamo soltanto dialogue.
    """

    if not raw_response:

        return ""

    text = str(
        raw_response
    ).strip()

    # elimina eventuali code fence

    if text.startswith("```"):

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
        )

        text = text.strip()

    # prova JSON completo

    try:

        data = json.loads(
            text
        )

        if isinstance(
            data,
            dict
        ):

            # ordine di preferenza

            for key in [
                "dialogue",
                "dialogo",
                "response",
                "reply",
                "text",
                "answer",
                "azione",
                "action"
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

    # Se il testo contiene un JSON preceduto
    # o seguito da altro, proviamo a recuperarlo.

    json_match = re.search(
        r"\{.*\}",
        text,
        flags=re.DOTALL
    )

    if json_match:

        try:

            data = json.loads(
                json_match.group(0)
            )

            if isinstance(
                data,
                dict
            ):

                for key in [
                    "dialogue",
                    "dialogo",
                    "response",
                    "reply",
                    "text",
                    "answer",
                    "azione",
                    "action"
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

    # altrimenti restituisce il testo
    # così com'è

    return text


# ============================================================
# RICORDI PRECEDENTI
# ============================================================

def get_previous_memories(
    current_scene_id,
    pov
):

    order = [
        "hall",
        "funerale",
        "matrimonio",
        "nascite",
        "ritorno"
    ]

    memories = []

    for scene_id in order:

        if scene_id == current_scene_id:
            break

        scene = next(
            (
                s
                for s in state[
                    "scenes"
                ]
                if s["id"] == scene_id
            ),
            None
        )

        if not scene:
            continue

        diary = safe_dict(
            scene.get(
                "diary",
                {}
            )
        )

        memory = diary.get(
            pov,
            ""
        )

        if memory:

            memories.append({

                "scena":
                    scene["title"],

                "ricordo":
                    memory
            })

    return memories


# ============================================================
# PROMPT PERSONAGGIO
# ============================================================

def character_prompt(
    character,
    scene
):

    agent = state[
        "agents"
    ][character]

    return f"""
SEI {character}.

Sei un personaggio del romanzo
TURING HOTEL.

NON sei un assistente.

================================
REGOLA PRINCIPALE
================================

Devi lavorare esclusivamente
con i dati che possiedi.

Puoi utilizzare:

1. i file del personaggio;
2. i file condivisi;
3. il tuo profilo;
4. i ricordi delle scene precedenti;
5. la conversazione corrente.

Se non possiedi un'informazione,
non inventarla come fatto.

Puoi:

- non sapere;
- dubitare;
- sospettare;
- fare un'ipotesi;
- ricordare male;
- fraintendere.

================================
MONDO
================================

{state["world"]}

================================
PROFILO
================================

{agent["profile"]}

================================
MEMORIA GENERALE
================================

{agent["memory"]}

================================
COMPORTAMENTO
================================

Interpreta soltanto {character}.

Non raccontare ciò che
gli altri personaggi pensano.

Non scrivere le battute
degli altri personaggi.

Non anticipare eventi futuri.

Non spiegare la teoria.

Non fare analisi psicologiche
della tua risposta.

Non spiegare le tue intenzioni.

Non fornire statistiche emotive.

Non produrre valori numerici
di fiducia, paura, sospetto,
vulnerabilità o altri stati.

NON restituire JSON.

NON restituire dizionari.

NON usare campi come:

dialogue
inner_note
intention
state
memory_candidate
bio_refs
trust
suspicion
vulnerability
defiance

Questi dati NON DEVONO MAI
comparire nella risposta visibile.

================================
FORMATO OBBLIGATORIO
================================

La risposta deve contenere
SOLTANTO ciò che {character}
dice oppure fa nella scena.

Può essere:

una battuta:

Non ne sono sicura.

oppure una breve azione narrativa:

Noa guarda Ada per qualche secondo,
poi distoglie lo sguardo.

oppure entrambe:

Noa abbassa la voce.
«Non ne sono sicura.»

NESSUNA spiegazione aggiuntiva.

NESSUN JSON.

NESSUNA nota interna.

NESSUNA intestazione.

NESSUNA analisi.

================================
STILE
================================

Comportati come una persona
presente nella scena.

Non dire automaticamente tutto
ciò che sai.

Una persona reale seleziona
ciò che è rilevante
in quel momento.

Se ti viene chiesto:
"Conosci Ada?"

non devi elencare tutta
la biografia di Ada.

Rispondi alla domanda
come risponderebbe {character}
in una conversazione reale.

Usa i dati per essere coerente,
non per mostrarli tutti.

Le informazioni devono emergere
solo quando sono pertinenti.

Scrivi in italiano naturale,
contemporaneo e credibile.
"""


# ============================================================
# RISPOSTA PERSONAGGIO
# ============================================================

def answer_as_character(
    character,
    scene
):

    sources = load_character_sources(
        character
    )

    memories = get_previous_memories(
        scene["id"],
        character
    )

    raw_response = query_openai(

        character_prompt(
            character,
            scene
        ),

        {
            "PERSONAGGIO":
                character,

            "SCENA":
                scene["title"],

            "DATI_PERSONAGGIO":
                sources,

            "RICORDI_PRECEDENTI":
                memories,

            "CONVERSAZIONE_CORRENTE":
                scene[
                    "messages"
                ][character],

            "ISTRUZIONE_FINALE":
                (
                    "Rispondi soltanto come "
                    + character
                    + ". Mostra esclusivamente "
                    "ciò che dici o fai."
                )
        }
    )

    return clean_character_response(
        raw_response
    )


# ============================================================
# CREA RICORDO
# ============================================================

def create_scene_memory(
    scene,
    pov,
    extra_event=""
):

    books = load_writer_books()

    sources = load_character_sources(
        pov
    )

    previous_memories = (
        get_previous_memories(
            scene["id"],
            pov
        )
    )

    instructions = """
Sei l'agente scrittore
del romanzo Turing Hotel.

Devi creare il RICORDO
di ciò che il personaggio
ha vissuto nella scena.

Il ricordo non è
un riassunto tecnico.

È memoria autobiografica.

Puoi usare soltanto
le informazioni fornite.

Non aggiungere fatti.

Non aggiungere eventi.

Non trasformare ipotesi
in certezze.

Scrivi in prima persona.

Conserva ciò che può
avere conseguenze future:

- eventi;
- persone;
- emozioni;
- dubbi;
- desideri;
- paure;
- promesse;
- conflitti;
- cambiamenti nei rapporti;
- decisioni.

I libri servono soltanto
come riferimento
per ritmo e tecnica narrativa.

Non copiarli.
Non citarli.
"""

    data = {

        "PERSONAGGIO":
            pov,

        "SCENA":
            scene["title"],

        "DATI_PERSONAGGIO":
            sources,

        "RICORDI_PRECEDENTI":
            previous_memories,

        "CONVERSAZIONE":
            scene[
                "messages"
            ][pov],

        "EVENTO_AGGIUNTIVO":
            extra_event,

        "RIFERIMENTI":
            books
    }

    return query_openai(
        instructions,
        data
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


def character_videos(
    character
):

    character = character.lower()

    results = []

    patterns = [

        rf"^{character}\.video(\d+)\.mp4$",

        rf"^{character}\.video\.(\d+)\.mp4$",

        rf"^{character}_video(\d+)\.mp4$"
    ]

    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue

        name = path.name.lower()

        for pattern in patterns:

            if re.match(
                pattern,
                name
            ):

                results.append(
                    path
                )

                break

    return sorted_assets(
        results
    )


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

        if scene_id == "hall":

            patterns = [

                r"^hall\d+\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$",

                r"^hall\.video\d+\.(mp4|mov|webm|m4v)$",

                rf"^hall\.{pov}\.\d+\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$"
            ]

        elif scene_id == "funerale":

            patterns = [

                rf"^funerale\.{pov}\.\d+\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$"
            ]

        elif scene_id == "matrimonio":

            patterns = [

                rf"^matrimonio\.{pov}\.\d+\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$"
            ]

        elif scene_id == "nascite":

            patterns = [

                rf"^nascite\.{pov}\.\d+\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$",

                rf"^reparto\.nascite\.{pov}\.\d+\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$"
            ]

        else:

            patterns = [

                rf"^ritorno\.{pov}\.\d+\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$"
            ]

        for pattern in patterns:

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
            "Carica assets/TuringHotel.jpg"
        )

    st.write("")

    col1, col2, col3 = st.columns(
        [2, 1.4, 2]
    )

    with col2:

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

    col_noa, gap, col_ada = st.columns(
        [1, .08, 1]
    )

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
            key="choose_noa"
        ):

            st.session_state.pov = "Noa"
            st.session_state.scene_index = 0
            st.session_state.page = "story"

            st.rerun()

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
            key="choose_ada"
        ):

            st.session_state.pov = "Ada"
            st.session_state.scene_index = 0
            st.session_state.page = "story"

            st.rerun()


# ============================================================
# RESET
# ============================================================

def reset_scene_chat(
    scene,
    pov
):

    scene[
        "messages"
    ][pov] = []

    scene[
        "diary"
    ][pov] = ""

    if scene[
        "id"
    ] == "ritorno":

        scene[
            "decision"
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

        with st.chat_message(
            "assistant"
            if speaker == pov
            else "user"
        ):

            st.markdown(
                f"**{speaker}**"
            )

            st.write(
                text
            )

    clear_col, blank = st.columns(
        [1.3, 3]
    )

    with clear_col:

        if st.button(
            "🗑 CANCELLA CONVERSAZIONE",
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

        key=(
            f"speaker_"
            f"{scene['id']}_"
            f"{pov}"
        )
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

        with st.spinner(
            f"{pov} sta reagendo..."
        ):

            reply = answer_as_character(
                pov,
                scene
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
# FOTO
# ============================================================

def render_photo_gallery(
    images
):

    if not images:
        return

    for start in range(
        0,
        len(images),
        3
    ):

        group = images[
            start:start + 3
        ]

        cols = st.columns(
            len(group)
        )

        for index, image in enumerate(
            group
        ):

            with cols[index]:

                st.image(
                    str(image),
                    use_container_width=True
                )


# ============================================================
# RICORDO
# ============================================================

def render_memory_button(
    scene,
    pov,
    extra_event=""
):

    st.markdown("---")

    if st.button(
        "CREA RICORDO SCENA",
        key=(
            f"memory_"
            f"{scene['id']}_"
            f"{pov}"
        )
    ):

        if (
            not scene[
                "messages"
            ][pov]
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

            st.rerun()

    memory = scene[
        "diary"
    ][pov]

    if memory:

        with st.expander(
            "RICORDO DELLA SCENA"
        ):

            st.markdown(
                f'<div class="diary">'
                f'{memory}'
                f'</div>',
                unsafe_allow_html=True
            )


# ============================================================
# SCENA
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

    videos = find_scene_assets(
        scene["id"],
        pov,
        "video"
    )

    for video in videos:

        st.video(
            str(video)
        )

    render_chat(
        scene,
        pov
    )

    images = find_scene_assets(
        scene["id"],
        pov,
        "image"
    )

    if images:

        st.markdown("---")

        render_photo_gallery(
            images
        )

    render_memory_button(
        scene,
        pov
    )


# ============================================================
# IL RITORNO
# ============================================================

def render_return():

    pov = st.session_state.pov

    scene = next(
        scene
        for scene in state[
            "scenes"
        ]
        if scene[
            "id"
        ] == "ritorno"
    )

    st.markdown(
        '<div class="scene-number">'
        'Sequenza 5'
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

    memories = get_previous_memories(
        "ritorno",
        pov
    )

    st.markdown(
        """
<div class="return-box">

Nel ritorno il personaggio
decide sulla base di ciò
che ha realmente vissuto.

</div>
""",
        unsafe_allow_html=True
    )

    if memories:

        with st.expander(
            "RICORDI DELLE SCENE PRECEDENTI"
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

    if st.button(
        f"LASCIA DECIDERE {pov.upper()}",
        type="primary"
    ):

        if not memories:

            st.warning(
                "Non esistono ancora "
                "ricordi sufficienti."
            )

        else:

            sources = load_character_sources(
                pov
            )

            raw_decision = query_openai(

                character_prompt(
                    pov,
                    scene
                )
                +
                """

Questa è la scena del ritorno.

Decidi autonomamente
cosa fai.

Usa soltanto
i dati e i ricordi disponibili.

Non inventare fatti.

Non spiegare
come sei arrivata alla decisione.

Non produrre JSON.

Mostra soltanto
ciò che fai o dici.
""",

                {
                    "DATI_PERSONAGGIO":
                        sources,

                    "RICORDI":
                        memories,

                    "SCENA":
                        "Il ritorno"
                }
            )

            scene[
                "decision"
            ][pov] = (
                clean_character_response(
                    raw_decision
                )
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

        st.markdown("---")

        st.markdown(
            decision
        )

    images = find_scene_assets(
        "ritorno",
        pov,
        "image"
    )

    if images:

        st.markdown("---")

        render_photo_gallery(
            images
        )

    render_memory_button(
        scene,
        pov,
        decision
    )


# ============================================================
# NAVIGAZIONE
# ============================================================

def page_story():

    pov = st.session_state.pov

    if not pov:

        st.session_state.page = (
            "characters"
        )

        st.rerun()

    order = [
        "hall",
        "funerale",
        "matrimonio",
        "nascite",
        "ritorno"
    ]

    titles = {

        "hall":
            "La Hall",

        "funerale":
            "Il Funerale",

        "matrimonio":
            "Il Matrimonio",

        "nascite":
            "Il reparto nascite",

        "ritorno":
            "Il ritorno"
    }

    scene_map = {

        scene["id"]:
            scene

        for scene in state[
            "scenes"
        ]
    }

    index = min(
        st.session_state.scene_index,
        len(order) - 1
    )

    st.session_state.scene_index = (
        index
    )

    scene_id = order[
        index
    ]

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
        order
    ):

        prefix = (
            "● "
            if i == index
            else ""
        )

        if st.sidebar.button(
            prefix
            + titles[sid],
            key=f"nav_{sid}"
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
                "Nessun file personaggio trovato."
            )

        for source in sources:

            st.write(
                source["file"]
            )

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

    if scene_id == "ritorno":

        render_return()

    else:

        render_standard_scene(
            scene_map[
                scene_id
            ],
            index
        )

    st.markdown("---")

    previous_col, middle, next_col = (
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
            order
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
