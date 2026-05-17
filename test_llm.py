from llama_cpp import Llama

llm = Llama(
    model_path="models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
    n_gpu_layers=40,
    n_ctx=4096,
    verbose=False
)

response = llm.create_chat_completion(
    messages=[
        {"role": "user", "content": "is there lpg gas shortage in india  "}
    ],
    max_tokens=150,
)

print(response["choices"][0]["message"]["content"])