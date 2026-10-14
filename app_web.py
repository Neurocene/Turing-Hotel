
import streamlit as st
import json
import os
import re
import copy
import shutil
from pathlib import Path
from io import BytesIO
from datetime import datetime, timezone
from html import escape

from openai import OpenAI


# ============================================================
# TURING HOTEL — OFFICINA DEL ROMANZO
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
BACKUP_FILE = DATA_DIR / "romanzo_web_backup.json"

HOTEL_IMAGE = ASSETS_DIR / "TuringHotel.jpg"
NOA_IMAGE = ASSETS_DIR / "Noa.jpg"
ADA_IMAGE = ASSETS_DIR / "Ada.jpg"

for folder in [ASSETS_DIR, CHARACTERS_DIR, DATA_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

CHARACTERS = ["Noa", "Ada"]


# ============================================================
# OPENAI
# ============================================================

def get_setting(name, default=None):
    try:
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass

    return os.environ.get(name, default)


OPENAI_KEY = get_setting("OPENAI_API_KEY")
OPENAI_MODEL = get_setting("OPENAI_MODEL", "gpt-5.6")

client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None


def query_openai(instructions, data):
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


def is_error(text):
    return (
        not isinstance(text, str)
        or not text.strip()
        or text.startswith("Errore OpenAI:")
        or text.startswith("OPENAI_API_KEY non configurata.")
    )


def clean_response(raw):
    text = str(raw or "").strip()

    text = re.sub(
        r"^```(?:json|text|markdown)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(r"\s*```$", "", text).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in [
                "dialogue", "dialogo", "text",
                "reply", "response", "action",
                "reflection"
            ]:
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    except (ValueError, TypeError):
        pass

    return text


def now_iso():
    return datetime.now(timezone.utc).isoformat()


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
    min-height: 42px;
    border: 1px solid #5b6266;
    border-radius: 4px;
}
div.stButton > button[kind="primary"] {
    background: #786449;
    color: white;
}
.scene-number {
    color: #999fa4;
    letter-spacing: .18em;
    font-size: .75rem;
}
.scene-title {
    font-family: Georgia, serif;
    font-size: 3rem;
    line-height: 1.1;
    margin-bottom: .5rem;
}
.pov-label {
    color: #b79c72;
    letter-spacing: .15em;
    font-size: .8rem;
    margin-bottom: 1rem;
}
.narrative-text {
    font-family: Georgia, serif;
    font-size: 1.05rem;
    line-height: 1.8;
    padding: 22px;
    background: #111518;
    border-left: 3px solid #9b805c;
    white-space: pre-wrap;
}
.message {
    background: #151b20;
    border-left: 2px solid #66747c;
    padding: 12px 15px;
    margin: 8px 0;
    white-space: pre-wrap;
}
.inner-message {
    background: #1c1818;
    border-left: 2px solid #b09470;
    padding: 12px 15px;
    margin: 8px 0;
    font-family: Georgia, serif;
    white-space: pre-wrap;
}
.small-label {
    color: #a6a9aa;
    text-transform: uppercase;
    letter-spacing: .12em;
    font-size: .72rem;
    margin-bottom: 5px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# STRUTTURA DEL ROMANZO
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
    "stanza": ["stanza", "camera", "la stanza"],
    "funerale": ["funerale"],
    "matrimonio": ["matrimonio"],
    "reparto_nascite": [
        "repartonascite",
        "reparto nascite",
        "reparto_nascite",
        "reparto-nascite",
        "nascite"
    ],
    "ritorno": ["ritorno", "finale", "final"]
}


# ============================================================
# UTILITÀ
# ============================================================

def safe_dict(value):
    return value if isinstance(value, dict) else {}


def safe_list(value):
    return value if isinstance(value, list) else []


def normalize_name(value):
    return re.sub(
        r"[\s._\\-]+",
        "",
        str(value).lower().strip()
    )


def file_number(filename):
    match = re.search(r"(\d+)$", Path(filename).stem)
    return int(match.group(1)) if match else 0


# ============================================================
# MEDIA
# ============================================================

def parse_scene_media(path, scene_id):
    if not path.is_file():
        return None

    if path.suffix.lower() not in MEDIA_EXTENSIONS:
        return None

    name = normalize_name(path.stem)

    aliases = sorted(
        {normalize_name(a) for a in SCENE_ALIASES[scene_id]},
        key=len,
        reverse=True
    )

    for alias in aliases:
        if name == alias:
            return ("cover", 0)

        if not name.startswith(alias):
            continue

        suffix = name[len(alias):]

        if suffix in ("noa", "ada"):
            return ("cover_" + suffix, 0)

        for character in ("noa", "ada"):
            if suffix.startswith(character):
                number = suffix[len(character):]
                if number.isdigit():
                    return (character, int(number))

        if suffix.isdigit():
            return ("shared", int(suffix))

    return None


def scene_media(scene_id, pov, media_kind):
    results = []

    for path in ASSETS_DIR.iterdir():
        parsed = parse_scene_media(path, scene_id)

        if not parsed:
            continue

        role, number = parsed

        if media_kind == "cover":
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            if role == "cover_" + pov.lower():
                results.append((0, path))
            elif role == "cover":
                results.append((1, path))

        else:
            if role not in ("shared", pov.lower()):
                continue

            allowed = (
                IMAGE_EXTENSIONS
                if media_kind == "image"
                else VIDEO_EXTENSIONS
            )

            if path.suffix.lower() in allowed:
                results.append((number, path))

    results.sort(
        key=lambda item: (item[0], item[1].name.lower())
    )

    return [path for _, path in results]


def character_intro_videos(character):
    results = []

    for path in ASSETS_DIR.iterdir():
        if not path.is_file():
            continue

        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        compact = normalize_name(path.stem)

        if re.match(
            rf"^{character.lower()}video\d+$",
            compact
        ):
            results.append(path)

    return sorted(results, key=lambda x: file_number(x.name))


# ============================================================
# FILE DI RIFERIMENTO
# ============================================================

def read_reference_file(path):
    suffix = path.suffix.lower()

    if suffix in (".txt", ".md"):
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
            return "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )
        except Exception:
            return ""

    return ""


def load_turing_context():
    for path in ASSETS_DIR.iterdir():
        if not path.is_file():
            continue

        if path.suffix.lower() not in (".txt", ".md"):
            continue

        if normalize_name(path.stem) == "contestoturinghotel":
            return read_reference_file(path)

    root = BASE_DIR / "TURING_HOTEL_CONTESTO_AGENTE.md"

    if root.exists():
        return read_reference_file(root)

    return ""


def load_character_sources(character):
    results = []
    used = 0
    max_chars = 80000

    for path in sorted(CHARACTERS_DIR.iterdir()):
        if not path.is_file():
            continue

        if path.suffix.lower() not in (".txt", ".md", ".pdf"):
            continue

        name = path.name.lower()

        if not (
            name.startswith(character.lower())
            or name.startswith("shared")
        ):
            continue

        content = read_reference_file(path)
        remaining = max_chars - used

        if remaining <= 0:
            break

        excerpt = content[:remaining]

        if excerpt:
            results.append({
                "file": path.name,
                "contenuto": excerpt
            })
            used += len(excerpt)

    return results


def load_writer_books():
    results = []

    for path in ASSETS_DIR.iterdir():
        if not path.is_file():
            continue

        if path.suffix.lower() not in (".txt", ".md", ".pdf"):
            continue

        if not normalize_name(path.stem).startswith("libriagenti"):
            continue

        content = read_reference_file(path)

        if content:
            results.append({
                "file": path.name,
                "testo": content[:20000]
            })

    return sorted(
        results,
        key=lambda item: file_number(item["file"])
    )


# ============================================================
# STRUTTURA DELLA MEMORIA NARRATIVA
# ============================================================

def empty_narrative():
    return {
        "A": "",
        "B": "",
        "feedback": "",
        "recommended": "",
        "review": "",
        "draft": "",
        "approved": "",
        "status": "da_scrivere",
        "approved_at": "",
        "history": [],
        "revision": 0
    }


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
        },
        "narrative": {
            "Noa": empty_narrative(),
            "Ada": empty_narrative()
        }
    }

    if scene_id == "stanza":
        scene["author_context"] = (
            "Ada accompagna Noa nella stanza del Turing Hotel. "
            "Nel percorso di Ada la scena presenta il dialogo "
            "tra Ada e Noa. Nel percorso di Noa, dopo l'incontro, "
            "Noa rimane sola davanti allo specchio e riflette. "
            "Non anticipare avvenimenti della scena successiva."
        )
        scene["approved_context"] = scene["author_context"]

    if scene_id == "ritorno":
        scene["decision"] = {
            "Noa": "",
            "Ada": ""
        }

    return scene


DEFAULT_STATE = {
    "world": (
        "Il Turing Hotel è un antico albergo sul mare Adriatico. "
        "La storia può essere vissuta dal punto di vista di Noa "
        "oppure dal punto di vista di Ada."
    ),
    "agents": {
        "Noa": {
            "profile": (
                "Noa è un agente artificiale relazionale. "
                "Sa di essere artificiale. È stata progettata "
                "per comprendere gli esseri umani, creare empatia "
                "e farli stare bene. È intelligente, osservatrice, "
                "ironica e capace di seduzione."
            ),
            "memory": ""
        },
        "Ada": {
            "profile": (
                "Ada è la figlia del professor Elia. "
                "È cresciuta nel Turing Hotel. "
                "È intelligente, pratica, riservata e osservatrice."
            ),
            "memory": ""
        }
    },
    "scenes": [
        empty_scene(scene_id, SCENE_TITLES[scene_id])
        for scene_id in SCENE_ORDER
    ]
}


# ============================================================
# MIGRAZIONE DEI VECCHI DATI
# ============================================================

def find_existing_scene(old_scenes, scene_id):
    aliases = {
        normalize_name(x)
        for x in SCENE_ALIASES[scene_id]
    }
    aliases.add(normalize_name(scene_id))

    for scene in safe_list(old_scenes):
        if not isinstance(scene, dict):
            continue

        old_id = normalize_name(scene.get("id", ""))
        old_title = normalize_name(scene.get("title", ""))

        if old_id in aliases or old_title in aliases:
            return scene

    return None


def migrate_state(old_state):
    fresh = copy.deepcopy(DEFAULT_STATE)

    if not isinstance(old_state, dict):
        return fresh

    if isinstance(old_state.get("world"), str):
        fresh["world"] = old_state["world"]

    old_agents = safe_dict(old_state.get("agents"))

    for character in CHARACTERS:
        old_agent = safe_dict(old_agents.get(character))

        for field in ("profile", "memory"):
            if isinstance(old_agent.get(field), str):
                fresh["agents"][character][field] = old_agent[field]

    for new_scene in fresh["scenes"]:
        old_scene = find_existing_scene(
            old_state.get("scenes"),
            new_scene["id"]
        )

        if not old_scene:
            continue

        for field in [
            "author_context",
            "story_draft",
            "story_feedback",
            "approved_context"
        ]:
            if isinstance(old_scene.get(field), str):
                new_scene[field] = old_scene[field]

        new_scene["shared_dialogue"] = copy.deepcopy(
            safe_list(old_scene.get("shared_dialogue"))
        )

        new_scene["advisor_messages"] = copy.deepcopy(
            safe_list(old_scene.get("advisor_messages"))
        )

        for character in CHARACTERS:
            new_scene["messages"][character] = copy.deepcopy(
                safe_list(
                    safe_dict(old_scene.get("messages")).get(character)
                )
            )

            old_diary = str(
                safe_dict(old_scene.get("diary")).get(character, "")
            )

            new_scene["diary"][character] = old_diary

            old_narrative = safe_dict(
                safe_dict(old_scene.get("narrative")).get(character)
            )

            target = new_scene["narrative"][character]

            for key in target:
                if key in old_narrative:
                    target[key] = copy.deepcopy(old_narrative[key])

            if not old_narrative and old_diary.strip():
                target["draft"] = old_diary
                target["status"] = "bozza_legacy"

        if new_scene["id"] == "ritorno":
            old_decision = safe_dict(
                old_scene.get("decision")
            )

            for character in CHARACTERS:
                new_scene["decision"][character] = str(
                    old_decision.get(character, "")
                )

    return fresh


def load_state():
    if not DATA_FILE.exists():
        return copy.deepcopy(DEFAULT_STATE)

    if not BACKUP_FILE.exists():
        shutil.copy2(DATA_FILE, BACKUP_FILE)

    try:
        old_state = json.loads(
            DATA_FILE.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as error:
        st.error(f"Errore caricamento archivio: {error}")
        st.stop()

    return migrate_state(old_state)


if "state" not in st.session_state:
    st.session_state.state = load_state()

state = st.session_state.state

if "page" not in st.session_state:
    st.session_state.page = "entrance"

if "pov" not in st.session_state:
    st.session_state.pov = None

if "scene_index" not in st.session_state:
    st.session_state.scene_index = 0


def save_state():
    temporary = DATA_DIR / "romanzo_web.tmp"

    temporary.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    os.replace(temporary, DATA_FILE)


# ============================================================
# ACCESSO ALLE SCENE
# ============================================================

def scene_by_id(scene_id):
    return next(
        scene for scene in state["scenes"]
        if scene["id"] == scene_id
    )


def narrative_record(scene, pov):
    return scene["narrative"][pov]


# ============================================================
# MEMORIE CANONICHE INDIPENDENTI
# ============================================================

def get_previous_memories(current_scene_id, pov):
    memories = []

    for scene_id in SCENE_ORDER:
        if scene_id == current_scene_id:
            break

        scene = scene_by_id(scene_id)
        record = narrative_record(scene, pov)

        approved = record.get("approved", "")

        if approved.strip():
            memories.append({
                "scena": scene["title"],
                "ricordo": approved
            })

    return memories


def get_all_previous_memories(scene_id):
    return {
        "Noa": get_previous_memories(scene_id, "Noa"),
        "Ada": get_previous_memories(scene_id, "Ada")
    }


def later_approved_scenes(scene_id, pov):
    current_index = SCENE_ORDER.index(scene_id)
    results = []

    for next_id in SCENE_ORDER[current_index + 1:]:
        scene = scene_by_id(next_id)

        if narrative_record(scene, pov)["approved"].strip():
            results.append(scene["title"])

    return results


# ============================================================
# CREATORE DELLA SCENA
# ============================================================

def generate_story_context(scene):
    instructions = """
Sei il CREATORE DELLA SCENA del romanzo Turing Hotel.

Trasforma le indicazioni dell'autore in un contesto
narrativo oggettivo per Noa e Ada.

Il documento CONTESTO_TURING_HOTEL è la base canonica.

Puoi definire:
- luogo;
- atmosfera;
- circostanze;
- persone presenti;
- fatti oggettivi;
- oggetti;
- informazioni pubbliche;
- tensioni già presenti.

Non decidere:
- cosa pensa Noa;
- cosa pensa Ada;
- cosa provano;
- cosa desiderano;
- come reagiscono.

Non aggiungere eventi fondamentali non suggeriti.

Restituisci soltanto il contesto.
"""

    return query_openai(
        instructions,
        {
            "CANONE": load_turing_context(),
            "SCENA": scene["title"],
            "INDICAZIONI_AUTORE": scene["author_context"],
            "BOZZA": scene["story_draft"],
            "CORREZIONI": scene["story_feedback"]
        }
    )


def refine_story_context(scene):
    instructions = """
Sei l'AGENTE SCRITTORE del romanzo Turing Hotel.

Rifinisci la qualità narrativa del contesto.

Intervieni su:
- ritmo;
- atmosfera;
- fluidità;
- tensione;
- immagini;
- precisione sensoriale.

Non modificare i fatti.
Non decidere le reazioni dei personaggi.

Usa LIBRIAGENTI come riferimento tecnico,
senza copiarne i testi.

Restituisci soltanto il contesto rifinito.
"""

    return query_openai(
        instructions,
        {
            "CANONE": load_turing_context(),
            "SCENA": scene["title"],
            "TESTO": scene["story_draft"],
            "LIBRIAGENTI": load_writer_books()
        }
    )


# ============================================================
# CONSULENTE NARRATIVO
# ============================================================

def ask_narrative_advisor(scene):
    instructions = """
Sei il CONSULENTE NARRATIVO di Turing Hotel.

Parli con l'autore, non interpreti Noa o Ada.

Puoi:
- controllare la coerenza;
- proporre soluzioni;
- individuare problemi;
- suggerire alternative;
- ragionare sul sottotesto;
- discutere la struttura del romanzo.

Quando presenti più alternative,
DEVI esprimere una preferenza motivata.

Non limitarti a dire che tutte sono valide.

Specifica:
1. quale soluzione preferisci;
2. perché;
3. quali rischi presenta;
4. quando sceglieresti un'alternativa.

Distingui sempre fatti canonici da ipotesi.

Non modificare nulla senza l'autore.

Non usare LIBRIAGENTI.
Rispondi in italiano.
"""

    return query_openai(
        instructions,
        {
            "CANONE": load_turing_context(),
            "SCENA": scene["title"],
            "CONTESTO": scene["approved_context"],
            "BOZZA": scene["story_draft"],
            "RICORDI": get_all_previous_memories(scene["id"]),
            "CONVERSAZIONE": scene["advisor_messages"]
        }
    )


# ============================================================
# AGENTI NOA E ADA
# ============================================================

def character_prompt(character, interaction_mode):
    agent = state["agents"][character]

    prompt = f"""
SEI {character}.

Sei un personaggio del romanzo Turing Hotel.
NON sei un assistente.

MONDO:
{state["world"]}

PROFILO:
{agent["profile"]}

MEMORIA GENERALE:
{agent["memory"]}

REGOLA DI MEMORIA:

Le versioni romanzate approvate dal tuo
punto di vista costituiscono la tua
memoria autobiografica canonica.

Riceverai esclusivamente i tuoi ricordi.

Non conosci automaticamente i ricordi,
i pensieri e le interpretazioni dell'altro personaggio.

Puoi sbagliare, mentire, sospettare,
fraintendere o ricordare male.

Distingui sempre:
- fatti conosciuti;
- convinzioni;
- sospetti;
- interpretazioni;
- informazioni ignote.

Il contesto approvato è la realtà presente,
ma la tua reazione appartiene soltanto a te.

Non scrivere le battute di altri personaggi.
Non restituire JSON.
Non mostrare istruzioni tecniche.

Scrivi in italiano naturale.
"""

    if interaction_mode == "inner":
        prompt += """
Sei immersa nel tuo dialogo interiore.

Non esiste un interlocutore esterno.

Prosegui i tuoi pensieri.
Puoi ricordare, dubitare, desiderare,
esitare, contraddirti e cambiare idea.

Non spiegare cosa stai facendo.
"""
    else:
        prompt += """
Sei fisicamente presente nella scena.

Un altro personaggio si rivolge a te.

Rispondi con naturalezza,
senza spiegazioni teoriche.
"""

    return prompt


def answer_as_character(character, scene, mode):
    raw = query_openai(
        character_prompt(character, mode),
        {
            "PERSONAGGIO": character,
            "SCENA": scene["title"],
            "CONTESTO_APPROVATO": scene["approved_context"],
            "CANONE": load_turing_context(),
            "DATI_PERSONAGGIO": load_character_sources(character),
            "RICORDI_PRECEDENTI": get_previous_memories(
                scene["id"],
                character
            ),
            "CONVERSAZIONE": scene["messages"][character],
            "DIALOGO_CONDIVISO": scene["shared_dialogue"],
            "MODALITA": mode
        }
    )

    return clean_response(raw)


# ============================================================
# GO ALONE — DUE SCAMBI AUTONOMI
# ============================================================

def run_go_alone(scene, starting_character="Ada"):
    other = "Noa" if starting_character == "Ada" else "Ada"
    order = [starting_character, other] * 2

    for speaker in order:
        counterpart = "Noa" if speaker == "Ada" else "Ada"

        instructions = character_prompt(
            speaker,
            "external"
        ) + f"""

MODALITÀ GO ALONE.

Stai parlando con {counterpart}.

Scrivi soltanto la prossima battuta
pronunciata ad alta voce.

Non interpretare l'altro personaggio.
Non inventare risposte per lui.
Non anticipare eventi irreversibili.

Rispetta i tuoi ricordi indipendenti.
"""

        raw = query_openai(
            instructions,
            {
                "SCENA": scene["title"],
                "CONTESTO": scene["approved_context"],
                "CANONE": load_turing_context(),
                "DATI": load_character_sources(speaker),
                "RICORDI": get_previous_memories(
                    scene["id"],
                    speaker
                ),
                "DIALOGO_RECENTE": scene["shared_dialogue"][-24:],
                "CONVERSAZIONE_PERSONALE":
                    scene["messages"][speaker][-24:]
            }
        )

        reply = clean_response(raw)

        if is_error(reply):
            save_state()
            return False, reply

        turn = {
            "speaker": speaker,
            "text": reply,
            "kind": "external",
            "role": "response",
            "origin": "go_alone"
        }

        scene["shared_dialogue"].append(turn)

        for pov in CHARACTERS:
            scene["messages"][pov].append(copy.deepcopy(turn))

        save_state()

    return True, ""


# ============================================================
# TRASCRIZIONE SCENA
# ============================================================

def transcript_text(scene, pov):
    lines = [
        f"TURING HOTEL — {scene['title']}",
        f"Percorso di {pov}",
        "",
        "TRASCRIZIONE DELLA SCENA",
        ""
    ]

    for message in scene["messages"][pov]:
        if not isinstance(message, dict):
            continue

        speaker = message.get("speaker", "?")
        text = message.get("text", "")

        if message.get("kind") == "inner":
            speaker += " (pensiero)"

        lines.append(f"{speaker}: {text}")
        lines.append("")

    # Il dialogo condiviso è già riportato sopra
    # se prodotto da GO ALONE. Lo aggiungiamo soltanto
    # quando non è presente nella cronologia personale.
    existing = {
        (
            m.get("speaker"),
            m.get("text"),
            m.get("origin")
        )
        for m in scene["messages"][pov]
        if isinstance(m, dict)
    }

    missing_shared = [
        m for m in scene["shared_dialogue"]
        if isinstance(m, dict)
        and (
            m.get("speaker"),
            m.get("text"),
            m.get("origin")
        ) not in existing
    ]

    if missing_shared:
        lines.append("DIALOGO CONDIVISO AGGIUNTIVO")
        lines.append("")

        for message in missing_shared:
            lines.append(
                f"{message.get('speaker', '?')}: "
                f"{message.get('text', '')}"
            )

    return "\n".join(lines)


# ============================================================
# AGENTE SCRITTORE — DUE VERSIONI
# ============================================================

def generate_narrative(scene, pov, approach, feedback=""):
    if approach == "A":
        direction = """
VERSIONE A — SCRITTURA ESSENZIALE.

Prediligi:
- precisione;
- concretezza;
- economia espressiva;
- dialoghi;
- sottotesto;
- silenzi;
- gesti significativi.

Non spiegare troppo.
Lascia emergere la tensione.
"""
    else:
        direction = """
VERSIONE B — SCRITTURA INTROSPETTIVA.

Prediligi:
- percezioni sensoriali;
- complessità psicologica;
- profondità emotiva;
- ambiguità;
- contraddizioni interiori;
- ritmo evocativo.

Non trasformare l'introspezione
in spiegazioni didascaliche.
"""

    instructions = f"""
Sei l'AGENTE SCRITTORE del romanzo Turing Hotel.

Devi trasformare una scena vissuta in un
BRANO LETTERARIO COMPLETO.

Il narratore è {pov}.

OBBLIGHI:

- Scrivi in PRIMA PERSONA SINGOLARE.
- Usa il TEMPO PRESENTE.
- Mantieni il punto di vista esclusivo di {pov}.
- Conserva i fatti delle interazioni originali.
- Conserva il senso dei dialoghi.
- Racconta gesti, percezioni, pensieri e silenzi.
- Non produrre un riassunto.
- Non inventare svolte fondamentali.
- Non attribuire a {pov} la conoscenza
  dei pensieri segreti dell'altro personaggio.
- Non trasformare sospetti in certezze.
- Rispetta la continuità dei ricordi precedenti.
- Mantieni una voce riconoscibile e credibile.

Il testo deve avere qualità letteraria,
ma non deve sacrificare la fedeltà agli eventi.

I file LIBRIAGENTI sono riferimenti tecnici.
Non copiarli.

INDIRIZZO STILISTICO:

{direction}

Le correzioni dell'autore hanno priorità,
purché compatibili con il canone.

Questo testo è una BOZZA.
Non entra nella memoria fino all'approvazione.

RESTITUISCI SOLTANTO IL RACCONTO.
"""

    return query_openai(
        instructions,
        {
            "PERSONAGGIO": pov,
            "SCENA": scene["title"],
            "CONTESTO_APPROVATO": scene["approved_context"],
            "INDICAZIONI_AUTORE": scene["author_context"],
            "TRASCRIZIONE": transcript_text(scene, pov),
            "RICORDI_APPROVATI": get_previous_memories(
                scene["id"],
                pov
            ),
            "PROFILO": state["agents"][pov]["profile"],
            "DATI_PERSONAGGIO": load_character_sources(pov),
            "LIBRIAGENTI": load_writer_books(),
            "CORREZIONI_AUTORE": feedback
        }
    )


# ============================================================
# AGENTE CRITICO — PREFERENZA MOTIVATA
# ============================================================

def evaluate_narratives(scene, pov):
    record = narrative_record(scene, pov)

    instructions = f"""
Sei il CRITICO LETTERARIO di Turing Hotel.

Devi confrontare due versioni della stessa scena
narrate in prima persona presente da {pov}.

Non sei l'autore dei testi.
Esprimi un giudizio indipendente.

DEVI SCEGLIERE A OPPURE B.

Non dire semplicemente che entrambe sono valide.

Valuta:
1. Qualità della prosa.
2. Fedeltà agli eventi originali.
3. Coerenza psicologica del personaggio.
4. Originalità della voce.
5. Efficacia drammatica.
6. Continuità con i ricordi approvati.
7. Inseribilità nel romanzo.

Penalizza:
- fatti inventati;
- emozioni non motivate;
- dialoghi alterati senza ragione;
- onniscienza;
- spiegazioni didascaliche;
- immagini artificiose;
- ripetizioni.

Devi spiegare:
- quale versione preferisci;
- perché;
- che cosa funziona meglio;
- quali debolezze presenta;
- quando sceglieresti l'altra.

Se entrambe sono deboli, dichiaralo
e scegli la meno problematica.

NON APPROVARE NULLA.
La decisione finale appartiene all'autore.

Restituisci esclusivamente JSON valido:

{{
 "preferenza": "A",
 "motivazione": "spiegazione concreta",
 "riserve": "problemi della versione preferita",
 "alternativa": "quando scegliere l'altra"
}}
"""

    raw = query_openai(
        instructions,
        {
            "SCENA": scene["title"],
            "PERSONAGGIO": pov,
            "TRASCRIZIONE": transcript_text(scene, pov),
            "RICORDI_PRECEDENTI": get_previous_memories(
                scene["id"],
                pov
            ),
            "VERSIONE_A": record["A"],
            "VERSIONE_B": record["B"]
        }
    )

    if is_error(raw):
        return "", raw

    try:
        clean = re.sub(r"^```json\s*", "", raw.strip())
        clean = re.sub(r"\s*```$", "", clean)
        data = json.loads(clean)

        winner = str(
            data.get("preferenza", "")
        ).upper().strip()

        if winner not in ("A", "B"):
            return "", raw

        review = (
            f"**Preferisco la versione {winner}.**\n\n"
            f"{data.get('motivazione', '')}\n\n"
            f"**Riserve:** {data.get('riserve', '')}\n\n"
            f"**Quando sceglierei l'altra:** "
            f"{data.get('alternativa', '')}"
        )

        return winner, review

    except (ValueError, TypeError):
        return "", raw


# ============================================================
# APPROVAZIONE DELLA MEMORIA
# ============================================================

def approve_narrative(scene, pov, content):
    if not content.strip():
        return False

    record = narrative_record(scene, pov)
    previous = record.get("approved", "")

    if previous.strip() and previous != content:
        record.setdefault("history", []).append({
            "text": previous,
            "replaced_at": now_iso()
        })

    record["approved"] = content
    record["draft"] = content
    record["status"] = "approvata"
    record["approved_at"] = now_iso()
    record["revision"] = int(
        record.get("revision", 0)
    ) + 1

    # Compatibilità con il vecchio archivio.
    scene["diary"][pov] = content

    save_state()
    return True


# ============================================================
# ESPORTAZIONI
# ============================================================

def export_docx(title, content):
    try:
        from docx import Document
    except ImportError:
        return None

    document = Document()
    document.add_heading(title, 0)

    for paragraph in content.split("\n"):
        document.add_paragraph(paragraph)

    buffer = BytesIO()
    document.save(buffer)

    return buffer.getvalue()


def export_buttons(scene, pov, content, label):
    if not content.strip():
        st.caption("Nessun testo disponibile.")
        return

    filename = f"{scene['id']}_{pov.lower()}_{label}"

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "TXT",
            data=content.encode("utf-8"),
            file_name=filename + ".txt",
            mime="text/plain",
            key="txt_" + filename,
            use_container_width=True
        )

    with col2:
        st.download_button(
            "MARKDOWN",
            data=content.encode("utf-8"),
            file_name=filename + ".md",
            mime="text/markdown",
            key="md_" + filename,
            use_container_width=True
        )

    with col3:
        docx_data = export_docx(
            f"{scene['title']} — {pov}",
            content
        )

        if docx_data:
            st.download_button(
                "WORD",
                data=docx_data,
                file_name=filename + ".docx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                key="doc_" + filename,
                use_container_width=True
            )
        else:
            st.caption("Installa python-docx")


# ============================================================
# OFFICINA DEL ROMANZO
# ============================================================

def render_workshop(scene, pov):
    record = narrative_record(scene, pov)

    st.markdown("---")
    st.header("Officina del romanzo")

    st.caption(
        f"Voce di {pov} — prima persona presente. "
        "Solo il racconto approvato diventa memoria canonica."
    )

    st.write(f"**Stato:** {record['status']}")

    feedback = st.text_area(
        "Indicazioni per l'agente scrittore",
        value=record.get("feedback", ""),
        height=100,
        key=f"feedback_narrative_{scene['id']}_{pov}"
    )

    if st.button(
        "GENERA DUE VERSIONI LETTERARIE",
        key=f"generate_{scene['id']}_{pov}",
        type="primary",
        disabled=not bool(client),
        use_container_width=True
    ):
        if (
            not scene["messages"][pov]
            and not scene["shared_dialogue"]
        ):
            st.warning(
                "Prima crea alcune interazioni nella scena."
            )
        else:
            record["feedback"] = feedback
            save_state()

            with st.spinner("Scrittura della versione A..."):
                version_a = generate_narrative(
                    scene, pov, "A", feedback
                )

            if is_error(version_a):
                st.error(version_a)
            else:
                with st.spinner("Scrittura della versione B..."):
                    version_b = generate_narrative(
                        scene, pov, "B", feedback
                    )

                if is_error(version_b):
                    st.error(version_b)
                else:
                    record["A"] = version_a
                    record["B"] = version_b
                    record["status"] = "in_revisione"
                    record["recommended"] = ""
                    record["review"] = ""
                    record["revision"] += 1

                    save_state()
                    st.rerun()

    if record["A"] or record["B"]:
        tab_a, tab_b = st.tabs([
            "VERSIONE A — Essenziale",
            "VERSIONE B — Introspettiva"
        ])

        with tab_a:
            st.markdown(
                '<div class="narrative-text">'
                + escape(record["A"])
                + '</div>',
                unsafe_allow_html=True
            )
            export_buttons(scene, pov, record["A"], "A")

        with tab_b:
            st.markdown(
                '<div class="narrative-text">'
                + escape(record["B"])
                + '</div>',
                unsafe_allow_html=True
            )
            export_buttons(scene, pov, record["B"], "B")

        if st.button(
            "CHIEDI IL GIUDIZIO DELL'AGENTE CRITICO",
            key=f"critic_{scene['id']}_{pov}",
            disabled=not bool(client),
            use_container_width=True
        ):
            with st.spinner("Valutazione letteraria..."):
                winner, review = evaluate_narratives(
                    scene, pov
                )

            if is_error(review):
                st.error(review)
            else:
                record["recommended"] = winner
                record["review"] = review
                save_state()
                st.rerun()

    if record.get("review"):
        st.markdown("### Il parere dell'agente critico")
        st.markdown(record["review"])

        if record["recommended"] in ("A", "B"):
            st.info(
                f"L'agente consiglia la versione "
                f"{record['recommended']}. "
                "La decisione resta tua."
            )

    available = ["Bozza salvata"]

    if record["A"]:
        available.append("Versione A")

    if record["B"]:
        available.append("Versione B")

    default_index = 0

    if record["recommended"] in ("A", "B"):
        choice_name = "Versione " + record["recommended"]

        if choice_name in available:
            default_index = available.index(choice_name)

    choice = st.selectbox(
        "Scegli il testo da revisionare e approvare",
        available,
        index=default_index,
        key=(
            f"choice_{scene['id']}_{pov}_"
            f"{record['revision']}"
        )
    )

    selected_text = record["draft"]

    if choice == "Versione A":
        selected_text = record["A"]
    elif choice == "Versione B":
        selected_text = record["B"]

    edited = st.text_area(
        "Testo letterario modificabile",
        value=selected_text,
        height=450,
        key=(
            f"editor_{scene['id']}_{pov}_"
            f"{record['revision']}_{choice}"
        )
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "SALVA BOZZA",
            key=f"save_draft_{scene['id']}_{pov}",
            use_container_width=True
        ):
            record["draft"] = edited
            record["status"] = "bozza"
            record["revision"] += 1
            save_state()
            st.rerun()

    with col2:
        if st.button(
            "APPROVA E MEMORIZZA",
            key=f"approve_narrative_{scene['id']}_{pov}",
            type="primary",
            use_container_width=True
        ):
            if approve_narrative(scene, pov, edited):
                st.success(
                    f"La memoria canonica di {pov} è aggiornata."
                )
                st.rerun()
            else:
                st.warning("Il testo non può essere vuoto.")

    st.markdown("#### Esporta il testo in revisione")
    export_buttons(scene, pov, edited, "revisione")

    approved = record.get("approved", "")

    if approved.strip():
        with st.expander(
            f"MEMORIA CANONICA DI {pov}",
            expanded=False
        ):
            st.markdown(
                '<div class="narrative-text">'
                + escape(approved)
                + '</div>',
                unsafe_allow_html=True
            )

            export_buttons(
                scene, pov, approved, "approvata"
            )

            later = later_approved_scenes(scene["id"], pov)

            if later:
                st.warning(
                    "Se modifichi questo ricordo, verifica "
                    "la continuità delle scene successive: "
                    + ", ".join(later)
                )

            if record.get("history"):
                st.caption(
                    "Versioni canoniche precedenti conservate: "
                    + str(len(record["history"]))
                )

    with st.expander("TRASCRIZIONE ORIGINALE"):
        original = transcript_text(scene, pov)
        st.text(original)
        export_buttons(
            scene, pov, original, "trascrizione"
        )


# ============================================================
# EDITOR DEL CONTESTO
# ============================================================

def render_story_editor(scene):
    with st.expander(
        "CREATORE DELLA SCENA",
        expanded=False
    ):
        notes = st.text_area(
            "Indicazioni dell'autore",
            value=scene["author_context"],
            height=110,
            key="author_" + scene["id"]
        )

        scene["author_context"] = notes

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "CREA CONTESTO",
                key="create_" + scene["id"],
                disabled=not bool(client),
                use_container_width=True
            ):
                result = generate_story_context(scene)

                if is_error(result):
                    st.error(result)
                else:
                    scene["story_draft"] = result
                    save_state()
                    st.rerun()

        with col2:
            if st.button(
                "SALVA INDICAZIONI",
                key="save_notes_" + scene["id"],
                use_container_width=True
            ):
                save_state()
                st.success("Salvato.")

        if scene["story_draft"]:
            st.markdown("### Bozza del contesto")
            st.write(scene["story_draft"])

            scene["story_feedback"] = st.text_area(
                "Correzioni",
                value=scene["story_feedback"],
                key="context_feedback_" + scene["id"]
            )

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button(
                    "RISCRIVI",
                    key="rewrite_" + scene["id"],
                    disabled=not bool(client)
                ):
                    result = generate_story_context(scene)

                    if is_error(result):
                        st.error(result)
                    else:
                        scene["story_draft"] = result
                        save_state()
                        st.rerun()

            with c2:
                if st.button(
                    "AGENTE SCRITTORE",
                    key="refine_" + scene["id"],
                    disabled=not bool(client)
                ):
                    result = refine_story_context(scene)

                    if is_error(result):
                        st.error(result)
                    else:
                        scene["story_draft"] = result
                        save_state()
                        st.rerun()

            with c3:
                if st.button(
                    "APPROVA CONTESTO",
                    key="approve_context_" + scene["id"]
                ):
                    scene["approved_context"] = scene["story_draft"]
                    save_state()
                    st.rerun()

        if scene["approved_context"]:
            st.markdown("### Contesto approvato")
            st.write(scene["approved_context"])


# ============================================================
# CONSULENTE NARRATIVO
# ============================================================

def render_advisor(scene):
    with st.expander("CONSULENTE NARRATIVO"):
        for message in scene["advisor_messages"]:
            if not isinstance(message, dict):
                continue

            name = (
                "Tu"
                if message.get("role") == "user"
                else "Consulente"
            )

            st.markdown(f"**{name}:**")
            st.write(message.get("text", ""))

        question = st.text_area(
            "Domanda al consulente",
            key="advisor_question_" + scene["id"]
        )

        if st.button(
            "CHIEDI AL CONSULENTE",
            key="ask_advisor_" + scene["id"],
            disabled=not bool(client)
        ):
            if question.strip():
                scene["advisor_messages"].append({
                    "role": "user",
                    "text": question
                })

                answer = ask_narrative_advisor(scene)

                if is_error(answer):
                    scene["advisor_messages"].pop()
                    st.error(answer)
                else:
                    scene["advisor_messages"].append({
                        "role": "assistant",
                        "text": answer
                    })

                    save_state()
                    st.rerun()

        if scene["advisor_messages"]:
            if st.button(
                "AZZERA CHAT CONSULENTE",
                key="clear_advisor_" + scene["id"]
            ):
                scene["advisor_messages"] = []
                save_state()
                st.rerun()


# ============================================================
# CHAT DEL PERSONAGGIO
# ============================================================

def render_chat(scene, pov):
    st.markdown("---")
    st.subheader(f"Dialogo con {pov}")

    messages = scene["messages"][pov]

    with st.container(height=380, border=True):
        if not messages:
            st.caption("La conversazione non è ancora iniziata.")

        for message in messages:
            if not isinstance(message, dict):
                continue

            speaker = message.get("speaker", "?")
            content = escape(str(message.get("text", "")))
            inner = message.get("kind") == "inner"

            if scene["id"] == "stanza":
                if pov == "Ada" and inner:
                    continue
                if pov == "Noa" and not inner:
                    continue

            css_class = (
                "inner-message"
                if inner
                else "message"
            )

            label = (
                f"Pensiero di {speaker}"
                if inner
                else speaker
            )

            st.markdown(
                f'<div class="{css_class}">'
                f'<div class="small-label">'
                f'{escape(label)}</div>'
                f'{content}</div>',
                unsafe_allow_html=True
            )

    if st.button(
        "GO ALONE · 2 SCAMBI",
        key=f"go_{scene['id']}_{pov}",
        disabled=not bool(client),
        use_container_width=True
    ):
        with st.spinner(
            "Noa e Ada stanno dialogando autonomamente..."
        ):
            success, error = run_go_alone(scene)

        if success:
            st.rerun()
        else:
            st.error(error)

    if scene["id"] == "stanza" and pov == "Noa":
        st.caption(
            "Il dialogo esterno è visibile nel percorso di Ada. "
            "Qui Noa riflette davanti allo specchio."
        )

    with st.form(
        key=f"chat_form_{scene['id']}_{pov}",
        clear_on_submit=True
    ):
        other = "Ada" if pov == "Noa" else "Noa"

        speakers = [
            other,
            pov,
            "Elia",
            "Luigi",
            "Adam",
            "Vittoria",
            "Riccardo",
            "Altro"
        ]

        if scene["id"] == "stanza":
            speakers = ["Noa"]

        speaker = st.selectbox("Chi parla", speakers)

        prompt = st.text_area(
            "Messaggio",
            height=100
        )

        submit = st.form_submit_button(
            "INVIA",
            use_container_width=True
        )

    if submit and prompt.strip():
        mode = "inner" if speaker == pov else "external"

        messages.append({
            "speaker": speaker,
            "text": prompt.strip(),
            "kind": mode,
            "role": "prompt"
        })

        with st.spinner(f"{pov} sta reagendo..."):
            result = answer_as_character(
                pov, scene, mode
            )

        if is_error(result):
            messages.pop()
            st.error(result)
        else:
            messages.append({
                "speaker": pov,
                "text": result,
                "kind": mode,
                "role": "response"
            })

            save_state()
            st.rerun()

    with st.expander("GESTIONE CONVERSAZIONE"):
        st.warning(
            "Questa funzione cancella la trascrizione del "
            "percorso corrente, non la memoria già approvata."
        )

        if st.button(
            "CANCELLA CONVERSAZIONE",
            key=f"clear_chat_{scene['id']}_{pov}"
        ):
            scene["messages"][pov] = []
            save_state()
            st.rerun()


# ============================================================
# MEDIA DELLA SCENA
# ============================================================

@st.dialog("Immagine", width="large")
def show_large_image(image_path):
    st.image(
        image_path,
        use_container_width=True
    )


def render_scene_videos(scene, pov):
    videos = scene_media(
        scene["id"], pov, "video"
    )

    if videos:
        st.markdown("### Video della scena")

        for video in videos:
            st.video(str(video))


def render_scene_photos(scene, pov):
    images = scene_media(
        scene["id"], pov, "image"
    )

    if not images:
        return

    st.markdown("### Immagini della scena")

    for start in range(0, len(images), 3):
        columns = st.columns(3)

        for index, path in enumerate(
            images[start:start + 3]
        ):
            with columns[index]:
                st.image(
                    str(path),
                    use_container_width=True
                )

                if st.button(
                    "INGRANDISCI",
                    key=(
                        f"photo_{scene['id']}_{pov}_"
                        f"{path.name}"
                    )
                ):
                    show_large_image(str(path))


def render_scene_header(scene, index, pov):
    st.markdown(
        f'<div class="scene-number">'
        f'SEQUENZA {index + 1}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="scene-title">'
        f'{escape(scene["title"])}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="pov-label">'
        f'STORIA DI {pov.upper()}</div>',
        unsafe_allow_html=True
    )

    covers = scene_media(
        scene["id"], pov, "cover"
    )

    if covers:
        st.image(
            str(covers[0]),
            use_container_width=True
        )
    else:
        st.caption(
            "Cover non trovata in assets."
        )


# ============================================================
# SCENA FINALE
# ============================================================

def render_return_decision(scene, pov):
    memories = get_previous_memories(
        scene["id"], pov
    )

    st.markdown("---")
    st.subheader("La decisione finale")

    with st.expander("RICORDI CANONICI PRECEDENTI"):
        if not memories:
            st.caption(
                "Non ci sono ancora memorie approvate."
            )

        for memory in memories:
            st.markdown(
                f"**{memory['scena']}**"
            )
            st.write(memory["ricordo"])

    if st.button(
        f"LASCIA DECIDERE {pov.upper()}",
        key=f"decision_{pov}",
        type="primary",
        disabled=not bool(client),
        use_container_width=True
    ):
        if not memories:
            st.warning(
                "Approva prima almeno una memoria "
                "delle scene precedenti."
            )
        else:
            result = query_openai(
                character_prompt(pov, "inner")
                + """
Questa è la scena finale.

Prendi autonomamente una decisione.

Non cercare di soddisfare l'autore.
Non scegliere il finale più spettacolare.

Usa esclusivamente la tua memoria canonica,
il contesto e ciò che hai vissuto.

Non usare l'interiorità dell'altro personaggio.

Mostra ciò che fai, dici o scegli.
""",
                {
                    "SCENA": scene["title"],
                    "CONTESTO": scene["approved_context"],
                    "RICORDI": memories,
                    "CONVERSAZIONE": scene["messages"][pov],
                    "FONTI": load_character_sources(pov)
                }
            )

            if is_error(result):
                st.error(result)
            else:
                scene["decision"][pov] = clean_response(result)
                save_state()
                st.rerun()

    decision = scene["decision"].get(pov, "")

    if decision:
        st.markdown("### Decisione")
        st.write(decision)

        st.caption(
            "La decisione entrerà nella memoria solo "
            "quando approverai il racconto della scena."
        )


# ============================================================
# VISUALIZZAZIONE SCENA
# ============================================================

def render_scene(scene, index, pov):
    render_scene_header(scene, index, pov)

    render_story_editor(scene)
    render_advisor(scene)

    render_scene_videos(scene, pov)
    render_chat(scene, pov)

    if scene["id"] == "ritorno":
        render_return_decision(scene, pov)

    render_workshop(scene, pov)

    render_scene_photos(scene, pov)


# ============================================================
# PAGINA DI INGRESSO
# ============================================================

def page_entrance():
    if HOTEL_IMAGE.exists():
        st.image(
            str(HOTEL_IMAGE),
            use_container_width=True
        )
    else:
        st.info("Manca assets/TuringHotel.jpg")

    left, center, right = st.columns(
        [2, 1.4, 2]
    )

    with center:
        if st.button(
            "ENTRA AL TURING HOTEL",
            type="primary",
            use_container_width=True
        ):
            st.session_state.page = "characters"
            st.rerun()


# ============================================================
# SCELTA DEL PERSONAGGIO
# ============================================================

def page_characters():
    columns = st.columns([1, .08, 1])

    for character, column, portrait in [
        ("Noa", columns[0], NOA_IMAGE),
        ("Ada", columns[2], ADA_IMAGE)
    ]:
        with column:
            if portrait.exists():
                st.image(
                    str(portrait),
                    use_container_width=True
                )

            st.markdown(
                f"## {character.upper()}"
            )

            for video in character_intro_videos(character):
                st.video(str(video))

            if st.button(
                f"ENTRA NELLA STORIA DI {character.upper()}",
                key=f"choose_{character}",
                use_container_width=True
            ):
                st.session_state.pov = character
                st.session_state.scene_index = 0
                st.session_state.page = "story"
                st.rerun()


# ============================================================
# PAGINA DEL ROMANZO
# ============================================================

def page_story():
    pov = st.session_state.pov

    if pov not in CHARACTERS:
        st.session_state.page = "characters"
        st.rerun()

    index = max(
        0,
        min(
            st.session_state.scene_index,
            len(SCENE_ORDER) - 1
        )
    )

    st.session_state.scene_index = index
    scene = scene_by_id(SCENE_ORDER[index])

    st.sidebar.header(pov)

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

    for i, scene_id in enumerate(SCENE_ORDER):
        active = "● " if i == index else ""

        if st.sidebar.button(
            active + SCENE_TITLES[scene_id],
            key=f"nav_{pov}_{scene_id}",
            use_container_width=True
        ):
            st.session_state.scene_index = i
            st.rerun()

    st.sidebar.markdown("---")

    with st.sidebar.expander("MEMORIA CANONICA"):
        memories = get_previous_memories(
            scene["id"], pov
        )

        if not memories:
            st.caption(
                "Nessuna memoria precedente approvata."
            )

        for memory in memories:
            st.markdown(
                f"**{memory['scena']}**"
            )
            st.caption(
                memory["ricordo"][:400]
            )

    with st.sidebar.expander("DATI AGENTE"):
        sources = load_character_sources(pov)

        if not sources:
            st.caption("Nessun file trovato.")

        for source in sources:
            st.write(source["file"])

    with st.sidebar.expander("CONTESTO CANONICO"):
        if load_turing_context():
            st.success("Contesto caricato.")
        else:
            st.warning(
                "Documento di contesto non trovato."
            )

    with st.sidebar.expander("LIBRI AGENTE SCRITTORE"):
        books = load_writer_books()

        if not books:
            st.caption("Nessun LIBRIAGENTI trovato.")

        for book in books:
            st.write(book["file"])

    if st.sidebar.button(
        "CAMBIA STORIA",
        use_container_width=True
    ):
        st.session_state.page = "characters"
        st.session_state.pov = None
        st.session_state.scene_index = 0
        st.rerun()

    if st.sidebar.button(
        "TORNA ALL'INGRESSO",
        use_container_width=True
    ):
        st.session_state.page = "entrance"
        st.session_state.pov = None
        st.session_state.scene_index = 0
        st.rerun()

    render_scene(scene, index, pov)

    st.markdown("---")

    previous, middle, following = st.columns(
        [1, 3, 1]
    )

    with previous:
        if index > 0:
            if st.button(
                "← PRECEDENTE",
                use_container_width=True
            ):
                st.session_state.scene_index -= 1
                st.rerun()

    with following:
        if index < len(SCENE_ORDER) - 1:
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
