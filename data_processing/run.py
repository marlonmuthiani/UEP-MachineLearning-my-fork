#!/usr/bin/env python3
"""
Entry point script to avoid RuntimeWarning when running as module.
Usage: python -m data_processing.run
"""

import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")

if __name__ == "__main__":
    import argparse

    from .main import main

    parser = argparse.ArgumentParser(description="Process market data for ML")
    parser.add_argument("--embeddings", action="store_true", help="Include text embeddings in the dataset")
    parser.add_argument(
        "--use-external-dataset",
        action="store_true",
        help="Use data from dataset folder (markets.csv) instead of collected data",
    )
    args = parser.parse_args()

    main(include_embeddings=args.embeddings, use_dataset_folder=args.use_external_dataset)
