from __future__ import annotations

import asyncio
from io import BytesIO

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .models import Player


CARD_SIZE = (1200, 675)
PANEL_WIDTH = CARD_SIZE[0] // 2


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_avatar(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGB")
    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)


async def _download_avatar(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                return None
            return Image.open(BytesIO(await response.read())).convert("RGB")
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return None


def _initial_avatar(player: Player, size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", size, (30, 35, 55))
    draw = ImageDraw.Draw(image)
    initial = (player.display_name or player.username or "?")[0].upper()
    font = _font(min(size) // 2, bold=True)
    box = draw.textbbox((0, 0), initial, font=font)
    draw.text(
        ((size[0] - (box[2] - box[0])) / 2, (size[1] - (box[3] - box[1])) / 2 - box[1]),
        initial,
        font=font,
        fill=(232, 238, 255),
    )
    return image


async def create_battle_card(player_one: Player, player_two: Player) -> BytesIO:
    avatar_size = (560, 560)
    async with aiohttp.ClientSession() as session:
        first, second = await asyncio.gather(
            _download_avatar(session, player_one.avatar_url),
            _download_avatar(session, player_two.avatar_url),
        )

    first = _fit_avatar(first or _initial_avatar(player_one, avatar_size), avatar_size)
    second = _fit_avatar(second or _initial_avatar(player_two, avatar_size), avatar_size)

    image = Image.new("RGB", CARD_SIZE, (11, 13, 27))
    draw = ImageDraw.Draw(image)
    image.paste(first, (35, 58))
    image.paste(second, (CARD_SIZE[0] - avatar_size[0] - 35, 58))
    draw.rectangle((0, 0, PANEL_WIDTH, CARD_SIZE[1]), outline=(107, 63, 225), width=8)
    draw.rectangle((PANEL_WIDTH, 0, CARD_SIZE[0], CARD_SIZE[1]), outline=(231, 75, 126), width=8)
    draw.rectangle((PANEL_WIDTH - 4, 0, PANEL_WIDTH + 4, CARD_SIZE[1]), fill=(245, 197, 66))
    vs_font = _font(90, bold=True)
    vs_box = draw.textbbox((0, 0), "VS", font=vs_font)
    draw.text(
        (PANEL_WIDTH - (vs_box[2] - vs_box[0]) / 2, 270),
        "VS",
        font=vs_font,
        fill=(255, 240, 178),
        stroke_width=3,
        stroke_fill=(20, 16, 38),
    )

    name_font = _font(34, bold=True)
    for player, x in ((player_one, 35), (player_two, CARD_SIZE[0] - 595)):
        label = player.display_name[:24]
        draw.rectangle((x, 575, x + 560, 635), fill=(8, 10, 20))
        draw.text((x + 18, 588), label, font=name_font, fill=(245, 247, 255))

    result = BytesIO()
    image.save(result, format="PNG", optimize=True)
    result.seek(0)
    return result


def create_battle_banner() -> BytesIO:
    image = Image.new("RGB", (800, 450), (12, 15, 30))
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 790, 440), outline=(245, 197, 66), width=7)
    draw.line((170, 340, 370, 110), fill=(168, 120, 255), width=22)
    draw.line((630, 340, 430, 110), fill=(255, 91, 133), width=22)
    draw.line((150, 325, 390, 325), fill=(225, 230, 245), width=8)
    draw.line((650, 325, 410, 325), fill=(225, 230, 245), width=8)
    font = _font(52, bold=True)
    text = "BATTLE OF CREATION"
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((800 - (box[2] - box[0])) / 2, 30), text, font=font, fill=(245, 247, 255))
    result = BytesIO()
    image.save(result, format="PNG", optimize=True)
    result.seek(0)
    return result
