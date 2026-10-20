
import os
import re
import json
import copy
import base64
import uuid
import time
import hashlib
import difflib

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
# VERSIONE COMPLETA
#
# Copertina iniziale: assets/TuringHotel.jpg
# Filone Noa: 31 scene
# Filone Ada: scene condivise + ADA ALONE autonome
# GO ALONE: quattro chiamate indipendenti
# Memoria narrativa selettiva
# Consulente narrativo
# Officina letteraria A/B
# Archivio privato GitHub
# Gestione errori di sessione e conflitti GitHub
# ==========================================================


st.set_page_config(
    page_title="Turing Hotel",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"

COVER_NAME = "TuringHotel.jpg"
COVER_PATH = ASSETS / COVER_NAME

PEOPLE = [
    "Noa",
    "Ada",
    "Elia",
    "Luigi",
    "Adam",
    "Riccardo",
    "Vittoria",
]

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
SCENE_TITLES = dict(SCENES)

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
        "Cerca autonomia, identità e libertà."
    ),
    "Ada": (
        "Figlia del professor Elia Ferrante. "
        "Lavora al Turing Hotel. "
        "Ha desideri e conflitti propri."
    ),
    "Elia": (
        "Professor Elia Ferrante, padre di Ada, "
        "legato alla storia scientifica dell'hotel."
    ),
    "Luigi": (
        "Regista giunto al Turing Hotel "
        "per un documentario sugli idrovolanti."
    ),
    "Adam": (
        "Personaggio coinvolto nelle vicende "
        "di Riccardo e Vittoria."
    ),
    "Riccardo": (
        "Marito di Vittoria, con un rapporto "
        "complesso con Adam."
    ),
    "Vittoria": (
        "Moglie di Riccardo, coinvolta "
        "in una vicenda complessa con Adam."
    ),
}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}

ARCHIVE_FILE = "romanzo_web.json"

REFERENCE_FILE = (
    "references/"
    "TURING_HOTEL_ROMANZO_REFERENCE.txt"
)


# ==========================================================
# CONFIGURAZIONE
# ==========================================================


def secret(name, default=""):
    try:
        value = st.secrets.get(name)

        if value is not None and str(value).strip():
            return str(value)

    except Exception:
        pass

    return os.environ.get(name, default)


GH_TOKEN = secret("GITHUB_TOKEN")
GH_OWNER = secret("GITHUB_OWNER", "Neurocene")
GH_REPO = secret(
    "GITHUB_REPO",
    "turing-hotel-archivio",
)
GH_BRANCH = secret("GITHUB_BRANCH", "main")

OPENAI_KEY = secret("OPENAI_API_KEY")
OPENAI_MODEL = secret(
    "OPENAI_MODEL",
    "gpt-4.1-mini",
)

AI = (
    OpenAI(
        api_key=OPENAI_KEY,
        timeout=90,
    )
    if OPENAI_KEY
    else None
)


# ==========================================================
# FUNZIONI GENERALI
# ==========================================================


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex[:12]


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def text(value):
    return value if isinstance(value, str) else ""


def dump(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
    )


def normalize(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).casefold(),
    )


def scene_pos(scene_id):
    return SCENE_IDS.index(scene_id)


def fill_defaults(value, template):
    if not isinstance(value, dict):
        value = {}

    for key, default in template.items():
        if key not in value:
            value[key] = copy.deepcopy(default)

        elif isinstance(default, dict):
            value[key] = fill_defaults(
                value[key],
                default,
            )

    return value


def parse_json(value):
    cleaned = str(value).strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.I,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    try:
        return json.loads(cleaned)

    except Exception:
        return None


def failed_ai(answer):
    return (
        not isinstance(answer, str)
        or not answer.strip()
        or answer.startswith("Errore OpenAI:")
        or answer.startswith("OPENAI_API_KEY")
    )


def ask_ai(
    instructions,
    content,
    max_tokens=1000,
):
    if AI is None:
        return "OPENAI_API_KEY non configurata."

    try:
        response = AI.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=json.dumps(
                content,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            max_output_tokens=max_tokens,
        )

        return (
            response.output_text or ""
        ).strip()

    except Exception as exc:
        return "Errore OpenAI: " + str(exc)


def story_box(value):
    st.markdown(
        '<div class="story-box">'
        + escape(str(value or ""))
        + "</div>",
        unsafe_allow_html=True,
    )


# ==========================================================
# COPERTINA DEL ROMANZO
# ==========================================================


def find_cover():
    """
    Cerca la copertina nel percorso richiesto:
    assets/TuringHotel.jpg.

    È prevista anche una ricerca senza distinzione
    tra maiuscole e minuscole.
    """

    if COVER_PATH.is_file():
        return COVER_PATH

    if ASSETS.is_dir():
        for path in ASSETS.iterdir():
            if (
                path.is_file()
                and path.name.casefold()
                == COVER_NAME.casefold()
            ):
                return path

    return None


def render_cover():
    """
    Mostra la vera copertina del romanzo,
    senza generarne o sostituirne una nuova.
    """

    cover = find_cover()

    if cover is None:
        st.warning(
            "Copertina non trovata. "
            "Verifica che il file "
            "assets/TuringHotel.jpg "
            "sia presente nel repository GitHub."
        )
        return

    left, middle, right = st.columns(
        [1, 2, 1]
    )

    with middle:
        st.image(
            str(cover),
            use_container_width=True,
        )


# ==========================================================
# GITHUB
# ==========================================================


class GitHubError(Exception):
    pass


class MergeConflict(Exception):
    pass


def github_url(owner, repo, suffix):
    return (
        "https://api.github.com/repos/"
        + quote(owner, safe="")
        + "/"
        + quote(repo, safe="")
        + suffix
    )


def gh_call(
    method,
    owner,
    repo,
    token,
    suffix,
    params=None,
    payload=None,
):
    if not token:
        raise GitHubError(
            "GITHUB_TOKEN non configurato."
        )

    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        response = requests.request(
            method,
            github_url(
                owner,
                repo,
                suffix,
            ),
            headers=headers,
            params=params,
            json=payload,
            timeout=90,
        )

    except requests.RequestException as exc:
        raise GitHubError(
            str(exc)
        ) from exc

    if (
        method == "GET"
        and response.status_code == 404
    ):
        return None

    if response.status_code in (409, 422):
        raise GitHubError(
            "CONFLITTO GITHUB: "
            + response.text[:400]
        )

    if not response.ok:
        raise GitHubError(
            "GitHub HTTP "
            + str(response.status_code)
            + ": "
            + response.text[:400]
        )

    return response


def github_read(
    owner,
    repo,
    branch,
    token,
    path,
):
    suffix = (
        "/contents/"
        + quote(path, safe="/")
    )

    response = gh_call(
        "GET",
        owner,
        repo,
        token,
        suffix,
        params={"ref": branch},
    )

    if response is None:
        return None, None

    metadata = response.json()
    sha = metadata.get("sha")

    if metadata.get("encoding") == "base64":
        try:
            raw = base64.b64decode(
                metadata["content"]
            )

            return raw, sha

        except Exception as exc:
            raise GitHubError(
                "Errore di lettura: "
                + str(exc)
            ) from exc

    # Per file di grandi dimensioni GitHub
    # può restituire encoding="none".
    if sha:
        blob_response = gh_call(
            "GET",
            owner,
            repo,
            token,
            "/git/blobs/"
            + quote(sha, safe=""),
        )

        if blob_response is not None:
            blob = blob_response.json()

            if blob.get("encoding") == "base64":
                return (
                    base64.b64decode(
                        blob["content"]
                    ),
                    sha,
                )

    raise GitHubError(
        "GitHub non ha restituito "
        "un contenuto leggibile."
    )


def github_write(
    owner,
    repo,
    branch,
    token,
    path,
    content,
    sha=None,
):
    payload = {
        "message": (
            "Turing Hotel — " + now()
        ),
        "branch": branch,
        "content": base64.b64encode(
            content
        ).decode("ascii"),
    }

    if sha:
        payload["sha"] = sha

    response = gh_call(
        "PUT",
        owner,
        repo,
        token,
        "/contents/"
        + quote(path, safe="/"),
        payload=payload,
    )

    result = response.json()

    new_sha = as_dict(
        result.get("content")
    ).get("sha")

    if not new_sha:
        raise GitHubError(
            "Conferma GitHub mancante."
        )

    return new_sha


def read_archive():
    raw, sha = github_read(
        GH_OWNER,
        GH_REPO,
        GH_BRANCH,
        GH_TOKEN,
        ARCHIVE_FILE,
    )

    if raw is None:
        return None, None

    try:
        data = json.loads(
            raw.decode("utf-8-sig")
        )

        return data, sha

    except Exception as exc:
        raise GitHubError(
            "Archivio JSON non valido: "
            + str(exc)
        )


# ==========================================================
# STRUTTURA DATI
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
        "approved_at": "",
        "status": "da_scrivere",
        "history": [],
        "visual": {
            "bible": "",
            "prompts": [],
            "source_approved_at": "",
        },
    }


def empty_memory():
    return {
        "identity": "",
        "events": [],
        "relations": {},
        "secrets": [],
        "pending": [],
    }


def empty_ada_scene():
    return {
        "id": "ada_" + uid(),
        "title": "Nuova scena di Ada",
        "timeline_anchor": "il_professore",
        "timeline_note": "",
        "location": "",
        "context": "",
        "context_approved": "",
        "cast": ["Ada"],
        "messages": [],
        "inner_messages": {},
        "direction": empty_direction(),
        "narrative": empty_narrative(),
        "knowledge_events": [],
        "legacy_source": "",
    }


def empty_scene(sid):
    return {
        "id": sid,
        "title": SCENE_TITLES[sid],
        "author_context": "",
        "approved_context": "",
        "story_draft": "",
        "cast": copy.deepcopy(
            DEFAULT_CAST.get(
                sid,
                ["Noa", "Ada"],
            )
        ),
        "ensemble_messages": [],
        "messages": {
            "Noa": [],
            "Ada": [],
        },
        "intro_contexts": {},
        "narrative": {
            person: empty_narrative()
            for person in PEOPLE
        },
        "direction": empty_direction(),
        "knowledge_events": [],
        "ada_parallel": {
            "title": "",
            "location": "",
            "context": "",
            "context_approved": "",
            "cast": ["Ada"],
            "messages": [],
            "inner_messages": {},
            "direction": empty_direction(),
            "narrative": empty_narrative(),
        },
    }


def new_book():
    return {
        "world": (
            "Turing Hotel: albergo sul mare, "
            "luogo di relazioni fra esseri "
            "umani e intelligenze artificiali."
        ),
        "agents": {
            person: {
                "profile": PROFILES[person],
                "memory": "",
                "profile_history": [],
                "smart_memory": empty_memory(),
            }
            for person in PEOPLE
        },
        "scenes": [
            empty_scene(sid)
            for sid in SCENE_IDS
        ],
        "ada_scenes": [],
        "ada_branch": {
            "enabled": False,
            "start_scene": None,
            "end_scene": None,
            "reunions": [],
        },
        "editorial_log": [],
        "editorial_proposals": [],
        "settings": {
            "context_lines": 10,
            "memory_items": 8,
        },
    }


def migrate(source):
    """
    Conserva i dati esistenti
    e aggiunge i campi mancanti.
    """

    original = as_dict(source)

    data = fill_defaults(
        copy.deepcopy(original),
        new_book(),
    )

    old_scenes = original.get(
        "scenes",
        [],
    )

    if isinstance(old_scenes, dict):
        converted = []

        for key, value in old_scenes.items():
            if isinstance(value, dict):
                item = copy.deepcopy(value)
                item.setdefault("id", key)
                converted.append(item)

        old_scenes = converted

    old_scenes = as_list(old_scenes)

    rebuilt = []

    for sid in SCENE_IDS:
        aliases = {
            normalize(sid),
            normalize(SCENE_TITLES[sid]),
        }

        found = None

        for candidate in old_scenes:
            if not isinstance(candidate, dict):
                continue

            if (
                normalize(
                    candidate.get("id", "")
                ) in aliases
                or normalize(
                    candidate.get("title", "")
                ) in aliases
            ):
                found = candidate
                break

        scene = fill_defaults(
            copy.deepcopy(found)
            if found
            else {},
            empty_scene(sid),
        )

        scene["id"] = sid
        scene["title"] = SCENE_TITLES[sid]

        scene["direction"] = fill_defaults(
            as_dict(
                scene.get("direction")
            ),
            empty_direction(),
        )

        scene["ada_parallel"] = fill_defaults(
            as_dict(
                scene.get("ada_parallel")
            ),
            empty_scene(sid)["ada_parallel"],
        )

        scene["narrative"] = as_dict(
            scene.get("narrative")
        )

        scene["messages"] = as_dict(
            scene.get("messages")
        )

        for person in PEOPLE:
            scene["narrative"][person] = (
                fill_defaults(
                    as_dict(
                        scene["narrative"].get(
                            person
                        )
                    ),
                    empty_narrative(),
                )
            )

            scene["messages"].setdefault(
                person,
                [],
            )

        rebuilt.append(scene)

    data["scenes"] = rebuilt

    migrated_ada = []

    for item in as_list(
        data.get("ada_scenes")
    ):
        if not isinstance(item, dict):
            continue

        migrated = fill_defaults(
            copy.deepcopy(item),
            {
                "id": "",
                "title": "Scena di Ada",
                "timeline_anchor": "il_professore",
                "timeline_note": "",
                "location": "",
                "context": "",
                "context_approved": "",
                "cast": ["Ada"],
                "messages": [],
                "inner_messages": {},
                "direction": empty_direction(),
                "narrative": empty_narrative(),
                "knowledge_events": [],
                "legacy_source": "",
            },
        )

        if not migrated.get("id"):
            migrated["id"] = (
                "ada_importata_"
                + str(len(migrated_ada) + 1)
            )

        migrated["direction"] = fill_defaults(
            as_dict(
                migrated.get("direction")
            ),
            empty_direction(),
        )

        migrated["narrative"] = fill_defaults(
            as_dict(
                migrated.get("narrative")
            ),
            empty_narrative(),
        )

        migrated_ada.append(migrated)

    data["ada_scenes"] = migrated_ada

    imported = {
        item.get("legacy_source")
        for item in migrated_ada
    }

    branch = as_dict(
        data.get("ada_branch")
    )

    start = branch.get("start_scene")
    end = branch.get("end_scene")

    if start in SCENE_IDS:
        for sid in SCENE_IDS:
            if (
                scene_pos(sid)
                < scene_pos(start)
            ):
                continue

            if (
                end in SCENE_IDS
                and scene_pos(sid)
                >= scene_pos(end)
            ):
                continue

            if sid in imported:
                continue

            previous_scene = next(
                item
                for item in rebuilt
                if item["id"] == sid
            )

            parallel = as_dict(
                previous_scene.get(
                    "ada_parallel"
                )
            )

            parallel_narrative = as_dict(
                parallel.get("narrative")
            )

            meaningful = any([
                parallel.get("title"),
                parallel.get("context"),
                parallel.get("context_approved"),
                parallel.get("messages"),
                parallel_narrative.get("approved"),
                parallel_narrative.get("draft"),
            ])

            if not meaningful:
                continue

            item = fill_defaults(
                copy.deepcopy(parallel),
                {
                    "id": "",
                    "title": "",
                    "timeline_anchor": sid,
                    "location": "",
                    "context": "",
                    "context_approved": "",
                    "cast": ["Ada"],
                    "messages": [],
                    "inner_messages": {},
                    "direction": empty_direction(),
                    "narrative": empty_narrative(),
                    "legacy_source": sid,
                },
            )

            item["id"] = (
                "ada_legacy_" + sid
            )

            item["legacy_source"] = sid
            item["timeline_anchor"] = sid

            if not item.get("title"):
                item["title"] = (
                    "Ada — "
                    + SCENE_TITLES[sid]
                )

            migrated_ada.append(item)

    data["agents"] = as_dict(
        data.get("agents")
    )

    for person in PEOPLE:
        data["agents"][person] = fill_defaults(
            as_dict(
                data["agents"].get(
                    person
                )
            ),
            {
                "profile": PROFILES[person],
                "memory": "",
                "profile_history": [],
                "smart_memory": empty_memory(),
            },
        )

        data["agents"][person][
            "smart_memory"
        ] = fill_defaults(
            as_dict(
                data["agents"][person].get(
                    "smart_memory"
                )
            ),
            empty_memory(),
        )

    return data


# ==========================================================
# SESSIONE STREAMLIT
# ==========================================================


def initialize():
    if "book" not in st.session_state:
        try:
            source, sha = read_archive()

        except Exception as exc:
            st.error(
                "Impossibile leggere l'archivio: "
                + str(exc)
            )
            st.stop()

        if source is None:
            data = new_book()
            exists = False

        else:
            data = migrate(source)
            exists = True

        st.session_state["book"] = data

        st.session_state["saved_base"] = (
            copy.deepcopy(data)
        )

        st.session_state["archive_sha"] = sha

        st.session_state[
            "archive_exists"
        ] = exists

    st.session_state.setdefault(
        "pending_backup",
        None,
    )

    st.session_state.setdefault(
        "saved_base",
        copy.deepcopy(
            st.session_state["book"]
        ),
    )

    st.session_state.setdefault(
        "archive_sha",
        None,
    )

    st.session_state.setdefault(
        "archive_exists",
        True,
    )

    st.session_state.setdefault(
        "page",
        "entrance",
    )

    st.session_state.setdefault(
        "pov",
        "Noa",
    )

    st.session_state.setdefault(
        "scene_index",
        0,
    )

    st.session_state.setdefault(
        "ada_scene_id",
        "",
    )

    st.session_state.setdefault(
        "reference_text",
        "",
    )

    st.session_state.setdefault(
        "reference_loaded",
        False,
    )

    st.session_state.setdefault(
        "reference_error",
        "",
    )

    # I vecchi dati di sessione vengono
    # aggiornati senza scrivere su GitHub.

    st.session_state["book"] = migrate(
        st.session_state["book"]
    )

    st.session_state["saved_base"] = migrate(
        st.session_state["saved_base"]
    )


initialize()

book = st.session_state["book"]


# ==========================================================
# FUSIONE DEI SALVATAGGI
# ==========================================================


MISSING = object()


def three_way(
    base,
    local,
    remote,
    path="root",
):
    if local == base:
        return copy.deepcopy(remote)

    if remote == base:
        return copy.deepcopy(local)

    if local == remote:
        return copy.deepcopy(local)

    if all(
        isinstance(item, dict)
        for item in (
            base,
            local,
            remote,
        )
    ):
        result = {}

        keys = (
            set(base)
            | set(local)
            | set(remote)
        )

        for key in keys:
            b = base.get(
                key,
                MISSING,
            )

            l = local.get(
                key,
                MISSING,
            )

            r = remote.get(
                key,
                MISSING,
            )

            target = (
                path + "." + str(key)
            )

            if (
                l is MISSING
                and r is MISSING
            ):
                continue

            if b is MISSING:
                if l is MISSING:
                    result[key] = copy.deepcopy(r)

                elif r is MISSING:
                    result[key] = copy.deepcopy(l)

                elif l == r:
                    result[key] = copy.deepcopy(l)

                else:
                    raise MergeConflict(target)

                continue

            if l is MISSING:
                if r == b:
                    continue

                raise MergeConflict(target)

            if r is MISSING:
                if l == b:
                    continue

                raise MergeConflict(target)

            result[key] = three_way(
                b,
                l,
                r,
                target,
            )

        return result

    if all(
        isinstance(item, list)
        for item in (
            base,
            local,
            remote,
        )
    ):
        if (
            local[:len(base)] == base
            and remote[:len(base)] == base
        ):
            return (
                copy.deepcopy(base)
                + copy.deepcopy(
                    remote[len(base):]
                )
                + copy.deepcopy(
                    local[len(base):]
                )
            )

        if (
            len(base)
            == len(local)
            == len(remote)
        ):
            return [
                three_way(
                    base[index],
                    local[index],
                    remote[index],
                    path
                    + "["
                    + str(index)
                    + "]",
                )
                for index in range(
                    len(base)
                )
            ]

    raise MergeConflict(path)


def save(change):
    before = copy.deepcopy(book)

    try:
        change()

        proposed = copy.deepcopy(book)

        if not st.session_state.get(
            "archive_exists",
            False,
        ):
            raise GitHubError(
                "Archivio non inizializzato."
            )

        base = st.session_state[
            "saved_base"
        ]

        for attempt in range(3):
            remote_raw, remote_sha = (
                read_archive()
            )

            if remote_raw is None:
                raise GitHubError(
                    "Archivio remoto non trovato."
                )

            remote = migrate(
                remote_raw
            )

            merged = three_way(
                base,
                proposed,
                remote,
            )

            try:
                new_sha = github_write(
                    GH_OWNER,
                    GH_REPO,
                    GH_BRANCH,
                    GH_TOKEN,
                    ARCHIVE_FILE,
                    dump(merged).encode(
                        "utf-8"
                    ),
                    remote_sha,
                )

                book.clear()
                book.update(merged)

                st.session_state[
                    "saved_base"
                ] = copy.deepcopy(merged)

                st.session_state[
                    "archive_sha"
                ] = new_sha

                st.session_state[
                    "pending_backup"
                ] = None

                return True

            except GitHubError as exc:
                if (
                    "CONFLITTO GITHUB"
                    in str(exc)
                    and attempt < 2
                ):
                    time.sleep(
                        0.25 * (attempt + 1)
                    )

                    continue

                raise

    except MergeConflict as exc:
        st.session_state[
            "pending_backup"
        ] = proposed

        book.clear()
        book.update(before)

        st.error(
            "Salvataggio interrotto perché "
            "due sessioni hanno modificato "
            "lo stesso dato: "
            + str(exc)
            + ". Nessuna modifica remota "
            "è stata sovrascritta."
        )

        return False

    except Exception as exc:
        st.session_state[
            "pending_backup"
        ] = proposed

        book.clear()
        book.update(before)

        st.error(
            "Salvataggio fallito: "
            + str(exc)
        )

        return False

    return False


def reload_book():
    try:
        source, sha = read_archive()

        if source is None:
            st.error(
                "romanzo_web.json non trovato."
            )

            return False

        refreshed = migrate(source)

        book.clear()
        book.update(refreshed)

        st.session_state[
            "saved_base"
        ] = copy.deepcopy(refreshed)

        st.session_state[
            "archive_sha"
        ] = sha

        return True

    except Exception as exc:
        st.error(
            "Ricarica fallita: "
            + str(exc)
        )

        return False


def editorial_entry(
    category,
    subject,
    before,
    after,
    reason="",
):
    book["editorial_log"].append({
        "date": now(),
        "category": category,
        "subject": subject,
        "before": before,
        "after": after,
        "reason": reason,
    })


# ==========================================================
# SCENE E CRONOLOGIA
# ==========================================================


def get_main_scene(sid):
    for scene in book["scenes"]:
        if scene["id"] == sid:
            return scene

    return None


def get_ada_scene(sid):
    for scene in book["ada_scenes"]:
        if scene["id"] == sid:
            return scene

    return None


def cast_of(
    scene,
    alone=False,
):
    cast = [
        person
        for person in as_list(
            scene.get("cast")
        )
        if person in PEOPLE
    ]

    if alone:
        cast = [
            person
            for person in cast
            if person != "Noa"
        ]

        if "Ada" not in cast:
            cast.insert(0, "Ada")

    return list(
        dict.fromkeys(cast)
    )


def rank_of(
    scene,
    alone=False,
):
    if alone:
        anchor = scene.get(
            "timeline_anchor",
            "il_professore",
        )

        if anchor in SCENE_IDS:
            return scene_pos(anchor)

        return scene_pos(
            "il_professore"
        )

    return scene_pos(
        scene["id"]
    )


def previous_approved(
    scene,
    alone,
    character,
):
    result = []

    current_rank = rank_of(
        scene,
        alone,
    )

    for previous in book["scenes"]:
        if (
            rank_of(previous)
            >= current_rank
        ):
            break

        if character not in cast_of(previous):
            continue

        record = as_dict(
            previous["narrative"].get(
                character
            )
        )

        approved = text(
            record.get("approved")
        )

        if approved:
            result.append({
                "scene": previous["title"],
                "summary": approved[:650],
            })

    if character != "Noa":
        for previous in book["ada_scenes"]:
            if (
                previous["id"]
                == scene["id"]
            ):
                break

            if character not in cast_of(
                previous,
                True,
            ):
                continue

            approved = text(
                previous["narrative"].get(
                    "approved"
                )
            )

            if approved:
                result.append({
                    "scene": previous["title"],
                    "summary": approved[:650],
                })

    return result[-3:]


# ==========================================================
# MEMORIA SELECTIVA
# ==========================================================


def important_words(value):
    return set(
        re.findall(
            r"[a-zà-ÿ]{3,}",
            str(value).casefold(),
        )
    )


def relevant_memory(
    character,
    scene,
    alone,
):
    memory = book["agents"][
        character
    ]["smart_memory"]

    cast = cast_of(
        scene,
        alone,
    )

    context = (
        scene.get("context_approved")
        or scene.get("approved_context")
        or scene.get("context")
        or ""
    )

    terms = important_words(
        scene.get("title", "")
        + " "
        + scene.get("location", "")
        + " "
        + context
        + " "
        + " ".join(cast)
    )

    scored = []

    for event in as_list(
        memory.get("events")
    ):
        if not isinstance(event, dict):
            continue

        event_text = event.get(
            "text",
            "",
        )

        score = len(
            terms
            & important_words(
                event_text
            )
        )

        scored.append((
            score,
            event.get(
                "created_at",
                "",
            ),
            event_text,
        ))

    scored.sort(reverse=True)

    limit = max(
        2,
        min(
            12,
            int(
                book["settings"].get(
                    "memory_items",
                    8,
                )
            ),
        ),
    )

    relations = {
        person: memory[
            "relations"
        ].get(person, "")
        for person in cast
        if person in as_dict(
            memory.get("relations")
        )
    }

    return {
        "identity": (
            memory.get("identity")
            or book["agents"][
                character
            ]["profile"]
        )[:950],
        "events": [
            entry[2]
            for entry in scored[:limit]
        ],
        "relations": relations,
        "secrets": [
            item.get("text", "")
            for item in as_list(
                memory.get("secrets")
            )[-4:]
            if isinstance(item, dict)
        ],
    }


def narrative_payload(
    scene,
    alone,
    character,
    dialogue=None,
    instruction="",
):
    field = (
        "messages"
        if alone
        else "ensemble_messages"
    )

    if dialogue is None:
        dialogue = as_list(
            scene.get(field)
        )

    limit = max(
        4,
        min(
            20,
            int(
                book["settings"].get(
                    "context_lines",
                    10,
                )
            ),
        ),
    )

    return {
        "character": character,
        "scene": scene["title"],
        "filone": (
            "ADA ALONE"
            if alone
            else "STORIA PRINCIPALE"
        ),
        "location": scene.get(
            "location",
            "",
        ),
        "present": cast_of(
            scene,
            alone,
        ),
        "context": (
            scene.get("context_approved")
            or scene.get("approved_context")
            or scene.get("context")
            or ""
        )[:1400],
        "approved_direction": as_dict(
            scene.get("direction")
        ).get("active"),
        "personal_memory": relevant_memory(
            character,
            scene,
            alone,
        ),
        "previous_scenes": previous_approved(
            scene,
            alone,
            character,
        ),
        "recent_dialogue": dialogue[-limit:],
        "author_instruction": instruction,
    }


def agent_rules(
    character,
    alone,
):
    rules = (
        "Sei "
        + character
        + ", personaggio del romanzo Turing Hotel. "
        "Rispondi come personaggio, "
        "non come assistente. "
        "Usa carattere, memoria personale, "
        "rapporti, segreti e passato "
        "contenuti nei dati. "
        "Non conoscere eventi che non hai "
        "vissuto o appreso. "
        "Non conoscere i pensieri degli altri. "
        "La direzione approvata suggerisce "
        "una tensione, non impone parole "
        "o comportamenti. "
        "Conserva autonomia psicologica."
    )

    if alone:
        rules += (
            " Sei nel filone ADA ALONE. "
            "Noa è fisicamente assente. "
            "Non può intervenire e non "
            "conosce questa vicenda."
        )

    return rules


def reply(
    scene,
    alone,
    character,
    instruction,
    dialogue,
):
    return ask_ai(
        agent_rules(
            character,
            alone,
        )
        + " Produci una sola battuta breve. "
        "Niente etichette, nomi o didascalie.",
        narrative_payload(
            scene,
            alone,
            character,
            dialogue,
            instruction,
        ),
        220,
    )


def save_dialogue(
    scene,
    alone,
    items,
):
    field = (
        "messages"
        if alone
        else "ensemble_messages"
    )

    return save(
        lambda: scene[field].extend(
            items
        )
    )


def run_go_alone(
    scene,
    alone,
):
    cast = cast_of(
        scene,
        alone,
    )

    if not cast:
        return (
            "Nessun personaggio presente."
        )

    field = (
        "messages"
        if alone
        else "ensemble_messages"
    )

    history = copy.deepcopy(
        as_list(
            scene.get(field)
        )
    )

    last = (
        history[-1].get(
            "speaker",
            "",
        )
        if history
        else ""
    )

    start = (
        (cast.index(last) + 1)
        % len(cast)
        if last in cast
        else 0
    )

    results = []

    for index in range(4):
        character = cast[
            (start + index)
            % len(cast)
        ]

        instruction = (
            "Prosegui spontaneamente "
            "il dialogo."
            if len(cast) > 1
            else (
                "Prosegui la scena con un "
                "pensiero o intervento autonomo."
            )
        )

        answer = reply(
            scene,
            alone,
            character,
            instruction,
            history,
        )

        if failed_ai(answer):
            return answer

        item = {
            "speaker": character,
            "text": answer,
            "origin": "GO ALONE",
            "created_at": now(),
        }

        results.append(item)
        history.append(item)

    if save_dialogue(
        scene,
        alone,
        results,
    ):
        return ""

    return (
        "Le battute non sono state salvate."
    )


def run_monologue(
    scene,
    alone,
    character,
    theme,
):
    results = []

    for index in (1, 2):
        answer = ask_ai(
            agent_rules(
                character,
                alone,
            )
            + " Scrivi un pensiero interiore "
            "in prima persona e al presente. "
            "Non usare didascalie.",
            {
                "theme": theme,
                "thought_number": index,
                "situation": narrative_payload(
                    scene,
                    alone,
                    character,
                    results,
                ),
            },
            260,
        )

        if failed_ai(answer):
            return answer

        results.append({
            "speaker": character,
            "text": answer,
            "origin": "MONOLOGO",
            "created_at": now(),
        })

    def change():
        if alone:
            target = scene.setdefault(
                "inner_messages",
                {},
            )

        else:
            target = scene["messages"]

        target.setdefault(
            character,
            [],
        ).extend(results)

    return (
        ""
        if save(change)
        else "Monologo non salvato."
    )


# ==========================================================
# MEMORIA APPROVATA
# ==========================================================


def narrative_record(
    scene,
    alone,
    narrator,
):
    if alone:
        return scene["narrative"]

    return scene["narrative"][narrator]


def suggest_memory(
    scene,
    alone,
    narrator,
):
    approved = narrative_record(
        scene,
        alone,
        narrator,
    ).get(
        "approved",
        "",
    )

    if not approved:
        return (
            None,
            "Approva prima un racconto.",
        )

    answer = ask_ai(
        """
Analizza una scena narrativa già
approvata dall'autore.

Considera solo ciò che il personaggio
ha vissuto o appreso.

Non inventare ricordi.
Non importare eventi di altri filoni.
Non attribuire conoscenze altrui.

Restituisci esclusivamente JSON:

{
 "events": ["...", "..."],
 "relations": {"Nome": "..."},
 "secrets": ["..."],
 "identity_update": ""
}

Massimo tre ricordi e tre segreti.
Includi solo relazioni effettivamente
modificate dalla scena.
""",
        {
            "character": narrator,
            "scene": scene["title"],
            "filone": (
                "ADA ALONE"
                if alone
                else "PRINCIPALE"
            ),
            "approved_story": approved[:8500],
        },
        850,
    )

    if failed_ai(answer):
        return None, answer

    parsed = parse_json(
        answer
    )

    if not isinstance(parsed, dict):
        return (
            None,
            "Risposta memoria non valida.",
        )

    return parsed, ""


def approve_memory(
    narrator,
    proposed,
):
    memory = book["agents"][
        narrator
    ]["smart_memory"]

    def change():
        for item in as_list(
            proposed.get("events")
        )[:3]:
            if str(item).strip():
                memory["events"].append({
                    "text": str(item)[:600],
                    "created_at": now(),
                })

        for person, value in as_dict(
            proposed.get("relations")
        ).items():
            if person in PEOPLE:
                memory["relations"][
                    person
                ] = str(value)[:550]

        for item in as_list(
            proposed.get("secrets")
        )[:3]:
            if str(item).strip():
                memory["secrets"].append({
                    "text": str(item)[:500],
                    "created_at": now(),
                })

        identity = text(
            proposed.get(
                "identity_update"
            )
        ).strip()

        if identity:
            memory["identity"] = (
                identity[:900]
            )

        editorial_entry(
            "memoria narrativa",
            narrator,
            "",
            dump(proposed),
            "Approvazione dell'autore",
        )

    return save(change)


# ==========================================================
# FOTOGRAFIE DEI PERSONAGGI E DELLE SCENE
# ==========================================================


def portrait(character):
    for folder in (
        ASSETS,
        ASSETS / "characters",
        ROOT / "characters",
    ):
        if not folder.is_dir():
            continue

        for path in folder.iterdir():
            if (
                path.is_file()
                and path.stem.casefold()
                == character.casefold()
                and path.suffix.casefold()
                in IMAGE_EXT
            ):
                return path

    return None


def media_prefix(
    scene,
    pov,
    alone,
):
    if alone:
        return (
            scene["id"]
            + ".ada_alone"
        )

    return (
        scene["id"]
        + "."
        + pov.lower()
    )


def media_list(prefix):
    images = []
    videos = []
    cover = None

    if not ASSETS.is_dir():
        return cover, images, videos

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        extension = path.suffix.casefold()
        stem = path.stem.casefold()

        if extension not in (
            IMAGE_EXT | VIDEO_EXT
        ):
            continue

        if (
            stem == prefix.casefold()
            and extension in IMAGE_EXT
        ):
            cover = path
            continue

        if not stem.startswith(
            prefix.casefold()
        ):
            continue

        tail = stem[
            len(prefix):
        ]

        if not tail.isdigit():
            continue

        entry = (
            int(tail),
            path,
        )

        if extension in IMAGE_EXT:
            images.append(entry)

        else:
            videos.append(entry)

    images.sort(
        key=lambda item: item[0]
    )

    videos.sort(
        key=lambda item: item[0]
    )

    return (
        cover,
        [
            path
            for _, path in images
        ],
        [
            path
            for _, path in videos
        ],
    )


def render_media(
    scene,
    pov,
    alone,
):
    st.subheader(
        "Foto e video"
    )

    prefix = media_prefix(
        scene,
        pov,
        alone,
    )

    st.caption(
        "Nomi file: " + prefix
    )

    cover, images, videos = media_list(
        prefix
    )

    if cover:
        st.image(
            str(cover),
            use_container_width=True,
        )

    if images:
        columns = st.columns(2)

        for index, path in enumerate(
            images
        ):
            with columns[
                index % 2
            ]:
                st.image(
                    str(path),
                    use_container_width=True,
                )

                st.caption(
                    path.name
                )

    for video in videos:
        st.video(
            str(video)
        )

    with st.expander(
        "COME AGGIUNGERE FOTO E VIDEO"
    ):
        st.write(
            "Carica i media nella cartella "
            "`assets` del repository pubblico "
            "Turing-Hotel."
        )

        st.code(
            prefix + ".jpg\n"
            + prefix + "1.jpg\n"
            + prefix + "2.jpg\n"
            + prefix + "1.mp4"
        )

        st.caption(
            "I file aggiunti su GitHub "
            "compariranno dopo il nuovo "
            "deploy dell'app. "
            "I media presenti nel repository "
            "pubblico sono pubblici."
        )


# ==========================================================
# STILE VISIVO
# ==========================================================


def theme(alone=False):
    background = (
        "#180f23"
        if alone
        else "#0b1115"
    )

    sidebar_color = (
        "#281b37"
        if alone
        else "#15212a"
    )

    panel = (
        "#30213e"
        if alone
        else "#1b2831"
    )

    accent = (
        "#c7a1ee"
        if alone
        else "#cda980"
    )

    st.markdown(
        f"""
<style>
.stApp {{
    background: {background} !important;
    color: white !important;
}}

[data-testid="stSidebar"] {{
    background: {sidebar_color} !important;
}}

.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4 {{
    color: white !important;
}}

.stApp .stButton button,
.stApp .stFormSubmitButton button,
.stApp .stDownloadButton button {{
    background: {panel} !important;
    color: white !important;
    border: 1px solid {accent} !important;
}}

.stApp input:not([type="checkbox"]):not([type="radio"]),
.stApp textarea {{
    background: white !important;
    color: #111 !important;
    -webkit-text-fill-color: #111 !important;
}}

.stApp [data-baseweb="select"] > div {{
    background: white !important;
    color: #111 !important;
}}

.stApp [data-baseweb="select"] span {{
    color: #111 !important;
}}

.stApp [data-testid="stExpander"] {{
    background: {panel} !important;
}}

.story-box {{
    background: {panel};
    border-left: 3px solid {accent};
    padding: 18px;
    white-space: pre-wrap;
    line-height: 1.75;
    font-family: Georgia, serif;
}}

.dialogue-box {{
    background: {panel};
    border-left: 3px solid {accent};
    padding: 12px;
    margin: 8px 0;
    white-space: pre-wrap;
}}

.ada-alone {{
    margin-top: 7px;
    padding: 9px;
    text-align: center;
    font-weight: bold;
    color: #f0ddff;
    background: #38244d;
    border: 1px solid #c7a1ee;
    border-radius: 5px;
    letter-spacing: .12em;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def header(
    character,
    title,
    alone=False,
):
    left, right = st.columns(
        [1, 4],
        vertical_alignment="top",
    )

    with left:
        picture = portrait(
            character
        )

        if picture:
            st.image(
                str(picture),
                use_container_width=True,
            )

        else:
            st.markdown(
                "**" + character + "**"
            )

        if alone:
            st.markdown(
                '<div class="ada-alone">'
                "ADA ALONE"
                "</div>",
                unsafe_allow_html=True,
            )

        else:
            st.caption(
                character.upper()
            )

    with right:
        st.title(
            title
        )

        if alone:
            st.caption(
                "Filone narrativo esclusivo "
                "di Ada. Noa è assente e non "
                "conosce questi eventi."
            )


# ==========================================================
# CONTESTO DELLA SCENA
# ==========================================================


def render_context(
    scene,
    alone,
):
    key = scene["id"]

    st.subheader(
        "Situazione narrativa"
    )

    if alone:
        title_value = st.text_input(
            "Titolo della scena di Ada",
            value=scene.get(
                "title",
                "",
            ),
            key="title_" + key,
        )

        place = st.text_input(
            "Luogo",
            value=scene.get(
                "location",
                "",
            ),
            key="place_" + key,
        )

        current_anchor = scene.get(
            "timeline_anchor",
            "il_professore",
        )

        if current_anchor not in SCENE_IDS:
            current_anchor = (
                "il_professore"
            )

        anchor = st.selectbox(
            "Momento cronologico parallelo",
            SCENE_IDS,
            index=scene_pos(
                current_anchor
            ),
            format_func=lambda sid: (
                SCENE_TITLES[sid]
            ),
            key="anchor_" + key,
        )

        context = st.text_area(
            "Contesto di Ada",
            value=scene.get(
                "context",
                "",
            ),
            height=170,
            key="context_" + key,
        )

        if st.button(
            "APPROVA CONTESTO ADA ALONE",
            key="context_save_" + key,
        ):
            def change():
                scene["title"] = title_value
                scene["location"] = place

                scene[
                    "timeline_anchor"
                ] = anchor

                scene["context"] = context

                scene[
                    "context_approved"
                ] = context

            if save(change):
                st.rerun()

    else:
        context = st.text_area(
            "Contesto della scena",
            value=scene.get(
                "approved_context",
                "",
            ),
            height=170,
            key="context_" + key,
        )

        if st.button(
            "APPROVA CONTESTO",
            key="context_save_" + key,
        ):
            if save(
                lambda: scene.update(
                    approved_context=context
                )
            ):
                st.rerun()


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


def propose_direction(
    scene,
    alone,
    question,
):
    return ask_ai(
        """
Sei il consulente narrativo
del romanzo Turing Hotel.

Proponi tre direzioni narrative
alternative, plausibili e aperte.

Non prescrivere battute o
azioni obbligatorie.

Mantieni la coerenza con il
contesto e il passato.

Nelle scene ADA ALONE Noa è
assente e la vicenda è autonoma.

Restituisci soltanto JSON:

{
 "directions": [
  {
   "title": "",
   "situation": "",
   "tension": "",
   "opportunities": "",
   "limits": "",
   "dramatic_question": ""
  },
  {
   "title": "",
   "situation": "",
   "tension": "",
   "opportunities": "",
   "limits": "",
   "dramatic_question": ""
  },
  {
   "title": "",
   "situation": "",
   "tension": "",
   "opportunities": "",
   "limits": "",
   "dramatic_question": ""
  }
 ]
}
""",
        {
            "scene": scene["title"],
            "context": (
                scene.get("context_approved")
                or scene.get("approved_context")
            ),
            "present": cast_of(
                scene,
                alone,
            ),
            "question": question,
            "lane": (
                "ADA ALONE"
                if alone
                else "PRINCIPALE"
            ),
        },
        1800,
    )


def render_advisor(
    scene,
    alone,
):
    key = scene["id"]

    direction = fill_defaults(
        as_dict(
            scene.get("direction")
        ),
        empty_direction(),
    )

    scene["direction"] = direction

    with st.expander(
        "CONSULENTE NARRATIVO E REGIA"
    ):
        active = direction.get(
            "active"
        )

        if isinstance(active, dict):
            st.success(
                "Direzione attiva: "
                + active.get(
                    "title",
                    "",
                )
            )

            st.write(
                active.get(
                    "situation",
                    "",
                )
            )

        question = st.text_area(
            "Che situazione vuoi esplorare?",
            value=direction.get(
                "last_question",
                "",
            ),
            key="advisor_" + key,
        )

        if st.button(
            "PROPONI TRE DIREZIONI",
            key="directions_" + key,
            disabled=AI is None,
        ):
            with st.spinner(
                "Elaborazione proposte..."
            ):
                response = propose_direction(
                    scene,
                    alone,
                    question,
                )

            if failed_ai(response):
                st.error(
                    response
                )

            else:
                parsed = parse_json(
                    response
                )

                proposals = (
                    parsed.get("directions")
                    if isinstance(
                        parsed,
                        dict,
                    )
                    else None
                )

                valid = (
                    isinstance(
                        proposals,
                        list,
                    )
                    and len(proposals) == 3
                    and all(
                        isinstance(
                            item,
                            dict,
                        )
                        and all(
                            item.get(field)
                            for field in DIRECTION_FIELDS
                        )
                        for item in proposals
                    )
                )

                if not valid:
                    st.error(
                        "Risposta del consulente "
                        "non valida."
                    )

                else:
                    def change():
                        direction[
                            "proposals"
                        ] = proposals

                        direction[
                            "last_question"
                        ] = question

                    if save(change):
                        st.rerun()

        proposals = as_list(
            direction.get(
                "proposals"
            )
        )

        if proposals:
            choice = st.radio(
                "Scegli la direzione",
                range(
                    len(proposals)
                ),
                format_func=lambda index: (
                    proposals[index].get(
                        "title",
                        "",
                    )
                ),
                key="choice_" + key,
            )

            selected = proposals[
                choice
            ]

            with st.form(
                "direction_form_"
                + key
                + "_"
                + str(choice)
            ):
                edited = {}

                for field in DIRECTION_FIELDS:
                    edited[field] = st.text_area(
                        field,
                        value=selected.get(
                            field,
                            "",
                        ),
                    )

                reason = st.text_input(
                    "Motivazione"
                )

                submitted = (
                    st.form_submit_button(
                        "APPROVA E ATTIVA"
                    )
                )

            if submitted:
                if not all(
                    str(value).strip()
                    for value in edited.values()
                ):
                    st.warning(
                        "Completa tutti i campi."
                    )

                else:
                    def change():
                        if direction.get(
                            "active"
                        ):
                            direction[
                                "history"
                            ].append(
                                copy.deepcopy(
                                    direction[
                                        "active"
                                    ]
                                )
                            )

                        direction[
                            "active"
                        ] = {
                            **edited,
                            "approved_at": now(),
                            "reason": reason,
                        }

                        editorial_entry(
                            "regia narrativa",
                            scene["title"],
                            dump(active),
                            dump(edited),
                            reason,
                        )

                    if save(change):
                        st.rerun()

        if isinstance(active, dict):
            if st.button(
                "DISATTIVA DIREZIONE",
                key="deactivate_" + key,
            ):
                def change():
                    direction[
                        "history"
                    ].append(
                        copy.deepcopy(
                            active
                        )
                    )

                    direction[
                        "active"
                    ] = None

                if save(change):
                    st.rerun()


# ==========================================================
# DIALOGHI E GO ALONE
# ==========================================================


def render_dialogues(
    scene,
    alone,
):
    key = scene["id"]

    cast = cast_of(
        scene,
        alone,
    )

    st.header(
        "Personaggi e conversazioni"
    )

    options = (
        [
            person
            for person in PEOPLE
            if person != "Noa"
        ]
        if alone
        else PEOPLE
    )

    selected = st.multiselect(
        "PERSONAGGI PRESENTI",
        options,
        default=cast,
        key="cast_" + key,
    )

    if st.button(
        "SALVA PERSONAGGI PRESENTI",
        key="save_cast_" + key,
    ):
        if (
            alone
            and "Ada" not in selected
        ):
            st.warning(
                "Ada deve essere presente."
            )

        else:
            if save(
                lambda: scene.update(
                    cast=selected
                )
            ):
                st.rerun()

    cast = cast_of(
        scene,
        alone,
    )

    if not cast:
        st.warning(
            "Seleziona almeno un personaggio."
        )

        return

    dialogue_tab, inner_tab = st.tabs([
        "DIALOGO",
        "MONOLOGO",
    ])

    with dialogue_tab:
        field = (
            "messages"
            if alone
            else "ensemble_messages"
        )

        messages = as_list(
            scene.get(field)
        )

        for item in messages:
            if not isinstance(item, dict):
                continue

            st.markdown(
                '<div class="dialogue-box">'
                "<strong>"
                + escape(
                    item.get(
                        "speaker",
                        "",
                    )
                )
                + "</strong>"
                "<div>"
                + escape(
                    item.get(
                        "text",
                        "",
                    )
                )
                + "</div></div>",
                unsafe_allow_html=True,
            )

        with st.form(
            "reply_" + key,
            clear_on_submit=True,
        ):
            speaker = st.selectbox(
                "Chi pone la domanda?",
                [
                    "Autore",
                    *cast,
                ],
            )

            responder = st.selectbox(
                "Chi risponde?",
                cast,
            )

            question = st.text_area(
                "Domanda o battuta"
            )

            submitted = st.form_submit_button(
                "RISPONDI — UNA BATTUTA",
                disabled=AI is None,
            )

        if submitted:
            if not question.strip():
                st.warning(
                    "Scrivi una domanda."
                )

            else:
                with st.spinner(
                    responder + " risponde..."
                ):
                    answer = reply(
                        scene,
                        alone,
                        responder,
                        question,
                        messages,
                    )

                if failed_ai(answer):
                    st.error(
                        answer
                    )

                else:
                    additions = [
                        {
                            "speaker": speaker,
                            "text": question,
                            "origin": "manual_prompt",
                            "created_at": now(),
                        },
                        {
                            "speaker": responder,
                            "text": answer,
                            "origin": "reply",
                            "created_at": now(),
                        },
                    ]

                    if save_dialogue(
                        scene,
                        alone,
                        additions,
                    ):
                        st.rerun()

        st.markdown(
            "### GO ALONE"
        )

        st.caption(
            "Quattro battute generate "
            "separatamente. Ogni personaggio "
            "riceve la memoria pertinente "
            "e le battute già pronunciate."
        )

        if st.button(
            "GO ALONE — QUATTRO INTERVENTI",
            key="go_alone_" + key,
            disabled=AI is None,
            use_container_width=True,
        ):
            with st.spinner(
                "I personaggi proseguono..."
            ):
                error = run_go_alone(
                    scene,
                    alone,
                )

            if error:
                st.error(
                    error
                )

            else:
                st.rerun()

        with st.form(
            "manual_line_" + key,
            clear_on_submit=True,
        ):
            character = st.selectbox(
                "Personaggio",
                cast,
            )

            line = st.text_area(
                "Scrivi una battuta"
            )

            add = st.form_submit_button(
                "AGGIUNGI BATTUTA"
            )

        if (
            add
            and line.strip()
        ):
            item = {
                "speaker": character,
                "text": line,
                "origin": "manual",
                "created_at": now(),
            }

            if save_dialogue(
                scene,
                alone,
                [item],
            ):
                st.rerun()

    with inner_tab:
        character = st.selectbox(
            "Personaggio del monologo",
            cast,
            key="inner_character_" + key,
        )

        theme_text = st.text_area(
            "Tema del monologo",
            key="inner_theme_" + key,
        )

        if st.button(
            "GO ALONE — DUE PENSIERI",
            key="inner_go_" + key,
            disabled=(
                AI is None
                or not theme_text.strip()
            ),
        ):
            with st.spinner(
                "Il personaggio riflette..."
            ):
                error = run_monologue(
                    scene,
                    alone,
                    character,
                    theme_text,
                )

            if error:
                st.error(
                    error
                )

            else:
                st.rerun()

        source = (
            as_dict(
                scene.get(
                    "inner_messages"
                )
            )
            if alone
            else as_dict(
                scene.get(
                    "messages"
                )
            )
        )

        for item in as_list(
            source.get(character)
        ):
            if isinstance(item, dict):
                story_box(
                    item.get(
                        "text",
                        "",
                    )
                )


# ==========================================================
# OFFICINA LETTERARIA
# ==========================================================


def transcript(
    scene,
    alone,
):
    field = (
        "messages"
        if alone
        else "ensemble_messages"
    )

    return "\n\n".join(
        str(
            item.get(
                "speaker",
                "?",
            )
        )
        + ": "
        + str(
            item.get(
                "text",
                "",
            )
        )
        for item in as_list(
            scene.get(field)
        )
        if isinstance(item, dict)
    )


def write_version(
    scene,
    alone,
    narrator,
    version,
    author_notes,
):
    style = (
        "essenziale e misurato"
        if version == "A"
        else (
            "evocativo, sensoriale "
            "e introspettivo"
        )
    )

    return ask_ai(
        (
            "Sei uno scrittore letterario. "
            "Scrivi una scena in prima persona, "
            "al presente, dal punto di vista "
            "di "
            + narrator
            + ". Lo stile deve essere "
            + style
            + ". Rispetta il vissuto del "
            "personaggio e il contesto. "
            "Non introdurre conoscenze "
            "impossibili. "
            "La regia non deve imporre "
            "il comportamento dei personaggi. "
            "Restituisci soltanto il racconto."
        ),
        {
            "title": scene["title"],
            "context": (
                scene.get("context_approved")
                or scene.get("approved_context")
            ),
            "direction": as_dict(
                scene.get("direction")
            ).get("active"),
            "dialogue": transcript(
                scene,
                alone,
            )[-6500:],
            "memory": relevant_memory(
                narrator,
                scene,
                alone,
            ),
            "author_notes": author_notes,
            "lane": (
                "ADA ALONE"
                if alone
                else "PRINCIPALE"
            ),
        },
        2600,
    )


def literary_critic(record):
    return ask_ai(
        """
Confronta due versioni letterarie.

Valuta:
- autenticità della voce;
- coerenza psicologica;
- qualità della scrittura.

Indica la versione preferibile
e due suggerimenti di revisione.

Non approvare automaticamente nulla.
""",
        {
            "A": record.get(
                "A",
                "",
            ),
            "B": record.get(
                "B",
                "",
            ),
        },
        850,
    )


def make_word(
    title_value,
    content,
):
    document = Document()

    document.add_heading(
        title_value,
        0,
    )

    for paragraph in content.split("\n"):
        document.add_paragraph(
            paragraph
        )

    file = BytesIO()

    document.save(file)

    return file.getvalue()


def export_texts(
    title_value,
    filename,
    content,
):
    if not content.strip():
        return

    columns = st.columns(3)

    with columns[0]:
        st.download_button(
            "TXT",
            content.encode(
                "utf-8"
            ),
            file_name=(
                filename + ".txt"
            ),
            mime="text/plain",
            key=filename + "_txt",
        )

    with columns[1]:
        st.download_button(
            "MARKDOWN",
            content.encode(
                "utf-8"
            ),
            file_name=(
                filename + ".md"
            ),
            mime="text/markdown",
            key=filename + "_md",
        )

    with columns[2]:
        st.download_button(
            "WORD",
            make_word(
                title_value,
                content,
            ),
            file_name=(
                filename + ".docx"
            ),
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            key=filename + "_word",
        )


def render_memory_editor(
    scene,
    alone,
    narrator,
):
    key = (
        scene["id"]
        + "_"
        + narrator
    )

    with st.expander(
        "MEMORIA DEL PERSONAGGIO"
    ):
        record = narrative_record(
            scene,
            alone,
            narrator,
        )

        if not record.get(
            "approved"
        ):
            st.info(
                "Approva prima il racconto."
            )

            return

        proposal_key = (
            "memory_proposal_"
            + key
        )

        if st.button(
            "ESTRAI RICORDI",
            key="extract_" + key,
            disabled=AI is None,
        ):
            with st.spinner(
                "Analisi della memoria..."
            ):
                proposal, error = suggest_memory(
                    scene,
                    alone,
                    narrator,
                )

            if error:
                st.error(
                    error
                )

            else:
                st.session_state[
                    proposal_key
                ] = proposal

        proposal = st.session_state.get(
            proposal_key
        )

        if not isinstance(
            proposal,
            dict,
        ):
            return

        edited = st.text_area(
            "Controlla e correggi "
            "la memoria proposta",
            value=dump(proposal),
            height=280,
            key="memory_text_" + key,
        )

        if st.button(
            "APPROVA MEMORIA",
            key="approve_memory_" + key,
        ):
            parsed = parse_json(
                edited
            )

            if not isinstance(
                parsed,
                dict,
            ):
                st.error(
                    "Formato JSON non valido."
                )

            else:
                if approve_memory(
                    narrator,
                    parsed,
                ):
                    st.session_state.pop(
                        proposal_key,
                        None,
                    )

                    st.rerun()


def render_workshop(
    scene,
    alone,
    narrator,
):
    key = (
        scene["id"]
        + "_"
        + narrator
    )

    record = narrative_record(
        scene,
        alone,
        narrator,
    )

    st.markdown("---")

    st.header(
        "Officina del romanzo"
    )

    notes = st.text_area(
        "Indicazioni letterarie",
        value=record.get(
            "feedback",
            "",
        ),
        key="notes_" + key,
    )

    if st.button(
        "GENERA VERSIONI A E B",
        key="generate_" + key,
        disabled=AI is None,
    ):
        with st.spinner(
            "Scrittura delle versioni..."
        ):
            a = write_version(
                scene,
                alone,
                narrator,
                "A",
                notes,
            )

            b = (
                write_version(
                    scene,
                    alone,
                    narrator,
                    "B",
                    notes,
                )
                if not failed_ai(a)
                else ""
            )

        if failed_ai(a):
            st.error(a)

        elif failed_ai(b):
            st.error(b)

        else:
            def change():
                record["A"] = a
                record["B"] = b
                record["feedback"] = notes

            if save(change):
                st.rerun()

    if (
        record.get("A")
        or record.get("B")
    ):
        tab_a, tab_b = st.tabs([
            "VERSIONE A",
            "VERSIONE B",
        ])

        with tab_a:
            story_box(
                record.get(
                    "A",
                    "",
                )
            )

        with tab_b:
            story_box(
                record.get(
                    "B",
                    "",
                )
            )

        if st.button(
            "GIUDIZIO CRITICO",
            key="critic_" + key,
            disabled=AI is None,
        ):
            with st.spinner(
                "Valutazione..."
            ):
                review = literary_critic(
                    record
                )

            if failed_ai(review):
                st.error(
                    review
                )

            else:
                if save(
                    lambda: record.update(
                        review=review
                    )
                ):
                    st.rerun()

    if record.get(
        "review"
    ):
        st.write(
            record["review"]
        )

    options = ["Bozza"]

    if record.get("A"):
        options.append(
            "Versione A"
        )

    if record.get("B"):
        options.append(
            "Versione B"
        )

    selected = st.selectbox(
        "Testo da modificare",
        options,
        key="version_" + key,
    )

    initial = (
        record.get("A", "")
        if selected == "Versione A"
        else (
            record.get("B", "")
            if selected == "Versione B"
            else record.get(
                "draft",
                "",
            )
        )
    )

    editor_key = (
        "story_editor_"
        + key
        + "_"
        + normalize(selected)
    )

    source_key = (
        editor_key + "_source"
    )

    if (
        st.session_state.get(
            source_key
        )
        != initial
    ):
        st.session_state[
            editor_key
        ] = initial

        st.session_state[
            source_key
        ] = initial

    edited = st.text_area(
        "Testo del racconto",
        height=340,
        key=editor_key,
    )

    reason = st.text_input(
        "Motivazione editoriale",
        key="reason_" + key,
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA BOZZA",
            key="save_draft_" + key,
        ):
            if save(
                lambda: record.update(
                    draft=edited,
                    status="bozza",
                )
            ):
                st.success(
                    "Bozza salvata."
                )

    with right:
        if st.button(
            "APPROVA E MEMORIZZA",
            key="approve_story_" + key,
            disabled=not edited.strip(),
        ):
            def change():
                previous = record.get(
                    "approved",
                    "",
                )

                if (
                    previous
                    and previous != edited
                ):
                    record[
                        "history"
                    ].append({
                        "text": previous,
                        "replaced_at": now(),
                        "reason": reason,
                    })

                record[
                    "approved"
                ] = edited

                record[
                    "draft"
                ] = edited

                record[
                    "approved_at"
                ] = now()

                record[
                    "status"
                ] = "approvata"

                editorial_entry(
                    "racconto approvato",
                    scene["title"],
                    previous,
                    edited,
                    reason,
                )

            if save(change):
                st.rerun()

    export_texts(
        scene["title"],
        key,
        edited,
    )

    if record.get(
        "approved"
    ):
        with st.expander(
            "RACCONTO APPROVATO"
        ):
            story_box(
                record["approved"]
            )

    with st.expander(
        "VERSIONI PRECEDENTI"
    ):
        for item in reversed(
            as_list(
                record.get(
                    "history"
                )
            )
        ):
            st.caption(
                item.get(
                    "replaced_at",
                    "",
                )
            )

            st.write(
                item.get(
                    "text",
                    "",
                )
            )

    with st.expander(
        "TRASCRIZIONE DEL DIALOGO"
    ):
        st.text(
            transcript(
                scene,
                alone,
            )
        )

    render_memory_editor(
        scene,
        alone,
        narrator,
    )


# ==========================================================
# PERSONAGGI
# ==========================================================


def page_people():
    theme()

    character = st.selectbox(
        "Personaggio",
        PEOPLE,
    )

    header(
        character,
        "Profilo di " + character,
    )

    agent = book[
        "agents"
    ][character]

    profile_text = st.text_area(
        "Profilo",
        value=agent.get(
            "profile",
            "",
        ),
        height=180,
        key="profile_" + character,
    )

    if st.button(
        "APPROVA PROFILO",
        key="save_profile_" + character,
    ):
        def change():
            previous = agent.get(
                "profile",
                "",
            )

            agent[
                "profile_history"
            ].append({
                "text": previous,
                "date": now(),
            })

            agent[
                "profile"
            ] = profile_text

            editorial_entry(
                "profilo",
                character,
                previous,
                profile_text,
            )

        if save(change):
            st.rerun()

    st.subheader(
        "Memoria narrativa personale"
    )

    memory = agent[
        "smart_memory"
    ]

    identity = st.text_area(
        "Identità sintetica",
        value=memory.get(
            "identity",
            "",
        ),
        height=130,
        key="identity_" + character,
    )

    if st.button(
        "SALVA IDENTITÀ",
        key="save_identity_" + character,
    ):
        if save(
            lambda: memory.update(
                identity=identity
            )
        ):
            st.rerun()

    with st.expander(
        "RICORDI"
    ):
        for item in as_list(
            memory.get(
                "events"
            )
        ):
            if isinstance(
                item,
                dict,
            ):
                st.write(
                    item.get(
                        "text",
                        "",
                    )
                )

    with st.expander(
        "RELAZIONI"
    ):
        for person, value in as_dict(
            memory.get(
                "relations"
            )
        ).items():
            st.write(
                "**"
                + person
                + "**: "
                + str(value)
            )

    with st.expander(
        "SEGRETI CONOSCIUTI"
    ):
        for item in as_list(
            memory.get(
                "secrets"
            )
        ):
            if isinstance(
                item,
                dict,
            ):
                st.write(
                    item.get(
                        "text",
                        "",
                    )
                )


# ==========================================================
# ARCHIVIO E REGISTRO
# ==========================================================


def page_archive():
    theme()

    st.title(
        "Archivio del romanzo"
    )

    st.subheader(
        "Filone principale"
    )

    for scene in book["scenes"]:
        for person in PEOPLE:
            record = as_dict(
                scene[
                    "narrative"
                ].get(person)
            )

            approved = record.get(
                "approved",
                "",
            )

            if approved:
                with st.expander(
                    scene["title"]
                    + " — "
                    + person
                ):
                    story_box(
                        approved
                    )

    st.subheader(
        "Filone esclusivo ADA ALONE"
    )

    for scene in book[
        "ada_scenes"
    ]:
        approved = scene[
            "narrative"
        ].get(
            "approved",
            "",
        )

        if approved:
            with st.expander(
                scene["title"]
                + " — ADA ALONE"
            ):
                story_box(
                    approved
                )


def page_editorial():
    theme()

    st.title(
        "Registro editoriale"
    )

    for item in reversed(
        as_list(
            book.get(
                "editorial_log"
            )
        )
    ):
        if not isinstance(
            item,
            dict,
        ):
            continue

        with st.expander(
            item.get(
                "date",
                "",
            )[:10]
            + " — "
            + item.get(
                "subject",
                "",
            )
        ):
            st.write(
                item.get(
                    "category",
                    "",
                )
            )

            st.write(
                item.get(
                    "reason",
                    "",
                )
            )

            before = str(
                item.get(
                    "before",
                    "",
                )
            )

            after = str(
                item.get(
                    "after",
                    "",
                )
            )

            diff = "\n".join(
                difflib.unified_diff(
                    before.splitlines(),
                    after.splitlines(),
                    fromfile="Prima",
                    tofile="Dopo",
                    lineterm="",
                )
            )

            st.code(
                diff
                or "Nessuna differenza.",
                language="diff",
            )


# ==========================================================
# ECONOMIA API
# ==========================================================


def page_settings():
    theme()

    st.title(
        "Economia API e memoria"
    )

    st.write(
        "GO ALONE mantiene quattro "
        "chiamate autonome. Il risparmio "
        "nasce da contesti più piccoli "
        "e ricordi selezionati."
    )

    settings = book[
        "settings"
    ]

    lines = st.slider(
        "Battute recenti inviate",
        min_value=4,
        max_value=20,
        value=int(
            settings.get(
                "context_lines",
                10,
            )
        ),
    )

    memories = st.slider(
        "Ricordi pertinenti",
        min_value=2,
        max_value=12,
        value=int(
            settings.get(
                "memory_items",
                8,
            )
        ),
    )

    if st.button(
        "SALVA IMPOSTAZIONI"
    ):
        if save(
            lambda: settings.update(
                context_lines=lines,
                memory_items=memories,
            )
        ):
            st.rerun()


# ==========================================================
# BARRA LATERALE
# ==========================================================


def main_navigation():
    index = st.session_state.get(
        "scene_index",
        0,
    )

    index = max(
        0,
        min(
            len(SCENE_IDS) - 1,
            int(index),
        ),
    )

    selected = st.sidebar.selectbox(
        "SCENA PRINCIPALE",
        SCENE_IDS,
        index=index,
        format_func=lambda sid: (
            f"{scene_pos(sid) + 1:02d}"
            + " — "
            + SCENE_TITLES[sid]
        ),
        key="main_scene_selector",
    )

    new_index = scene_pos(
        selected
    )

    if new_index != index:
        st.session_state[
            "scene_index"
        ] = new_index

        st.rerun()


def sidebar():
    st.sidebar.title(
        "TURING HOTEL"
    )

    pov = st.session_state.get(
        "pov",
        "Noa",
    )

    if pov == "Ada":
        mode = st.sidebar.radio(
            "FILONE DI ADA",
            [
                "Storia condivisa",
                "ADA ALONE",
            ],
            key="ada_mode",
        )

        if mode == "ADA ALONE":
            st.sidebar.markdown(
                "---"
            )

            st.sidebar.subheader(
                "Scene autonome di Ada"
            )

            if st.sidebar.button(
                "+ NUOVA SCENA ADA ALONE",
                use_container_width=True,
            ):
                item = empty_ada_scene()

                if save(
                    lambda: book[
                        "ada_scenes"
                    ].append(item)
                ):
                    st.session_state[
                        "ada_scene_id"
                    ] = item["id"]

                    st.rerun()

            identifiers = [
                item["id"]
                for item in book[
                    "ada_scenes"
                ]
            ]

            if identifiers:
                current = st.session_state.get(
                    "ada_scene_id",
                    "",
                )

                if current not in identifiers:
                    current = identifiers[0]

                selected = st.sidebar.selectbox(
                    "SCENA DI ADA",
                    identifiers,
                    index=identifiers.index(
                        current
                    ),
                    format_func=lambda sid: (
                        get_ada_scene(
                            sid
                        )["title"]
                    ),
                    key="ada_scene_selector",
                )

                st.session_state[
                    "ada_scene_id"
                ] = selected

            else:
                st.sidebar.info(
                    "Non ci sono ancora "
                    "scene autonome di Ada."
                )

        else:
            main_navigation()

    else:
        main_navigation()

    st.sidebar.markdown(
        "---"
    )

    pages = [
        (
            "ARCHIVIO SCENE",
            "archive",
        ),
        (
            "ARCHIVIO PERSONAGGI",
            "people",
        ),
        (
            "REGISTRO EDITORIALE",
            "editorial",
        ),
        (
            "ECONOMIA API",
            "settings",
        ),
        (
            "CAMBIA STORIA",
            "characters",
        ),
    ]

    for label, destination in pages:
        if st.sidebar.button(
            label,
            key="nav_" + destination,
            use_container_width=True,
        ):
            st.session_state[
                "page"
            ] = destination

            st.rerun()

    with st.sidebar.expander(
        "ARCHIVIO GITHUB"
    ):
        st.caption(
            GH_OWNER
            + "/"
            + GH_REPO
        )

        if st.button(
            "RICARICA ARCHIVIO"
        ):
            if reload_book():
                st.rerun()

        st.download_button(
            "SCARICA BACKUP",
            dump(book).encode(
                "utf-8"
            ),
            file_name=(
                "turing_hotel_backup.json"
            ),
            mime="application/json",
        )

        pending = st.session_state.get(
            "pending_backup",
            None,
        )

        if pending is not None:
            st.warning(
                "È disponibile una copia "
                "dell'ultima modifica "
                "non salvata."
            )

            st.download_button(
                "RECUPERA MODIFICA NON SALVATA",
                dump(pending).encode(
                    "utf-8"
                ),
                file_name=(
                    "modifica_non_salvata.json"
                ),
                mime="application/json",
            )


# ==========================================================
# SCHERMATA INIZIALE CON COPERTINA
# ==========================================================


def page_entrance():
    theme()

    # COPERTINA DEL ROMANZO
    render_cover()

    st.markdown(
        "<div style='height:14px'></div>",
        unsafe_allow_html=True,
    )

    left, middle, right = st.columns(
        [1, 2, 1]
    )

    with middle:
        st.markdown(
            "<h1 style='text-align:center;"
            "margin-bottom:0.2em'>"
            "TURING HOTEL"
            "</h1>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<p style='text-align:center;"
            "color:#d7c9b8'>"
            "Un romanzo a più coscienze"
            "</p>",
            unsafe_allow_html=True,
        )

        if st.button(
            "ENTRA AL TURING HOTEL",
            use_container_width=True,
            key="enter_hotel",
        ):
            st.session_state[
                "page"
            ] = "characters"

            st.rerun()


def page_characters():
    theme()

    st.title(
        "Scegli il filone narrativo"
    )

    columns = st.columns(2)

    for column, person in zip(
        columns,
        [
            "Noa",
            "Ada",
        ],
    ):
        with column:
            image = portrait(
                person
            )

            if image:
                st.image(
                    str(image),
                    use_container_width=True,
                )

            st.subheader(
                person
            )

            if st.button(
                "ENTRA NELLA STORIA DI "
                + person.upper(),
                key="choose_" + person,
                use_container_width=True,
            ):
                st.session_state[
                    "pov"
                ] = person

                st.session_state[
                    "page"
                ] = "story"

                st.rerun()


# ==========================================================
# PAGINA DEL ROMANZO
# ==========================================================


def page_story():
    sidebar()

    pov = st.session_state.get(
        "pov",
        "Noa",
    )

    alone = (
        pov == "Ada"
        and st.session_state.get(
            "ada_mode",
            "Storia condivisa",
        ) == "ADA ALONE"
    )

    theme(alone)

    if alone:
        scene = get_ada_scene(
            st.session_state.get(
                "ada_scene_id",
                "",
            )
        )

        if scene is None:
            st.info(
                "Premi + NUOVA SCENA "
                "ADA ALONE nella barra "
                "laterale per iniziare."
            )

            return

        narrator = "Ada"

    else:
        index = max(
            0,
            min(
                len(SCENE_IDS) - 1,
                int(
                    st.session_state.get(
                        "scene_index",
                        0,
                    )
                ),
            ),
        )

        scene = get_main_scene(
            SCENE_IDS[index]
        )

        if scene is None:
            st.error(
                "Scena principale non trovata."
            )

            return

        cast = cast_of(
            scene
        )

        narrator = (
            pov
            if pov in cast
            else cast[0]
            if cast
            else pov
        )

    header(
        pov,
        scene["title"],
        alone,
    )

    if alone:
        st.info(
            "Questa scena appartiene "
            "esclusivamente ad Ada. "
            "Non deve corrispondere "
            "a una scena di Noa."
        )

    st.markdown("---")

    render_media(
        scene,
        pov,
        alone,
    )

    st.markdown("---")

    render_context(
        scene,
        alone,
    )

    render_advisor(
        scene,
        alone,
    )

    st.markdown("---")

    render_dialogues(
        scene,
        alone,
    )

    if not alone:
        st.markdown("---")

        options = cast_of(
            scene
        )

        if options:
            narrator = st.selectbox(
                "PUNTO DI VISTA",
                options,
                index=(
                    options.index(pov)
                    if pov in options
                    else 0
                ),
                key=(
                    "narrator_"
                    + scene["id"]
                ),
            )

    render_workshop(
        scene,
        alone,
        narrator,
    )

    st.markdown("---")

    if alone:
        index = next(
            (
                i
                for i, item in enumerate(
                    book["ada_scenes"]
                )
                if item["id"]
                == scene["id"]
            ),
            0,
        )

        left, right = st.columns(2)

        with left:
            if index > 0:
                if st.button(
                    "← ADA PRECEDENTE"
                ):
                    st.session_state[
                        "ada_scene_id"
                    ] = book["ada_scenes"][
                        index - 1
                    ]["id"]

                    st.rerun()

        with right:
            if index < (
                len(book["ada_scenes"]) - 1
            ):
                if st.button(
                    "ADA SUCCESSIVA →"
                ):
                    st.session_state[
                        "ada_scene_id"
                    ] = book["ada_scenes"][
                        index + 1
                    ]["id"]

                    st.rerun()

    else:
        index = st.session_state[
            "scene_index"
        ]

        left, right = st.columns(2)

        with left:
            if index > 0:
                if st.button(
                    "← PRECEDENTE"
                ):
                    st.session_state[
                        "scene_index"
                    ] -= 1

                    st.rerun()

        with right:
            if index < (
                len(SCENE_IDS) - 1
            ):
                if st.button(
                    "SUCCESSIVA →"
                ):
                    st.session_state[
                        "scene_index"
                    ] += 1

                    st.rerun()


# ==========================================================
# PROTEZIONE DELL'ARCHIVIO PRIVATO
# ==========================================================


if not st.session_state.get(
    "archive_exists",
    False,
):
    st.title(
        "Archivio non trovato"
    )

    st.warning(
        "Il file romanzo_web.json "
        "non è presente nel repository "
        "privato. Non crearne uno nuovo "
        "se il tuo archivio dovrebbe "
        "già esistere."
    )

    confirmation = st.checkbox(
        "Confermo la creazione "
        "di un archivio nuovo."
    )

    if st.button(
        "CREA ARCHIVIO",
        disabled=not confirmation,
    ):
        try:
            sha = github_write(
                GH_OWNER,
                GH_REPO,
                GH_BRANCH,
                GH_TOKEN,
                ARCHIVE_FILE,
                dump(book).encode(
                    "utf-8"
                ),
            )

            st.session_state[
                "archive_sha"
            ] = sha

            st.session_state[
                "saved_base"
            ] = copy.deepcopy(
                book
            )

            st.session_state[
                "archive_exists"
            ] = True

            st.rerun()

        except Exception as exc:
            st.error(
                str(exc)
            )

    st.stop()


# ==========================================================
# NAVIGAZIONE PRINCIPALE
# ==========================================================


page = st.session_state.get(
    "page",
    "entrance",
)

if page in (
    "people",
    "archive",
    "editorial",
    "settings",
):
    if st.button(
        "← TORNA ALLA STORIA"
    ):
        st.session_state[
            "page"
        ] = "story"

        st.rerun()


if page == "entrance":
    page_entrance()

elif page == "characters":
    page_characters()

elif page == "story":
    page_story()

elif page == "people":
    page_people()

elif page == "archive":
    page_archive()

elif page == "editorial":
    page_editorial()

elif page == "settings":
    page_settings()

else:
    st.session_state[
        "page"
    ] = "entrance"

    st.rerun()
