# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os

from core.parameters import Params


def ensure_pictures_fixture(scenario):
    if scenario.platform != 'Windows':
        return

    userprofile = scenario._call(['cmd.exe', '/C echo %USERPROFILE%'])
    pictures_path = os.path.join(userprofile, 'Pictures')
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        'explorer_pictures_thumbnails',
        'image_thumbnail_extra_large.png',
    )
    fixture_count = int(Params.get(
        'explorer_pictures_thumbnails', 'fixture_count', log=False
    ) or '24')
    if fixture_count < 1 or fixture_count > 200:
        raise ValueError('explorer_pictures_thumbnails:fixture_count must be 1-200')
    scenario._remote_make_dir(pictures_path)
    scenario._upload(fixture_path, pictures_path)
    source_path = os.path.join(pictures_path, os.path.basename(fixture_path))
    command = (
        f"$source='{source_path}'; $pictures='{pictures_path}'; "
        "Get-ChildItem -LiteralPath $pictures -Filter 'hobl_annoyance_*.png' "
        "-ErrorAction SilentlyContinue | Remove-Item -Force; "
        f"1..{fixture_count} | ForEach-Object {{ "
        "$destination=Join-Path $pictures ('hobl_annoyance_{0:D3}.png' -f $_); "
        "Copy-Item -LiteralPath $source -Destination $destination -Force; "
        "(Get-Item -LiteralPath $destination).LastWriteTimeUtc="
        "[DateTime]::UtcNow.AddMilliseconds($_) }"
    )
    scenario._call(['powershell.exe', '-NoProfile -Command ' + command])