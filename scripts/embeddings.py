import os

import pandas as pd
from sentence_transformers import SentenceTransformer

from .config import Config
from .data_loader import load_markets_static_only


def generate_text_embeddings(cfg: Config) -> pd.DataFrame:
    """Generate text embeddings for market data."""
    print("Loading markets data (skipping trades and snapshots)...")
    markets_static = load_markets_static_only(cfg)

    print(f"Loading embedding model: {cfg.embedding_model_name}")
    model = SentenceTransformer(cfg.embedding_model_name)
    print(f"  Model loaded (embedding dim: {cfg.embedding_dim})")

    result = pd.DataFrame({"market_id": markets_static["market_id"].astype(str)})
    print(f"\nGenerating embeddings for {len(markets_static):,} markets...")

    if cfg.use_dataset_folder:
        if "question" in markets_static.columns:
            texts = markets_static["question"].fillna("").astype(str).tolist()
            embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
            embedding_df = pd.DataFrame(
                embeddings, columns=[f"question_embedding_dim{i}" for i in range(embeddings.shape[1])]
            )
            result = pd.concat([result, embedding_df], axis=1)
            print(f"  Generated {embeddings.shape[1]} dimensions from question")
    else:
        if "event_title" in markets_static.columns and "question" in markets_static.columns:
            combined_text = (
                markets_static["event_title"].fillna("").astype(str)
                + " "
                + markets_static["question"].fillna("").astype(str)
            ).str.strip()
            texts = combined_text.tolist()
            embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
            embedding_df = pd.DataFrame(
                embeddings, columns=[f"event_question_embedding_dim{i}" for i in range(embeddings.shape[1])]
            )
            result = pd.concat([result, embedding_df], axis=1)
            print(f"  Generated {embeddings.shape[1]} dimensions from event_title + question")

        if "market_title" in markets_static.columns:
            texts = markets_static["market_title"].fillna("").astype(str).tolist()
            embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
            embedding_df = pd.DataFrame(
                embeddings, columns=[f"market_title_embedding_dim{i}" for i in range(embeddings.shape[1])]
            )
            result = pd.concat([result, embedding_df], axis=1)
            print(f"  Generated {embeddings.shape[1]} dimensions from market_title")

    return result


def main(use_dataset_folder: bool = False):
    """Main entry point for embeddings generation."""
    print("\n" + "=" * 60)
    print("TEXT EMBEDDINGS GENERATION")
    print("=" * 60 + "\n")

    cfg = Config()
    cfg.use_dataset_folder = use_dataset_folder
    os.makedirs(cfg.modeling_dir, exist_ok=True)

    embeddings_df = generate_text_embeddings(cfg)

    data_source_suffix = "_dataset" if use_dataset_folder else "_collected"
    output_path = os.path.join(cfg.modeling_dir, f"text_embeddings{data_source_suffix}.csv")
    print(f"\nSaving embeddings to: {output_path}")
    embeddings_df.to_csv(output_path, index=False)

    print("\n" + "=" * 60)
    print("EMBEDDINGS GENERATION COMPLETE")
    print("=" * 60)
    print(f"Shape: {embeddings_df.shape[0]:,} rows × {embeddings_df.shape[1]} columns")
    print(f"Embedding columns: {embeddings_df.shape[1] - 1}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate text embeddings for market data")
    parser.add_argument(
        "--use-external-dataset",
        action="store_true",
        help="Use data from dataset folder (dataset/markets.csv) instead of collected data",
    )
    args = parser.parse_args()
    main(use_dataset_folder=args.use_external_dataset)