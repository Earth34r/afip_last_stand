import json
import os
from PIL import Image, UnidentifiedImageError
import random


def get_json_data(self, config_path):
    configFilePath = os.path.join(os.getcwd(), config_path)

    if not os.path.exists(configFilePath):
        exit("No config.json file found. Read the README")

    with open(configFilePath) as f:
        json_data = json.load(f)

    return json_data

    # Read the input image.jpg file


def load_image(self):
    # Read and load the image to draw and get its dimensions
    try:
        im = Image.open(self.image_path)
    except FileNotFoundError:
        self.logger.exception("Failed to load image")
        exit()
    except UnidentifiedImageError:
        self.logger.exception("File found, but couldn't identify image format")

    # Convert all images to RGBA - Transparency should only be supported with PNG
    if im.mode != "RGBA":
        im = im.convert("RGBA")
        self.logger.info("Converted to rgba")
    self.pix = im.load()

    self.logger.info("Loaded image size: {}", im.size)

    self.image_size = im.size
    
def select_user_agent(self):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.3",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5.1 Safari/605.1.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.79",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.8",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.79",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115."
    ]
    return random.choice(user_agents)
