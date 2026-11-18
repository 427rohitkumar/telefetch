# ⚡ TeleFetch - Telegram Bulk Downloader & PDF Master Suite

A modern desktop application built with **CustomTkinter**, **Telethon**, and **PyPDF** featuring a multi-tab interface:
- **Tab 1: Telegram Downloader:** Search, filter, preview, and bulk-download files (PDFs, documents, and archives) from Telegram channels and chats into a local folder or a compressed ZIP archive.
- **Tab 2: PDF Split & Master Merger:** Select up to 100 PDF files or folders, extract the first **N** pages (default: 30) from each, and assemble them into a sequentially sorted master PDF.

---

## 🚀 Key Features

### 📑 Tab 1: Telegram Downloader
* **🔑 Authentication & Credential Storage:**
  * Enter `API_ID`, `API_HASH`, and `Phone Number`.
  * Support for OTP verification and Two-Factor Authentication (2FA) cloud passwords.
  * Session persistence (`telefetch_session.session`) and local configuration (`telefetch_config.json`) with auto-reconnection.
  * Direct guidance to obtain API keys from [my.telegram.org](https://my.telegram.org).
* **🎯 Target Channel Support:**
  * Public channel usernames (`@example_channel`), links (`https://t.me/example_channel`), invite links (`https://t.me/+join_hash`), or numeric IDs (`-100...`).
  * **"Verify Channel"** button to confirm access and subscriber count before scanning.
* **🔍 Search & Filter Pipeline:**
  * **File Extension Filtering:** Select `.pdf` (default), `.epub`, `.docx`, `.zip`, or `All Files`.
  * **Pattern Matching (Regex & Wildcard):** Flexible search box supporting full regex (e.g. `Prefix_.*\.pdf`) or wildcards (`Report_*`).
  * **Date Range Filtering:** Filter messages between Start and End dates (`YYYY-MM-DD`).
  * **Scan Limits:** Scan 500, 1000, 2000, 5000 latest messages or All messages.
* **📊 Interactive Preview Table:**
  * Columns: `[✔] Select`, `File Name`, `Size`, `Upload Date`, and `Message ID`.
  * Single-click toggle, **Select All**, **Deselect All**, and **Invert Selection** buttons.
  * Column sorting (click any header to sort ascending/descending).
  * Instant quick-search filtering inside already fetched results.
* **📦 Storage & Compression Pipeline:**
  * Option to package all selected files directly into `{Channel_Name}_export_{timestamp}.zip`.
  * Automatic filename sanitization and duplicate handling (`file_1.pdf`, `file_2.pdf`).
  * Memory-efficient chunked streaming.
* **⚡ Rate-Limit Resilience:**
  * Automatic `FloodWaitError` recovery: pauses with a live countdown timer when Telegram rate limits apply and resumes automatically.
  * Real-time dual progress bars (Overall progress + Current file progress with speed in MB/s).

---

### 📑 Tab 2: PDF Split & Master Merger
* **📁 Input Selection:**
  * **"Select Folder"**: Automatically scans and loads all `.pdf` files recursively.
  * **"Select PDF Files"**: Multi-file file picker supporting up to 100 PDFs.
  * Interactive preview table showing: `PDF File Name`, `Pages`, `Size`, and `Source Path`.
  * **"Remove Selected"** and **"Clear All"** controls.
  * Live stats: Total PDFs, combined page count, and total file size.
* **✂️ Extraction & Slicing Settings:**
  * **Pages to Extract:** SpinBox / number input (default: `30` pages).
  * **Graceful Slicing:** If any PDF has fewer than the requested pages, all available pages from that file are extracted without crashing.
* **📄 Master File Configuration:**
  * **Master File Name:** Configurable output name (default: `Master_Merged.pdf`).
  * **Output Folder:** Directory picker with quick buttons:
    * *"Use Downloads Folder"*
    * *"Same as Input Folder"*
* **⚙️ Background Execution & Natural Sorting:**
  * Slicing and merging run in a dedicated background worker thread (`QThread`/Worker) so the GUI never hangs.
  * Files are sorted in **Natural Numerical Order** (`natsort`) so `file_1.pdf`, `file_2.pdf`, `file_10.pdf` are ordered correctly.
  * Real-time progress bar updating as each file is processed.
  * Success pop-up modal with direct **"Open Folder"** and **"Open Master PDF"** buttons.

---

## 🛠️ Tech Stack

* **Language:** Python 3.10+
* **GUI Framework:** CustomTkinter (Modern dark theme)
* **Telegram Client:** Telethon (Async MTProto API)
* **PDF Engine:** PyPDF (`pypdf.PdfReader` & `pypdf.PdfWriter`)
* **Sorting:** `natsort` (Natural alphanumeric ordering)
* **Compression:** Python built-in `zipfile` module

---

## 📥 Installation & Setup

1. **Clone or open the repository:**
   ```powershell
   cd d:\Dev-2026\AI\telefetch
   ```

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

---

## 💻 Running the Application

Launch the desktop GUI:
```powershell
python main.py
```

---

## 🧪 Running Tests

To run the complete automated test suite (including Telethon utilities, config manager, ZIP archiver, and PDF Split & Merger tests):
```powershell
python -m unittest discover tests
```
