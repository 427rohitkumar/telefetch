Yeh raha aapke project ke liye ek complete aur structured **High-Level PRD (Product Requirement Document)** jise aap seedhe antigravity ya kisi bhi AI coder ko provide karke project build karwa sakte hain:

---

# Product Requirement Document (PRD): Telegram Bulk File Downloader GUI

## 1. Project Overview

Ek desktop-based GUI application jo users ko kisi specific Telegram channel/chat se targeted PDF files search, filter, preview aur bulk download karne ki suvidha deta hai. Files download hone ke baad seedhe ek ZIP archive ke andar local machine par store hongi.

---

## 2. Tech Stack Recommendations

* **Language:** Python 3.10+
* **GUI Framework:** PyQt6 / PySide6 ya CustomTkinter (modern and clean UI)
* **Telegram Client Library:** `Telethon` (async support ke sath best performance)
* **Compression:** Python built-in `zipfile` module
* **Packaging (Optional):** `PyInstaller` (stand-alone .exe build karne ke liye)

---

## 3. Core Features & Functional Requirements

### 3.1 Authentication & Configuration

* User ko initial screen par credentials enter karne ka option mile:
* `API_ID` (Integer)
* `API_HASH` (String)
* `Phone Number` (OTP verification ke liye)


* Credentials ko locally encrypted format ya simple config file (`config.json`) mein securely save karne ka option (taaki baar-baar login na karna pade).
* First-time login ke liye OTP aur (agar enable ho toh) Two-Factor Authentication (2FA) password enter karne ka pop-up modal.

### 3.2 Channel Input & Target Selection

* User channel ko multiple tariko se specify kar sake:
* Public Channel Username (e.g., `@example_channel`)
* Channel Invitation Link / Direct Join Link
* Channel ID (e.g., `-100xxxxxxxxxx`)


* Ek **"Verify Channel"** button jo check karega ki bot/user account ko us channel ka access hai ya nahi.

### 3.3 Search Filters & Pattern Matching

* **File Type Filter:** Fixed to `.pdf` (dropdown mein future extension support jaise `.epub`, `.docx` ke liye jagah ho).
* **Pattern Matching (Regex / Wildcard):**
* Custom input box jahan user pattern specify kar sake (e.g., `Prefix_*`, `[A-Za-z]+_\d{8}\.pdf`, etc.).


* **Date Range Filter (Optional but recommended):**
* Start Date aur End Date select karne ka calendar widget.



### 3.4 Data Fetching, Pagination & Preview Table

* **Lazy Loading / Pagination:**
* Background worker thread (`QThread`) ke through Telegram messages batch-wise fetch ho (e.g., 50 ya 100 messages per request) taaki UI freeze na ho.


* **Result Statistics:**
* Total files scanned, matching files count live show ho.


* **Interactive Table / List View:**
* Columns: `Select (Checkbox)`, `File Name`, `File Size (MB)`, `Upload Date`, `Message ID`.
* "Select All" aur "Deselect All" ka master toggle button.



### 3.5 Storage & Download Pipeline

* **Destination Picker:**
* **Default Path:** User ka default `Downloads/Telegram_Exports/` folder pre-selected ho.
* **Browse Button:** Directory picker dialog se user custom folder select kar sake.


* **ZIP Packaging:**
* Matching files direct memory stream se ya temp files se ek clean ZIP archive mein compress hon (File naming format: `{Channel_Name}_export_{timestamp}.zip`).


* **Progress Tracking:**
* Real-time Progress Bar (overall percentage aur individual file speed/MB downloaded).
* Error Handling: Agar koi network timeout ya rate limit (`FloodWaitError`) aaye, toh script crash na ho balki wait timer dikhaye.



---

## 4. UI/UX Flow Layout

1. **Top Section (Auth & Target):**
* Telegram Status Indicator (Connected/Disconnected)
* Channel Input Field + "Fetch Files" Button


2. **Middle Section (Filters & Preview):**
* Pattern Regex input field + Apply Filter button
* Data Table jisme matched PDFs list out honge checkbox ke sath.
* Total Files Found Counter & Pagination controls (Next / Previous / Load More).


3. **Bottom Section (Export Settings & Action):**
* Output directory path input + "Browse..." button.
* Checkbox: "Compress to ZIP directly" (Checked by default).
* Big Primary Button: **"Start Download"**.
* Live Download Progress Bar + Log Terminal box (for real-time status updates).



---

## 5. Non-Functional Requirements & Edge Cases

* **Rate Limit Handling:** Telethon ka automatic `FloodWaitError` catch mechanism implement hona chahiye taaki Telegram account ban ya cooldown se bache.
* **Asynchronous Execution:** Heavy network calls aur file writing hamesha background thread mein chale taaki desktop GUI responsive rahe ("Not Responding" freeze error na aaye).
* **Memory Management:** Badi PDF files ke liye disk buffer/stream download use ho, pura data ek sath RAM mein load na kiya jaye.