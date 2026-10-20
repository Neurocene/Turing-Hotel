
import os
import re
import json
import copy
import base64
import uuid
import time
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
# VERSIONE CON OFFICINA A / B / C
#
# - Copertina assets/TuringHotel.jpg
# - 31 scene principali
# - Scene ADA ALONE indipendenti
# - GO ALONE con quattro chiamate autonome
# - Memoria narrativa selettiva
# - Consulente narrativo
# - Officina A, B e C
# - Versione C guidata dal giudizio critico
# - Revisione e approvazione umana
# - Archivio privato GitHub
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
    "Noa", "Ada", "Elia", "Luigi",
    "Adam", "Riccardo", "Vittoria",
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
        "Regista arrivato al Turing Hotel "
        "per preparare un documentario "
        "sugli idrovolanti."
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
COVER_FILE = "TuringHotel.jpg"


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
    "GITHUB_REPO", "turing-hotel-archivio"
)
GH_BRANCH = secret("GITHUB_BRANCH", "main")

OPENAI_KEY = secret("OPENAI_API_KEY")
OPENAI_MODEL = secret(
    "OPENAI_MODEL", "gpt-4.1-mini"
)

AI = (
    OpenAI(api_key=OPENAI_KEY, timeout=90)
    if OPENAI_KEY else None
)


# ==========================================================
# UTILITÀ
# ==========================================================


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex[:12]


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def as_text(value):
    return value if isinstance(value, str) else ""


def dump(value):
    return json.dumps(
        value, ensure_ascii=False, indent=2
    )


def normalize(value):
    return re.sub(
        r"[^a-z0-9]+", "",
        str(value).casefold()
    )


def scene_pos(sid):
    return SCENE_IDS.index(sid)


def fill_defaults(value, template):
    if not isinstance(value, dict):
        value = {}

    for key, default in template.items():
        if key not in value:
            value[key] = copy.deepcopy(default)
        elif isinstance(default, dict):
            value[key] = fill_defaults(
                value[key], default
            )
    return value


def parse_json(value):
    cleaned = str(value).strip()
    cleaned = re.sub(
        r"^```(?:json)?\s*", "",
        cleaned, flags=re.I
    )
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except Exception:
        return None


def ai_failed(value):
    return (
        not isinstance(value, str)
        or not value.strip()
        or value.startswith("Errore OpenAI:")
        or value.startswith("OPENAI_API_KEY")
    )


def ask_ai(instructions, payload, max_tokens=1000):
    if AI is None:
        return "OPENAI_API_KEY non configurata."

    try:
        response = AI.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            max_output_tokens=max_tokens,
        )
        return (response.output_text or "").strip()

    except Exception as exc:
        return "Errore OpenAI: " + str(exc)


def story_box(value):
    st.markdown(
        '<div class="story-box">'
        + escape(str(value or ""))
        + "</div>",
        unsafe_allow_html=True,
    )


def words(value):
    return set(
        re.findall(
            r"[a-zà-ÿ]{3,}",
            str(value).casefold()
        )
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
    method, owner, repo, token, suffix,
    params=None, payload=None
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
            github_url(owner, repo, suffix),
            headers=headers,
            params=params,
            json=payload,
            timeout=90,
        )

    except requests.RequestException as exc:
        raise GitHubError(str(exc)) from exc

    if method == "GET" and response.status_code == 404:
        return None

    if response.status_code in (409, 422):
        raise GitHubError(
            "CONFLITTO GITHUB: "
            + response.text[:350]
        )

    if not response.ok:
        raise GitHubError(
            f"GitHub HTTP {response.status_code}: "
            + response.text[:350]
        )

    return response


def github_read(owner, repo, branch, token, path):
    response = gh_call(
        "GET", owner, repo, token,
        "/contents/" + quote(path, safe="/"),
        params={"ref": branch},
    )

    if response is None:
        return None, None

    metadata = response.json()
    sha = metadata.get("sha")

    if metadata.get("encoding") == "base64":
        return (
            base64.b64decode(metadata["content"]),
            sha,
        )

    # Lettura dei file JSON grandi
    # tramite Git Blobs API.
    if sha:
        blob_response = gh_call(
            "GET", owner, repo, token,
            "/git/blobs/" + quote(sha, safe=""),
        )

        if blob_response is not None:
            blob = blob_response.json()

            if blob.get("encoding") == "base64":
                return (
                    base64.b64decode(blob["content"]),
                    sha,
                )

    raise GitHubError(
        "Il file GitHub non è leggibile."
    )


def github_write(
    owner, repo, branch, token,
    path, content, sha=None
):
    payload = {
        "message": "Turing Hotel — " + now(),
        "branch": branch,
        "content": base64.b64encode(
            content
        ).decode("ascii"),
    }

    if sha:
        payload["sha"] = sha

    result = gh_call(
        "PUT", owner, repo, token,
        "/contents/" + quote(path, safe="/"),
        payload=payload,
    ).json()

    new_sha = as_dict(
        result.get("content")
    ).get("sha")

    if not new_sha:
        raise GitHubError(
            "GitHub non ha confermato il salvataggio."
        )

    return new_sha


def read_archive():
    raw, sha = github_read(
        GH_OWNER, GH_REPO,
        GH_BRANCH, GH_TOKEN,
        ARCHIVE_FILE,
    )

    if raw is None:
        return None, None

    try:
        return json.loads(
            raw.decode("utf-8-sig")
        ), sha

    except Exception as exc:
        raise GitHubError(
            "Archivio JSON non valido: "
            + str(exc)
        )


# ==========================================================
# STRUTTURA ARCHIVIO
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
        "C": "",
        "C_critique": "",
        "C_created_at": "",
        "draft": "",
        "approved": "",
        "feedback": "",
        "review": "",
        "review_at": "",
        "approved_at": "",
        "approved_source": "",
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
            DEFAULT_CAST.get(sid, ["Noa", "Ada"])
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
            "Turing Hotel: un albergo sul mare "
            "dove si intrecciano vite umane "
            "e intelligenze artificiali."
        ),
        "agents": {
            p: {
                "profile": PROFILES[p],
                "memory": "",
                "profile_history": [],
                "smart_memory": empty_memory(),
            }
            for p in PEOPLE
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
    original = as_dict(source)
    data = fill_defaults(
        copy.deepcopy(original), new_book()
    )

    old_scenes = original.get("scenes", [])

    if isinstance(old_scenes, dict):
        converted = []

        for sid, value in old_scenes.items():
            if isinstance(value, dict):
                item = copy.deepcopy(value)
                item.setdefault("id", sid)
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

        for old in old_scenes:
            if not isinstance(old, dict):
                continue

            if (
                normalize(old.get("id", "")) in aliases
                or normalize(old.get("title", "")) in aliases
            ):
                found = old
                break

        scene = fill_defaults(
            copy.deepcopy(found) if found else {},
            empty_scene(sid),
        )

        scene["id"] = sid
        scene["title"] = SCENE_TITLES[sid]

        scene["direction"] = fill_defaults(
            as_dict(scene.get("direction")),
            empty_direction(),
        )

        scene["ada_parallel"] = fill_defaults(
            as_dict(scene.get("ada_parallel")),
            empty_scene(sid)["ada_parallel"],
        )

        scene["ada_parallel"]["narrative"] = (
            fill_defaults(
                as_dict(
                    scene["ada_parallel"].get("narrative")
                ),
                empty_narrative(),
            )
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
                        scene["narrative"].get(person)
                    ),
                    empty_narrative(),
                )
            )
            scene["messages"].setdefault(
                person, []
            )

        rebuilt.append(scene)

    data["scenes"] = rebuilt

    # Le scene autonome di Ada vengono conservate.
    ada_items = []

    for item in as_list(data.get("ada_scenes")):
        if not isinstance(item, dict):
            continue

        converted = fill_defaults(
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

        if not converted.get("id"):
            converted["id"] = (
                "ada_importata_" + str(len(ada_items) + 1)
            )

        converted["direction"] = fill_defaults(
            as_dict(converted.get("direction")),
            empty_direction(),
        )

        converted["narrative"] = fill_defaults(
            as_dict(converted.get("narrative")),
            empty_narrative(),
        )

        ada_items.append(converted)

    # Compatibilità con il vecchio sistema
    # che conservava ADA ALONE dentro le scene Noa.
    imported = {
        item.get("legacy_source")
        for item in ada_items
    }

    branch = as_dict(data.get("ada_branch"))
    start = branch.get("start_scene")
    end = branch.get("end_scene")

    if start in SCENE_IDS:
        for sid in SCENE_IDS:
            if scene_pos(sid) < scene_pos(start):
                continue

            if (
                end in SCENE_IDS
                and scene_pos(sid) >= scene_pos(end)
            ):
                continue

            if sid in imported:
                continue

            previous = next(
                x for x in rebuilt if x["id"] == sid
            )

            parallel = as_dict(
                previous.get("ada_parallel")
            )

            previous_narrative = as_dict(
                parallel.get("narrative")
            )

            meaningful = any([
                parallel.get("title"),
                parallel.get("context"),
                parallel.get("context_approved"),
                parallel.get("messages"),
                previous_narrative.get("approved"),
                previous_narrative.get("draft"),
            ])

            if not meaningful:
                continue

            item = fill_defaults(
                copy.deepcopy(parallel),
                {
                    "id": "ada_legacy_" + sid,
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

            item["id"] = "ada_legacy_" + sid
            item["legacy_source"] = sid
            item["timeline_anchor"] = sid

            if not item.get("title"):
                item["title"] = (
                    "Ada — " + SCENE_TITLES[sid]
                )

            item["narrative"] = fill_defaults(
                as_dict(item.get("narrative")),
                empty_narrative(),
            )

            ada_items.append(item)

    data["ada_scenes"] = ada_items
    data["agents"] = as_dict(data.get("agents"))

    for person in PEOPLE:
        agent = fill_defaults(
            as_dict(data["agents"].get(person)),
            {
                "profile": PROFILES[person],
                "memory": "",
                "profile_history": [],
                "smart_memory": empty_memory(),
            },
        )

        agent["smart_memory"] = fill_defaults(
            as_dict(agent.get("smart_memory")),
            empty_memory(),
        )

        data["agents"][person] = agent

    return data


# ==========================================================
# SESSIONE
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
        st.session_state["saved_base"] = copy.deepcopy(data)
        st.session_state["archive_sha"] = sha
        st.session_state["archive_exists"] = exists

    st.session_state.setdefault(
        "pending_backup", None
    )

    st.session_state.setdefault(
        "saved_base",
        copy.deepcopy(st.session_state["book"]),
    )

    st.session_state.setdefault("archive_sha", None)
    st.session_state.setdefault("archive_exists", True)
    st.session_state.setdefault("page", "entrance")
    st.session_state.setdefault("pov", "Noa")
    st.session_state.setdefault("scene_index", 0)
    st.session_state.setdefault("ada_scene_id", "")

    st.session_state["book"] = migrate(
        st.session_state["book"]
    )

    st.session_state["saved_base"] = migrate(
        st.session_state["saved_base"]
    )


initialize()

book = st.session_state["book"]


# ==========================================================
# SALVATAGGIO SICURO
# ==========================================================


MISSING = object()


def three_way(base, local, remote, path="root"):
    if local == base:
        return copy.deepcopy(remote)

    if remote == base:
        return copy.deepcopy(local)

    if local == remote:
        return copy.deepcopy(local)

    if all(
        isinstance(x, dict)
        for x in (base, local, remote)
    ):
        result = {}

        for key in set(base) | set(local) | set(remote):
            b = base.get(key, MISSING)
            l = local.get(key, MISSING)
            r = remote.get(key, MISSING)

            target = path + "." + str(key)

            if l is MISSING and r is MISSING:
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
                b, l, r, target
            )

        return result

    if all(
        isinstance(x, list)
        for x in (base, local, remote)
    ):
        if (
            local[:len(base)] == base
            and remote[:len(base)] == base
        ):
            return (
                copy.deepcopy(base)
                + copy.deepcopy(remote[len(base):])
                + copy.deepcopy(local[len(base):])
            )

        if len(base) == len(local) == len(remote):
            return [
                three_way(
                    base[i], local[i], remote[i],
                    path + "[" + str(i) + "]"
                )
                for i in range(len(base))
            ]

    raise MergeConflict(path)


def save(change):
    before = copy.deepcopy(book)

    try:
        change()
        proposed = copy.deepcopy(book)

        if not st.session_state.get(
            "archive_exists", False
        ):
            raise GitHubError(
                "Archivio non inizializzato."
            )

        base = st.session_state["saved_base"]

        for attempt in range(3):
            remote_raw, remote_sha = read_archive()

            if remote_raw is None:
                raise GitHubError(
                    "Archivio remoto non trovato."
                )

            remote = migrate(remote_raw)

            merged = three_way(
                base, proposed, remote
            )

            try:
                new_sha = github_write(
                    GH_OWNER, GH_REPO,
                    GH_BRANCH, GH_TOKEN,
                    ARCHIVE_FILE,
                    dump(merged).encode("utf-8"),
                    remote_sha,
                )

                book.clear()
                book.update(merged)

                st.session_state["saved_base"] = (
                    copy.deepcopy(merged)
                )
                st.session_state["archive_sha"] = new_sha
                st.session_state["pending_backup"] = None

                return True

            except GitHubError as exc:
                if (
                    "CONFLITTO GITHUB" in str(exc)
                    and attempt < 2
                ):
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise

    except MergeConflict as exc:
        st.session_state["pending_backup"] = proposed
        book.clear()
        book.update(before)

        st.error(
            "Salvataggio interrotto: "
            "due sessioni hanno modificato "
            "lo stesso dato: "
            + str(exc)
            + ". Nessun dato remoto è stato sovrascritto."
        )
        return False

    except Exception as exc:
        st.session_state["pending_backup"] = proposed
        book.clear()
        book.update(before)

        st.error(
            "Salvataggio fallito: " + str(exc)
        )
        return False

    return False


def reload_book():
    try:
        source, sha = read_archive()

        if source is None:
            st.error("Archivio non trovato.")
            return False

        refreshed = migrate(source)

        book.clear()
        book.update(refreshed)

        st.session_state["saved_base"] = (
            copy.deepcopy(refreshed)
        )
        st.session_state["archive_sha"] = sha
        return True

    except Exception as exc:
        st.error(
            "Ricarica fallita: " + str(exc)
        )
        return False


def editorial_entry(
    category, subject, before, after, reason=""
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
# SCENE E MEMORIA
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


def cast_of(scene, alone=False):
    cast = [
        p for p in as_list(scene.get("cast"))
        if p in PEOPLE
    ]

    if alone:
        cast = [p for p in cast if p != "Noa"]

        if "Ada" not in cast:
            cast.insert(0, "Ada")

    return list(dict.fromkeys(cast))


def rank_of(scene, alone=False):
    if alone:
        anchor = scene.get(
            "timeline_anchor", "il_professore"
        )

        return (
            scene_pos(anchor)
            if anchor in SCENE_IDS
            else scene_pos("il_professore")
        )

    return scene_pos(scene["id"])


def previous_approved(scene, alone, character):
    result = []
    current_rank = rank_of(scene, alone)

    branch_start = as_dict(
        book.get("ada_branch")
    ).get("start_scene")

    cutoff = (
        scene_pos(branch_start)
        if branch_start in SCENE_IDS
        else scene_pos("il_professore")
    )

    for previous in book["scenes"]:
        rank = rank_of(previous)

        if rank >= current_rank:
            break

        # Dopo la divergenza, Ada non importa
        # automaticamente esperienze di Noa.
        if alone and rank >= cutoff:
            continue

        if character not in cast_of(previous):
            continue

        record = as_dict(
            previous["narrative"].get(character)
        )

        approved = as_text(
            record.get("approved")
        )

        if approved:
            result.append({
                "scene": previous["title"],
                "summary": approved[:550],
            })

    if alone or character != "Noa":
        for previous in book["ada_scenes"]:
            if alone and previous["id"] == scene["id"]:
                break

            if not alone:
                continue

            if character not in cast_of(previous, True):
                continue

            approved = as_text(
                previous["narrative"].get("approved")
            )

            if approved:
                result.append({
                    "scene": previous["title"],
                    "summary": approved[:550],
                })

    return result[-3:]


def relevant_memory(character, scene, alone):
    memory = book["agents"][character]["smart_memory"]
    cast = cast_of(scene, alone)

    context = (
        scene.get("context_approved")
        or scene.get("approved_context")
        or scene.get("context")
        or ""
    )

    terms = words(
        scene.get("title", "")
        + " "
        + scene.get("location", "")
        + " "
        + context
        + " "
        + " ".join(cast)
    )

    scored = []

    for item in as_list(memory.get("events")):
        if not isinstance(item, dict):
            continue

        value = item.get("text", "")
        score = len(terms & words(value))

        scored.append((
            score,
            item.get("created_at", ""),
            value,
        ))

    scored.sort(reverse=True)

    limit = max(
        2,
        min(
            12,
            int(
                book["settings"].get(
                    "memory_items", 8
                )
            ),
        ),
    )

    relations = {
        person: as_dict(
            memory.get("relations")
        ).get(person, "")
        for person in cast
        if person in as_dict(memory.get("relations"))
    }

    return {
        "identity": (
            memory.get("identity")
            or book["agents"][character]["profile"]
        )[:900],
        "events": [
            item[2] for item in scored[:limit]
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
    scene, alone, character,
    dialogue=None, instruction=""
):
    field = (
        "messages" if alone
        else "ensemble_messages"
    )

    if dialogue is None:
        dialogue = as_list(scene.get(field))

    limit = max(
        4,
        min(
            20,
            int(
                book["settings"].get(
                    "context_lines", 10
                )
            ),
        ),
    )

    return {
        "character": character,
        "scene": scene["title"],
        "filone": (
            "ADA ALONE" if alone
            else "STORIA PRINCIPALE"
        ),
        "location": scene.get("location", ""),
        "present": cast_of(scene, alone),
        "context": (
            scene.get("context_approved")
            or scene.get("approved_context")
            or scene.get("context")
            or ""
        )[:1400],
        "direction": as_dict(
            scene.get("direction")
        ).get("active"),
        "memory": relevant_memory(
            character, scene, alone
        ),
        "previous_scenes": previous_approved(
            scene, alone, character
        ),
        "recent_dialogue": dialogue[-limit:],
        "instruction": instruction,
    }


def agent_rules(character, alone):
    result = (
        "Sei " + character
        + ", personaggio di Turing Hotel. "
        "Rispondi come personaggio, non come assistente. "
        "Rispetta il tuo passato, i desideri, "
        "la memoria, le relazioni e i segreti. "
        "Non puoi conoscere eventi che non hai "
        "vissuto o appreso. "
        "La regia suggerisce una situazione, "
        "ma non obbliga a parole o azioni. "
        "Conserva autonomia psicologica."
    )

    if alone:
        result += (
            " Questa è una scena ADA ALONE. "
            "Noa non è presente e non conosce "
            "ciò che accade."
        )

    return result


def reply(
    scene, alone, character,
    instruction, dialogue
):
    return ask_ai(
        agent_rules(character, alone)
        + " Pronuncia una sola battuta. "
        "Non scrivere etichette o didascalie.",
        narrative_payload(
            scene, alone, character,
            dialogue, instruction
        ),
        220,
    )


def save_dialogue(scene, alone, items):
    field = (
        "messages" if alone
        else "ensemble_messages"
    )
    return save(
        lambda: scene[field].extend(items)
    )


def run_go_alone(scene, alone):
    cast = cast_of(scene, alone)

    if not cast:
        return "Nessun personaggio presente."

    field = (
        "messages" if alone
        else "ensemble_messages"
    )

    history = copy.deepcopy(
        as_list(scene.get(field))
    )

    last = (
        history[-1].get("speaker", "")
        if history else ""
    )

    start = (
        (cast.index(last) + 1) % len(cast)
        if last in cast else 0
    )

    results = []

    for i in range(4):
        character = cast[
            (start + i) % len(cast)
        ]

        instruction = (
            "Prosegui spontaneamente il dialogo."
            if len(cast) > 1
            else (
                "Prosegui la scena con un pensiero "
                "o intervento autonomo."
            )
        )

        answer = reply(
            scene, alone, character,
            instruction, history
        )

        if ai_failed(answer):
            return answer

        item = {
            "speaker": character,
            "text": answer,
            "origin": "GO ALONE",
            "created_at": now(),
        }

        results.append(item)
        history.append(item)

    if save_dialogue(scene, alone, results):
        return ""

    return "Dialogo non salvato."


def run_monologue(scene, alone, character, theme):
    results = []

    for i in (1, 2):
        answer = ask_ai(
            agent_rules(character, alone)
            + " Scrivi un pensiero interiore "
            "in prima persona, al presente. "
            "Nessuna didascalia.",
            {
                "theme": theme,
                "thought_number": i,
                "context": narrative_payload(
                    scene, alone, character, results
                ),
            },
            260,
        )

        if ai_failed(answer):
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
                "inner_messages", {}
            )
        else:
            target = scene["messages"]

        target.setdefault(
            character, []
        ).extend(results)

    return (
        "" if save(change)
        else "Monologo non salvato."
    )


# ==========================================================
# MEMORIA APPROVATA DALL'AUTORE
# ==========================================================


def narrative_record(scene, alone, narrator):
    if alone:
        return scene["narrative"]

    return scene["narrative"][narrator]


def suggest_memory(scene, alone, narrator):
    approved = narrative_record(
        scene, alone, narrator
    ).get("approved", "")

    if not approved:
        return None, "Approva prima un racconto."

    answer = ask_ai(
        """
Analizza questa scena già approvata.

Estrai solo ciò che il personaggio ha
vissuto o appreso, senza inventare.

Restituisci esclusivamente JSON:
{
 "events": ["...", "..."],
 "relations": {"Nome": "..."},
 "secrets": ["..."],
 "identity_update": ""
}

Massimo tre ricordi e tre segreti.
Non importare conoscenze da altri filoni.
""",
        {
            "character": narrator,
            "scene": scene["title"],
            "lane": (
                "ADA ALONE" if alone
                else "PRINCIPALE"
            ),
            "approved_story": approved[:8500],
        },
        850,
    )

    if ai_failed(answer):
        return None, answer

    parsed = parse_json(answer)

    if not isinstance(parsed, dict):
        return None, "Formato memoria non valido."

    return parsed, ""


def approve_memory(narrator, proposal):
    memory = book["agents"][narrator]["smart_memory"]

    def change():
        for value in as_list(
            proposal.get("events")
        )[:3]:
            if str(value).strip():
                memory["events"].append({
                    "text": str(value)[:600],
                    "created_at": now(),
                })

        for person, value in as_dict(
            proposal.get("relations")
        ).items():
            if person in PEOPLE:
                memory["relations"][person] = (
                    str(value)[:550]
                )

        for value in as_list(
            proposal.get("secrets")
        )[:3]:
            if str(value).strip():
                memory["secrets"].append({
                    "text": str(value)[:500],
                    "created_at": now(),
                })

        identity = as_text(
            proposal.get("identity_update")
        ).strip()

        if identity:
            memory["identity"] = identity[:900]

        editorial_entry(
            "memoria narrativa",
            narrator, "", dump(proposal),
            "Approvazione dell'autore",
        )

    return save(change)


# ==========================================================
# COPERTINA, RITRATTI E MEDIA
# ==========================================================


def find_cover():
    exact = ASSETS / "TuringHotel.jpg"

    if exact.is_file():
        return exact

    if ASSETS.is_dir():
        for path in ASSETS.iterdir():
            if (
                path.is_file()
                and path.name.casefold()
                == COVER_FILE.casefold()
            ):
                return path

    return None


def render_cover():
    cover = find_cover()

    if cover is None:
        st.warning(
            "Copertina non trovata: "
            "assets/TuringHotel.jpg"
        )
        return

    left, middle, right = st.columns([1, 2, 1])

    with middle:
        st.image(
            str(cover),
            use_container_width=True,
        )


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
                and path.suffix.casefold() in IMAGE_EXT
            ):
                return path

    return None


def media_prefix(scene, pov, alone):
    if alone:
        return scene["id"] + ".ada_alone"

    return scene["id"] + "." + pov.lower()


def media_list(prefix):
    cover = None
    images = []
    videos = []

    if not ASSETS.is_dir():
        return cover, images, videos

    for path in ASSETS.iterdir():
        if not path.is_file():
            continue

        ext = path.suffix.casefold()
        stem = path.stem.casefold()

        if ext not in IMAGE_EXT | VIDEO_EXT:
            continue

        if stem == prefix.casefold() and ext in IMAGE_EXT:
            cover = path
            continue

        if not stem.startswith(prefix.casefold()):
            continue

        tail = stem[len(prefix):]

        if not tail.isdigit():
            continue

        item = (int(tail), path)

        if ext in IMAGE_EXT:
            images.append(item)
        else:
            videos.append(item)

    images.sort(key=lambda x: x[0])
    videos.sort(key=lambda x: x[0])

    return (
        cover,
        [path for _, path in images],
        [path for _, path in videos],
    )


def render_media(scene, pov, alone):
    st.subheader("Foto e video")

    prefix = media_prefix(scene, pov, alone)
    st.caption("Nomi file: " + prefix)

    cover, images, videos = media_list(prefix)

    if cover:
        st.image(
            str(cover),
            use_container_width=True,
        )

    if images:
        columns = st.columns(2)

        for i, path in enumerate(images):
            with columns[i % 2]:
                st.image(
                    str(path),
                    use_container_width=True,
                )
                st.caption(path.name)

    for path in videos:
        st.video(str(path))

    with st.expander("COME AGGIUNGERE FOTO E VIDEO"):
        st.write(
            "Carica i media nella cartella `assets` "
            "del repository GitHub Turing-Hotel."
        )
        st.code(
            prefix + ".jpg\n"
            + prefix + "1.jpg\n"
            + prefix + "2.jpg\n"
            + prefix + "1.mp4"
        )


# ==========================================================
# ASPETTO GRAFICO
# ==========================================================


def theme(alone=False):
    background = "#180f23" if alone else "#0b1115"
    sidebar_color = "#281b37" if alone else "#15212a"
    panel = "#30213e" if alone else "#1b2831"
    accent = "#c7a1ee" if alone else "#cda980"

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
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {{
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


def header(character, title, alone=False):
    left, right = st.columns(
        [1, 4], vertical_alignment="top"
    )

    with left:
        picture = portrait(character)

        if picture:
            st.image(
                str(picture),
                use_container_width=True,
            )
        else:
            st.markdown("**" + character + "**")

        if alone:
            st.markdown(
                '<div class="ada-alone">ADA ALONE</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption(character.upper())

    with right:
        st.title(title)

        if alone:
            st.caption(
                "Filone esclusivo di Ada. "
                "Noa è assente e non conosce "
                "gli eventi di questa scena."
            )


# ==========================================================
# CONTESTO
# ==========================================================


def render_context(scene, alone):
    key = scene["id"]
    st.subheader("Situazione narrativa")

    if alone:
        title = st.text_input(
            "Titolo della scena ADA ALONE",
            value=scene.get("title", ""),
            key="title_" + key,
        )

        place = st.text_input(
            "Luogo",
            value=scene.get("location", ""),
            key="place_" + key,
        )

        anchor = scene.get(
            "timeline_anchor", "il_professore"
        )

        if anchor not in SCENE_IDS:
            anchor = "il_professore"

        selected_anchor = st.selectbox(
            "Momento cronologico parallelo",
            SCENE_IDS,
            index=scene_pos(anchor),
            format_func=lambda sid: SCENE_TITLES[sid],
            key="anchor_" + key,
        )

        context = st.text_area(
            "Contesto di Ada",
            value=scene.get("context", ""),
            height=160,
            key="context_" + key,
        )

        if st.button(
            "APPROVA CONTESTO ADA ALONE",
            key="context_save_" + key,
        ):
            def change():
                scene["title"] = title
                scene["location"] = place
                scene["timeline_anchor"] = selected_anchor
                scene["context"] = context
                scene["context_approved"] = context

            if save(change):
                st.rerun()

    else:
        context = st.text_area(
            "Contesto della scena",
            value=scene.get("approved_context", ""),
            height=160,
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
    "title", "situation", "tension",
    "opportunities", "limits",
    "dramatic_question",
]


def propose_direction(scene, alone, question):
    return ask_ai(
        """
Sei consulente narrativo di Turing Hotel.

Proponi tre direzioni alternative.
Le situazioni devono essere aperte.
Non imporre battute né esiti.
Rispetta la continuità narrativa.

Nelle scene ADA ALONE Noa è assente.

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
            "cast": cast_of(scene, alone),
            "question": question,
            "lane": (
                "ADA ALONE" if alone
                else "PRINCIPALE"
            ),
        },
        1800,
    )


def render_advisor(scene, alone):
    key = scene["id"]

    direction = fill_defaults(
        as_dict(scene.get("direction")),
        empty_direction(),
    )
    scene["direction"] = direction

    with st.expander(
        "CONSULENTE NARRATIVO E REGIA"
    ):
        active = direction.get("active")

        if isinstance(active, dict):
            st.success(
                "Direzione attiva: "
                + active.get("title", "")
            )
            st.write(active.get("situation", ""))

        question = st.text_area(
            "Che sviluppo vuoi esplorare?",
            value=direction.get("last_question", ""),
            key="advisor_" + key,
        )

        if st.button(
            "PROPONI TRE DIREZIONI",
            key="directions_" + key,
            disabled=AI is None,
        ):
            with st.spinner("Elaborazione proposte..."):
                answer = propose_direction(
                    scene, alone, question
                )

            if ai_failed(answer):
                st.error(answer)
            else:
                parsed = parse_json(answer)
                proposals = (
                    parsed.get("directions")
                    if isinstance(parsed, dict)
                    else None
                )

                valid = (
                    isinstance(proposals, list)
                    and len(proposals) == 3
                    and all(
                        isinstance(p, dict)
                        and all(
                            p.get(f)
                            for f in DIRECTION_FIELDS
                        )
                        for p in proposals
                    )
                )

                if not valid:
                    st.error(
                        "Formato proposte non valido."
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
            choice = st.radio(
                "Scegli una direzione",
                range(len(proposals)),
                format_func=lambda i: (
                    proposals[i].get("title", "")
                ),
                key="direction_choice_" + key,
            )

            chosen = proposals[choice]

            with st.form(
                "direction_form_" + key + str(choice)
            ):
                edited = {}

                for field in DIRECTION_FIELDS:
                    edited[field] = st.text_area(
                        field,
                        value=chosen.get(field, ""),
                    )

                reason = st.text_input("Motivazione")

                submitted = st.form_submit_button(
                    "APPROVA E ATTIVA"
                )

            if submitted:
                if not all(
                    str(v).strip()
                    for v in edited.values()
                ):
                    st.warning(
                        "Completa tutti i campi."
                    )
                else:
                    def change():
                        if direction.get("active"):
                            direction["history"].append(
                                copy.deepcopy(
                                    direction["active"]
                                )
                            )

                        direction["active"] = {
                            **edited,
                            "approved_at": now(),
                            "reason": reason,
                        }

                        editorial_entry(
                            "regia narrativa",
                            scene["title"],
                            str(active),
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
                    direction["history"].append(
                        copy.deepcopy(active)
                    )
                    direction["active"] = None

                if save(change):
                    st.rerun()


# ==========================================================
# DIALOGHI
# ==========================================================


def render_dialogues(scene, alone):
    key = scene["id"]

    st.header("Personaggi e conversazioni")

    cast = cast_of(scene, alone)

    options = (
        [p for p in PEOPLE if p != "Noa"]
        if alone else PEOPLE
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
        if alone and "Ada" not in selected:
            st.warning(
                "Ada deve essere presente."
            )
        elif save(
            lambda: scene.update(cast=selected)
        ):
            st.rerun()

    cast = cast_of(scene, alone)

    if not cast:
        st.warning(
            "Seleziona almeno un personaggio."
        )
        return

    dialog_tab, inner_tab = st.tabs([
        "DIALOGO", "MONOLOGO"
    ])

    with dialog_tab:
        field = (
            "messages" if alone
            else "ensemble_messages"
        )

        history = as_list(scene.get(field))

        for item in history:
            if not isinstance(item, dict):
                continue

            st.markdown(
                '<div class="dialogue-box"><strong>'
                + escape(item.get("speaker", ""))
                + "</strong><div>"
                + escape(item.get("text", ""))
                + "</div></div>",
                unsafe_allow_html=True,
            )

        with st.form(
            "reply_form_" + key,
            clear_on_submit=True,
        ):
            speaker = st.selectbox(
                "Chi pone la domanda?",
                ["Autore", *cast],
            )

            responder = st.selectbox(
                "Chi risponde?", cast
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
                st.warning("Scrivi una domanda.")
            else:
                with st.spinner(
                    responder + " risponde..."
                ):
                    answer = reply(
                        scene, alone, responder,
                        question, history
                    )

                if ai_failed(answer):
                    st.error(answer)
                else:
                    items = [
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
                        scene, alone, items
                    ):
                        st.rerun()

        st.markdown("### GO ALONE")

        st.caption(
            "Quattro interventi autonomi: "
            "una chiamata distinta per ogni battuta."
        )

        if st.button(
            "GO ALONE — QUATTRO INTERVENTI",
            key="go_" + key,
            disabled=AI is None,
            use_container_width=True,
        ):
            with st.spinner(
                "I personaggi proseguono..."
            ):
                error = run_go_alone(
                    scene, alone
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        with st.form(
            "manual_form_" + key,
            clear_on_submit=True,
        ):
            person = st.selectbox(
                "Personaggio", cast
            )
            line = st.text_area(
                "Battuta manuale"
            )
            add = st.form_submit_button(
                "AGGIUNGI BATTUTA"
            )

        if add and line.strip():
            if save_dialogue(
                scene,
                alone,
                [{
                    "speaker": person,
                    "text": line,
                    "origin": "manual",
                    "created_at": now(),
                }],
            ):
                st.rerun()

    with inner_tab:
        person = st.selectbox(
            "Personaggio del monologo",
            cast,
            key="inner_person_" + key,
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
                    scene, alone,
                    person, theme_text
                )

            if error:
                st.error(error)
            else:
                st.rerun()

        source = (
            as_dict(scene.get("inner_messages"))
            if alone
            else as_dict(scene.get("messages"))
        )

        for item in as_list(source.get(person)):
            if isinstance(item, dict):
                story_box(item.get("text", ""))


# ==========================================================
# OFFICINA LETTERARIA — A E B
# ==========================================================


def transcript(scene, alone):
    field = (
        "messages" if alone
        else "ensemble_messages"
    )

    return "\n\n".join(
        str(item.get("speaker", "?"))
        + ": "
        + str(item.get("text", ""))
        for item in as_list(scene.get(field))
        if isinstance(item, dict)
    )


def write_version(
    scene, alone, narrator,
    version, author_notes
):
    style = (
        "essenziale e misurato"
        if version == "A"
        else "evocativo, sensoriale e introspettivo"
    )

    return ask_ai(
        (
            "Sei uno scrittore letterario. "
            "Scrivi una scena in prima persona, "
            "al presente, dal punto di vista "
            "di " + narrator + ". "
            "Usa uno stile " + style + ". "
            "Rispetta memoria, passato, contesto "
            "e conoscenze effettive. "
            "Restituisci soltanto il racconto."
        ),
        {
            "scene": scene["title"],
            "context": (
                scene.get("context_approved")
                or scene.get("approved_context")
            ),
            "direction": as_dict(
                scene.get("direction")
            ).get("active"),
            "dialogue": transcript(
                scene, alone
            )[-6500:],
            "memory": relevant_memory(
                narrator, scene, alone
            ),
            "author_notes": author_notes,
            "lane": (
                "ADA ALONE" if alone
                else "PRINCIPALE"
            ),
        },
        2600,
    )


def literary_critic(record):
    return ask_ai(
        """
Sei un critico letterario e un editor.

Confronta le versioni A e B considerando:
- autenticità della voce narrante;
- coerenza psicologica;
- qualità dei dialoghi;
- atmosfera e sensorialità;
- tensione drammatica;
- ritmo, originalità e precisione.

Indica cosa funziona in A e cosa in B.

Se ritieni che gli elementi migliori
possano essere combinati, spiega in modo
concreto come creare una terza versione
organica, senza assemblaggi meccanici.

Individua anche ciò che va eliminato:
ripetizioni, spiegazioni superflue,
incoerenze o passaggi deboli.

Non approvare automaticamente nessun testo.
""",
        {
            "version_A": record.get("A", ""),
            "version_B": record.get("B", ""),
        },
        1050,
    )


# ==========================================================
# NUOVA FUNZIONE — VERSIONE C
# ==========================================================


def write_version_c(
    scene, alone, narrator, record,
    additional_notes=""
):
    """
    Una sola chiamata API.
    Usa A, B e il giudizio critico.

    Non altera A e B.
    Non approva automaticamente C.
    """

    return ask_ai(
        """
Sei un romanziere ed editor letterario.

Devi creare una VERSIONE C:
una nuova stesura compiuta, ottenuta
dalla fusione artistica delle versioni
A e B alla luce del giudizio critico.

REGOLE:

1. Leggi attentamente A, B e il giudizio.

2. Se il giudizio individua elementi
migliori in entrambe, combinali davvero:
dialoghi, struttura, atmosfera,
introspezione, gesti, tensione e ritmo.

3. NON cucire insieme meccanicamente
blocchi di A e B. Riscrivi la scena
come un'opera narrativa unitaria.

4. Mantieni una voce coerente e
riconoscibile dall'inizio alla fine.

5. Usa la prima persona singolare
e il tempo presente.

6. Evita ripetizioni, contraddizioni,
passaggi ridondanti e cambi di stile
improvvisi.

7. Rispetta i fatti approvati, la memoria
del personaggio, le sue relazioni e
le informazioni che effettivamente conosce.

8. Non aggiungere avvenimenti importanti
che non siano sostenuti dal contesto,
dalle versioni e dalla regia.

9. La direzione narrativa approvata
orienta la scena, ma non obbliga
il comportamento del protagonista.

10. Se il filone è ADA ALONE,
Noa non compare e non conosce
gli eventi di questa vicenda.

11. Il giudizio critico è una guida,
non un testo da riportare nel racconto.

12. Se il giudizio suggerisce che una
versione è nettamente superiore,
parti dalla migliore e integra soltanto
ciò che arricchisce davvero la scena.

13. Restituisci esclusivamente il
racconto completo, senza titolo
introduttivo, commenti o spiegazioni.

Il risultato deve sembrare scritto
da un unico autore, non assemblato
da due stesure differenti.
""",
        {
            "narrator": narrator,
            "scene": scene["title"],
            "narrative_lane": (
                "ADA ALONE"
                if alone else "PRINCIPALE"
            ),
            "context": (
                scene.get("context_approved")
                or scene.get("approved_context")
                or scene.get("context")
                or ""
            )[:1500],
            "approved_direction": as_dict(
                scene.get("direction")
            ).get("active"),
            "character_memory": relevant_memory(
                narrator, scene, alone
            ),
            "version_A": record.get("A", ""),
            "version_B": record.get("B", ""),
            "critical_review": record.get("review", ""),
            "additional_author_notes": additional_notes,
        },
        3300,
    )


# ==========================================================
# ESPORTAZIONE
# ==========================================================


def make_word(title, content):
    document = Document()
    document.add_heading(title, 0)

    for paragraph in content.split("\n"):
        document.add_paragraph(paragraph)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def export_texts(title, filename, content):
    if not content.strip():
        return

    columns = st.columns(3)

    with columns[0]:
        st.download_button(
            "TXT",
            content.encode("utf-8"),
            file_name=filename + ".txt",
            mime="text/plain",
            key=filename + "_txt",
        )

    with columns[1]:
        st.download_button(
            "MARKDOWN",
            content.encode("utf-8"),
            file_name=filename + ".md",
            mime="text/markdown",
            key=filename + "_md",
        )

    with columns[2]:
        st.download_button(
            "WORD",
            make_word(title, content),
            file_name=filename + ".docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            key=filename + "_docx",
        )


# ==========================================================
# INTERFACCIA MEMORIA
# ==========================================================


def render_memory_editor(scene, alone, narrator):
    key = scene["id"] + "_" + narrator

    with st.expander("MEMORIA DEL PERSONAGGIO"):
        record = narrative_record(
            scene, alone, narrator
        )

        if not record.get("approved"):
            st.info(
                "Approva prima il racconto."
            )
            return

        proposal_key = "memory_proposal_" + key

        if st.button(
            "ESTRAI RICORDI",
            key="extract_" + key,
            disabled=AI is None,
        ):
            with st.spinner("Analisi della memoria..."):
                proposal, error = suggest_memory(
                    scene, alone, narrator
                )

            if error:
                st.error(error)
            else:
                st.session_state[
                    proposal_key
                ] = proposal

        proposal = st.session_state.get(
            proposal_key
        )

        if not isinstance(proposal, dict):
            return

        edited = st.text_area(
            "Controlla e correggi la memoria",
            value=dump(proposal),
            height=260,
            key="memory_text_" + key,
        )

        if st.button(
            "APPROVA MEMORIA",
            key="approve_memory_" + key,
        ):
            parsed = parse_json(edited)

            if not isinstance(parsed, dict):
                st.error("JSON non valido.")
            elif approve_memory(narrator, parsed):
                st.session_state.pop(
                    proposal_key, None
                )
                st.rerun()


# ==========================================================
# OFFICINA DEL ROMANZO — A / B / C
# ==========================================================


def render_workshop(scene, alone, narrator):
    key = scene["id"] + "_" + narrator

    record = narrative_record(
        scene, alone, narrator
    )

    record.update(
        fill_defaults(record, empty_narrative())
    )

    st.markdown("---")
    st.header("Officina del romanzo")

    notes = st.text_area(
        "Indicazioni letterarie dell'autore",
        value=record.get("feedback", ""),
        key="notes_" + key,
    )

    # ------------------------------------------------------
    # VERSIONI A E B
    # ------------------------------------------------------

    if st.button(
        "GENERA VERSIONI A E B",
        key="generate_ab_" + key,
        disabled=AI is None,
    ):
        with st.spinner(
            "Scrittura delle versioni A e B..."
        ):
            a = write_version(
                scene, alone, narrator, "A", notes
            )

            b = (
                write_version(
                    scene, alone, narrator, "B", notes
                )
                if not ai_failed(a)
                else ""
            )

        if ai_failed(a):
            st.error(a)

        elif ai_failed(b):
            st.error(b)

        else:
            def change():
                record["A"] = a
                record["B"] = b
                record["feedback"] = notes

                # A e B sono cambiate: il vecchio
                # giudizio non va più considerato
                # automaticamente attuale.
                record["review"] = ""
                record["review_at"] = ""

                # L'eventuale C precedente è
                # conservata: non cancelliamo testo.
                editorial_entry(
                    "versioni A e B",
                    scene["title"],
                    "",
                    "Nuove stesure A e B generate",
                )

            if save(change):
                st.rerun()

    # ------------------------------------------------------
    # VISUALIZZAZIONE DELLE TRE VERSIONI
    # ------------------------------------------------------

    if any(
        record.get(version)
        for version in ("A", "B", "C")
    ):
        tabs = st.tabs([
            "VERSIONE A",
            "VERSIONE B",
            "VERSIONE C",
        ])

        for tab, version in zip(
            tabs, ("A", "B", "C")
        ):
            with tab:
                value = record.get(version, "")

                if value:
                    if version == "C":
                        st.caption(
                            "Fusione letteraria guidata "
                            "dal giudizio critico."
                        )
                    story_box(value)
                else:
                    st.info(
                        "Versione non ancora generata."
                    )

    # ------------------------------------------------------
    # GIUDIZIO CRITICO
    # ------------------------------------------------------

    st.subheader("Giudizio critico")

    has_ab = bool(
        record.get("A", "").strip()
        and record.get("B", "").strip()
    )

    if st.button(
        "RICHIEDI GIUDIZIO CRITICO",
        key="critic_" + key,
        disabled=(
            AI is None
            or not has_ab
        ),
    ):
        with st.spinner(
            "Il critico confronta A e B..."
        ):
            review = literary_critic(record)

        if ai_failed(review):
            st.error(review)

        else:
            previous_review = record.get(
                "review", ""
            )

            def change():
                record["review"] = review
                record["review_at"] = now()

                editorial_entry(
                    "giudizio critico",
                    scene["title"],
                    previous_review,
                    review,
                )

            if save(change):
                st.rerun()

    if record.get("review"):
        story_box(record["review"])

    # ------------------------------------------------------
    # VERSIONE C: FUSIONE DELLE DUE STESURE
    # ------------------------------------------------------

    st.markdown("---")
    st.subheader("Versione C — Fusione letteraria")

    st.write(
        "La Versione C nasce dagli elementi migliori "
        "di A e B, seguendo le indicazioni del critico. "
        "Il programma la riscrive con una voce "
        "narrativa unitaria, senza assemblare "
        "meccanicamente i paragrafi."
    )

    c_notes = st.text_area(
        "Indicazioni aggiuntive per la fusione",
        placeholder=(
            "Esempio: conserva i dialoghi di A "
            "e l'introspezione di B. "
            "Rendi il finale più asciutto."
        ),
        key="c_notes_" + key,
        height=100,
    )

    c_ready = bool(
        record.get("A", "").strip()
        and record.get("B", "").strip()
        and record.get("review", "").strip()
    )

    if not c_ready:
        st.caption(
            "Per generare C occorrono "
            "le versioni A e B e il giudizio critico."
        )

    if record.get("C"):
        st.warning(
            "Esiste già una Versione C. "
            "Se ne generi un'altra, quella attuale "
            "sarà conservata nello storico delle bozze C."
        )

    if st.button(
        "GENERA VERSIONE C — FUSIONE CRITICA",
        key="generate_c_" + key,
        disabled=(
            AI is None
            or not c_ready
        ),
        use_container_width=True,
    ):
        with st.spinner(
            "Riscrittura letteraria della Versione C..."
        ):
            c = write_version_c(
                scene,
                alone,
                narrator,
                record,
                c_notes,
            )

        if ai_failed(c):
            st.error(c)

        else:
            def change():
                previous_c = record.get("C", "")

                if previous_c:
                    record["history"].append({
                        "text": previous_c,
                        "type": "versione_C_precedente",
                        "replaced_at": now(),
                        "reason": (
                            "Nuova fusione letteraria generata"
                        ),
                    })

                record["C"] = c
                record["C_critique"] = record.get(
                    "review", ""
                )
                record["C_created_at"] = now()

                editorial_entry(
                    "versione C",
                    scene["title"],
                    previous_c,
                    c,
                    "Fusione di A e B secondo il giudizio critico",
                )

            if save(change):
                st.rerun()

    if record.get("C"):
        st.caption(
            "Questa versione è una proposta. "
            "Non è ancora il testo canonico."
        )

    # ------------------------------------------------------
    # EDITOR A / B / C / BOZZA
    # ------------------------------------------------------

    st.markdown("---")
    st.subheader("Revisione e approvazione")

    options = ["Bozza libera"]

    if record.get("A"):
        options.append("Versione A")

    if record.get("B"):
        options.append("Versione B")

    if record.get("C"):
        options.append("Versione C")

    selected = st.selectbox(
        "Quale versione vuoi modificare?",
        options,
        key="version_choice_" + key,
    )

    selected_field = {
        "Bozza libera": "draft",
        "Versione A": "A",
        "Versione B": "B",
        "Versione C": "C",
    }[selected]

    initial = record.get(selected_field, "")

    editor_key = (
        "story_editor_"
        + key
        + "_"
        + selected_field
    )

    source_key = editor_key + "_source"

    # Mantiene il testo dell'autore durante
    # le normali interazioni. Lo aggiorna
    # quando cambia effettivamente la fonte.
    if (
        st.session_state.get(source_key)
        != initial
    ):
        st.session_state[editor_key] = initial
        st.session_state[source_key] = initial

    edited = st.text_area(
        "Racconto modificabile",
        height=360,
        key=editor_key,
    )

    reason = st.text_input(
        "Motivazione delle modifiche",
        key="reason_" + key,
    )

    left, right = st.columns(2)

    with left:
        if st.button(
            "SALVA LA VERSIONE MODIFICATA",
            key="save_edited_" + key,
            disabled=not edited.strip(),
        ):
            def change():
                previous = record.get(
                    selected_field, ""
                )

                if previous and previous != edited:
                    record["history"].append({
                        "text": previous,
                        "type": selected_field,
                        "replaced_at": now(),
                        "reason": reason,
                    })

                record[selected_field] = edited

                editorial_entry(
                    "revisione letteraria",
                    scene["title"],
                    previous,
                    edited,
                    reason,
                )

            if save(change):
                st.rerun()

    with right:
        if st.button(
            "APPROVA E MEMORIZZA",
            key="approve_story_" + key,
            disabled=not edited.strip(),
        ):
            def change():
                previous = record.get(
                    "approved", ""
                )

                if previous and previous != edited:
                    record["history"].append({
                        "text": previous,
                        "type": "testo_approvato_precedente",
                        "replaced_at": now(),
                        "reason": reason,
                    })

                # Il testo approvato è quello
                # attualmente visibile nell'editor.
                record[selected_field] = edited
                record["draft"] = edited
                record["approved"] = edited
                record["approved_source"] = selected
                record["approved_at"] = now()
                record["status"] = "approvata"

                editorial_entry(
                    "racconto approvato",
                    scene["title"],
                    previous,
                    edited,
                    (
                        "Fonte: "
                        + selected
                        + ". "
                        + reason
                    ),
                )

            if save(change):
                st.rerun()

    st.caption(
        "Soltanto APPROVA E MEMORIZZA rende "
        "il testo definitivo. Generare C non "
        "cambia il racconto già approvato."
    )

    export_texts(
        scene["title"],
        key + "_" + selected_field,
        edited,
    )

    # ------------------------------------------------------
    # STORICO E MEMORIA
    # ------------------------------------------------------

    if record.get("approved"):
        with st.expander("RACCONTO APPROVATO"):
            st.caption(
                "Fonte: "
                + record.get(
                    "approved_source", "non specificata"
                )
            )
            story_box(record["approved"])

    with st.expander("STORICO DELLE VERSIONI"):
        for item in reversed(
            as_list(record.get("history"))
        ):
            if not isinstance(item, dict):
                continue

            st.caption(
                item.get("replaced_at", "")
                + " — "
                + item.get("type", "")
            )
            story_box(item.get("text", ""))

    with st.expander("TRASCRIZIONE DEL DIALOGO"):
        st.text(transcript(scene, alone))

    render_memory_editor(
        scene, alone, narrator
    )


# ==========================================================
# PERSONAGGI
# ==========================================================


def page_people():
    theme()

    character = st.selectbox(
        "Personaggio", PEOPLE
    )

    header(
        character,
        "Profilo di " + character,
    )

    agent = book["agents"][character]

    profile_text = st.text_area(
        "Profilo",
        value=agent.get("profile", ""),
        height=180,
        key="profile_" + character,
    )

    if st.button(
        "APPROVA PROFILO",
        key="save_profile_" + character,
    ):
        def change():
            previous = agent.get("profile", "")

            agent["profile_history"].append({
                "text": previous,
                "date": now(),
            })

            agent["profile"] = profile_text

            editorial_entry(
                "profilo",
                character,
                previous,
                profile_text,
            )

        if save(change):
            st.rerun()

    st.subheader("Memoria narrativa personale")

    memory = agent["smart_memory"]

    identity = st.text_area(
        "Identità narrativa sintetica",
        value=memory.get("identity", ""),
        height=120,
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

    with st.expander("RICORDI"):
        for item in as_list(memory.get("events")):
            if isinstance(item, dict):
                st.write(item.get("text", ""))

    with st.expander("RELAZIONI"):
        for person, value in as_dict(
            memory.get("relations")
        ).items():
            st.write(
                "**" + person + ":** " + str(value)
            )

    with st.expander("SEGRETI CONOSCIUTI"):
        for item in as_list(
            memory.get("secrets")
        ):
            if isinstance(item, dict):
                st.write(item.get("text", ""))


# ==========================================================
# ARCHIVIO E REGISTRO EDITORIALE
# ==========================================================


def page_archive():
    theme()
    st.title("Archivio del romanzo")

    st.subheader("Filone principale")

    for scene in book["scenes"]:
        for person in PEOPLE:
            record = as_dict(
                scene["narrative"].get(person)
            )

            approved = record.get("approved", "")

            if approved:
                with st.expander(
                    scene["title"] + " — " + person
                ):
                    story_box(approved)

    st.subheader(
        "Filone esclusivo ADA ALONE"
    )

    for scene in book["ada_scenes"]:
        approved = scene[
            "narrative"
        ].get("approved", "")

        if approved:
            with st.expander(
                scene["title"] + " — ADA ALONE"
            ):
                story_box(approved)


def page_editorial():
    theme()
    st.title("Registro editoriale")

    for item in reversed(
        as_list(book.get("editorial_log"))
    ):
        if not isinstance(item, dict):
            continue

        with st.expander(
            item.get("date", "")[:10]
            + " — "
            + item.get("subject", "")
        ):
            st.write(item.get("category", ""))
            st.write(item.get("reason", ""))

            before = str(item.get("before", ""))
            after = str(item.get("after", ""))

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
                diff or "Nessuna differenza.",
                language="diff",
            )


# ==========================================================
# ECONOMIA API
# ==========================================================


def page_settings():
    theme()
    st.title("Economia API e memoria")

    st.write(
        "GO ALONE mantiene quattro chiamate "
        "autonome. La Versione C utilizza "
        "una chiamata aggiuntiva, solo quando "
        "premi il pulsante di generazione."
    )

    settings = book["settings"]

    lines = st.slider(
        "Battute recenti inviate",
        min_value=4,
        max_value=20,
        value=int(
            settings.get("context_lines", 10)
        ),
    )

    memories = st.slider(
        "Ricordi pertinenti",
        min_value=2,
        max_value=12,
        value=int(
            settings.get("memory_items", 8)
        ),
    )

    if st.button("SALVA IMPOSTAZIONI"):
        if save(
            lambda: settings.update(
                context_lines=lines,
                memory_items=memories,
            )
        ):
            st.rerun()


# ==========================================================
# NAVIGAZIONE LATERALE
# ==========================================================


def main_navigation():
    index = max(
        0,
        min(
            len(SCENE_IDS) - 1,
            int(
                st.session_state.get(
                    "scene_index", 0
                )
            ),
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

    new_index = scene_pos(selected)

    if new_index != index:
        st.session_state["scene_index"] = new_index
        st.rerun()


def sidebar():
    st.sidebar.title("TURING HOTEL")

    pov = st.session_state.get("pov", "Noa")

    if pov == "Ada":
        mode = st.sidebar.radio(
            "FILONE DI ADA",
            ["Storia condivisa", "ADA ALONE"],
            key="ada_mode",
        )

        if mode == "ADA ALONE":
            st.sidebar.markdown("---")
            st.sidebar.subheader(
                "Scene autonome di Ada"
            )

            if st.sidebar.button(
                "+ NUOVA SCENA ADA ALONE",
                use_container_width=True,
            ):
                item = empty_ada_scene()

                if save(
                    lambda: book["ada_scenes"].append(item)
                ):
                    st.session_state[
                        "ada_scene_id"
                    ] = item["id"]
                    st.rerun()

            identifiers = [
                item["id"]
                for item in book["ada_scenes"]
            ]

            if identifiers:
                current = st.session_state.get(
                    "ada_scene_id", ""
                )

                if current not in identifiers:
                    current = identifiers[0]

                selected = st.sidebar.selectbox(
                    "SCENA DI ADA",
                    identifiers,
                    index=identifiers.index(current),
                    format_func=lambda sid: (
                        get_ada_scene(sid)["title"]
                    ),
                    key="ada_scene_selector",
                )

                st.session_state[
                    "ada_scene_id"
                ] = selected
            else:
                st.sidebar.info(
                    "Non ci sono ancora scene "
                    "autonome di Ada."
                )

        else:
            main_navigation()

    else:
        main_navigation()

    st.sidebar.markdown("---")

    pages = [
        ("ARCHIVIO SCENE", "archive"),
        ("ARCHIVIO PERSONAGGI", "people"),
        ("REGISTRO EDITORIALE", "editorial"),
        ("ECONOMIA API", "settings"),
        ("CAMBIA STORIA", "characters"),
    ]

    for label, target in pages:
        if st.sidebar.button(
            label,
            key="nav_" + target,
            use_container_width=True,
        ):
            st.session_state["page"] = target
            st.rerun()

    with st.sidebar.expander("ARCHIVIO GITHUB"):
        st.caption(GH_OWNER + "/" + GH_REPO)

        if st.button("RICARICA ARCHIVIO"):
            if reload_book():
                st.rerun()

        st.download_button(
            "SCARICA BACKUP",
            dump(book).encode("utf-8"),
            file_name="turing_hotel_backup.json",
            mime="application/json",
        )

        pending = st.session_state.get(
            "pending_backup", None
        )

        if pending is not None:
            st.warning(
                "È disponibile una copia "
                "dell'ultima modifica non salvata."
            )

            st.download_button(
                "RECUPERA MODIFICA NON SALVATA",
                dump(pending).encode("utf-8"),
                file_name="modifica_non_salvata.json",
                mime="application/json",
            )


# ==========================================================
# SCHERMATA INIZIALE CON COPERTINA
# ==========================================================


def page_entrance():
    theme()
    render_cover()

    st.markdown(
        "<div style='height:14px'></div>",
        unsafe_allow_html=True,
    )

    left, middle, right = st.columns([1, 2, 1])

    with middle:
        st.markdown(
            "<h1 style='text-align:center'>"
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
        ):
            st.session_state["page"] = "characters"
            st.rerun()


def page_characters():
    theme()
    st.title("Scegli il filone narrativo")

    columns = st.columns(2)

    for column, person in zip(
        columns, ["Noa", "Ada"]
    ):
        with column:
            image = portrait(person)

            if image:
                st.image(
                    str(image),
                    use_container_width=True,
                )

            st.subheader(person)

            if st.button(
                "ENTRA NELLA STORIA DI "
                + person.upper(),
                key="choose_" + person,
                use_container_width=True,
            ):
                st.session_state["pov"] = person
                st.session_state["page"] = "story"
                st.rerun()


# ==========================================================
# PAGINA STORIA
# ==========================================================


def page_story():
    sidebar()

    pov = st.session_state.get("pov", "Noa")

    alone = (
        pov == "Ada"
        and st.session_state.get(
            "ada_mode", "Storia condivisa"
        ) == "ADA ALONE"
    )

    theme(alone)

    if alone:
        scene = get_ada_scene(
            st.session_state.get("ada_scene_id", "")
        )

        if scene is None:
            st.info(
                "Premi + NUOVA SCENA ADA ALONE "
                "nella barra laterale."
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
                        "scene_index", 0
                    )
                ),
            ),
        )

        scene = get_main_scene(
            SCENE_IDS[index]
        )

        if scene is None:
            st.error("Scena principale non trovata.")
            return

        cast = cast_of(scene)

        narrator = (
            pov if pov in cast
            else cast[0] if cast
            else pov
        )

    header(pov, scene["title"], alone)

    if alone:
        st.info(
            "Questa scena appartiene esclusivamente "
            "ad Ada. Non deve corrispondere "
            "a una scena di Noa."
        )

    st.markdown("---")
    render_media(scene, pov, alone)

    st.markdown("---")
    render_context(scene, alone)

    render_advisor(scene, alone)

    st.markdown("---")
    render_dialogues(scene, alone)

    if not alone:
        st.markdown("---")
        options = cast_of(scene)

        if options:
            narrator = st.selectbox(
                "PUNTO DI VISTA",
                options,
                index=(
                    options.index(pov)
                    if pov in options
                    else 0
                ),
                key="narrator_" + scene["id"],
            )

    render_workshop(scene, alone, narrator)

    st.markdown("---")

    if alone:
        index = next(
            (
                i
                for i, item in enumerate(
                    book["ada_scenes"]
                )
                if item["id"] == scene["id"]
            ),
            0,
        )

        left, right = st.columns(2)

        with left:
            if index > 0:
                if st.button("← ADA PRECEDENTE"):
                    st.session_state[
                        "ada_scene_id"
                    ] = book["ada_scenes"][
                        index - 1
                    ]["id"]
                    st.rerun()

        with right:
            if index < len(book["ada_scenes"]) - 1:
                if st.button("ADA SUCCESSIVA →"):
                    st.session_state[
                        "ada_scene_id"
                    ] = book["ada_scenes"][
                        index + 1
                    ]["id"]
                    st.rerun()

    else:
        index = st.session_state["scene_index"]
        left, right = st.columns(2)

        with left:
            if index > 0:
                if st.button("← PRECEDENTE"):
                    st.session_state[
                        "scene_index"
                    ] -= 1
                    st.rerun()

        with right:
            if index < len(SCENE_IDS) - 1:
                if st.button("SUCCESSIVA →"):
                    st.session_state[
                        "scene_index"
                    ] += 1
                    st.rerun()


# ==========================================================
# PROTEZIONE ARCHIVIO
# ==========================================================


if not st.session_state.get(
    "archive_exists", False
):
    st.title("Archivio non trovato")

    st.warning(
        "romanzo_web.json non è presente "
        "nel repository privato. "
        "Non creare un archivio nuovo se "
        "dovrebbe già esistere."
    )

    confirmed = st.checkbox(
        "Confermo la creazione di un archivio nuovo."
    )

    if st.button(
        "CREA ARCHIVIO",
        disabled=not confirmed,
    ):
        try:
            sha = github_write(
                GH_OWNER, GH_REPO,
                GH_BRANCH, GH_TOKEN,
                ARCHIVE_FILE,
                dump(book).encode("utf-8"),
            )

            st.session_state["archive_sha"] = sha
            st.session_state["saved_base"] = (
                copy.deepcopy(book)
            )
            st.session_state["archive_exists"] = True
            st.rerun()

        except Exception as exc:
            st.error(str(exc))

    st.stop()


# ==========================================================
# NAVIGAZIONE PRINCIPALE
# ==========================================================


page = st.session_state.get("page", "entrance")

if page in (
    "people", "archive", "editorial", "settings"
):
    if st.button("← TORNA ALLA STORIA"):
        st.session_state["page"] = "story"
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
    st.session_state["page"] = "entrance"
    st.rerun()
