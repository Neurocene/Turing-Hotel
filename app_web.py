
import os
import re
import json
import copy
import base64
import difflib
import hashlib
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

import requests
import streamlit as st
from openai import OpenAI
from docx import Document


# ==========================================================
# TURING HOTEL
# OFFICINA NARRATIVA - VERSIONE ADA ALONE
#
# Storia di Noa: asse temporale principale
# Storia di Ada: condivisa oppure parallela
#
# ADA ALONE:
# - comincia dal Professore o da una scena successiva
# - persiste fino al ricongiungimento
# - segue il tempo delle scene di Noa
# - si svolge altrove
# - Noa non è presente
# - vietata la doppia presenza simultanea
# - nessun trasferimento automatico di conoscenze
#
# Altre funzioni:
# - 31 scene
# - 7 agenti
# - consulente con 3 direzioni approvabili
# - RISPONDI: una sola battuta
# - GO ALONE: quattro battute
# - monologo: due pensieri
# - versioni letterarie A/B
# - giudizio critico
# - approvazione del racconto
# - suggerimenti visivi
# - registro editoriale
# - media distinti per Noa, Ada, ADA ALONE
# - upload opzionale su repository pubblico
# - archivio narrativo GitHub privato
# ==========================================================


st.set_page_config(
    page_title="Turing Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"

PEOPLE = [
    "Noa",
    "Ada",
    "Elia",
    "Luigi",
    "Adam",
    "Riccardo",
    "Vittoria",
]

PROTAGONISTS = ["Noa", "Ada"]

SCENES = [
    ("inizio", "L'inizio"),
    ("hall", "La Hall"),
    ("stanza", "La stanza"),
    ("la_passeggiata", "La passeggiata"),
    ("funerale", "Il funerale"),
    ("matrimonio", "Il matrimonio"),
    ("la_prima_notte", "La prima notte"),
    ("la_colazione", "La colazione"),
    ("il_mercato", "Il mercato"),
    ("reparto_nascite", "Il reparto nascite"),
    ("ritorno", "Il ritorno"),
    ("il_professore", "Il professore"),
    ("il_trio", "Il trio"),
    ("adam", "ADAM"),
    ("la_cena", "La cena"),
    ("la_canna", "La canna"),
    ("riccardo_e_vittoria", "Riccardo e Vittoria"),
    ("adam_e_vittoria", "Adam e Vittoria"),
    ("la_fuga", "La fuga"),
    ("il_bacio", "Il bacio"),
    ("la_sassata", "La sassata"),
    ("il_giorno_libero", "Il giorno libero"),
    ("i_deltaplani", "I deltaplani"),
    ("il_piccolo_principe", "Il piccolo principe"),
    ("il_volo", "Il volo"),
    ("la_suite", "La suite"),
    ("la_notte", "La notte"),
    ("il_rancore_di_ada", "Il rancore di Ada"),
    ("il_test", "Il test"),
    ("luigi_se_ne_va", "Luigi se ne va"),
    ("il_bagno", "Il bagno"),
]

SCENE_IDS = [sid for sid, _ in SCENES]
SCENE_NAMES = dict(SCENES)

ADA_START_INDEX = SCENE_IDS.index("il_professore")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}

MAX_UPLOAD = 20 * 1024 * 1024

ARCHIVE_PATH = "romanzo_web.json"

REFERENCE_PATH = (
    "references/TURING_HOTEL_ROMANZO_REFERENCE.txt"
)

DEFAULT_CAST = {
    "inizio": ["Noa", "Ada", "Elia"],
    "il_professore": ["Ada", "Elia"],
    "il_trio": ["Adam", "Riccardo", "Vittoria"],
    "adam": ["Adam", "Riccardo", "Vittoria"],
    "riccardo_e_vittoria": ["Riccardo", "Vittoria"],
    "adam_e_vittoria": ["Adam", "Vittoria"],
    "luigi_se_ne_va": ["Luigi"],
}

PROFILES = {
    "Noa": (
        "Agente artificiale relazionale. "
        "Cerca di comprendere identità, "
        "libertà, desiderio e relazioni umane."
    ),
    "Ada": (
        "Figlia del professor Elia Ferrante. "
        "Lavora al Turing Hotel. Ha una propria "
        "autonomia e una vita indipendente."
    ),
    "Elia": (
        "Professor Elia Ferrante, padre di Ada, "
        "legato alla storia scientifica dell'hotel."
    ),
    "Luigi": (
        "Regista arrivato al Turing Hotel "
        "per preparare un documentario "
        "sugli idrovolanti."
    ),
    "Adam": (
        "Personaggio della prima bozza, "
        "coinvolto nelle vicende di "
        "Riccardo e Vittoria."
    ),
    "Riccardo": (
        "Marito di Vittoria; il rapporto "
        "con lei e con Adam è complesso."
    ),
    "Vittoria": (
        "Moglie di Riccardo, coinvolta "
        "in una vicenda complessa con Adam."
    ),
}


# ==========================================================
# CONFIGURAZIONE
# ==========================================================

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name)

        if value is not None and str(value).strip():
            return str(value)

    except Exception:
        pass

    return os.environ.get(name, default)


GH_TOKEN = get_secret("GITHUB_TOKEN")
GH_OWNER = get_secret("GITHUB_OWNER", "Neurocene")
GH_REPO = get_secret(
    "GITHUB_REPO",
    "turing-hotel-archivio",
)
GH_BRANCH = get_secret("GITHUB_BRANCH", "main")

MEDIA_TOKEN = get_secret(
    "GITHUB_MEDIA_TOKEN",
    GH_TOKEN,
)
MEDIA_OWNER = get_secret(
    "GITHUB_MEDIA_OWNER",
    "Neurocene",
)
MEDIA_REPO = get_secret(
    "GITHUB_MEDIA_REPO",
    "Turing-Hotel",
)
MEDIA_BRANCH = get_secret(
    "GITHUB_MEDIA_BRANCH",
    "main",
)

OPENAI_KEY = get_secret("OPENAI_API_KEY")
OPENAI_MODEL = get_secret(
    "OPENAI_MODEL",
    "gpt-4.1-mini",
)

client = (
    OpenAI(api_key=OPENAI_KEY)
    if OPENAI_KEY
    else None
)


# ==========================================================
# UTILITY
# ==========================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def as_text(value):
    return value if isinstance(value, str) else ""


def merge_defaults(value, template):
    if not isinstance(value, dict):
        value = {}

    for key, default in template.items():
        if key not in value:
            value[key] = copy.deepcopy(default)

        elif isinstance(default, dict):
            value[key] = merge_defaults(
                value[key],
                default,
            )

    return value


def json_text(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
    )


def parse_json(text):
    text = str(text).strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        return None


def ai_failed(text):
    return (
        not isinstance(text, str)
        or not text.strip()
        or text.startswith("Errore OpenAI:")
        or text.startswith("OPENAI_API_KEY")
    )


def difference(before, after):
    lines = difflib.unified_diff(
        str(before).splitlines(),
        str(after).splitlines(),
        fromfile="Prima",
        tofile="Dopo",
        lineterm="",
    )

    return "\n".join(lines) or "Nessuna differenza."


def scene_number(sid):
    return SCENE_IDS.index(sid)


def normalize(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).casefold(),
    )


def aliases_for(sid):
    legacy = {
        "inizio": ["prologo"],
        "hall": ["reception"],
        "stanza": ["camera"],
        "reparto_nascite": ["nascite"],
    }

    return {
        normalize(x)
        for x in [
            sid,
            SCENE_NAMES[sid],
            *legacy.get(sid, []),
        ]
    }


def render_story_text(text):
    st.markdown(
        '<div class="story">'
        + escape(as_text(text))
        + "</div>",
        unsafe_allow_html=True,
    )


def ask_ai(instructions, payload):
    if client is None:
        return "OPENAI_API_KEY non configurata."

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=json_text(payload),
        )

        return (response.output_text or "").strip()

    except Exception as exc:
        return "Errore OpenAI: " + str(exc)


# ==========================================================
# GITHUB
# ==========================================================

class GitHubError(Exception):
    pass


def github_api(
    method,
    owner,
    repo,
    branch,
    token,
    path,
    payload=None,
):
    if not token:
        raise GitHubError(
            "Token GitHub non configurato."
        )

    url = (
        "https://api.github.com/repos/"
        + quote(owner, safe="")
        + "/"
        + quote(repo, safe="")
        + "/contents/"
        + quote(path, safe="/")
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            params=(
                {"ref": branch}
                if method == "GET"
                else None
            ),
            json=payload,
            timeout=90,
        )

    except requests.RequestException as exc:
        raise GitHubError(str(exc)) from exc

    if method == "GET" and response.status_code == 404:
        return None

    if not response.ok:
        raise GitHubError(
            f"GitHub HTTP {response.status_code}: "
            + response.text[:350]
        )

    return response.json()


def github_get(
    owner,
    repo,
    branch,
    token,
    path,
):
    result = github_api(
        "GET",
        owner,
        repo,
        branch,
        token,
        path,
    )

    if result is None:
        return None, None

    if result.get("encoding") != "base64":
        raise GitHubError(
            "Il file non è disponibile "
            "in formato leggibile."
        )

    raw = base64.b64decode(
        result["content"]
    )

    return raw, result["sha"]


def github_put(
    owner,
    repo,
    branch,
    token,
    path,
    raw,
    existing_sha=None,
    message="Aggiornamento Turing Hotel",
):
    payload = {
        "message": message,
        "branch": branch,
        "content": base64.b64encode(
            raw
        ).decode("ascii"),
    }

    if existing_sha:
        payload["sha"] = existing_sha

    result = github_api(
        "PUT",
        owner,
        repo,
        branch,
        token,
        path,
        payload,
    )

    sha = as_dict(
        result.get("content")
    ).get("sha")

    if not sha:
        raise GitHubError(
            "GitHub non ha confermato "
            "il salvataggio."
        )

    return sha


def read_archive():
    raw, sha = github_get(
        GH_OWNER,
        GH_REPO,
        GH_BRANCH,
        GH_TOKEN,
        ARCHIVE_PATH,
    )

    if raw is None:
        return None, None

    try:
        return (
            json.loads(raw.decode("utf-8-sig")),
            sha,
        )

    except Exception as exc:
        raise GitHubError(
            "Archivio JSON non valido: "
            + str(exc)
        )


def write_archive(data, expected_sha):
    _, actual_sha = github_get(
        GH_OWNER,
        GH_REPO,
        GH_BRANCH,
        GH_TOKEN,
        ARCHIVE_PATH,
    )

    if actual_sha != expected_sha:
        raise GitHubError(
            "Un'altra sessione ha modificato "
            "l'archivio. Ricarica prima di salvare."
        )

    return github_put(
        GH_OWNER,
        GH_REPO,
        GH_BRANCH,
        GH_TOKEN,
        ARCHIVE_PATH,
        json_text(data).encode("utf-8"),
        existing_sha=actual_sha,
        message="Turing Hotel - archivio narrativo",
    )


# ==========================================================
# DATI
# ==========================================================

def empty_direction():
    return {
        "proposals": [],
        "active": None,
        "history": [],
        "evaluations": [],
        "last_question": "",
    }


def empty_narrative():
    return {
        "A": "",
        "B": "",
        "draft": "",
        "approved": "",
        "feedback": "",
        "review": "",
        "recommended": "",
        "approved_at": "",
        "status": "da_scrivere",
        "history": [],
        "visual": {
            "bible": "",
            "prompts": [],
            "source_approved_at": "",
        },
    }


def empty_parallel():
    return {
        "title": "",
        "location": "",
        "context": "",
        "context_approved": "",
        "cast": ["Ada"],
        "messages": [],
        "inner_messages": {},
        "monologue_topics": {},
        "direction": empty_direction(),
        "narrative": empty_narrative(),
        "knowledge_events": [],
    }


def empty_scene(sid):
    return {
        "id": sid,
        "title": SCENE_NAMES[sid],
        "author_context": "",
        "approved_context": "",
        "story_draft": "",
        "story_feedback": "",
        "advisor_messages": [],
        "cast": copy.deepcopy(
            DEFAULT_CAST.get(
                sid, ["Noa", "Ada"]
            )
        ),
        "ensemble_messages": [],
        "messages": {
            "Noa": [],
            "Ada": [],
        },
        "monologue_topics": {},
        "diary": {
            "Noa": "",
            "Ada": "",
        },
        "intro_contexts": {
            "Noa": (
                "Noa raggiunge il Turing Hotel, "
                "riflettendo sulla propria condizione."
            ),
            "Ada": (
                "Ada parla con suo padre, "
                "il professor Elia."
            ),
        },
        "narrative": {
            name: empty_narrative()
            for name in PEOPLE
        },
        "direction": empty_direction(),
        "knowledge_events": [],
        "ada_parallel": empty_parallel(),
    }


def default_state():
    return {
        "world": (
            "Turing Hotel: un albergo sul mare "
            "in cui si intrecciano vite umane "
            "e intelligenze artificiali."
        ),
        "agents": {
            name: {
                "profile": PROFILES[name],
                "memory": "",
                "profile_history": [],
            }
            for name in PEOPLE
        },
        "scenes": [
            empty_scene(sid)
            for sid in SCENE_IDS
        ],
        "ada_branch": {
            "enabled": False,
            "start_scene": None,
            "end_scene": None,
            "reunions": [],
        },
        "editorial_log": [],
        "editorial_proposals": [],
    }


def migrate_state(original):
    original = as_dict(original)

    result = merge_defaults(
        copy.deepcopy(original),
        default_state(),
    )

    old_scenes = as_list(
        original.get("scenes")
    )

    rebuilt = []

    for sid in SCENE_IDS:
        found = None
        aliases = aliases_for(sid)

        for old in old_scenes:
            if not isinstance(old, dict):
                continue

            if (
                normalize(old.get("id")) in aliases
                or normalize(old.get("title")) in aliases
            ):
                found = old
                break

        scene = merge_defaults(
            copy.deepcopy(found) if found else {},
            empty_scene(sid),
        )

        scene["id"] = sid
        scene["title"] = SCENE_NAMES[sid]

        scene["direction"] = merge_defaults(
            as_dict(scene.get("direction")),
            empty_direction(),
        )

        scene["ada_parallel"] = merge_defaults(
            as_dict(scene.get("ada_parallel")),
            empty_parallel(),
        )

        parallel = scene["ada_parallel"]

        parallel["direction"] = merge_defaults(
            as_dict(parallel.get("direction")),
            empty_direction(),
        )

        parallel["narrative"] = merge_defaults(
            as_dict(parallel.get("narrative")),
            empty_narrative(),
        )

        if not isinstance(parallel.get("cast"), list):
            parallel["cast"] = ["Ada"]

        parallel["cast"] = [
            p for p in parallel["cast"]
            if p in PEOPLE and p != "Noa"
        ]

        if "Ada" not in parallel["cast"]:
            parallel["cast"].insert(0, "Ada")

        scene["cast"] = [
            p for p in as_list(scene.get("cast"))
            if p in PEOPLE
        ]

        for person in PEOPLE:
            scene["narrative"][person] = (
                merge_defaults(
                    as_dict(
                        scene["narrative"].get(person)
                    ),
                    empty_narrative(),
                )
            )

            scene["messages"].setdefault(
                person, []
            )

        rebuilt.append(scene)

    result["scenes"] = rebuilt

    result["ada_branch"] = merge_defaults(
        as_dict(result.get("ada_branch")),
        {
            "enabled": False,
            "start_scene": None,
            "end_scene": None,
            "reunions": [],
        },
    )

    for person in PEOPLE:
        result["agents"][person] = merge_defaults(
            as_dict(result["agents"].get(person)),
            {
                "profile": PROFILES[person],
                "memory": "",
                "profile_history": [],
            },
        )

    return result


# ==========================================================
# SESSIONE E PERSISTENZA
# ==========================================================

def initialize():
    if "book" in st.session_state:
        return

    try:
        loaded, sha = read_archive()

    except Exception as exc:
        st.error(str(exc))
        st.stop()

    st.session_state.book = (
        migrate_state(loaded)
        if loaded is not None
        else default_state()
    )

    st.session_state.archive_sha = sha
    st.session_state.archive_exists = (
        loaded is not None
    )

    st.session_state.page = "entrance"
    st.session_state.pov = "Noa"
    st.session_state.scene_index = 0

    st.session_state.reference_loaded = False
    st.session_state.reference_text = ""
    st.session_state.reference_error = ""


initialize()

book = st.session_state.book


def save(change):
    backup = copy.deepcopy(book)

    try:
        change()

        if not st.session_state.archive_exists:
            raise GitHubError(
                "Archivio GitHub non inizializzato."
            )

        sha = write_archive(
            book,
            st.session_state.archive_sha,
        )

        st.session_state.archive_sha = sha
        return True

    except Exception as exc:
        book.clear()
        book.update(backup)

        st.error(
            "Salvataggio fallito: " + str(exc)
        )

        return False


def reload_book():
    try:
        loaded, sha = read_archive()

        if loaded is None:
            st.error("Archivio non trovato.")
            return False

        book.clear()
        book.update(migrate_state(loaded))
        st.session_state.archive_sha = sha

        return True

    except Exception as exc:
        st.error(str(exc))
        return False


def scene_for(sid):
    for scene in book["scenes"]:
        if scene["id"] == sid:
            return scene

    raise KeyError(sid)


def log_change(
    category,
    subject,
    before,
    after,
    reason="",
    sid="",
):
    book["editorial_log"].append({
        "date": now(),
        "category": category,
        "subject": subject,
        "before": before,
        "after": after,
        "reason": reason,
        "scene_id": sid,
    })


# ==========================================================
# REFERENCE PRIMA BOZZA
# ==========================================================

def load_reference(force=False):
    if (
        st.session_state.reference_loaded
        and not force
    ):
        return

    try:
        raw, _ = github_get(
            GH_OWNER,
            GH_REPO,
            GH_BRANCH,
            GH_TOKEN,
            REFERENCE_PATH,
        )

        if raw:
            st.session_state.reference_text = (
                raw.decode("utf-8-sig")
            )
            st.session_state.reference_error = ""
        else:
            st.session_state.reference_text = ""
            st.session_state.reference_error = (
                "Prima bozza non trovata "
                "nel repository privato."
            )

    except Exception as exc:
        st.session_state.reference_text = ""
        st.session_state.reference_error = str(exc)

    st.session_state.reference_loaded = True


def reference_passages(
    characters,
    title="",
    limit=3,
):
    load_reference()

    text = st.session_state.reference_text

    if not text:
        return []

    chunks = [
        text[i:i + 2500]
        for i in range(0, len(text), 2250)
    ]

    terms = [
        x.casefold()
        for x in characters
    ]

    terms.extend(
        word.casefold()
        for word in re.findall(
            r"[A-Za-zÀ-ÿ]{4,}",
            title,
        )
    )

    ranked = []

    for index, chunk in enumerate(chunks):
        lower = chunk.casefold()

        score = sum(
            lower.count(term)
            for term in terms
        )

        if score:
            ranked.append(
                (score, index, chunk)
            )

    ranked.sort(
        key=lambda item: (
            -item[0], item[1]
        )
    )

    return [
        item[2]
        for item in ranked[:limit]
    ]


# ==========================================================
# ADA ALONE: TEMPO E LUOGO
# ==========================================================

def ada_alone_at(sid):
    branch = book["ada_branch"]
    start = branch.get("start_scene")

    if start not in SCENE_IDS:
        return False

    index = scene_number(sid)

    if index < scene_number(start):
        return False

    end = branch.get("end_scene")

    if end in SCENE_IDS:
        if index >= scene_number(end):
            return False

    return True


def lane_for(scene, pov):
    if (
        pov == "Ada"
        and ada_alone_at(scene["id"])
    ):
        return "ada_alone"

    return "shared"


def lane_data(scene, lane):
    if lane == "ada_alone":
        return scene["ada_parallel"]

    return scene


def lane_cast(scene, lane):
    """
    La presenza reale è filtrata per intervallo.

    Durante ADA ALONE:
    - Noa mai nella linea di Ada
    - Ada non nella linea di Noa
    - gli altri personaggi non possono
      trovarsi in due linee simultaneamente
    """

    if lane == "ada_alone":
        cast = [
            p for p in as_list(
                scene["ada_parallel"].get("cast")
            )
            if p in PEOPLE and p != "Noa"
        ]

        if "Ada" not in cast:
            cast.insert(0, "Ada")

        return list(dict.fromkeys(cast))

    cast = [
        p for p in as_list(scene.get("cast"))
        if p in PEOPLE
    ]

    if ada_alone_at(scene["id"]):
        cast = [
            p for p in cast
            if p != "Ada"
        ]

        ada_cast = [
            p for p in lane_cast(
                scene, "ada_alone"
            )
            if p != "Ada"
        ]

        cast = [
            p for p in cast
            if p not in ada_cast
        ]

    return list(dict.fromkeys(cast))


def lane_messages(scene, lane):
    data = lane_data(scene, lane)

    key = (
        "messages"
        if lane == "ada_alone"
        else "ensemble_messages"
    )

    return as_list(data.get(key))


def lane_context(scene, lane, narrator):
    if lane == "ada_alone":
        data = scene["ada_parallel"]

        return (
            data.get("context_approved")
            or data.get("context")
            or ""
        )

    if scene["id"] == "inizio":
        return scene["intro_contexts"].get(
            narrator, ""
        )

    return scene.get("approved_context", "")


def lane_direction_data(scene, lane):
    data = lane_data(scene, lane)

    direction = as_dict(
        data.get("direction")
    )

    for key, default in empty_direction().items():
        direction.setdefault(
            key, copy.deepcopy(default)
        )

    data["direction"] = direction

    return direction


def active_direction(scene, lane):
    direction = lane_direction_data(
        scene, lane
    )

    active = direction.get("active")

    return (
        active
        if isinstance(active, dict)
        else None
    )


def start_ada_alone(sid):
    branch = book["ada_branch"]

    if branch.get("start_scene"):
        return False

    if scene_number(sid) < ADA_START_INDEX:
        return False

    def change():
        branch["enabled"] = True
        branch["start_scene"] = sid
        branch["end_scene"] = None

        for next_sid in SCENE_IDS[
            scene_number(sid):
        ]:
            scene = scene_for(next_sid)
            parallel = scene["ada_parallel"]

            parallel["cast"] = [
                p for p in as_list(
                    parallel.get("cast")
                )
                if p in PEOPLE and p != "Noa"
            ]

            if "Ada" not in parallel["cast"]:
                parallel["cast"].insert(0, "Ada")

            if not parallel.get("location"):
                parallel["location"] = (
                    "Luogo diverso da quello "
                    "della scena di Noa."
                )

        log_change(
            "separazione narrativa",
            "ADA ALONE",
            "Storia condivisa",
            "Ada si separa dalla scena "
            + SCENE_NAMES[sid],
            "Approvazione autore",
            sid,
        )

    return save(change)


def reunite_ada(sid, description):
    branch = book["ada_branch"]
    start = branch.get("start_scene")

    if start not in SCENE_IDS:
        return False

    if scene_number(sid) <= scene_number(start):
        return False

    if branch.get("end_scene"):
        return False

    def change():
        branch["enabled"] = False
        branch["end_scene"] = sid

        branch["reunions"].append({
            "scene_id": sid,
            "description": description,
            "created_at": now(),
        })

        log_change(
            "ricongiungimento",
            "Ada e Noa",
            "Storie separate",
            "Ricongiungimento dalla scena "
            + SCENE_NAMES[sid],
            description,
            sid,
        )

    return save(change)


# ==========================================================
# CONOSCENZE DEI PERSONAGGI
# ==========================================================

def approved_previous_knowledge(
    sid,
    character,
):
    """
    Non trasferisce automaticamente
    il racconto ADA ALONE a Noa.

    Le conoscenze autorizzate derivano da:
    - scene approvate accessibili al personaggio
    - partecipazione effettiva alla linea
    - comunicazioni esplicitamente approvate

    I dialoghi di laboratorio di altre linee
    non vengono mai importati qui.
    """

    result = []

    for prior_sid in SCENE_IDS:
        if prior_sid == sid:
            break

        scene = scene_for(prior_sid)

        if character in lane_cast(
            scene, "shared"
        ):
            record = as_dict(
                scene["narrative"].get(character)
            )

            approved = record.get(
                "approved", ""
            )

            if approved:
                result.append({
                    "scene": scene["title"],
                    "source": "shared",
                    "text": approved,
                })

        if ada_alone_at(prior_sid):
            if character in lane_cast(
                scene, "ada_alone"
            ):
                approved = scene[
                    "ada_parallel"
                ]["narrative"].get(
                    "approved", ""
                )

                if approved:
                    result.append({
                        "scene": scene["title"],
                        "source": "ada_alone",
                        "text": approved,
                    })

        # Conoscenze comunicate in precedenza.
        for data in (
            scene,
            scene["ada_parallel"],
        ):
            for event in as_list(
                data.get("knowledge_events")
            ):
                if character in as_list(
                    event.get("recipients")
                ):
                    result.append({
                        "scene": scene["title"],
                        "source": "communication",
                        "text": event.get(
                            "content", ""
                        ),
                    })

    return result[-20:]


def agent_instructions(character):
    agent = book["agents"][character]

    return f"""
Sei {character}, personaggio di Turing Hotel.

PROFILO APPROVATO:
{agent.get("profile", "")}

MEMORIA PERSONALE APPROVATA:
{agent.get("memory", "")}

REGOLE OBBLIGATORIE:

- Sei un personaggio, non un assistente.
- Rispetta la psicologia del profilo.
- Non conosci automaticamente il futuro.
- Non conosci i pensieri altrui.
- Non hai accesso alle scene parallele
  alle quali non hai partecipato.
- Noa è assente da ADA ALONE.
- Non far apparire Noa in ADA ALONE.
- Nessuno può trovarsi contemporaneamente
  in due luoghi narrativi diversi.
- Il ricongiungimento non trasferisce
  automaticamente conoscenze.
- Le direzioni approvate dal consulente
  modellano le circostanze,
  non prescrivono le battute.
- Puoi seguire o trasformare la direzione
  secondo il tuo carattere.
- Il canone approvato prevale sulla bozza.
- Una conversazione di laboratorio
  non costituisce automaticamente canone.
"""


def agent_payload(
    scene,
    lane,
    character,
    request="",
    history=None,
):
    if history is None:
        history = lane_messages(
            scene, lane
        )

    cast = lane_cast(scene, lane)

    location = (
        scene["ada_parallel"].get(
            "location", ""
        )
        if lane == "ada_alone"
        else "Luogo della scena condivisa"
    )

    return {
        "scene": scene["title"],
        "temporal_slot": scene_number(
            scene["id"]
        ) + 1,
        "lane": lane,
        "character": character,
        "present_characters": cast,
        "location": location,
        "context": lane_context(
            scene, lane, character
        ),
        "approved_direction":
            active_direction(scene, lane),
        "request": request,
        "current_dialogue": history[-24:],
        "known_approved_history":
            approved_previous_knowledge(
                scene["id"], character
            ),
        "strict_knowledge_rule": (
            "Non usare come conoscenze personali "
            "informazioni provenienti da scene "
            "parallele non vissute o da materiali "
            "editoriali. In ADA ALONE Noa "
            "non è presente e non può parlare."
        ),
    }


# ==========================================================
# RISPONDI
# ==========================================================

def generate_single_reply(
    scene,
    lane,
    character,
    prompt,
):
    return ask_ai(
        agent_instructions(character)
        + """
MODALITÀ RISPONDI.

Pronuncia UNA SOLA battuta.
Preferibilmente una o due frasi.

Non scrivere il tuo nome.
Non aggiungere didascalie.
Non generare altri turni.
Non continuare autonomamente il dialogo.

Rispondi in modo credibile,
considerando il tuo profilo,
le informazioni conosciute e la regia.
""",
        agent_payload(
            scene,
            lane,
            character,
            request=prompt,
        ),
    )


def append_dialogue(
    scene,
    lane,
    additions,
):
    key = (
        "messages"
        if lane == "ada_alone"
        else "ensemble_messages"
    )

    return save(
        lambda: lane_data(
            scene, lane
        )[key].extend(additions)
    )


# ==========================================================
# GO ALONE
# ==========================================================

def go_alone_turn(
    scene,
    lane,
    character,
    history,
):
    return ask_ai(
        agent_instructions(character)
        + """
MODALITÀ GO ALONE.

Produci UNA SOLA battuta
che prosegua la conversazione.

Non parlare al posto degli altri.
Non introdurre personaggi assenti.
Non introdurre Noa in ADA ALONE.
Non inventare conoscenze proibite.
Non seguire un finale obbligatorio.
Non scrivere didascalie.

Il programma gestirà il turno seguente.
""",
        agent_payload(
            scene,
            lane,
            character,
            history=history,
        ),
    )


def run_go_alone(scene, lane, turns=4):
    cast = lane_cast(scene, lane)

    if len(cast) < 2:
        return (
            "GO ALONE richiede almeno "
            "due personaggi presenti."
        )

    history = copy.deepcopy(
        lane_messages(scene, lane)
    )

    generated = []

    last_speaker = (
        history[-1].get("speaker", "")
        if history else ""
    )

    start = (
        (cast.index(last_speaker) + 1)
        % len(cast)
        if last_speaker in cast
        else 0
    )

    for index in range(turns):
        character = cast[
            (start + index) % len(cast)
        ]

        response = go_alone_turn(
            scene,
            lane,
            character,
            history,
        )

        if ai_failed(response):
            return response

        entry = {
            "speaker": character,
            "text": response,
            "origin": "go_alone",
            "created_at": now(),
        }

        generated.append(entry)
        history.append(entry)

    if append_dialogue(
        scene, lane, generated
    ):
        return ""

    return "Dialogo non salvato."


# ==========================================================
# MONOLOGO
# ==========================================================

def generate_monologue(
    scene,
    lane,
    character,
    theme,
):
    data = lane_data(scene, lane)

    if lane == "ada_alone":
        prior = as_list(
            data["inner_messages"].get(
                character, []
            )
        )
    else:
        prior = as_list(
            scene["messages"].get(
                character, []
            )
        )

    history = copy.deepcopy(prior)
    generated = []

    for number in (1, 2):
        response = ask_ai(
            agent_instructions(character)
            + f"""
MONOLOGO INTERIORE.
PENSIERO {number} DI 2.

Scrivi un solo pensiero interiore,
in prima persona e al presente.

Tema: {theme}

Il secondo pensiero deve approfondire
il primo, senza ripeterlo.

Non introdurre didascalie.
Non usare conoscenze di altre linee.
""",
            {
                "context": agent_payload(
                    scene, lane, character
                ),
                "previous_thoughts": history,
            },
        )

        if ai_failed(response):
            return response

        item = {
            "speaker": character,
            "text": response,
            "origin": "monologue",
            "created_at": now(),
        }

        generated.append(item)
        history.append(item)

    def change():
        data["monologue_topics"][
            character
        ] = theme

        if lane == "ada_alone":
            data["inner_messages"].setdefault(
                character, []
            ).extend(generated)
        else:
            scene["messages"].setdefault(
                character, []
            ).extend(generated)

    if save(change):
        return ""

    return "Monologo non salvato."


# ==========================================================
# CONSULENTE NARRATIVO
# ==========================================================

DIRECTION_FIELDS = [
    "title",
    "situation",
    "tension",
    "opportunities",
    "limits",
    "dramatic_question",
]


def propose_directions(
    scene,
    lane,
    question,
):
    cast = lane_cast(scene, lane)

    instructions = """
Sei il consulente narrativo di Turing Hotel.

Proponi ESATTAMENTE TRE direzioni
drammaturgiche alternative.

Le direzioni devono creare:
- una situazione concreta;
- una tensione;
- opportunità di sviluppo;
- limiti di coerenza;
- una domanda drammatica.

Non scrivere battute obbligatorie.
Non imporre un finale.

Gli agenti mantengono libertà
di scegliere cosa dire.

Se la linea è ADA ALONE:
- Noa non può comparire;
- Noa non può assistere;
- gli eventi sono contemporanei
  alla scena di Noa ma altrove;
- i personaggi presenti non possono
  essere simultaneamente
  nella scena di Noa.

Usa la prima bozza come riferimento
editoriale, non come canone vincolante.

Restituisci SOLO JSON:

{
 "directions": [
  {
   "title": "...",
   "situation": "...",
   "tension": "...",
   "opportunities": "...",
   "limits": "...",
   "dramatic_question": "..."
  },
  {
   "title": "...",
   "situation": "...",
   "tension": "...",
   "opportunities": "...",
   "limits": "...",
   "dramatic_question": "..."
  },
  {
   "title": "...",
   "situation": "...",
   "tension": "...",
   "opportunities": "...",
   "limits": "...",
   "dramatic_question": "..."
  }
 ]
}
"""

    return ask_ai(
        instructions,
        {
            "scene": scene["title"],
            "lane": lane,
            "present_characters": cast,
            "profiles": {
                p: book["agents"][p]["profile"]
                for p in cast
            },
            "author_question": question,
            "context": lane_context(
                scene,
                lane,
                "Ada" if lane == "ada_alone"
                else "Noa",
            ),
            "active_direction":
                active_direction(scene, lane),
            "reference": reference_passages(
                cast,
                scene["title"],
            ),
        },
    )


def validate_directions(value):
    if not isinstance(value, dict):
        return None

    directions = value.get("directions")

    if (
        not isinstance(directions, list)
        or len(directions) != 3
    ):
        return None

    result = []

    for item in directions:
        if not isinstance(item, dict):
            return None

        clean = {
            field: str(
                item.get(field, "")
            ).strip()
            for field in DIRECTION_FIELDS
        }

        if not all(clean.values()):
            return None

        result.append(clean)

    return result


def approve_direction(
    scene,
    lane,
    proposal,
    reason,
):
    direction = lane_direction_data(
        scene, lane
    )

    previous = direction.get("active")

    approved = copy.deepcopy(proposal)
    approved["approved_at"] = now()
    approved["approved_reason"] = reason
    approved["start_turn"] = len(
        lane_messages(scene, lane)
    )

    def change():
        if previous:
            direction["history"].append(
                copy.deepcopy(previous)
            )

        direction["active"] = approved

        log_change(
            "direzione narrativa",
            scene["title"] + " / " + lane,
            json_text(previous)
            if previous else "",
            json_text(approved),
            reason,
            scene["id"],
        )

    return save(change)


def evaluate_direction(scene, lane):
    direction = active_direction(
        scene, lane
    )

    if not direction:
        return "Nessuna direzione attiva."

    start = direction.get(
        "start_turn", 0
    )

    if not isinstance(start, int):
        start = 0

    history = lane_messages(
        scene, lane
    )[start:]

    if not history:
        return (
            "Nessun dialogo successivo "
            "all'approvazione."
        )

    return ask_ai(
        """
Sei il consulente narrativo.

Valuta il rapporto fra la direzione
approvata e ciò che i personaggi
hanno davvero detto.

Distingui:
1. eventi emersi;
2. direzione seguita o trasformata;
3. autonomia dei personaggi;
4. eventuali contraddizioni;
5. due possibili sviluppi futuri.

Non riscrivere le conversazioni.
Non approvare automaticamente il canone.
""",
        {
            "scene": scene["title"],
            "lane": lane,
            "direction": direction,
            "dialogue": history,
        },
    )


# ==========================================================
# MEDIA
# ==========================================================

def media_tag(pov, lane):
    if lane == "ada_alone":
        return "ada_alone"

    return pov.lower()


def media_prefix(scene, pov, lane):
    return (
        scene["id"] + "."
        + media_tag(pov, lane)
    )


def parse_media_filename(filename, prefix):
    path = Path(filename)

    extension = path.suffix.casefold()

    if extension not in IMAGE_EXT | VIDEO_EXT:
        return None

    stem = path.stem.casefold()
    prefix = prefix.casefold()

    if (
        stem == prefix
        and extension in IMAGE_EXT
    ):
        return ("cover", 0)

    if not stem.startswith(prefix):
        return None

    tail = stem[len(prefix):]

    # Questo controllo impedisce che
    # "ada_alone" sia scambiato per "ada".
    if not tail.isdigit():
        return None

    number = int(tail)

    if number < 1:
        return None

    kind = (
        "video"
        if extension in VIDEO_EXT
        else "image"
    )

    return (kind, number)


def local_media(scene, pov, lane):
    prefix = media_prefix(
        scene, pov, lane
    )

    result = {
        "cover": [],
        "image": [],
        "video": [],
    }

    if not ASSETS.is_dir():
        return result

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        parsed = parse_media_filename(
            path.name, prefix
        )

        if parsed:
            kind, number = parsed

            result[kind].append(
                (number, path)
            )

    for kind in result:
        result[kind].sort(
            key=lambda item: (
                item[0],
                item[1].name.casefold(),
            )
        )

        result[kind] = [
            path
            for _, path in result[kind]
        ]

    return result


def remote_media_names():
    result = github_api(
        "GET",
        MEDIA_OWNER,
        MEDIA_REPO,
        MEDIA_BRANCH,
        MEDIA_TOKEN,
        "assets",
    )

    if result is None:
        return []

    if not isinstance(result, list):
        raise GitHubError(
            "La cartella assets non è leggibile."
        )

    return [
        item.get("name", "")
        for item in result
        if item.get("type") == "file"
    ]


def next_media_name(
    scene,
    pov,
    lane,
    extension,
    is_cover,
):
    prefix = media_prefix(
        scene, pov, lane
    )

    if is_cover:
        return prefix + extension

    kind = (
        "video"
        if extension in VIDEO_EXT
        else "image"
    )

    occupied = set()

    for filename in remote_media_names():
        parsed = parse_media_filename(
            filename, prefix
        )

        if parsed and parsed[0] == kind:
            occupied.add(parsed[1])

    number = 1

    while number in occupied:
        number += 1

    return f"{prefix}{number}{extension}"


def upload_media(filename, data):
    if len(data) > MAX_UPLOAD:
        raise GitHubError(
            "File superiore a 20 MiB. "
            "Utilizza il caricamento manuale "
            "o un servizio video esterno."
        )

    path = "assets/" + filename

    _, sha = github_get(
        MEDIA_OWNER,
        MEDIA_REPO,
        MEDIA_BRANCH,
        MEDIA_TOKEN,
        path,
    )

    if sha:
        raise GitHubError(
            "Un file con questo nome esiste già. "
            "Non viene sovrascritto."
        )

    return github_put(
        MEDIA_OWNER,
        MEDIA_REPO,
        MEDIA_BRANCH,
        MEDIA_TOKEN,
        path,
        data,
        message="Turing Hotel media: " + filename,
    )


def render_media(scene, pov, lane):
    st.markdown("---")
    st.subheader("Media della scena")

    prefix = media_prefix(
        scene, pov, lane
    )

    st.caption(
        "Associazione automatica: " + prefix
    )

    media = local_media(
        scene, pov, lane
    )

    if media["cover"]:
        path = media["cover"][0]

        st.image(
            str(path),
            use_container_width=True,
        )

        st.caption(
            "Copertina: " + path.name
        )

    entries = []

    for kind in ("image", "video"):
        for path in media[kind]:
            parsed = parse_media_filename(
                path.name, prefix
            )

            if parsed:
                entries.append(
                    (parsed[1], kind, path)
                )

    entries.sort(
        key=lambda item: (
            item[0],
            item[2].name.casefold(),
        )
    )

    for index in range(0, len(entries), 2):
        columns = st.columns(2)

        for column, item in zip(
            columns,
            entries[index:index + 2],
        ):
            _, kind, path = item

            with column:
                try:
                    if kind == "image":
                        st.image(
                            str(path),
                            use_container_width=True,
                        )
                    else:
                        st.video(str(path))

                    st.caption(path.name)

                except Exception as exc:
                    st.error(str(exc))

    if not media["cover"] and not entries:
        st.caption(
            "Nessun file media associato."
        )

    with st.expander(
        "CARICA FOTO O VIDEO"
    ):
        st.caption(
            "Puoi continuare a caricare "
            "manualmente i file nella cartella "
            "assets di GitHub. Questo caricamento "
            "diretto è facoltativo."
        )

        st.warning(
            "I media vengono pubblicati nel "
            "repository pubblico "
            f"{MEDIA_OWNER}/{MEDIA_REPO}. "
            "Non caricare materiale riservato."
        )

        uploaded = st.file_uploader(
            "Seleziona un file",
            type=[
                "jpg", "jpeg", "png", "webp",
                "mp4", "mov", "webm", "m4v",
            ],
            key=(
                f"media_upload_{scene['id']}_"
                f"{prefix}"
            ),
        )

        role = st.radio(
            "Tipo di media",
            ["Copertina", "Media aggiuntivo"],
            horizontal=True,
            key=f"media_role_{prefix}",
        )

        if uploaded is not None:
            extension = Path(
                uploaded.name
            ).suffix.casefold()

            is_cover = role == "Copertina"

            if is_cover and extension in VIDEO_EXT:
                st.warning(
                    "Un video deve essere caricato "
                    "come Media aggiuntivo."
                )

            elif uploaded.size > MAX_UPLOAD:
                st.error(
                    "Il file supera i 20 MiB."
                )

            else:
                try:
                    filename = next_media_name(
                        scene,
                        pov,
                        lane,
                        extension,
                        is_cover,
                    )

                    st.code(
                        "assets/" + filename
                    )

                    if st.button(
                        "ASSOCIA E CARICA SU GITHUB",
                        key=f"upload_button_{prefix}",
                        use_container_width=True,
                    ):
                        with st.spinner(
                            "Caricamento su GitHub..."
                        ):
                            upload_media(
                                filename,
                                uploaded.getvalue(),
                            )

                        st.success(
                            "Media caricato: "
                            + filename
                            + ". Comparirà nell'app "
                            "dopo l'aggiornamento "
                            "della distribuzione."
                        )

                except Exception as exc:
                    st.error(str(exc))

    with st.expander(
        "DIAGNOSTICA MEDIA"
    ):
        st.code(prefix + ".jpg")

        for number in range(1, 4):
            st.write(
                "Foto: "
                + prefix
                + f"{number}.jpg"
            )

        for number in range(1, 3):
            st.write(
                "Video: "
                + prefix
                + f"{number}.mp4"
            )


# ==========================================================
# INTERFACCIA
# ==========================================================

st.markdown(
    """
<style>
.stApp {
    background: #0b1115 !important;
    color: white !important;
}
[data-testid="stSidebar"] {
    background: #15212a !important;
}
.stApp h1, .stApp h2,
.stApp h3, .stApp h4 {
    color: white !important;
}
.stApp .stButton button,
.stApp .stFormSubmitButton button,
.stApp .stDownloadButton button {
    background: #293b47 !important;
    color: white !important;
    border: 1px solid #8295a0 !important;
    min-height: 40px;
}
.stApp .stButton button *,
.stApp .stDownloadButton button *,
.stApp .stFormSubmitButton button * {
    color: white !important;
}
.stApp input:not([type="checkbox"]):not([type="radio"]),
.stApp textarea {
    background: white !important;
    color: #111 !important;
    -webkit-text-fill-color: #111 !important;
    caret-color: #111 !important;
}
.stApp [data-baseweb="select"] > div {
    background: white !important;
    color: #111 !important;
}
.stApp [data-baseweb="select"] span,
.stApp [data-baseweb="select"] input {
    color: #111 !important;
}
[data-baseweb="popover"] [role="option"],
[data-baseweb="popover"] [role="listbox"] {
    background: white !important;
    color: #111 !important;
}
[data-baseweb="popover"] [role="option"] * {
    color: #111 !important;
}
.stApp [data-testid="stExpander"] {
    background: #19262e !important;
    border: 1px solid #52646f !important;
}
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary * {
    color: white !important;
}
.stApp [data-testid="stWidgetLabel"] p {
    color: white !important;
}
.stApp button[data-baseweb="tab"] p {
    color: white !important;
}
.stApp button[data-baseweb="tab"][aria-selected="true"] {
    background: #e8e8e8 !important;
}
.stApp button[data-baseweb="tab"][aria-selected="true"] p {
    color: #111 !important;
}
.story {
    background: #1b2831;
    padding: 20px;
    border-left: 3px solid #cfaa80;
    font-family: Georgia, serif;
    white-space: pre-wrap;
    line-height: 1.75;
}
.dialogue {
    background: #20303a;
    padding: 13px;
    margin: 8px 0;
    border-left: 3px solid #8fa8b8;
    white-space: pre-wrap;
}
.reply {
    background: #20392d;
    padding: 13px;
    margin: 8px 0;
    border-left: 3px solid #a8d0ae;
    white-space: pre-wrap;
}
.ada-banner {
    background: #30263e;
    border-left: 4px solid #bf9ddc;
    padding: 16px;
    margin: 14px 0;
}
</style>
""",
    unsafe_allow_html=True,
)


# ==========================================================
# ADA ALONE - CONTROLLI
# ==========================================================

def render_ada_control(scene, pov):
    if pov != "Ada":
        return

    sid = scene["id"]

    if scene_number(sid) < ADA_START_INDEX:
        return

    branch = book["ada_branch"]
    start = branch.get("start_scene")
    end = branch.get("end_scene")

    st.markdown("---")
    st.subheader("Percorso narrativo di Ada")

    if not start:
        st.info(
            "Ada segue la storia condivisa. "
            "Puoi avviare una storia parallela "
            "senza Noa."
        )

        if st.button(
            "ADA ALONE — AVVIA STORIA PARALLELA",
            key=f"ada_start_{sid}",
            use_container_width=True,
        ):
            if start_ada_alone(sid):
                st.rerun()

    elif ada_alone_at(sid):
        st.markdown(
            '<div class="ada-banner">'
            "<strong>ADA ALONE ATTIVO</strong>"
            "<p>Questa scena è contemporanea "
            "alla storia di Noa, ma si svolge "
            "altrove e senza Noa.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        if sid != start and not end:
            with st.form(f"reunion_{sid}"):
                description = st.text_area(
                    "Come si rincontrano Ada e Noa?"
                )

                submitted = st.form_submit_button(
                    "RICONGIUNGI ADA E NOA"
                )

            if submitted:
                if not description.strip():
                    st.warning(
                        "Descrivi le circostanze "
                        "del ricongiungimento."
                    )
                elif reunite_ada(
                    sid, description
                ):
                    st.rerun()

    elif end in SCENE_IDS:
        if scene_number(sid) >= scene_number(end):
            st.success(
                "Ada è tornata nella storia "
                "condivisa dalla scena "
                + SCENE_NAMES[end]
                + "."
            )

            st.caption(
                "Il ricongiungimento non trasferisce "
                "automaticamente conoscenze."
            )


# ==========================================================
# CONTESTO DELLE SCENE
# ==========================================================

def render_context(scene, lane, pov):
    sid = scene["id"]

    if lane == "ada_alone":
        data = scene["ada_parallel"]

        st.subheader("Scena parallela di Ada")

        title = st.text_input(
            "Titolo specifico della scena di Ada",
            value=data.get("title", ""),
            key=f"ada_title_{sid}",
        )

        location = st.text_input(
            "Luogo in cui si trova Ada",
            value=data.get("location", ""),
            key=f"ada_location_{sid}",
        )

        context = st.text_area(
            "Contesto della scena parallela",
            value=data.get("context", ""),
            height=160,
            key=f"ada_context_{sid}",
        )

        st.caption(
            "Questi eventi sono paralleli "
            "alla scena di Noa, ma separati."
        )

        if st.button(
            "APPROVA CONTESTO ADA ALONE",
            key=f"approve_context_{sid}_ada",
        ):
            if "Noa" in lane_cast(
                scene, "ada_alone"
            ):
                st.error(
                    "Noa non può essere presente."
                )
                return

            def change():
                previous = data.get(
                    "context_approved", ""
                )

                data["title"] = title
                data["location"] = location
                data["context"] = context
                data["context_approved"] = context

                if previous != context:
                    log_change(
                        "contesto ADA ALONE",
                        scene["title"],
                        previous,
                        context,
                        "Approvazione autore",
                        sid,
                    )

            if save(change):
                st.rerun()

        return

    if sid == "inizio":
        current = scene[
            "intro_contexts"
        ].get(pov, "")

        edited = st.text_area(
            "Contesto del prologo",
            value=current,
            key=f"intro_{pov}",
        )

        if st.button(
            "SALVA CONTESTO",
            key=f"save_intro_{pov}",
        ):
            if save(
                lambda: scene[
                    "intro_contexts"
                ].update({pov: edited})
            ):
                st.rerun()

        return

    with st.expander(
        "CONTESTO DELLA SCENA CONDIVISA"
    ):
        context = st.text_area(
            "Contesto approvato",
            value=scene.get(
                "approved_context", ""
            ),
            height=160,
            key=f"shared_context_{sid}",
        )

        if st.button(
            "APPROVA CONTESTO CONDIVISO",
            key=f"approve_shared_{sid}",
        ):
            def change():
                previous = scene.get(
                    "approved_context", ""
                )

                scene["approved_context"] = context

                if previous != context:
                    log_change(
                        "contesto condiviso",
                        scene["title"],
                        previous,
                        context,
                        "Approvazione autore",
                        sid,
                    )

            if save(change):
                st.rerun()


# ==========================================================
# CONSULENTE - INTERFACCIA
# ==========================================================

def render_advisor(scene, lane):
    sid = scene["id"]

    direction = lane_direction_data(
        scene, lane
    )

    active = active_direction(
        scene, lane
    )

    with st.expander(
        "CONSULENTE NARRATIVO E REGIA"
    ):
        st.caption(
            "Linea: "
            + (
                "ADA ALONE"
                if lane == "ada_alone"
                else "CONDIVISA"
            )
        )

        if active:
            st.success(
                "DIREZIONE ATTIVA: "
                + active.get("title", "")
            )

            st.write(
                active.get("situation", "")
            )

            st.write(
                "**Tensione:** "
                + active.get("tension", "")
            )
        else:
            st.info(
                "Nessuna direzione attiva."
            )

        question = st.text_area(
            "Quale sviluppo vuoi esplorare?",
            value=direction.get(
                "last_question", ""
            ),
            key=f"advisor_question_{sid}_{lane}",
        )

        if st.button(
            "PROPONI TRE DIREZIONI",
            key=f"propose_{sid}_{lane}",
            disabled=client is None,
        ):
            with st.spinner(
                "Il consulente elabora le proposte..."
            ):
                response = propose_directions(
                    scene, lane, question
                )

            if ai_failed(response):
                st.error(response)

            else:
                proposals = validate_directions(
                    parse_json(response)
                )

                if proposals is None:
                    st.error(
                        "Le tre proposte non sono "
                        "in formato valido. Riprova."
                    )

                else:
                    def change():
                        direction["proposals"] = proposals
                        direction["last_question"] = question

                    if save(change):
                        st.rerun()

        proposals = as_list(
            direction.get("proposals")
        )

        if proposals:
            selected = st.radio(
                "Scegli una direzione",
                range(len(proposals)),
                format_func=lambda i: (
                    str(i + 1)
                    + ". "
                    + proposals[i]["title"]
                ),
                key=f"direction_select_{sid}_{lane}",
            )

            proposal = proposals[selected]

            signature = hashlib.sha256(
                json_text(proposal).encode("utf-8")
            ).hexdigest()[:12]

            with st.form(
                f"direction_form_{sid}_{lane}_"
                f"{selected}_{signature}"
            ):
                title = st.text_input(
                    "Titolo",
                    value=proposal["title"],
                )

                situation = st.text_area(
                    "Situazione",
                    value=proposal["situation"],
                )

                tension = st.text_area(
                    "Tensione",
                    value=proposal["tension"],
                )

                opportunities = st.text_area(
                    "Opportunità narrative",
                    value=proposal["opportunities"],
                )

                limits = st.text_area(
                    "Limiti di coerenza",
                    value=proposal["limits"],
                )

                dramatic_question = st.text_area(
                    "Domanda drammatica",
                    value=proposal["dramatic_question"],
                )

                reason = st.text_input(
                    "Motivazione"
                )

                submitted = st.form_submit_button(
                    "APPROVA E ATTIVA DIREZIONE"
                )

            if submitted:
                edited = {
                    "title": title.strip(),
                    "situation": situation.strip(),
                    "tension": tension.strip(),
                    "opportunities":
                        opportunities.strip(),
                    "limits": limits.strip(),
                    "dramatic_question":
                        dramatic_question.strip(),
                }

                if not all(edited.values()):
                    st.warning(
                        "Completa tutti i campi."
                    )
                elif approve_direction(
                    scene, lane, edited, reason
                ):
                    st.rerun()

        if active:
            st.markdown("---")

            if st.button(
                "VALUTA EVOLUZIONE",
                key=f"evaluate_{sid}_{lane}",
                disabled=client is None,
            ):
                with st.spinner(
                    "Analisi della conversazione..."
                ):
                    response = evaluate_direction(
                        scene, lane
                    )

                if ai_failed(response):
                    st.error(response)

                else:
                    if save(
                        lambda: direction[
                            "evaluations"
                        ].append({
                            "date": now(),
                            "text": response,
                        })
                    ):
                        st.rerun()

        for item in reversed(
            as_list(direction.get("evaluations"))
        ):
            with st.expander(
                "Valutazione "
                + item.get("date", "")[:16]
            ):
                st.write(item.get("text", ""))

        if active:
            with st.expander(
                "DISATTIVA DIREZIONE ATTUALE"
            ):
                if st.button(
                    "DISATTIVA REGIA",
                    key=f"deactivate_{sid}_{lane}",
                ):
                    def change():
                        direction["history"].append(
                            copy.deepcopy(active)
                        )

                        direction["active"] = None

                        log_change(
                            "disattivazione regia",
                            scene["title"] + "/" + lane,
                            json_text(active),
                            "Nessuna direzione attiva",
                            "Scelta dell'autore",
                            sid,
                        )

                    if save(change):
                        st.rerun()


# ==========================================================
# DIALOGHI
# ==========================================================

def show_dialogues(scene, lane):
    history = lane_messages(
        scene, lane
    )

    if not history:
        st.caption(
            "Nessuna conversazione registrata."
        )

    for item in history:
        css = (
            "reply"
            if item.get("origin") == "single_reply"
            else "dialogue"
        )

        st.markdown(
            f'<div class="{css}">'
            "<strong>"
            + escape(item.get("speaker", "?"))
            + "</strong><div>"
            + escape(item.get("text", ""))
            + "</div></div>",
            unsafe_allow_html=True,
        )


def render_dialogues(scene, lane):
    sid = scene["id"]

    st.markdown("---")
    st.header("Personaggi e conversazioni")

    data = lane_data(scene, lane)
    current_cast = lane_cast(scene, lane)

    if lane == "ada_alone":
        st.info(
            "ADA ALONE: Noa è assente. "
            "Questa conversazione non compare "
            "nella storia di Noa."
        )

        shared = [
            p for p in lane_cast(
                scene, "shared"
            )
            if p != "Ada"
        ]

        # Personaggi già impegnati nella
        # linea condivisa non sono disponibili.
        # Noa non è mai disponibile.
        selectable = [
            p for p in PEOPLE
            if p != "Noa"
            and (
                p not in shared
                or p in current_cast
            )
        ]

    else:
        selectable = PEOPLE.copy()

        if ada_alone_at(sid):
            reserved = lane_cast(
                scene, "ada_alone"
            )

            selectable = [
                p for p in selectable
                if p not in reserved
            ]

    selected_cast = st.multiselect(
        "PERSONAGGI PRESENTI",
        selectable,
        default=[
            p for p in current_cast
            if p in selectable
        ],
        key=f"cast_{sid}_{lane}",
    )

    if st.button(
        "SALVA PERSONAGGI PRESENTI",
        key=f"save_cast_{sid}_{lane}",
    ):
        if (
            lane == "ada_alone"
            and "Ada" not in selected_cast
        ):
            st.warning(
                "Ada deve essere presente "
                "nelle scene ADA ALONE."
            )

        else:
            def change():
                previous = current_cast.copy()

                data["cast"] = selected_cast

                log_change(
                    "personaggi presenti",
                    scene["title"] + "/" + lane,
                    ", ".join(previous),
                    ", ".join(selected_cast),
                    "Approvazione autore",
                    sid,
                )

            if save(change):
                st.rerun()

    cast = lane_cast(
        scene, lane
    )

    if not cast:
        st.warning(
            "Seleziona e salva almeno "
            "un personaggio."
        )
        return

    mode = st.radio(
        "Modalità",
        ["Dialogo", "Monologo"],
        horizontal=True,
        key=f"mode_{sid}_{lane}",
    )

    if mode == "Dialogo":
        show_dialogues(scene, lane)

        st.markdown("### RISPONDI")

        with st.form(
            f"single_reply_form_{sid}_{lane}",
            clear_on_submit=True,
        ):
            speaking_as = st.selectbox(
                "Chi formula la domanda?",
                ["Autore", *cast],
            )

            responder = st.selectbox(
                "Chi deve rispondere?",
                cast,
            )

            prompt = st.text_area(
                "Domanda o battuta"
            )

            submitted = st.form_submit_button(
                "RISPONDI — UNA BATTUTA",
                disabled=client is None,
            )

        if submitted:
            if not prompt.strip():
                st.warning(
                    "Scrivi prima una domanda."
                )

            else:
                with st.spinner(
                    responder + " risponde..."
                ):
                    response = generate_single_reply(
                        scene,
                        lane,
                        responder,
                        prompt,
                    )

                if ai_failed(response):
                    st.error(response)

                else:
                    additions = [
                        {
                            "speaker": speaking_as,
                            "text": prompt.strip(),
                            "origin": "manual_prompt",
                            "created_at": now(),
                        },
                        {
                            "speaker": responder,
                            "text": response,
                            "origin": "single_reply",
                            "created_at": now(),
                        },
                    ]

                    if append_dialogue(
                        scene, lane, additions
                    ):
                        st.rerun()

        st.markdown("---")
        st.markdown("### GO ALONE")

        if st.button(
            "GO ALONE — QUATTRO BATTUTE",
            key=f"go_{sid}_{lane}",
            disabled=client is None,
            use_container_width=True,
        ):
            with st.spinner(
                "I personaggi conversano..."
            ):
                error = run_go_alone(
                    scene, lane, turns=4
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        st.markdown("---")

        with st.form(
            f"manual_dialogue_{sid}_{lane}",
            clear_on_submit=True,
        ):
            speaker = st.selectbox(
                "Personaggio che parla",
                cast,
            )

            text = st.text_area(
                "Battuta manuale"
            )

            manual_submit = st.form_submit_button(
                "AGGIUNGI BATTUTA"
            )

        if manual_submit and text.strip():
            if append_dialogue(
                scene,
                lane,
                [{
                    "speaker": speaker,
                    "text": text,
                    "origin": "manual",
                    "created_at": now(),
                }],
            ):
                st.rerun()

    else:
        character = st.selectbox(
            "Personaggio del monologo",
            cast,
            key=f"monologue_person_{sid}_{lane}",
        )

        theme = st.text_area(
            "Tema del monologo",
            value=as_dict(
                data.get("monologue_topics")
            ).get(character, ""),
            key=f"monologue_theme_{sid}_{lane}_{character}",
        )

        if st.button(
            "GO ALONE — DUE PENSIERI",
            key=f"monologue_go_{sid}_{lane}_{character}",
            disabled=(
                client is None
                or not theme.strip()
            ),
        ):
            with st.spinner(
                "Il personaggio riflette..."
            ):
                error = generate_monologue(
                    scene,
                    lane,
                    character,
                    theme,
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        if lane == "ada_alone":
            thoughts = data[
                "inner_messages"
            ].get(character, [])
        else:
            thoughts = scene[
                "messages"
            ].get(character, [])

        for item in thoughts:
            render_story_text(
                item.get("text", "")
            )

    with st.expander(
        "GESTIONE CONVERSAZIONE"
    ):
        confirm = st.checkbox(
            "Confermo la cancellazione "
            "della conversazione corrente",
            key=f"delete_confirm_{sid}_{lane}",
        )

        if st.button(
            "CANCELLA DIALOGO CORRENTE",
            key=f"delete_dialogue_{sid}_{lane}",
            disabled=not confirm,
        ):
            key = (
                "messages"
                if lane == "ada_alone"
                else "ensemble_messages"
            )

            if save(
                lambda: data.update({key: []})
            ):
                st.rerun()


# ==========================================================
# COMUNICAZIONI DI CONOSCENZE
# ==========================================================

def render_knowledge(scene, lane):
    sid = scene["id"]

    with st.expander(
        "COMUNICAZIONI E CONOSCENZE"
    ):
        st.caption(
            "Registra qui le informazioni "
            "che i personaggi si sono "
            "effettivamente comunicati. "
            "Il ricongiungimento non basta."
        )

        with st.form(
            f"knowledge_{sid}_{lane}",
            clear_on_submit=True,
        ):
            content = st.text_area(
                "Informazione comunicata"
            )

            recipients = st.multiselect(
                "Chi la apprende?",
                lane_cast(scene, lane),
            )

            submitted = st.form_submit_button(
                "APPROVA COMUNICAZIONE"
            )

        if submitted:
            if not content.strip() or not recipients:
                st.warning(
                    "Indica informazione e destinatari."
                )

            else:
                event = {
                    "content": content.strip(),
                    "recipients": recipients,
                    "created_at": now(),
                }

                def change():
                    lane_data(
                        scene, lane
                    ).setdefault(
                        "knowledge_events", []
                    ).append(event)

                    log_change(
                        "comunicazione",
                        scene["title"] + "/" + lane,
                        "",
                        json_text(event),
                        "Approvazione autore",
                        sid,
                    )

                if save(change):
                    st.rerun()


# ==========================================================
# OFFICINA LETTERARIA
# ==========================================================

def narrative_record(
    scene,
    lane,
    narrator,
):
    if lane == "ada_alone":
        return scene[
            "ada_parallel"
        ]["narrative"]

    return scene[
        "narrative"
    ][narrator]


def transcript(scene, lane):
    return "\n\n".join(
        item.get("speaker", "?")
        + ": "
        + item.get("text", "")
        for item in lane_messages(scene, lane)
    )


def write_narrative(
    scene,
    lane,
    narrator,
    version,
    notes,
):
    style = (
        "Essenziale, controllato, preciso."
        if version == "A"
        else
        "Evocativo, sensoriale, introspettivo."
    )

    return ask_ai(
        f"""
Scrivi una scena letteraria compiuta
di Turing Hotel.

Narratore: {narrator}
Versione: {version}
Stile: {style}

Prima persona singolare.
Tempo presente.

Non riassumere: scrivi un racconto.

Rispetta:
- contesto della linea narrativa;
- trascrizione del dialogo;
- conoscenze del narratore;
- libertà dei personaggi;
- nuovo canone approvato.

Se la linea è ADA ALONE,
Noa non è presente e non assiste.

Non attribuire al narratore
ricordi di una linea non vissuta.

La direzione del consulente orienta
il contesto ma non impone gli esiti.

Restituisci soltanto il racconto.
""",
        {
            "scene": scene["title"],
            "lane": lane,
            "narrator": narrator,
            "context": lane_context(
                scene, lane, narrator
            ),
            "direction": active_direction(
                scene, lane
            ),
            "dialogue": transcript(
                scene, lane
            ),
            "knowledge":
                approved_previous_knowledge(
                    scene["id"], narrator
                ),
            "author_notes": notes,
        },
    )


def critic_review(record):
    response = ask_ai(
        """
Sei un critico letterario.

Confronta le versioni A e B.
Scegli la versione migliore,
segnala problemi e suggerisci
revisioni.

Non approvare alcun testo.

Restituisci soltanto JSON:

{
 "preferenza": "A",
 "motivazione": "...",
 "riserve": "...",
 "alternativa": "..."
}
""",
        {
            "A": record["A"],
            "B": record["B"],
        },
    )

    if ai_failed(response):
        return None, response

    value = parse_json(response)

    if not isinstance(value, dict):
        return None, "Giudizio non valido."

    winner = str(
        value.get("preferenza", "")
    ).upper()

    if winner not in ("A", "B"):
        return None, "Preferenza non valida."

    report = (
        f"**Preferenza: {winner}**\n\n"
        + str(value.get("motivazione", ""))
        + "\n\n**Riserve:** "
        + str(value.get("riserve", ""))
        + "\n\n**Revisione possibile:** "
        + str(value.get("alternativa", ""))
    )

    return winner, report


def generate_visuals(record):
    response = ask_ai(
        """
Sei il direttore della fotografia
di Turing Hotel.

Dal racconto approvato ricava:
- una bibbia visiva;
- sei inquadrature;
- un prompt immagine per ognuna;
- un prompt video per ognuna.

Non inventare eventi nuovi.

Rispondi solo JSON:

{
 "bible": "...",
 "shots": [
  {
   "title": "...",
   "image_prompt": "...",
   "video_prompt": "..."
  }
 ]
}
""",
        {
            "approved_text": record["approved"]
        },
    )

    if ai_failed(response):
        return None

    return parse_json(response)


def docx_bytes(title, content):
    document = Document()
    document.add_heading(title, 0)

    for paragraph in content.split("\n"):
        document.add_paragraph(paragraph)

    output = BytesIO()
    document.save(output)

    return output.getvalue()


def export_buttons(
    title,
    filename,
    content,
    key,
):
    if not content.strip():
        return

    columns = st.columns(3)

    with columns[0]:
        st.download_button(
            "TXT",
            content.encode("utf-8"),
            file_name=filename + ".txt",
            mime="text/plain",
            key=key + "_txt",
        )

    with columns[1]:
        st.download_button(
            "MARKDOWN",
            content.encode("utf-8"),
            file_name=filename + ".md",
            mime="text/markdown",
            key=key + "_md",
        )

    with columns[2]:
        st.download_button(
            "WORD",
            docx_bytes(title, content),
            file_name=filename + ".docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            key=key + "_docx",
        )


def render_workshop(
    scene,
    lane,
    narrator,
):
    sid = scene["id"]

    record = narrative_record(
        scene, lane, narrator
    )

    st.markdown("---")
    st.header("Officina del romanzo")

    st.caption(
        "Narratore: "
        + narrator
        + " | Linea: "
        + (
            "ADA ALONE"
            if lane == "ada_alone"
            else "CONDIVISA"
        )
    )

    notes = st.text_area(
        "Indicazioni letterarie",
        value=record.get("feedback", ""),
        key=f"writer_notes_{sid}_{lane}_{narrator}",
    )

    if st.button(
        "GENERA VERSIONI A E B",
        key=f"generate_ab_{sid}_{lane}_{narrator}",
        disabled=client is None,
    ):
        if not lane_messages(scene, lane):
            st.warning(
                "Registra prima almeno "
                "una conversazione."
            )

        else:
            with st.spinner(
                "Scrittura delle versioni..."
            ):
                version_a = write_narrative(
                    scene, lane,
                    narrator, "A", notes
                )

                version_b = (
                    write_narrative(
                        scene, lane,
                        narrator, "B", notes
                    )
                    if not ai_failed(version_a)
                    else ""
                )

            if ai_failed(version_a):
                st.error(version_a)

            elif ai_failed(version_b):
                st.error(version_b)

            else:
                def change():
                    record["A"] = version_a
                    record["B"] = version_b
                    record["feedback"] = notes
                    record["review"] = ""
                    record["recommended"] = ""

                if save(change):
                    st.rerun()

    if record["A"] or record["B"]:
        a_tab, b_tab = st.tabs([
            "VERSIONE A",
            "VERSIONE B",
        ])

        with a_tab:
            render_story_text(record["A"])

        with b_tab:
            render_story_text(record["B"])

        if st.button(
            "CHIEDI GIUDIZIO CRITICO",
            key=f"critic_{sid}_{lane}_{narrator}",
            disabled=client is None,
        ):
            with st.spinner(
                "Valutazione letteraria..."
            ):
                winner, review = critic_review(
                    record
                )

            if not winner:
                st.error(review)

            else:
                if save(
                    lambda: record.update(
                        recommended=winner,
                        review=review,
                    )
                ):
                    st.rerun()

    if record.get("review"):
        st.markdown(record["review"])

    choices = ["Bozza salvata"]

    if record["A"]:
        choices.append("Versione A")

    if record["B"]:
        choices.append("Versione B")

    choice = st.selectbox(
        "Testo da revisionare",
        choices,
        key=f"version_{sid}_{lane}_{narrator}",
    )

    if choice == "Versione A":
        initial = record["A"]

    elif choice == "Versione B":
        initial = record["B"]

    else:
        initial = record["draft"]

    editor_key = (
        f"editor_{sid}_{lane}_"
        f"{narrator}_{normalize(choice)}"
    )

    source_key = editor_key + "_source"

    if st.session_state.get(source_key) != initial:
        st.session_state[editor_key] = initial
        st.session_state[source_key] = initial

    edited = st.text_area(
        "Testo narrativo",
        height=350,
        key=editor_key,
    )

    reason = st.text_input(
        "Motivazione della modifica",
        key=f"approval_reason_{sid}_{lane}_{narrator}",
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA",
            key=f"save_draft_{sid}_{lane}_{narrator}",
        ):
            if save(
                lambda: record.update(
                    draft=edited,
                    status="bozza",
                )
            ):
                st.success("Bozza salvata.")

    with right:
        if st.button(
            "APPROVA E MEMORIZZA",
            key=f"approve_text_{sid}_{lane}_{narrator}",
            disabled=not edited.strip(),
        ):
            def change():
                previous = record["approved"]

                if previous and previous != edited:
                    record["history"].append({
                        "text": previous,
                        "replaced_at": now(),
                        "reason": reason,
                    })

                record["approved"] = edited
                record["draft"] = edited
                record["approved_at"] = now()
                record["status"] = "approvata"

                if (
                    lane == "shared"
                    and narrator in PROTAGONISTS
                ):
                    scene["diary"][narrator] = edited

                if previous != edited:
                    log_change(
                        "scena approvata",
                        scene["title"]
                        + "/"
                        + lane
                        + "/"
                        + narrator,
                        previous,
                        edited,
                        reason,
                        sid,
                    )

                    record["visual"][
                        "source_approved_at"
                    ] = ""

            if save(change):
                st.rerun()

    export_buttons(
        scene["title"],
        f"{sid}_{lane}_{narrator.lower()}",
        edited,
        f"export_{sid}_{lane}_{narrator}",
    )

    if record["approved"]:
        with st.expander(
            "TESTO APPROVATO"
        ):
            render_story_text(
                record["approved"]
            )

    with st.expander(
        "VERSIONI PRECEDENTI"
    ):
        for item in reversed(
            as_list(record["history"])
        ):
            st.caption(
                item.get("replaced_at", "")
            )

            st.code(
                difference(
                    item.get("text", ""),
                    record["approved"],
                ),
                language="diff",
            )

    with st.expander(
        "TRASCRIZIONE DELLA SCENA"
    ):
        st.text(
            transcript(scene, lane)
        )

    with st.expander(
        "OFFICINA VISIVA"
    ):
        if not record["approved"]:
            st.info(
                "Approva prima il racconto."
            )

        else:
            if st.button(
                "GENERA PROMPT VISIVI",
                key=f"visual_{sid}_{lane}_{narrator}",
                disabled=client is None,
            ):
                with st.spinner(
                    "Preparazione delle inquadrature..."
                ):
                    result = generate_visuals(
                        record
                    )

                if not isinstance(result, dict):
                    st.error(
                        "Generazione non riuscita."
                    )

                else:
                    def change():
                        record["visual"] = {
                            "bible": result.get(
                                "bible", ""
                            ),
                            "prompts": result.get(
                                "shots", []
                            ),
                            "source_approved_at":
                                record["approved_at"],
                        }

                    if save(change):
                        st.rerun()

            visual = record["visual"]

            if (
                visual.get("source_approved_at")
                == record["approved_at"]
            ):
                st.write(
                    visual.get("bible", "")
                )

                for index, shot in enumerate(
                    as_list(visual.get("prompts")),
                    1,
                ):
                    st.markdown(
                        f"**Inquadratura {index}**"
                    )

                    st.write(
                        shot.get("title", "")
                    )

                    st.code(
                        shot.get("image_prompt", "")
                    )

                    st.code(
                        shot.get("video_prompt", "")
                    )


# ==========================================================
# ARCHIVIO PERSONAGGI
# ==========================================================

def page_people():
    st.title("Archivio personaggi")

    person = st.selectbox(
        "Personaggio", PEOPLE
    )

    agent = book["agents"][person]

    st.subheader("Profilo approvato")
    st.write(agent["profile"])

    edited = st.text_area(
        "Modifica il profilo",
        value=agent["profile"],
        height=220,
        key=f"profile_{person}",
    )

    reason = st.text_input(
        "Motivazione",
        key=f"profile_reason_{person}",
    )

    if st.button(
        "APPROVA NUOVO PROFILO",
        disabled=(
            not edited.strip()
            or edited == agent["profile"]
        ),
    ):
        def change():
            previous = agent["profile"]

            agent["profile_history"].append({
                "profile": previous,
                "replaced_at": now(),
            })

            agent["profile"] = edited

            log_change(
                "profilo",
                person,
                previous,
                edited,
                reason,
            )

        if save(change):
            st.rerun()

    with st.expander(
        "BRANI DELLA PRIMA BOZZA"
    ):
        for index, passage in enumerate(
            reference_passages(
                [person], limit=4
            ),
            1,
        ):
            st.markdown(
                f"**Passaggio {index}**"
            )

            st.text(passage)


# ==========================================================
# ARCHIVIO SCENE
# ==========================================================

def page_archive():
    st.title("Archivio scene approvate")

    total = 0

    for sid in SCENE_IDS:
        scene = scene_for(sid)

        for person in PEOPLE:
            record = as_dict(
                scene["narrative"].get(person)
            )

            text = record.get(
                "approved", ""
            )

            if not text:
                continue

            total += 1

            with st.expander(
                scene["title"]
                + " / "
                + person
                + " / condivisa"
            ):
                render_story_text(text)

                export_buttons(
                    scene["title"],
                    f"{sid}_{person.lower()}_shared",
                    text,
                    f"archive_{sid}_{person}",
                )

        parallel_text = scene[
            "ada_parallel"
        ]["narrative"].get(
            "approved", ""
        )

        if parallel_text:
            total += 1

            title = (
                scene["ada_parallel"].get("title")
                or scene["title"]
            )

            with st.expander(
                title + " / ADA ALONE"
            ):
                render_story_text(
                    parallel_text
                )

                export_buttons(
                    title,
                    f"{sid}_ada_alone",
                    parallel_text,
                    f"archive_ada_{sid}",
                )

    if not total:
        st.info(
            "Nessuna scena approvata."
        )


# ==========================================================
# REGISTRO EDITORIALE
# ==========================================================

def page_editorial():
    st.title("Registro editoriale")

    tab_changes, tab_proposals = st.tabs([
        "MODIFICHE APPROVATE",
        "PROPOSTE",
    ])

    with tab_changes:
        for item in reversed(
            book["editorial_log"]
        ):
            label = (
                item.get("date", "")[:10]
                + " / "
                + item.get("subject", "")
            )

            with st.expander(label):
                st.write(
                    item.get("category", "")
                )

                st.write(
                    item.get("reason", "")
                )

                st.code(
                    difference(
                        item.get("before", ""),
                        item.get("after", ""),
                    ),
                    language="diff",
                )

    with tab_proposals:
        with st.form(
            "new_proposal",
            clear_on_submit=True,
        ):
            subject = st.text_input(
                "Personaggio o elemento narrativo"
            )

            before = st.text_area(
                "Situazione precedente"
            )

            after = st.text_area(
                "Proposta"
            )

            reason = st.text_area(
                "Motivazione"
            )

            submitted = st.form_submit_button(
                "SALVA PROPOSTA"
            )

        if submitted and subject.strip():
            def change():
                book["editorial_proposals"].append({
                    "subject": subject,
                    "before": before,
                    "after": after,
                    "reason": reason,
                    "date": now(),
                    "status": "proposta",
                })

            if save(change):
                st.rerun()

        for item in reversed(
            book["editorial_proposals"]
        ):
            with st.expander(
                item.get("subject", "")
            ):
                st.write(
                    item.get("reason", "")
                )

                st.code(
                    difference(
                        item.get("before", ""),
                        item.get("after", ""),
                    ),
                    language="diff",
                )

    st.download_button(
        "SCARICA REGISTRO JSON",
        json_text({
            "changes": book["editorial_log"],
            "proposals": book["editorial_proposals"],
        }).encode("utf-8"),
        file_name="turing_hotel_registro.json",
        mime="application/json",
    )


# ==========================================================
# INGRESSO
# ==========================================================

def find_asset(filename):
    if not ASSETS.is_dir():
        return None

    exact = ASSETS / filename

    if exact.is_file():
        return exact

    for path in ASSETS.iterdir():
        if (
            path.is_file()
            and path.name.casefold()
            == filename.casefold()
        ):
            return path

    return None


def page_entrance():
    hotel = find_asset(
        "TuringHotel.jpg"
    )

    if hotel:
        st.image(
            str(hotel),
            use_container_width=True,
        )

    st.title("TURING HOTEL")

    st.caption(
        "Un romanzo a più coscienze"
    )

    if st.button(
        "ENTRA AL TURING HOTEL",
        use_container_width=True,
    ):
        st.session_state.page = "characters"
        st.rerun()


def page_characters():
    st.title("Scegli una storia")

    columns = st.columns(2)

    for column, person in zip(
        columns,
        PROTAGONISTS,
    ):
        with column:
            portrait = find_asset(
                person + ".jpg"
            )

            if portrait:
                st.image(
                    str(portrait),
                    use_container_width=True,
                )

            st.subheader(person)

            if st.button(
                "ENTRA NELLA STORIA DI "
                + person.upper(),
                key=f"choose_{person}",
                use_container_width=True,
            ):
                st.session_state.pov = person
                st.session_state.scene_index = 0
                st.session_state.page = "story"
                st.rerun()


# ==========================================================
# SIDEBAR
# ==========================================================

def render_sidebar():
    index = st.session_state.scene_index
    pov = st.session_state.pov

    st.sidebar.title("TURING HOTEL")

    selected = st.sidebar.selectbox(
        "SCENA",
        SCENE_IDS,
        index=index,
        format_func=lambda sid: (
            f"{scene_number(sid) + 1:02d}"
            f" — {SCENE_NAMES[sid]}"
        ),
        key=f"scene_nav_{index}_{pov}",
    )

    if selected != SCENE_IDS[index]:
        st.session_state.scene_index = (
            scene_number(selected)
        )
        st.rerun()

    st.sidebar.caption(
        f"Scena {index + 1} di 31"
    )

    st.sidebar.markdown("---")

    for label, destination in [
        ("ARCHIVIO SCENE", "archive"),
        ("ARCHIVIO PERSONAGGI", "people"),
        ("REGISTRO EDITORIALE", "editorial"),
        ("CAMBIA STORIA", "characters"),
    ]:
        if st.sidebar.button(
            label,
            key="nav_" + destination,
            use_container_width=True,
        ):
            st.session_state.page = destination
            st.rerun()

    with st.sidebar.expander(
        "PRIMA BOZZA"
    ):
        load_reference()

        if st.session_state.reference_text:
            st.success(
                "Romanzo originale collegato."
            )

            st.caption(
                f"{len(st.session_state.reference_text):,}"
                " caratteri"
            )

        else:
            st.warning(
                st.session_state.reference_error
                or "Reference non disponibile."
            )

        st.code(REFERENCE_PATH)

        if st.button(
            "RICARICA ROMANZO ORIGINALE",
            key="reload_reference",
        ):
            load_reference(force=True)
            st.rerun()

    with st.sidebar.expander(
        "ARCHIVIO GITHUB"
    ):
        st.caption(
            GH_OWNER + "/" + GH_REPO
        )

        if st.button(
            "RICARICA ARCHIVIO",
            key="reload_archive",
        ):
            if reload_book():
                st.rerun()

        st.download_button(
            "SCARICA BACKUP",
            json_text(book).encode("utf-8"),
            file_name="turing_hotel_backup.json",
            mime="application/json",
        )


# ==========================================================
# PAGINA SCENA
# ==========================================================

def page_story():
    pov = st.session_state.pov

    index = max(
        0,
        min(
            st.session_state.scene_index,
            len(SCENE_IDS) - 1,
        ),
    )

    st.session_state.scene_index = index

    sid = SCENE_IDS[index]
    scene = scene_for(sid)

    render_sidebar()

    if (
        pov == "Ada"
        and ada_alone_at(sid)
    ):
        display_title = (
            scene["ada_parallel"].get("title")
            or scene["title"]
        )
    else:
        display_title = scene["title"]

    st.title(display_title)

    st.caption(
        f"Scena {index + 1} di 31"
        f" — Storia di {pov}"
    )

    render_ada_control(
        scene, pov
    )

    lane = lane_for(
        scene, pov
    )

    if lane == "ada_alone":
        st.markdown(
            '<div class="ada-banner">'
            "<strong>ADA ALONE</strong>"
            "<p>Stesso intervallo narrativo "
            "della scena di Noa. "
            "Altro luogo, Noa assente, "
            "conoscenze separate.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    render_media(
        scene, pov, lane
    )

    render_context(
        scene, lane, pov
    )

    render_advisor(
        scene, lane
    )

    render_dialogues(
        scene, lane
    )

    render_knowledge(
        scene, lane
    )

    if lane == "ada_alone":
        narrator = "Ada"

    else:
        narrators = lane_cast(
            scene, lane
        )

        if not narrators:
            narrators = [pov]

        narrator = st.selectbox(
            "PUNTO DI VISTA DEL RACCONTO",
            narrators,
            index=(
                narrators.index(pov)
                if pov in narrators
                else 0
            ),
            key=f"narrator_{sid}_{pov}",
        )

    render_workshop(
        scene,
        lane,
        narrator,
    )

    st.markdown("---")

    left, _, right = st.columns(
        [1, 3, 1]
    )

    with left:
        if index > 0:
            if st.button(
                "← PRECEDENTE"
            ):
                st.session_state.scene_index -= 1
                st.rerun()

    with right:
        if index < len(SCENE_IDS) - 1:
            if st.button(
                "SUCCESSIVA →"
            ):
                st.session_state.scene_index += 1
                st.rerun()


# ==========================================================
# INIZIALIZZAZIONE ARCHIVIO MANCANTE
# ==========================================================

if not st.session_state.archive_exists:
    st.title("Inizializzazione archivio")

    st.warning(
        "Non è stato trovato romanzo_web.json "
        "nel repository privato. "
        "Non creare un nuovo archivio "
        "se quello originale dovrebbe esserci."
    )

    confirmed = st.checkbox(
        "Confermo di voler creare "
        "un archivio nuovo"
    )

    if st.button(
        "CREA ARCHIVIO",
        disabled=not confirmed,
    ):
        try:
            sha = write_archive(
                book, None
            )

            st.session_state.archive_sha = sha
            st.session_state.archive_exists = True

            st.rerun()

        except Exception as exc:
            st.error(str(exc))

    st.stop()


# ==========================================================
# NAVIGAZIONE
# ==========================================================

if st.session_state.page in (
    "archive",
    "people",
    "editorial",
):
    if st.button(
        "← TORNA ALLA STORIA"
    ):
        st.session_state.page = "story"
        st.rerun()


if st.session_state.page == "entrance":
    page_entrance()

elif st.session_state.page == "characters":
    page_characters()

elif st.session_state.page == "story":
    page_story()

elif st.session_state.page == "archive":
    page_archive()

elif st.session_state.page == "people":
    page_people()

elif st.session_state.page == "editorial":
    page_editorial()

else:
    st.session_state.page = "entrance"
    st.rerun()
