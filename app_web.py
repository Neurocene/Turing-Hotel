# ============================================================
# LOCATION / NOMI FILE ROBUSTI
# ============================================================

def normalize_media_name(value):

    value = str(value).lower().strip()

    # elimina estensione
    value = re.sub(
        r"\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$",
        "",
        value,
        flags=re.IGNORECASE
    )

    # rende equivalenti:
    # reparto nascite
    # reparto_nascite
    # reparto-nascite
    # repartonascite

    value = re.sub(
        r"[\s_\-]+",
        "",
        value
    )

    return value


def scene_location_aliases(scene_id):

    mapping = {

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
            "reparto nascite",
            "reparto_nascite",
            "reparto-nascite",
            "nascite"
        ],

        "ritorno": [
            "ritorno"
        ]
    }

    return mapping.get(
        scene_id,
        [scene_id]
    )


def scene_location_name(scene_id):

    mapping = {
        "hall": "hall",
        "funerale": "funerale",
        "matrimonio": "matrimonio",
        "reparto_nascite": "repartonascite",
        "ritorno": "ritorno"
    }

    return mapping.get(
        scene_id,
        scene_id
    )


# ============================================================
# TROVA FOTO PRINCIPALE LOCATION
# ============================================================

def get_scene_cover_image(scene_id):

    if not ASSETS_DIR.exists():
        return None

    aliases = scene_location_aliases(
        scene_id
    )

    normalized_aliases = {
        normalize_media_name(alias)
        for alias in aliases
    }

    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        stem = path.stem

        normalized_stem = normalize_media_name(
            stem
        )

        # cover pura:
        # matrimonio.jpg
        # Matrimonio.JPG
        # reparto nascite.jpg

        if normalized_stem in normalized_aliases:
            return path

    return None


# ============================================================
# MEDIA COMUNI + MEDIA SPECIFICI
# ============================================================

def find_scene_media(
    scene_id,
    character
):

    if not ASSETS_DIR.exists():
        return []

    character = character.lower()

    aliases = scene_location_aliases(
        scene_id
    )

    normalized_aliases = [
        normalize_media_name(alias)
        for alias in aliases
    ]

    results = []

    for path in ASSETS_DIR.iterdir():

        if not path.is_file():
            continue

        extension = path.suffix.lower()

        if (
            extension not in IMAGE_EXTENSIONS
            and
            extension not in VIDEO_EXTENSIONS
        ):
            continue

        filename = path.name.lower()

        # ----------------------------------------------------
        # non inserire la cover pura nella galleria/video
        # matrimonio.jpg
        # ritorno.jpg
        # ecc.
        # ----------------------------------------------------

        normalized_stem = normalize_media_name(
            path.stem
        )

        if normalized_stem in normalized_aliases:
            continue

        matched = False

        for alias in aliases:

            escaped = re.escape(
                alias.lower()
            )

            # =================================================
            # SPECIFICO PERSONAGGIO
            #
            # matrimonio.noa.1.jpg
            # matrimonio.ada.2.mp4
            #
            # tollera maiuscole/minuscole
            # =================================================

            character_pattern = (
                rf"^{escaped}"
                rf"\.{character}"
                rf"\.(\d+)"
                rf"\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$"
            )

            if re.match(
                character_pattern,
                filename,
                re.IGNORECASE
            ):

                matched = True
                break

            # =================================================
            # COMUNE CON PUNTO
            #
            # matrimonio.1.jpg
            # matrimonio.2.mp4
            # =================================================

            shared_dot_pattern = (
                rf"^{escaped}"
                rf"\.(\d+)"
                rf"\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$"
            )

            if re.match(
                shared_dot_pattern,
                filename,
                re.IGNORECASE
            ):

                matched = True
                break

            # =================================================
            # COMUNE CON TRATTINO
            #
            # matrimonio-1.jpg
            # matrimonio-2.mp4
            # =================================================

            shared_dash_pattern = (
                rf"^{escaped}"
                rf"-(\d+)"
                rf"\.(jpg|jpeg|png|webp|mp4|mov|webm|m4v)$"
            )

            if re.match(
                shared_dash_pattern,
                filename,
                re.IGNORECASE
            ):

                matched = True
                break

        # ====================================================
        # SE NON HA TROVATO MATCH LETTERALE,
        # PROVA VERSIONE NORMALIZZATA
        #
        # serve soprattutto a:
        #
        # reparto nascite-1.jpg
        # reparto_nascite-1.jpg
        # repartonascite-1.jpg
        # ====================================================

        if not matched:

            stem_lower = path.stem.lower()

            for normalized_alias in normalized_aliases:

                compact_stem = normalize_media_name(
                    stem_lower
                )

                # PERSONAGGIO
                #
                # repartonascitenoa1

                char_prefix = (
                    normalized_alias
                    + character
                )

                if compact_stem.startswith(
                    char_prefix
                ):

                    rest = compact_stem[
                        len(char_prefix):
                    ]

                    if rest.isdigit():

                        matched = True
                        break

                # COMUNE
                #
                # repartonascite1

                if compact_stem.startswith(
                    normalized_alias
                ):

                    rest = compact_stem[
                        len(normalized_alias):
                    ]

                    if rest.isdigit():

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


# ============================================================
# VIDEO DELLA SCENA
# ============================================================

def get_scene_videos(
    scene_id,
    character
):

    return [
        path

        for path in find_scene_media(
            scene_id,
            character
        )

        if path.suffix.lower()
        in VIDEO_EXTENSIONS
    ]


# ============================================================
# FOTO DELLA SCENA
# ============================================================

def get_scene_images(
    scene_id,
    character
):

    return [
        path

        for path in find_scene_media(
            scene_id,
            character
        )

        if path.suffix.lower()
        in IMAGE_EXTENSIONS
    ]
