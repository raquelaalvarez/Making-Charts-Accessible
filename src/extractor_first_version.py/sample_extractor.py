# pip install qwen-vl-utils[decord]==0.0.8 requests

import requests
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
import json

# Load the model on the available device(s)
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-7B-Instruct",
    torch_dtype="auto",
    device_map="auto"
)

# Load the processor
processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-72B-Instruct")

def extract_info_from_html_url(url):
    # Fetch the HTML content from the URL
    response = requests.get(url)
    html_content = response.text

    # Prepare the messages for the model
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": html_content},
                {"type": "text", "text": "Extract the important information from this HTML page and return it in JSON format with keys such as title, description, main_content, and any other relevant data."},
            ],
        }
    ]

    # Preparation for inference
    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    # For text-only input, no images or videos
    inputs = processor(
        text=[text],
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to("cuda" if model.device.type == "cuda" else "cpu")

    # Inference: Generation of the output
    generated_ids = model.generate(**inputs, max_new_tokens=512)
    generated_ids_trimmed = [
        out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]

    # Try to parse the output as JSON
    try:
        extracted_info = json.loads(output_text)
        return extracted_info
    except json.JSONDecodeError:
        # If not valid JSON, return the raw text
        return {"error": "Failed to parse JSON", "raw_output": output_text}

# Example usage
if __name__ == "__main__":
    url = "https://coinmarketcap.com/currencies/official-trump/"  # Replace with the actual URL
    result = extract_info_from_html_url(url)
    print(json.dumps(result, indent=4))