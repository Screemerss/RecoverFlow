import sys
import os
import platform  # Per distinguere il sistema operativo

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QLineEdit, QLabel, QTextEdit, QFileDialog,
    QStatusBar, QMessageBox, QProgressBar
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QPixmap, QIcon, QPainter, QBrush, QPalette

# Su Windows, importa la libreria WMI se disponibile
if platform.system() == "Windows":
    try:
        import wmi
    except ImportError:
        print("Libreria WMI non trovata. Esegui 'pip install WMI'.")
        wmi = None

def resource_path(relative_path):
    """
    Ottiene il percorso assoluto della risorsa, funziona sia in sviluppo
    che per l'eseguibile creato con PyInstaller.
    """
    try:
        # PyInstaller crea una cartella temporanea e salva il percorso in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- DEFINIZIONE DELLE FIRME DEI FILE ---
# Dizionario delle firme dei file. 'footer' è opzionale.
FILE_SIGNATURES = {
    "jpg": {
        "header": b'\xff\xd8\xff', # Header più generico per JPG/JPEG
        "footer": b'\xff\xd9',
        "max_size": 20 * 1024 * 1024 # 20 MB
    },
    "png": {
        "header": b'\x89PNG\r\n\x1a\n',
        "footer": b'IEND\xaeB`\x82',
        "max_size": 20 * 1024 * 1024 # 20 MB
    },
    "pdf": {
        "header": b'%PDF-',
        "footer": b'%%EOF',
        "max_size": 50 * 1024 * 1024 # 50 MB
    },
    "mp4": {
        "header": b'\x00\x00\x00\x18ftypmp42', # Una delle firme comuni per MP4
        "footer": None, # I file MP4 non hanno un footer semplice e affidabile
        "max_size": 500 * 1024 * 1024 # 500 MB, i video possono essere grandi
    },
    "mp3": {
        "header": b'ID3', # L'header più comune per i file MP3 con metadati
        "footer": None, # Non hanno un footer standard affidabile
        "max_size": 25 * 1024 * 1024 # 25 MB
    },
    "wav": {
        "header": b'RIFF', # L'header per i file WAV (e altri, come AVI)
        "footer": None, # La dimensione è nel header, ma per semplicità usiamo una dimensione massima
        "max_size": 100 * 1024 * 1024 # 100 MB per audio non compresso
    },
    "doc": {
        "header": b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1', # Header per file OLE (DOC, XLS, PPT)
        "footer": None,
        "max_size": 30 * 1024 * 1024 # 30 MB
    },
    "docx": {
        "header": b'PK\x03\x04', # Header per file ZIP (usato da DOCX, XLSX, etc.)
        "footer": b'PK\x05\x06', # Footer del record della directory centrale ZIP
        "max_size": 50 * 1024 * 1024 # 50 MB
    }
}

# Calcola la lunghezza massima dell'header una sola volta per ottimizzare
# e prevenire crash se il dizionario è vuoto.
MAX_HEADER_LEN = max(len(s["header"]) for s in FILE_SIGNATURES.values()) if FILE_SIGNATURES else 0

# --- FOGLIO DI STILE (QSS) PER LA GUI ---
STYLE_SHEET = """
    /* Stile generale della finestra */
    QMainWindow, QWidget {
        background-color: #2c3e50; /* Blu scuro/grigio ardesia */
    }

    /* Stile per le etichette */
    QLabel {
        color: #ecf0f1; /* Testo quasi bianco */
        font-size: 14px;
        font-weight: bold;
    }

    /* Stile per i campi di testo e aree di log */
    QLineEdit, QTextEdit {
        background-color: #34495e; /* Blu più scuro */
        color: #ecf0f1;
        border: 1px solid #566573;
        border-radius: 4px;
        padding: 5px;
        font-size: 13px;
    }

    /* Stile per il menu a tendina */
    QComboBox {
        background-color: #34495e;
        color: #ecf0f1;
        border: 1px solid #566573;
        border-radius: 4px;
        padding: 5px;
    }
    QComboBox::drop-down {
        border: none;
    }

    /* Stile generale dei pulsanti */
    QPushButton {
        color: white;
        border: 1px solid black;
        border-radius: 5px;
        padding: 8px 16px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover {
        opacity: 0.9;
    }
    QPushButton:pressed {
        border-style: inset;
    }

    /* Colori specifici per i pulsanti */
    QPushButton#startButton { background-color: #e67e22; } /* Arancione */
    QPushButton#stopButton { background-color: #27ae60; } /* Verde */
    QPushButton#browseButton, QPushButton#refreshButton { background-color: #3498db; } /* Azzurro */
"""

# --- CLASSE WORKER PER LA SCANSIONE ---
class ScanWorker(QThread):
    progress_update = Signal(str)
    progress_percentage = Signal(int)
    scan_finished = Signal(str)  # Invia un messaggio finale (successo o errore)

    def __init__(self, disk_path, output_dir):
        super().__init__()
        self.disk_path = disk_path
        self.output_dir = output_dir
        self.is_running = True

    def run(self):
        """
        Logica di recupero file (File Carving).
        Legge il disco settore per settore alla ricerca di firme di file.
        """
        self.progress_update.emit(f"Avvio scansione su {self.disk_path}...")
        file_count = 0
        
        total_size = 0
        try:
            with open(self.disk_path, "rb") as f:
                # Calcola la dimensione totale del disco per la progress bar
                f.seek(0, os.SEEK_END)
                total_size = f.tell()
                f.seek(0)
                if total_size == 0:
                    self.scan_finished.emit("ERRORE: Impossibile determinare la dimensione del disco.")
                    return

                # Leggiamo il disco in blocchi più grandi per migliorare le prestazioni
                # ma manteniamo un buffer scorrevole per non perdere gli header
                chunk_size = 4096
                buffer = b''
                while self.is_running:
                    new_data = f.read(chunk_size)
                    if not new_data:
                        break  # Fine del disco
                    
                    buffer += new_data

                    # Aggiorna la barra di progresso
                    current_pos = f.tell()
                    self.progress_percentage.emit(int((current_pos * 100) / total_size))

                    # --- Logica di Scansione Migliorata ---
                    found_pos = -1
                    found_type = None

                    # 1. Trova la prima occorrenza di QUALSIASI header nel buffer
                    for file_type, sigs in FILE_SIGNATURES.items():
                        pos = buffer.find(sigs["header"])
                        if pos != -1 and (found_pos == -1 or pos < found_pos):
                            found_pos = pos
                            found_type = file_type
                    
                    if found_type:
                        sigs = FILE_SIGNATURES[found_type]
                        header_pos = f.tell() - len(buffer) + found_pos
                        self.progress_update.emit(f"Trovato potenziale header {found_type.upper()} alla posizione: {header_pos}")
                        
                        # Estrai i dati a partire dall'header trovato
                        file_data = bytearray(buffer[found_pos:])
                        
                        # Se il file ha un footer definito, cercalo
                        if sigs["footer"]:
                            while sigs["footer"] not in file_data:
                                if len(file_data) > sigs["max_size"]:
                                    self.progress_update.emit(f"File {found_type.upper()} troppo grande o footer non trovato, scarto.")
                                    file_data = None
                                    break
                                
                                next_chunk = f.read(chunk_size)
                                if not next_chunk:
                                    file_data = None
                                    break
                                file_data.extend(next_chunk)
                            
                            if file_data:
                                end_index = file_data.find(sigs["footer"]) + len(sigs["footer"])
                                self.save_file(file_data[:end_index], found_type, file_count)
                                file_count += 1
                                # 3. Consuma il buffer fino alla fine del file recuperato
                                buffer = buffer[found_pos + end_index:]
                                continue # Riavvia il ciclo di ricerca dal buffer rimanente

                        else: # 2. Logica migliorata per file senza footer
                            end_pos = -1
                            while len(file_data) < sigs["max_size"]:
                                # Controlla se nel frattempo è iniziato un altro file
                                for other_type, other_sigs in FILE_SIGNATURES.items():
                                    # Cerca altri header, ma non all'inizio (che è il nostro file)
                                    pos = file_data.find(other_sigs["header"], 1)
                                    if pos != -1 and (end_pos == -1 or pos < end_pos):
                                        end_pos = pos
                                
                                if end_pos != -1:
                                    self.progress_update.emit(f"Trovato header di un altro file, termino recupero di {found_type.upper()}.")
                                    break # Trovato un altro file, fermati

                                next_chunk = f.read(chunk_size)
                                if not next_chunk: break
                                file_data.extend(next_chunk)
                            
                            # Determina la fine del file
                            final_size = end_pos if end_pos != -1 else min(len(file_data), sigs["max_size"])
                            self.save_file(file_data[:final_size], found_type, file_count)
                            file_count += 1
                            # 3. Consuma il buffer
                            buffer = buffer[found_pos + final_size:]
                            continue

                    # Se non viene trovato nessun header, svuota il buffer tranne l'ultima parte
                    # Mantieni solo l'ultima parte del buffer per cercare header a cavallo di due letture
                    buffer = buffer[-MAX_HEADER_LEN:]
            
            if self.is_running:
                self.scan_finished.emit(f"Scansione completata. Trovati {file_count} file.")
            else:
                self.scan_finished.emit("Scansione interrotta dall'utente.")
        except PermissionError:
            self.scan_finished.emit("ERRORE: Permesso negato. Esegui l'applicazione come amministratore/root.")
        except FileNotFoundError:
            self.scan_finished.emit(f"ERRORE: Disco '{self.disk_path}' non trovato.")
        except Exception as e:
            self.scan_finished.emit(f"Si è verificato un errore imprevisto: {e}")

    def save_file(self, data, file_type, file_count):
        """Salva i dati recuperati in un file."""
        filename = os.path.join(self.output_dir, f"recuperato_{file_count + 1}.{file_type}")
        try:
            with open(filename, "wb") as out_file:
                out_file.write(data)
            self.progress_update.emit(f"SALVATO: {filename}")
        except IOError as e:
            self.progress_update.emit(f"ERRORE nel salvataggio di {filename}: {e}")

    def stop(self):
        self.progress_update.emit("Interruzione della scansione in corso...")
        self.is_running = False

# --- FINESTRA DI AVVIO (MAIN MENU) ---
class MainMenu(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("app_icon.png")))
        self.setWindowTitle("RecoverFlow")
        self.setFixedSize(800, 600) # Blocca la dimensione a quella dell'immagine

        # Imposta l'immagine di sfondo
        self.background_label = QLabel(self)
        self.background_label.setGeometry(0, 0, 800, 600)
        pixmap = QPixmap(resource_path("background.png"))
        self.background_label.setPixmap(pixmap)
        self.background_label.setScaledContents(True)

        # Crea il pulsante di avvio, questa volta VISIBILE
        self.start_app_button = QPushButton("AVVIA SCANSIONE", self.background_label)
        
        # Posiziona e dimensiona il pulsante sopra il "SCAN FOR LOST FILES" dell'immagine
        # Modificato per essere in basso e per tutta la larghezza
        button_x = 0
        button_y = 540  # In basso nella finestra 800x600
        button_width = 800 # Tutta la larghezza
        button_height = 60 # Un po' più alto
        self.start_app_button.setGeometry(button_x, button_y, button_width, button_height)

        # Applica uno stile al pulsante per renderlo accattivante
        self.start_app_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(52, 152, 219, 0.8); /* Azzurro con trasparenza */
                color: white;
                border: 2px solid rgba(236, 240, 241, 0.7); /* Bordo bianco leggermente trasparente */
                border-radius: 0px; /* Niente bordi arrotondati per un look a tutta larghezza */
                font-size: 20px; /* Font più grande */
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(93, 173, 226, 0.9); /* Azzurro più chiaro, quasi opaco */
            }
            QPushButton:pressed {
                background-color: rgba(40, 116, 166, 0.9); /* Azzurro più scuro, quasi opaco */
            }
        """)
        
        # Imposta un cursore a forma di mano per indicare che è cliccabile
        self.start_app_button.setCursor(Qt.PointingHandCursor)

        # Collega il click del pulsante alla funzione per avviare l'app
        self.start_app_button.clicked.connect(self.launch_recovery_app)

        # Inizializza la finestra dell'app di recupero (ma non mostrarla ancora)
        self.recovery_window = None

    def launch_recovery_app(self):
        """Crea e mostra la finestra principale dell'app di recupero."""
        if not self.recovery_window:
            self.recovery_window = RecoveryWindow()
        
        self.recovery_window.show()
        self.close() # Chiude la finestra del menu principale


# --- FINESTRA DI RECUPERO ---
class RecoveryWindow(QMainWindow):
    def __init__(self):
        super().__init__() 
        self.setStyleSheet(STYLE_SHEET)
        self.setWindowIcon(QIcon(resource_path("app_icon.png")))

        self.setWindowTitle("RecoverFlow - Pannello di Recupero")
        self.setGeometry(100, 100, 700, 500)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Selezione del disco
        disk_layout = QHBoxLayout()
        disk_layout.addWidget(QLabel("Seleziona Disco:"))
        self.disk_combo = QComboBox()
        disk_layout.addWidget(self.disk_combo)
        refresh_btn = QPushButton("Aggiorna")
        refresh_btn.setObjectName("refreshButton") # Assegna un nome per lo stile
        refresh_btn.clicked.connect(self.populate_disks)
        disk_layout.addWidget(refresh_btn)
        main_layout.addLayout(disk_layout)


        # Selezione output
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Salva in:"))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setReadOnly(True)
        output_layout.addWidget(self.output_path_edit)
        browse_btn = QPushButton("Sfoglia...")
        browse_btn.setObjectName("browseButton") # Assegna un nome per lo stile
        browse_btn.clicked.connect(self.select_output_dir)
        output_layout.addWidget(browse_btn)
        main_layout.addLayout(output_layout)

        # Log dei risultati
        main_layout.addWidget(QLabel("Log di Scansione:"))
        self.log_area = QTextEdit()
        self.log_area.setObjectName("logArea") # Assegna un nome per lo stile
        self.log_area.setReadOnly(True)
        
        # **LA MODIFICA CHIAVE È QUI**
        # Rendiamo il viewport del log_area trasparente.
        self.log_area.viewport().setAutoFillBackground(False)
        
        # Applica l'icona come sfondo semi-trasparente in modo programmatico
        self.set_log_area_background()
        main_layout.addWidget(self.log_area)

        # Barra di progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        # --- Frame "vetro" per i pulsanti di azione ---
        action_frame = QWidget()
        # Stile per l'effetto vetro: sfondo semi-trasparente e bordi arrotondati
        action_frame.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); border-radius: 10px;")
        
        button_layout = QHBoxLayout(action_frame)

        self.start_button = QPushButton("Avvia Scansione")
        self.start_button.setObjectName("startButton") # Assegna un nome per lo stile
        self.start_button.clicked.connect(self.start_scan)
        
        self.stop_button = QPushButton("Ferma Scansione")
        self.stop_button.setObjectName("stopButton") # Assegna un nome per lo stile
        self.stop_button.clicked.connect(self.stop_scan)
        self.stop_button.setEnabled(False)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        
        main_layout.addWidget(action_frame)

        self.setStatusBar(QStatusBar(self))
        self.scan_thread = None
        
        self.populate_disks() # Popola i dischi all'avvio

    def get_available_drives(self):
        """Rileva i dischi fisici disponibili sul sistema."""
        drives = []
        system = platform.system()
        
        if system == "Windows":
            if not wmi:
                self.statusBar().showMessage("WMI non disponibile per rilevare i dischi.")
                return ["\\\\.\\PhysicalDrive0"] # Fallback
            c = wmi.WMI()
            for drive in c.Win32_DiskDrive():
                drives.append((drive.DeviceID, f"{drive.Caption} ({int(int(drive.Size) / 10**9)} GB)"))
        
        elif system == "Linux":
            # Approccio semplice per Linux: cerca dispositivi a blocchi comuni
            for device in os.listdir("/dev"):
                if device.startswith("sd") or device.startswith("nvme"):
                    if not any(char.isdigit() for char in device):
                        path = os.path.join("/dev", device)
                        drives.append((path, path))
        
        elif system == "Darwin": # macOS
             # Approccio simile a Linux per macOS
            for i in range(10): # Cerca /dev/disk0, /dev/disk1, etc.
                path = f"/dev/disk{i}"
                if os.path.exists(path):
                    drives.append((path, path))
        
        return drives

    def populate_disks(self):
        """Popola il menu a tendina con i dischi trovati."""
        self.disk_combo.clear()
        self.statusBar().showMessage("Ricerca dischi in corso...")
        try:
            drives = self.get_available_drives()
            if not drives:
                self.log_area.setText("Nessun disco fisico trovato o permessi insufficienti.")
            for path, name in drives:
                self.disk_combo.addItem(name, userData=path) # Salva il percorso in userData
            self.statusBar().showMessage("Pronto.")
        except Exception as e:
            self.statusBar().showMessage(f"Errore nel rilevare i dischi: {e}")

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Seleziona Cartella di Output")
        if dir_path:
            self.output_path_edit.setText(dir_path)

    def start_scan(self):
        if self.disk_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Attenzione", "Nessun disco selezionato.")
            return
            
        disk_path = self.disk_combo.currentData() # Prende il percorso da userData
        output_dir = self.output_path_edit.text()

        if not output_dir:
            QMessageBox.warning(self, "Attenzione", "Seleziona una cartella di output.")
            return

        self.log_area.clear()
        self.toggle_controls(is_scanning=True)

        self.scan_thread = ScanWorker(disk_path, output_dir)
        self.scan_thread.progress_update.connect(self.log_area.append)
        self.scan_thread.progress_percentage.connect(self.progress_bar.setValue)
        self.scan_thread.scan_finished.connect(self.on_scan_finished)
        self.scan_thread.start()

    def stop_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.toggle_controls(is_scanning=False)

    def on_scan_finished(self, message):
        self.statusBar().showMessage(message)
        self.toggle_controls(is_scanning=False)
        self.progress_bar.setValue(100 if "completata" in message else 0)
        QMessageBox.information(self, "Scansione Terminata", message)

    def toggle_controls(self, is_scanning):
        """Abilita/disabilita i controlli durante la scansione."""
        self.start_button.setEnabled(not is_scanning)
        self.stop_button.setEnabled(is_scanning)
        self.disk_combo.setEnabled(not is_scanning)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("Scansione in corso..." if is_scanning else "Pronto.")

    def closeEvent(self, event):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.wait()
        event.accept()

    def set_log_area_background(self):
        """
        Imposta un'immagine semi-trasparente come sfondo dell'area di log.
        """
        try:
            # Carica l'icona originale
            pixmap = QPixmap(resource_path("app_icon.png"))
            if pixmap.isNull():
                return # Non fare nulla se l'immagine non viene trovata

            # Crea un'immagine vuota su cui disegnare
            transparent_pixmap = QPixmap(pixmap.size())
            transparent_pixmap.fill(Qt.transparent)

            # Disegna l'icona originale sulla nuova immagine con un'opacità
            painter = QPainter(transparent_pixmap)
            painter.setOpacity(0.1)  # Opacità del 10% (molto "vedo e non vedo")
            painter.drawPixmap(0, 0, pixmap)
            painter.end()

            # Applica la nuova immagine come sfondo usando una palette
            brush = QBrush(transparent_pixmap)
            palette = self.log_area.palette()
            palette.setColor(QPalette.Text, Qt.white) # Assicura che il testo sia bianco
            palette.setBrush(QPalette.Base, brush)
            self.log_area.setPalette(palette)
        except Exception as e:
            print(f"Errore nell'impostare lo sfondo del log: {e}")

if __name__ == "__main__":
    # Su Windows, controlla i privilegi e, se necessario, riavvia come amministratore.
    if platform.system() == "Windows":
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
        
        if not is_admin:
            # Riavvia lo script con privilegi di amministratore
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit(0) # Esce dall'istanza corrente non privilegiata
    
    app = QApplication(sys.argv)
    
    # Avvia il menu principale invece dell'app di recupero direttamente
    main_menu = MainMenu()
    main_menu.show()

    sys.exit(app.exec())
