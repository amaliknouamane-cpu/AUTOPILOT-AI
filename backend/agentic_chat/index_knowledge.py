import argparse

from .services.knowledge import index_documents


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index approved chatbot knowledge documents.")
    parser.add_argument(
        "--lexical-only",
        action="store_true",
        help="Index without contacting Ollama for embeddings.",
    )
    args = parser.parse_args()
    print(index_documents(lexical_only=args.lexical_only))

