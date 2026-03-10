from sentence_transformers import SentenceTransformer


def load_model(model_name: str, device_opt: str | None = None) -> SentenceTransformer | None:
    if model_name == "None":
        return None
    print(f"model_name 1: {model_name}")

    try:
        print(f"model_name 2: {model_name}, dev_opt={device_opt}")
        model = SentenceTransformer(model_name, device=device_opt)
        print(f"model_name 3: {model_name}, dev_opt={device_opt}")
        model = model.to(device_opt)  # 명시적으로 GPU로 이동
        print(f"model_name 4: {model_name}, dev_opt={device_opt}")
        return model
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # kiwi 사용해서 토크나이징

    # embed_model_name = "/root/.cashe/huggingface/hub/models--dronkue--EGE-m3-ko/snapshots/eds??????????????????????68"
    embed_model_name = "dragonkue/BGE-m3-ko"
    device_opt = "cpu"  # "cudo:0" or "cpu"
    embedder = load_model(model_name=embed_model_name, device_opt=device_opt)

    print(embedder)
