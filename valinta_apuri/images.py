import json
import os
import shutil

import filetype
import piexif
import piexif.helper
from PIL import Image


TMP_FOLDER = "static/img_tmp"
CUR_FOLDER = "static/img_cur"
# {item id: IMG fileName} of the images currently in CUR_FOLDER. Replacing an image in the list
# gives it a new fileName, so an unchanged name means the converted webp can be reused.
MANIFEST_NAME = "manifest.json"


def sync_images(client, list_id, image_files):
    """Makes CUR_FOLDER hold <item id>.webp for every entry of image_files ({item id: fileName})."""
    if os.path.exists(TMP_FOLDER):
        shutil.rmtree(TMP_FOLDER)
    os.makedirs(TMP_FOLDER, exist_ok=True)
    os.makedirs(CUR_FOLDER, exist_ok=True)

    previous = _read_manifest()
    manifest = {}
    downloaded = 0
    # A broken image only loses that one card's picture; web.py serves
    # generic.jpg for missing images.
    for item_id, file_name in image_files.items():
        webp_name = f"{item_id}.webp"
        cur_path = os.path.join(CUR_FOLDER, webp_name)
        if previous.get(str(item_id)) == file_name and os.path.isfile(cur_path):
            shutil.copy2(cur_path, os.path.join(TMP_FOLDER, webp_name))
            manifest[str(item_id)] = file_name
            continue

        extension = os.path.splitext(file_name)[1] or ".img"
        image_path = os.path.join(TMP_FOLDER, f"{item_id}{extension}")
        try:
            data = client.download_attachment(list_id, item_id, file_name)
            with open(image_path, "wb") as image_file:
                image_file.write(data)
            if not filetype.is_image(image_path):
                raise ValueError("attachment is not an image")
            _convert_image(image_path)
            manifest[str(item_id)] = file_name
            downloaded += 1
        except Exception as error:
            print(f"Skipping image of item {item_id}: {error}")
            if os.path.exists(image_path):
                os.remove(image_path)

    with open(os.path.join(TMP_FOLDER, MANIFEST_NAME), "w") as manifest_file:
        json.dump(manifest, manifest_file)

    for entry in os.scandir(CUR_FOLDER):
        if entry.is_dir(follow_symlinks=False):
            shutil.rmtree(entry.path)
        else:
            os.unlink(entry.path)
    shutil.copytree(TMP_FOLDER, CUR_FOLDER, dirs_exist_ok=True)
    print(f"Pictures reloaded successfully! ({downloaded} downloaded, {len(manifest) - downloaded} reused)")


def _read_manifest():
    try:
        with open(os.path.join(CUR_FOLDER, MANIFEST_NAME)) as manifest_file:
            return json.load(manifest_file)
    except (OSError, ValueError):
        return {}


def _convert_image(image_path):
    with Image.open(image_path) as image:
        webp_path = image_path.rsplit(".", 1)[0] + ".webp"
        width, height = image.size
        max_side = 500
        if height >= width:
            new_height = max_side
            new_width = max(1, int(width * (new_height / height)))
        else:
            new_width = max_side
            new_height = max(1, int(height * (new_width / width)))

        exif = {"0th": {}, "Exif": {}, "1st": {}, "GPS": {}}
        exif["Exif"][piexif.ExifIFD.UserComment] = piexif.helper.UserComment.dump(
            json.dumps({"ow": width, "oh": height, "of": image.format})
        )
        image.resize((new_width, new_height), Image.Resampling.LANCZOS).convert("RGB").save(
            webp_path,
            format="WEBP",
            exif=piexif.dump(exif),
            lossless=False,
            quality=90,
            method=6,
        )
    # The list may already hold webp files; then the conversion overwrote the download.
    if os.path.abspath(image_path) != os.path.abspath(webp_path):
        os.remove(image_path)
    print(
        f"Converted {os.path.basename(image_path)} to {webp_path} "
        f"og w,h = {width}x{height} -> {new_width}x{new_height}"
    )
