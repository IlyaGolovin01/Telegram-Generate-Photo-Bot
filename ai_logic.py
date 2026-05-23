import os
import time
import json
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

TOKENS = [t.strip() for t in os.environ.get("HF_TOKENS", "").split(",") if t.strip()]
MAX_PER_TOKEN = int(os.environ.get("MAX_IMAGES_PER_TOKEN", "3"))

STATE_FILE = "used_tokens.json"

def load_state():
    global used_tokens, current_token_index
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            used_tokens = data.get("used_tokens", {})
            current_token_index = data.get("current_token_index", 0)
    else:
        used_tokens = {}
        current_token_index = 0

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump({"used_tokens": used_tokens, "current_token_index": current_token_index}, f)

load_state()

last_request_time = 0


def get_remaining_images():
    total = len(TOKENS) * MAX_PER_TOKEN
    used = sum(used_tokens.values())
    return total - used


def generate_image(
    prompt: str,
    save_path: str,
    model: str = "Tongyi-MAI/Z-Image-Turbo",
    max_retries: int = 3
) -> str:
    global current_token_index, last_request_time

    if get_remaining_images() <= 0:
        raise Exception("Лимит исчерпан! Все токены использованы.")

    directory = os.path.dirname(save_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    for attempt in range(max_retries):
        while used_tokens.get(current_token_index, 0) >= MAX_PER_TOKEN:
            current_token_index = (current_token_index + 1) % len(TOKENS)
            if get_remaining_images() <= 0:
                raise Exception("Лимит исчерпан! Все токены использованы.")

        token = TOKENS[current_token_index]
        token_num = current_token_index + 1
        used = used_tokens.get(current_token_index, 0)

        print(f"Using token #{token_num}/{len(TOKENS)} ({used}/{MAX_PER_TOKEN} used): {token[:10]}...")

        try:
            client = InferenceClient(provider="fal-ai", token=token)

            elapsed = time.time() - last_request_time
            if elapsed < 2:
                time.sleep(2 - elapsed)

            print(f"Generating with prompt: {prompt}")
            image = client.text_to_image(prompt, model=model)
            last_request_time = time.time()

            used_tokens[current_token_index] = used + 1
            save_state()

            image.save(save_path)
            return save_path

        except Exception as e:
            error_msg = str(e)
            print(f"Error with token #{token_num}: {error_msg}")

            if "402" in error_msg or "Payment Required" in error_msg or "depleted" in error_msg:
                print(f"Token {token[:10]}... exhausted, switching...")
                used_tokens[current_token_index] = MAX_PER_TOKEN
                current_token_index = (current_token_index + 1) % len(TOKENS)

                remaining = get_remaining_images()
                if remaining <= 0:
                    save_state()
                    raise Exception("Лимит исчерпан! Все токены использованы.")
                save_state()
                print(f"Switched to token #{current_token_index + 1}, remaining: {remaining}")
                time.sleep(1)
            else:
                raise

    raise Exception("Не удалось сгенерировать изображение после всех попыток")