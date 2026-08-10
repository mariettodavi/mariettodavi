"""App per spostare le foto scaricate da Google Foto (zip) nel NAS.

Flusso:
1. Scegli il file .zip scaricato da Google Foto (di solito in Download).
2. Scegli una sottocartella esistente dentro NAS_ROOT, oppure creane una nuova.
3. Estrai: il contenuto dello zip viene copiato nella sottocartella scelta
   e, se tutto va a buon fine, il file .zip originale viene cancellato.
"""

import os
import zipfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

# Percorso di destinazione sul NAS. Modifica qui se cambia il nome del NAS
# o della cartella condivisa.
NAS_ROOT = r"\\FS6706T-EC49\Picasa - Foto"

DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")

INVALID_FOLDER_CHARS = r'\/:*?"<>|'


class PicasaFotoApp:
    def __init__(self, root):
        self.root = root
        root.title("Picasa Foto - Estrai su NAS")
        root.geometry("560x460")
        root.resizable(False, False)

        self.zip_path = tk.StringVar()
        self.selected_folder = tk.StringVar()

        tk.Label(root, text="File ZIP da Download:").pack(anchor="w", padx=10, pady=(10, 0))
        frame_zip = tk.Frame(root)
        frame_zip.pack(fill="x", padx=10)
        tk.Entry(frame_zip, textvariable=self.zip_path, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        tk.Button(frame_zip, text="Sfoglia...", command=self.browse_zip).pack(
            side="left", padx=(5, 0)
        )

        tk.Label(root, text=f"Destinazione NAS: {NAS_ROOT}").pack(
            anchor="w", padx=10, pady=(15, 0)
        )

        tk.Label(root, text="Sottocartelle esistenti:").pack(anchor="w", padx=10, pady=(10, 0))
        frame_list = tk.Frame(root)
        frame_list.pack(fill="both", padx=10)
        self.listbox = tk.Listbox(frame_list, height=8)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(frame_list, command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.bind("<<ListboxSelect>>", self.on_select_folder)

        frame_new = tk.Frame(root)
        frame_new.pack(fill="x", padx=10, pady=(8, 0))
        tk.Button(frame_new, text="Aggiorna elenco", command=self.refresh_folders).pack(
            side="left"
        )
        tk.Button(frame_new, text="Nuova cartella...", command=self.create_folder).pack(
            side="left", padx=(5, 0)
        )

        tk.Label(root, text="Cartella selezionata:").pack(anchor="w", padx=10, pady=(10, 0))
        tk.Entry(root, textvariable=self.selected_folder, state="readonly").pack(
            fill="x", padx=10
        )

        self.extract_btn = tk.Button(
            root, text="Estrai ZIP nella cartella", command=self.start_extract, state="disabled"
        )
        self.extract_btn.pack(pady=15)

        self.status = tk.Label(root, text="", fg="blue", wraplength=520, justify="left")
        self.status.pack(fill="x", padx=10)

        self.zip_path.trace_add("write", lambda *_: self.update_extract_button())
        self.selected_folder.trace_add("write", lambda *_: self.update_extract_button())

        self.refresh_folders()

    def set_status(self, text, color="blue"):
        self.status.config(text=text, fg=color)

    def browse_zip(self):
        initial_dir = DOWNLOADS_DIR if os.path.isdir(DOWNLOADS_DIR) else os.path.expanduser("~")
        path = filedialog.askopenfilename(
            title="Seleziona il file ZIP scaricato da Google Foto",
            initialdir=initial_dir,
            filetypes=[("File ZIP", "*.zip")],
        )
        if path:
            self.zip_path.set(path)

    def refresh_folders(self):
        self.listbox.delete(0, tk.END)
        if not os.path.isdir(NAS_ROOT):
            self.set_status(f"Impossibile raggiungere il NAS: {NAS_ROOT}", "red")
            return
        try:
            entries = sorted(
                name
                for name in os.listdir(NAS_ROOT)
                if os.path.isdir(os.path.join(NAS_ROOT, name))
            )
        except OSError as exc:
            self.set_status(f"Errore lettura NAS: {exc}", "red")
            return
        for name in entries:
            self.listbox.insert(tk.END, name)
        self.set_status(f"Trovate {len(entries)} cartelle su NAS.")

    def on_select_folder(self, _event):
        selection = self.listbox.curselection()
        if selection:
            self.selected_folder.set(self.listbox.get(selection[0]))

    def create_folder(self):
        name = simpledialog.askstring(
            "Nuova cartella", "Nome della nuova cartella:", parent=self.root
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
        target = os.path.join(NAS_ROOT, name)
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Errore", f"Impossibile creare la cartella:\n{exc}")
            return
        self.refresh_folders()
        items = list(self.listbox.get(0, tk.END))
        if name in items:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(items.index(name))
        self.selected_folder.set(name)

    def update_extract_button(self):
        ready = bool(self.zip_path.get()) and bool(self.selected_folder.get())
        self.extract_btn.config(state="normal" if ready else "disabled")

    def start_extract(self):
        self.extract_btn.config(state="disabled")
        self.set_status("Estrazione in corso...")
        threading.Thread(target=self.extract, daemon=True).start()

    def extract(self):
        zip_path = self.zip_path.get()
        folder_name = self.selected_folder.get()
        target_dir = os.path.join(NAS_ROOT, folder_name)

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
                f'Fatto! Foto estratte in "{folder_name}" e zip cancellato da Download.',
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
