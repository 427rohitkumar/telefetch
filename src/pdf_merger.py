"""
PDF Split & Master Merger backend logic using pypdf and natsort.
Extracts up to N pages from each PDF and merges them into a sequential Master PDF.
"""

import os
import threading
from typing import Callable, List, Optional, Tuple

import natsort
import pypdf

from src.models import MergeProgress, PDFFileInfo


def inspect_pdf_file(file_path: str) -> Optional[PDFFileInfo]:
    """
    Inspects a PDF file and extracts its metadata (page count, size, encrypted status).
    Returns None if the file cannot be read or is invalid.
    """
    if not os.path.isfile(file_path):
        return None

    try:
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        reader = pypdf.PdfReader(file_path)
        is_encrypted = reader.is_encrypted
        
        # If encrypted, attempt to decrypt with empty password
        if is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass

        page_count = len(reader.pages)
        return PDFFileInfo(
            path=file_path,
            file_name=file_name,
            file_size=file_size,
            page_count=page_count,
            is_encrypted=is_encrypted,
        )
    except Exception as e:
        print(f"Error inspecting PDF '{file_path}': {e}")
        return None


class PDFMerger:
    """
    Manages slicing and merging multiple PDF files into a single master PDF.
    Runs safely in a background worker thread.
    """

    def __init__(self):
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def process_and_merge(
        self,
        files: List[PDFFileInfo],
        output_path: str,
        pages_to_extract: int = 30,
        progress_callback: Optional[Callable[[MergeProgress], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Extracts up to `pages_to_extract` pages from each PDF in sequential natural sort order
        and combines them into a single Master PDF.
        """
        if self.cancel_event.is_set():
            return False, "Merge cancelled by user.", None

        def log(msg: str):
            if log_callback:
                log_callback(msg)

        if not files:
            return False, "No PDF files provided for merging.", None

        # Sort files in natural numerical order (e.g. file_1.pdf, file_2.pdf, file_10.pdf)
        sorted_files = natsort.natsorted(files, key=lambda f: f.file_name)
        total_files = len(sorted_files)

        log(f"Starting PDF Split & Master Merge: {total_files} files, up to {pages_to_extract} pages each...")

        # Ensure output directory exists
        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        writer = pypdf.PdfWriter()
        total_pages_merged = 0

        progress = MergeProgress(
            current_index=0,
            total_files=total_files,
            total_pages_merged=0,
            status_text="Initializing merger...",
        )

        try:
            for idx, file_info in enumerate(sorted_files):
                if self.cancel_event.is_set():
                    log("Merge operation cancelled by user.")
                    progress.is_cancelled = True
                    progress.status_text = "Operation cancelled."
                    if progress_callback:
                        progress_callback(progress)
                    return False, "Merge cancelled by user.", None

                progress.current_index = idx + 1
                progress.current_file_name = file_info.file_name
                progress.status_text = f"Processing [{idx+1}/{total_files}]: {file_info.file_name}"
                if progress_callback:
                    progress_callback(progress)

                try:
                    reader = pypdf.PdfReader(file_info.path)
                    if reader.is_encrypted:
                        try:
                            reader.decrypt("")
                        except Exception:
                            log(f"⚠️ Warning: Encrypted file '{file_info.file_name}' could not be decrypted. Skipping.")
                            continue

                    available_pages = len(reader.pages)
                    # Extract min(pages_to_extract, available_pages)
                    extract_count = min(pages_to_extract, available_pages)

                    for p_idx in range(extract_count):
                        writer.add_page(reader.pages[p_idx])

                    total_pages_merged += extract_count
                    progress.pages_added = extract_count
                    progress.total_pages_merged = total_pages_merged

                    log(f"[{idx+1}/{total_files}] '{file_info.file_name}': Extracted {extract_count}/{available_pages} pages.")

                except Exception as file_err:
                    log(f"⚠️ Error reading '{file_info.file_name}': {str(file_err)}. Skipping.")

                if progress_callback:
                    progress_callback(progress)

            if total_pages_merged == 0:
                return False, "No pages could be extracted from the selected files.", None

            log(f"Writing Master PDF to '{output_path}' ({total_pages_merged} total pages)...")
            progress.status_text = "Saving Master PDF file to disk..."
            if progress_callback:
                progress_callback(progress)

            with open(output_path, "wb") as f_out:
                writer.write(f_out)

            progress.is_finished = True
            progress.output_path = output_path
            progress.status_text = f"Done! Merged {total_pages_merged} pages into master file."
            if progress_callback:
                progress_callback(progress)

            success_msg = f"Master PDF created successfully!\n\nMerged {total_pages_merged} pages from {total_files} files."
            log(f"🎉 {success_msg}")
            return True, success_msg, output_path

        except Exception as e:
            err_msg = f"Failed to create Master PDF: {str(e)}"
            log(f"❌ {err_msg}")
            progress.error_message = err_msg
            if progress_callback:
                progress_callback(progress)
            return False, err_msg, None
