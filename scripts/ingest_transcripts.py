#!/usr/bin/env python3
"""
Transcript ingestion script for Lenny's Podcast transcripts.

Processes markdown transcripts, chunks them, and uploads to Azure AI Search.

Usage:
    # Ingest all transcripts from a directory
    python ingest_transcripts.py --transcripts-dir /path/to/episodes

    # Ingest a single transcript
    python ingest_transcripts.py --file /path/to/transcript.md

    # Dry run (no upload)
    python ingest_transcripts.py --transcripts-dir /path/to/episodes --dry-run
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "functions"))

from shared.chunking import TranscriptChunker
from shared.search import SearchClient


def load_transcript(file_path: Path) -> tuple[str, str]:
    """
    Load a transcript file.

    Args:
        file_path: Path to markdown file

    Returns:
        Tuple of (content, transcript_id)
    """
    content = file_path.read_text(encoding="utf-8")

    # Generate transcript ID from path
    # e.g., /path/to/episodes/julie-zhuo/transcript.md -> julie-zhuo
    transcript_id = file_path.parent.name

    return content, transcript_id


def find_transcripts(directory: Path) -> list[Path]:
    """
    Find all transcript markdown files in a directory.

    Args:
        directory: Root directory to search

    Returns:
        List of paths to transcript files
    """
    transcripts = []

    # Pattern 1: episodes/guest-name/transcript.md
    for md_file in directory.glob("**/transcript.md"):
        transcripts.append(md_file)

    # Pattern 2: episodes/guest-name.md (single files)
    for md_file in directory.glob("*.md"):
        if md_file.name not in ["README.md", "CLAUDE.md"]:
            transcripts.append(md_file)

    return sorted(transcripts)


def ingest_transcript(
    file_path: Path,
    chunker: TranscriptChunker,
    search_client: SearchClient,
    dry_run: bool = False,
) -> dict:
    """
    Process and ingest a single transcript.

    Args:
        file_path: Path to transcript file
        chunker: TranscriptChunker instance
        search_client: SearchClient instance
        dry_run: If True, don't actually upload

    Returns:
        Ingestion result summary
    """
    content, transcript_id = load_transcript(file_path)

    # Chunk the transcript
    chunks = chunker.chunk_transcript(content, transcript_id)

    result = {
        "transcript_id": transcript_id,
        "file_path": str(file_path),
        "total_chunks": len(chunks),
        "chunk_types": {},
    }

    # Count chunk types
    for chunk in chunks:
        chunk_type = chunk.chunk_type
        result["chunk_types"][chunk_type] = result["chunk_types"].get(chunk_type, 0) + 1

    if not dry_run:
        # Upload to search index
        upload_result = search_client.upload_chunks_batch(chunks, batch_size=50)
        result["uploaded"] = upload_result["succeeded"]
        result["failed"] = upload_result["failed"]
    else:
        result["uploaded"] = 0
        result["failed"] = 0
        result["dry_run"] = True

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Lenny's Podcast transcripts into Azure AI Search"
    )
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        help="Directory containing transcript files (e.g., episodes/)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Single transcript file to ingest",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process files without uploading to search index",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for ingestion report (JSON)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for embedding generation (default: 50)",
    )

    args = parser.parse_args()

    if not args.transcripts_dir and not args.file:
        parser.error("Either --transcripts-dir or --file must be specified")

    # Initialize clients
    chunker = TranscriptChunker()
    search_client = None if args.dry_run else SearchClient()

    # Collect files to process
    if args.file:
        if not args.file.exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        files = [args.file]
    else:
        if not args.transcripts_dir.exists():
            print(f"Error: Directory not found: {args.transcripts_dir}")
            sys.exit(1)
        files = find_transcripts(args.transcripts_dir)

    print(f"Found {len(files)} transcript(s) to process")
    print(f"Dry run: {args.dry_run}")
    print()

    # Process each transcript
    results = []
    total_chunks = 0
    total_uploaded = 0
    total_failed = 0

    for i, file_path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] Processing: {file_path.name}...", end=" ")

        try:
            result = ingest_transcript(
                file_path,
                chunker,
                search_client,
                dry_run=args.dry_run,
            )
            results.append(result)

            total_chunks += result["total_chunks"]
            total_uploaded += result.get("uploaded", 0)
            total_failed += result.get("failed", 0)

            print(f"✓ {result['total_chunks']} chunks")

        except Exception as e:
            print(f"✗ Error: {e}")
            results.append({
                "transcript_id": file_path.parent.name,
                "file_path": str(file_path),
                "error": str(e),
            })

    # Print summary
    print()
    print("=" * 50)
    print("INGESTION SUMMARY")
    print("=" * 50)
    print(f"Transcripts processed: {len(files)}")
    print(f"Total chunks created: {total_chunks}")
    if not args.dry_run:
        print(f"Chunks uploaded: {total_uploaded}")
        print(f"Chunks failed: {total_failed}")
    print()

    # Save report if requested
    if args.output:
        report = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": args.dry_run,
            "total_transcripts": len(files),
            "total_chunks": total_chunks,
            "total_uploaded": total_uploaded,
            "total_failed": total_failed,
            "results": results,
        }
        args.output.write_text(json.dumps(report, indent=2))
        print(f"Report saved to: {args.output}")


if __name__ == "__main__":
    main()
