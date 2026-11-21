"""Classify discovered IDs for display only, preserving the original ID for requests."""
import re


def media_kind(model):
    name = re.sub(r"[^a-z0-9一-鿿]+", "-", model.casefold()).strip("-")
    if re.search(r"(?:^|-)(?:embedding[s]?|caption(?:ing)?|understanding|ocr|vision-language)(?:-|$)", name):
        return None

    def matches(pattern):
        return re.search(r"(?:^|-)(?:" + pattern + r")(?=-|[0-9]|$)", name) is not None

    if matches(r"image-to-video|text-to-video|i2v|t2v|r2v|v2v|ti2v|first-last-frame-to-video"):
        return "video"
    if matches(r"image|imageedit|imagen|dall-?e|flux|stable-diffusion|sdxl|sd3|"
               r"ideogram|recraft|midjourney|seedream|seededit|nano-?banana|"
               r"kolors|cogview|t2i|i2i|text-to-image|即梦图片|可灵图片|海螺图片"):
        return "image"
    if matches(r"veo|sora|seedance|kling|hailuo|hunyuan-?video|cogvideo[x]?|"
               r"pika|pixverse|dream-machine|ray-?2|ltx-?video|gen-?4|gen-?3a|"
               r"video|可灵视频|即梦视频|海螺视频"):
        return "video"
    return None
