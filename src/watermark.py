import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont
import os
import json
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def add_watermark_to_image(image, watermark_text, position, font, font_size, transparency, text_color, bg_color, spacing=None):
    """Add watermark to a single image frame."""
    original = image.convert("RGBA")

    # Make the image editable
    txt = Image.new('RGBA', original.size, (255, 255, 255, 0))

    # Initialize ImageDraw
    draw = ImageDraw.Draw(txt)

    # Prepare colors
    if bg_color is not None:
        if len(bg_color) == 3:
            bg_rgba = (bg_color[0], bg_color[1], bg_color[2], transparency)
        else:
            bg_rgba = tuple(bg_color)
    else:
        bg_rgba = None

    if len(text_color) == 3:
        text_rgba = (text_color[0], text_color[1], text_color[2], 255)
    else:
        text_rgba = tuple(text_color)

    # Calculate text dimensions
    text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]

    # Check for repetitive modes
    if position in ("repetitive", "repetitive-45degrees", "repetitive-45", "tiled"):
        if spacing is not None:
            if isinstance(spacing, (int, float)):
                pad_x = int(spacing) if spacing >= 1 else int(font_size * spacing)
                pad_y = pad_x
            elif isinstance(spacing, (list, tuple)) and len(spacing) >= 2:
                pad_x = int(spacing[0])
                pad_y = int(spacing[1])
            else:
                pad_x = max(30, int(font_size * 1.5))
                pad_y = pad_x
        else:
            pad_x = max(30, int(font_size * 1.5))
            pad_y = max(30, int(font_size * 1.5))

        if position in ("repetitive-45degrees", "repetitive-45"):
            # Create a single tile with text and optional background rectangle
            tile_w = text_width + 20
            tile_h = text_height + 20
            text_tile = Image.new('RGBA', (tile_w, tile_h), (255, 255, 255, 0))
            tile_draw = ImageDraw.Draw(text_tile)
            if bg_rgba and (len(bg_rgba) < 4 or bg_rgba[3] > 0):
                tile_draw.rectangle([0, 0, tile_w, tile_h], fill=bg_rgba)
            tile_draw.text((10, 10), watermark_text, fill=text_rgba, font=font)

            # Rotate single tile 45 degrees
            rotated_tile = text_tile.rotate(45, expand=True, resample=Image.BICUBIC)
            rw, rh = rotated_tile.size

            step_x = rw + pad_x
            step_y = rh + pad_y

            for y in range(-rh, original.height + rh, step_y):
                for x in range(-rw, original.width + rw, step_x):
                    txt.paste(rotated_tile, (x, y), rotated_tile)
        else:
            step_x = text_width + pad_x
            step_y = text_height + pad_y
            for y in range(10, original.height, step_y):
                for x in range(10, original.width, step_x):
                    if bg_rgba and (len(bg_rgba) < 4 or bg_rgba[3] > 0):
                        draw.rectangle([x - 5, y - 5, x + text_width + 5, y + text_height + 5], fill=bg_rgba)
                    draw.text((x, y), watermark_text, fill=text_rgba, font=font)

        watermarked = Image.alpha_composite(original, txt).convert("RGB")
        return watermarked

    # Single positioning
    if position == "top-left":
        pos = (10, 10)
    elif position == "top-right":
        pos = (original.width - text_width - 10, 10)
    elif position in ("top-center", "top_center"):
        pos = ((original.width - text_width) // 2, 10)
    elif position == "bottom-left":
        pos = (10, original.height - text_height - 10)
    elif position == "bottom-right":
        pos = (original.width - text_width - 10, original.height - text_height - 10)
    elif position in ("bottom-center", "bottom_center"):
        pos = ((original.width - text_width) // 2, original.height - text_height - 10)
    elif position == "center":
        pos = ((original.width - text_width) // 2, (original.height - text_height) // 2)
    else:
        pos = position  # Use as coordinates if not a predefined position

    # Add background rectangle if bg_color is provided and has non-zero alpha
    if bg_rgba and (len(bg_rgba) < 4 or bg_rgba[3] > 0):
        draw.rectangle([pos[0] - 5, pos[1] - 5, pos[0] + text_width + 5, pos[1] + text_height + 5], fill=bg_rgba)

    # Add text to image
    draw.text(pos, watermark_text, fill=text_rgba, font=font)

    # Combine original image with watermark
    watermarked = Image.alpha_composite(original, txt).convert("RGB")
    return watermarked

def process_image(input_image_path, output_image_path, watermark_text, position, font_path, font_size_ratio, transparency, text_color, bg_color, spacing=None):
    """Process image files and add watermark."""
    try:
        original = Image.open(input_image_path)
    except Exception as e:
        # Fallback to ffmpeg conversion if initial opening fails
        try:
            import subprocess
            temp_png = f"{input_image_path}.temp.png"
            subprocess.run(["ffmpeg", "-y", "-i", input_image_path, temp_png], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            original = Image.open(temp_png)
            os.remove(temp_png)
        except Exception as ffmpeg_e:
            logging.error(f"Failed to open {input_image_path} (PIL error: {e}, ffmpeg error: {ffmpeg_e})")
            return

    width, height = original.size
    min_dimension = min(width, height)
    font_size = max(10, int(min_dimension * font_size_ratio))
    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()

    watermarked = add_watermark_to_image(original, watermark_text, position, font, font_size, transparency, text_color, bg_color, spacing=spacing)
    watermarked.save(output_image_path)
    logging.info(f"Watermark added to {input_image_path}, saved as {output_image_path}")

def process_video(input_video_path, output_video_path, watermark_text, position, font_path, font_size_ratio, transparency, text_color, bg_color, spacing=None):
    """Process video files and add watermark to each frame."""
    try:
        video = VideoFileClip(input_video_path)
    except Exception as e:
        logging.error(f"Failed to open video {input_video_path}: {e}")
        return

    width, height = video.size
    min_dimension = min(width, height)
    font_size = max(10, int(min_dimension * font_size_ratio))
    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()

    def add_watermark_to_frame(get_frame, t):
        frame = Image.fromarray(get_frame(t))
        watermarked_frame = add_watermark_to_image(frame, watermark_text, position, font, font_size, transparency, text_color, bg_color, spacing=spacing)
        return np.array(watermarked_frame)

    watermarked_video = video.fl(add_watermark_to_frame)
    watermarked_video.write_videofile(output_video_path, codec='libx264', audio_codec='aac')
    logging.info(f"Watermark added to video {input_video_path}, saved as {output_video_path}")

def process_gif(input_gif_path, output_gif_path, watermark_text, position, font_path, font_size_ratio, transparency, text_color, bg_color, spacing=None):
    """Process GIF files and add watermark to each frame."""
    try:
        gif = Image.open(input_gif_path)
    except Exception as e:
        logging.error(f"Failed to open GIF {input_gif_path}: {e}")
        return

    frames = []
    try:
        while True:
            frame = gif.copy().convert("RGBA")
            width, height = frame.size
            min_dimension = min(width, height)
            font_size = max(10, int(min_dimension * font_size_ratio))
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()

            watermarked_frame = add_watermark_to_image(frame, watermark_text, position, font, font_size, transparency, text_color, bg_color, spacing=spacing)
            frames.append(watermarked_frame)
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass

    frames[0].save(output_gif_path, save_all=True, append_images=frames[1:], loop=0, duration=gif.info['duration'])
    logging.info(f"Watermark added to GIF {input_gif_path}, saved as {output_gif_path}")

def load_config(config_path):
    try:
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)
            return config
    except Exception as e:
        logging.error(f"Failed to load configuration file {config_path}: {e}")
        return {}

def parse_args():
    parser = argparse.ArgumentParser(description="Add watermark to images and videos.")
    parser.add_argument('--config', type=str, default='config.json', help='Path to the configuration file.')
    return parser.parse_args()

def main():
    args = parse_args()
    config = load_config(args.config)

    watermark_text = config.get("watermark_text", "Sample Watermark")
    position = config.get("position", "bottom-right")
    font_path = config.get("font_path", None)
    font_size_ratio = config.get("font_size_ratio", 0.05)
    input_folder = config.get("input_folder", "media")
    output_folder = config.get("output_folder", "watermarked_media")
    transparency = config.get("transparency", 128)
    spacing = config.get("spacing", None)
    text_color_cfg = config.get("text_color", [255, 255, 255])
    text_color = tuple(text_color_cfg) if text_color_cfg is not None else (255, 255, 255, 255)

    bg_color_cfg = config.get("bg_color", [0, 0, 0])
    bg_color = tuple(bg_color_cfg) if bg_color_cfg is not None else None

    os.makedirs(output_folder, exist_ok=True)

    for media_file in os.listdir(input_folder):
        input_media_path = os.path.join(input_folder, media_file)
        output_media_path = os.path.join(output_folder, f"watermarked_{media_file}")

        if media_file.lower().endswith(('png', 'jpg', 'jpeg', 'webp')):
            process_image(input_media_path, output_media_path, watermark_text, position, font_path, font_size_ratio, transparency, text_color, bg_color, spacing=spacing)
        elif media_file.lower().endswith(('mp4', 'avi', 'mov', 'mkv')):
            process_video(input_media_path, output_media_path, watermark_text, position, font_path, font_size_ratio, transparency, text_color, bg_color, spacing=spacing)
        elif media_file.lower().endswith(('gif',)):
            process_gif(input_media_path, output_media_path, watermark_text, position, font_path, font_size_ratio, transparency, text_color, bg_color, spacing=spacing)
        else:
            logging.warning(f"Unsupported file format: {media_file}")

if __name__ == "__main__":
    main()
