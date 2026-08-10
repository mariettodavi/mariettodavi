"""App per spostare le foto scaricate da Google Foto (zip) nel NAS.

Flusso:
1. Scegli il file .zip scaricato da Google Foto (di solito in Download).
2. Naviga tra le cartelle del NAS con doppio click (anche dentro
   sottocartelle di sottocartelle) fino a dove vuoi estrarre le foto,
   oppure creane una nuova nella posizione in cui ti trovi.
3. Estrai: il contenuto dello zip viene copiato nella cartella in cui ti
   trovi e, se tutto va a buon fine, il file .zip originale viene
   cancellato da Download.
"""

import os
import zipfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

# Percorso di destinazione sul NAS. Modifica qui se cambia il nome del NAS
# o della cartella condivisa.
NAS_ROOT = r"\\FS6706T-EC49\Picasa - Foto"
NAS_ROOT_LABEL = "Picasa - Foto"

DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

INVALID_FOLDER_CHARS = r'\/:*?"<>|'


class PicasaFotoApp:
    def __init__(self, root):
        self.root = root
        root.title("Picasa Foto - Estrai su NAS")
        root.geometry("560x500")
        root.resizable(False, False)

        self.zip_path = tk.StringVar()
        # Percorso relativo rispetto a NAS_ROOT: "" = radice, altrimenti
        # qualcosa come "antaeus" o "antaeus/vacanze".
        self.current_rel_path = ""

        tk.Label(root, text="File ZIP da Download:").pack(anchor="w", padx=10, pady=(10, 0))
        frame_zip = tk.Frame(root)
        frame_zip.pack(fill="x", padx=10)
        tk.Entry(frame_zip, textvariable=self.zip_path, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        tk.Button(frame_zip, text="Sfoglia...", command=self.browse_zip).pack(
            side="left", padx=(5, 0)
        )

        tk.Label(root, text="Sfoglia le cartelle sul NAS (doppio click per entrare):").pack(
            anchor="w", padx=10, pady=(15, 0)
        )
        self.path_label = tk.Label(root, text="", anchor="w")
        self.path_label.pack(fill="x", padx=10)

        frame_list = tk.Frame(root)
        frame_list.pack(fill="both", padx=10, pady=(5, 0))
        self.listbox = tk.Listbox(frame_list, height=10)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(frame_list, command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.bind("<Double-Button-1>", self.on_double_click)

        frame_nav = tk.Frame(root)
        frame_nav.pack(fill="x", padx=10, pady=(8, 0))
        self.up_btn = tk.Button(frame_nav, text="Su di un livello", command=self.go_up)
        self.up_btn.pack(side="left")
        tk.Button(frame_nav, text="Aggiorna", command=self.refresh_folders).pack(
            side="left", padx=(5, 0)
        )
        tk.Button(frame_nav, text="Nuova cartella qui...", command=self.create_folder).pack(
            side="left", padx=(5, 0)
        )

        self.extract_btn = tk.Button(
            root, text="Estrai ZIP QUI", command=self.start_extract, state="disabled"
        )
        self.extract_btn.pack(pady=15)

        self.status = tk.Label(root, text="", fg="blue", wraplength=520, justify="left")
        self.status.pack(fill="x", padx=10)

        self.zip_path.trace_add("write", lambda *_: self.update_extract_button())

        self.refresh_folders()

    # ---- percorso corrente ----

    def current_dir(self):
        if self.current_rel_path:
            return os.path.join(NAS_ROOT, self.current_rel_path)
        return NAS_ROOT

    def display_path(self):
        if self.current_rel_path:
            return NAS_ROOT_LABEL + " / " + self.current_rel_path.replace(os.sep, " / ")
        return NAS_ROOT_LABEL

    def set_status(self, text, color="blue"):
        self.status.config(text=text, fg=color)

    # ---- navigazione ----

    def refresh_folders(self):
        self.listbox.delete(0, tk.END)
        current = self.current_dir()
        self.path_label.config(text=f"Posizione attuale: {self.display_path()}")
        self.up_btn.config(state="normal" if self.current_rel_path else "disabled")

        if not os.path.isdir(current):
            self.set_status(f"Impossibile raggiungere: {current}", "red")
            self.update_extract_button()
            return
        try:
            entries = sorted(
                name
                for name in os.listdir(current)
                if os.path.isdir(os.path.join(current, name))
            )
        except OSError as exc:
            self.set_status(f"Errore lettura cartella: {exc}", "red")
            self.update_extract_button()
            return

        for name in entries:
            self.listbox.insert(tk.END, name)
        self.set_status(f"Trovate {len(entries)} sottocartelle qui. Doppio click per entrare.")
        self.update_extract_button()

    def on_double_click(self, _event):
        selection = self.listbox.curselection()
        if not selection:
            return
        name = self.listbox.get(selection[0])
        self.current_rel_path = (
            os.path.join(self.current_rel_path, name) if self.current_rel_path else name
        )
        self.refresh_folders()

    def go_up(self):
        if not self.current_rel_path:
            return
        self.current_rel_path = os.path.dirname(self.current_rel_path)
        self.refresh_folders()

    def create_folder(self):
        name = simpledialog.askstring(
            "Nuova cartella",
            f"Nome della nuova cartella dentro:\n{self.display_path()}",
            parent=self.root,
        )
        if not name:
            return
        name = name.strip()
        if not name or any(ch in name for ch in INVALID_FOLDER_CHARS):
            messagebox.showerror(
                "Nome non valido",
                "Il nome della cartella non può essere vuoto o contenere: " + INVALID_FOLDER_CHARS,
            )
            return
        target = os.path.join(self.current_dir(), name)
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Errore", f"Impossibile creare la cartella:\n{exc}")
            return
        self.refresh_folders()

    # ---- estrazione ----

    def browse_zip(self):
        initial_dir = DOWNLOADS_DIR if os.path.isdir(DOWNLOADS_DIR) else os.path.expanduser("~")
        path = filedialog.askopenfilename(
            title="Seleziona il file ZIP scaricato da Google Foto",
            initialdir=initial_dir,
            filetypes=[("File ZIP", "*.zip")],
        )
        if path:
            self.zip_path.set(path)

    def update_extract_button(self):
        ready = bool(self.zip_path.get()) and os.path.isdir(self.current_dir())
        self.extract_btn.config(state="normal" if ready else "disabled")

    def start_extract(self):
        target_dir = self.current_dir()
        target_label = self.display_path()
        if not messagebox.askyesno(
            "Conferma estrazione", f'Estrarre lo zip dentro:\n"{target_label}" ?'
        ):
            return
        self.extract_btn.config(state="disabled")
        self.set_status("Estrazione in corso...")
        threading.Thread(
            target=self.extract, args=(target_dir, target_label), daemon=True
        ).start()

    def extract(self, target_dir, target_label):
        zip_path = self.zip_path.get()

        if not os.path.isfile(zip_path):
            self.report_error("Il file ZIP selezionato non esiste più.")
            return
        if not os.path.isdir(target_dir):
            self.report_error(f"La cartella di destinazione non esiste: {target_dir}")
            return

        try:
            with zipfile.ZipFile(zip_path) as zf:
                bad_file = zf.testzip()
                if bad_file:
                    self.report_error(f"File ZIP corrotto: {bad_file}")
                    return
                zf.extractall(target_dir)
        except zipfile.BadZipFile:
            self.report_error("Il file selezionato non è un archivio ZIP valido.")
            return
        except OSError as exc:
            self.report_error(f"Errore durante l'estrazione: {exc}")
            return

        try:
            os.remove(zip_path)
        except OSError as exc:
            self.root.after(
                0,
                lambda: self.set_status(
                    f"Estrazione completata, ma non sono riuscito a cancellare lo zip: {exc}",
                    "orange",
                ),
            )
            self.root.after(0, self.update_extract_button)
            return

        self.root.after(
            0,
            lambda: self.set_status(
                f'Fatto! Foto estratte in "{target_label}" e zip cancellato da Download.',
                "green",
            ),
        )
        self.root.after(0, lambda: self.zip_path.set(""))
        self.root.after(0, self.update_extract_button)

    def report_error(self, message):
        self.root.after(0, lambda: self.set_status(message, "red"))
        self.root.after(0, self.update_extract_button)


def main():
    root = tk.Tk()
    PicasaFotoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
