# RecoverFlow: Windows File Rescue

![RecoverFlow](https://raw.githubusercontent.com/Screemerss/RecoverFlow/main/background.png)

A simple and intuitive open-source application, written in Python and Qt (PySide6), to recover deleted files from formatted or damaged drives.

## Features

- **Simple Graphical Interface:** An attractive splash screen and a clear control panel.
- **Automatic Drive Detection:** Automatically finds available physical drives on the system.
- **Signature-Based Recovery (File Carving):** Scans and recovers common file types, including:
  - **Images:** JPG, PNG
  - **Documents:** PDF, DOC, DOCX
  - **Audio/Video:** MP3, WAV, MP4
- **Progress Bar:** Track the scan's progress in real-time.
- **Cross-Platform (in theory):** Written to run on Windows, Linux, and macOS (requires administrator/root privileges).

---

## ⚠️ WARNING: Important Notice ⚠️

Using data recovery tools can be risky. To maximize your chances of success and avoid causing further damage:

- **DO NOT save recovered files to the same drive you are scanning!** Always save them to another drive (e.g., a USB stick or an external hard drive).
- **USE AT YOUR OWN RISK:** This software is provided "as is". I assume no responsibility for any data loss or system damage resulting from the use of this software.

---

## How to Use (for Windows Users)

1.  Download the latest `RecoverFlow.exe` file from the Releases section on GitHub.
2.  Double-click `RecoverFlow.exe`. Windows will ask for administrator permissions (this is necessary to scan drives).
3.  Click "AVVIA SCANSIONE" to start.
4.  In the recovery panel:
    - Select the drive to scan.
    - Choose an output folder on a **different drive**.
    - Start the scan and wait.

## Building from Source (for Developers)

To run the Python script directly, you will need:
- Python 3.x
- The following libraries, installable with `pip`:
  ```bash
  pip install PySide6 WMI
  ```
  *(WMI è necessario solo per Windows)*

Esegui lo script con privilegi elevati:
- **Windows:** `python recovery_app.py` (da un terminale avviato come amministratore).
- **Linux/macOS:** `sudo python3 recovery_app.py`.

---

## Sostieni il Progetto

Se trovi utile questa applicazione, considera di offrirmi un caffè per sostenere lo sviluppo futuro!

<a href="https://ko-fi.com/screemerss" target="_blank">
  <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Sostienimi su Ko-fi">
</a>

## Licenza

Questo progetto è rilasciato sotto la Licenza MIT. Vedi il file `LICENSE` per maggiori dettagli.