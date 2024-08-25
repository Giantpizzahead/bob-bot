import requests

API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
headers = {"Authorization": "Bearer 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"}


def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.content


image_bytes = query(
    {
        "inputs": "Zoe versus Ahri in a League of Legends game",
    }
)
# You can access the image with PIL.Image for example
import io

from PIL import Image

image = Image.open(io.BytesIO(image_bytes))
image.save("image.jpg")
