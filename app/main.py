"""
OpS Digitais Dados — leitor de impressão digital e registrador local
Autor: Joaquim Pedro de Morais Filho
Site: usacomment.com | E-mail: zicutake@mail.ru
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from database import Database  # noqa: E402
from export_import import export_package, import_package  # noqa: E402
from fingerprint import (  # noqa: E402
    extract_template,
    identify,
    save_preview_copy,
)

APP_NAME = "OpS Digitais Dados"
AUTHOR = "Joaquim Pedro de Morais Filho"
SITE = "https://usacomment.com"
EMAIL = "zicutake@mail.ru"
VERSION = "1.0.0"
MATCH_THRESHOLD = 35.0

FINGER_LABELS = [
    "polegar_direito",
    "indicador_direito",
    "medio_direito",
    "anelar_direito",
    "mindinho_direito",
    "polegar_esquerdo",
    "indicador_esquerdo",
    "medio_esquerdo",
    "anelar_esquerdo",
    "mindinho_esquerdo",
]


def data_paths() -> tuple[Path, Path, Path]:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        # Prefer writable folder next to EXE or in user data
        data = base / "data"
    else:
        data = ROOT / "data"
    data.mkdir(parents=True, exist_ok=True)
    db_path = data / "ops_digitais_dados.db"
    previews = data / "previews"
    previews.mkdir(parents=True, exist_ok=True)
    return data, db_path, previews


class OpSApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.data_dir, db_path, self.previews_dir = data_paths()
        self.db = Database(db_path)
        self.selected_user_id: int | None = None
        self.preview_photo = None
        self.enroll_image_path: Path | None = None
        self.verify_image_path: Path | None = None

        self.title(f"{APP_NAME} — {AUTHOR}")
        self.geometry("1200x780")
        self.minsize(1000, 680)

        self._build_ui()
        self.refresh_users()
        self.refresh_stats()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0, fg_color="#071a2e")
        header.pack(fill="x")
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=18, pady=12)
        ctk.CTkLabel(left, text=APP_NAME, font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text=f"por {AUTHOR}  ·  v{VERSION}  ·  banco interno local",
            text_color="#8fb7d8",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w")

        btns = ctk.CTkFrame(header, fg_color="transparent")
        btns.pack(side="right", padx=12)
        for text, cmd, color in [
            ("Exportar tudo", self.export_all, "#0e7c66"),
            ("Importar / Upload", self.import_all, "#3d5a80"),
            ("Website", self.open_site, None),
            ("Tutorial", self.open_tutorial, None),
            ("GitHub", self.open_github, "#24292f"),
        ]:
            kw = {"text": text, "width": 120, "command": cmd}
            if color:
                kw["fg_color"] = color
            ctk.CTkButton(btns, **kw).pack(side="left", padx=4)

        warn = ctk.CTkFrame(self, fg_color="#1f2a12", corner_radius=0)
        warn.pack(fill="x")
        ctk.CTkLabel(
            warn,
            text=(
                "Dados biométricos e cadastrais ficam no PC (SQLite local). "
                "Use Exportar para download do pacote completo e Importar para restaurar. "
                "Leitor: imagem de impressão digital (scanner/exportação). "
                f"Contato: {EMAIL} · {SITE}"
            ),
            wraplength=1120,
            justify="left",
            text_color="#d8efb0",
            font=ctk.CTkFont(size=12),
        ).pack(padx=14, pady=8, anchor="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=10)

        # Left: users
        col1 = ctk.CTkFrame(body, width=340)
        col1.pack(side="left", fill="both", padx=(0, 8))
        col1.pack_propagate(False)
        ctk.CTkLabel(col1, text="Usuários registrados", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=12, pady=(12, 4)
        )
        self.search_var = ctk.StringVar()
        search_row = ctk.CTkFrame(col1, fg_color="transparent")
        search_row.pack(fill="x", padx=10)
        ctk.CTkEntry(search_row, textvariable=self.search_var, placeholder_text="Buscar…").pack(
            side="left", fill="x", expand=True
        )
        ctk.CTkButton(search_row, text="OK", width=50, command=self.refresh_users).pack(side="left", padx=4)
        self.user_list = ctk.CTkScrollableFrame(col1)
        self.user_list.pack(fill="both", expand=True, padx=8, pady=8)

        # Center: form
        col2 = ctk.CTkFrame(body)
        col2.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(col2, text="Cadastro do usuário", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=12, pady=(12, 6)
        )
        form = ctk.CTkFrame(col2, fg_color="transparent")
        form.pack(fill="x", padx=12)

        self.fields = {}
        for key, label in [
            ("full_name", "Nome completo *"),
            ("document_id", "Documento / ID"),
            ("email", "E-mail"),
            ("phone", "Telefone"),
            ("notes", "Observações"),
        ]:
            ctk.CTkLabel(form, text=label).pack(anchor="w")
            if key == "notes":
                e = ctk.CTkTextbox(form, height=70)
                e.pack(fill="x", pady=(0, 8))
            else:
                e = ctk.CTkEntry(form)
                e.pack(fill="x", pady=(0, 8))
            self.fields[key] = e

        row = ctk.CTkFrame(col2, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkButton(row, text="Novo", width=90, command=self.clear_form, fg_color="#4a5568").pack(
            side="left", padx=3
        )
        ctk.CTkButton(row, text="Salvar", width=90, command=self.save_user, fg_color="#0e7c66").pack(
            side="left", padx=3
        )
        ctk.CTkButton(row, text="Excluir", width=90, command=self.delete_user, fg_color="#9b2c2c").pack(
            side="left", padx=3
        )

        self.stats_label = ctk.CTkLabel(col2, text="", text_color="#9db4c7")
        self.stats_label.pack(anchor="w", padx=12, pady=8)

        self.fp_info = ctk.CTkTextbox(col2, height=160)
        self.fp_info.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.fp_info.insert("1.0", "Selecione um usuário para ver as digitais cadastradas.")
        self.fp_info.configure(state="disabled")

        # Right: biometrics
        col3 = ctk.CTkFrame(body, width=360)
        col3.pack(side="right", fill="both", padx=(8, 0))
        col3.pack_propagate(False)
        ctk.CTkLabel(col3, text="Impressão digital", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=12, pady=(12, 6)
        )

        ctk.CTkLabel(col3, text="Dedo / etiqueta").pack(anchor="w", padx=12)
        self.finger_var = ctk.StringVar(value="indicador_direito")
        ctk.CTkOptionMenu(col3, variable=self.finger_var, values=FINGER_LABELS).pack(
            fill="x", padx=12, pady=(0, 8)
        )

        ctk.CTkButton(col3, text="1) Carregar imagem da digital…", command=self.load_enroll_image).pack(
            fill="x", padx=12, pady=4
        )
        ctk.CTkButton(
            col3, text="2) Registrar digital no usuário", command=self.enroll_fingerprint, fg_color="#0e7c66"
        ).pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(col3, text="Verificação / identificação (1:N)").pack(anchor="w", padx=12, pady=(14, 4))
        ctk.CTkButton(col3, text="Carregar digital para verificar…", command=self.load_verify_image).pack(
            fill="x", padx=12, pady=4
        )
        ctk.CTkButton(
            col3, text="Identificar no banco", command=self.verify_fingerprint, fg_color="#2b6cb0"
        ).pack(fill="x", padx=12, pady=4)

        self.preview_label = ctk.CTkLabel(col3, text="Pré-visualização", height=220)
        self.preview_label.pack(fill="both", expand=True, padx=12, pady=12)

        foot = ctk.CTkLabel(
            self,
            text=f"© {APP_NAME} · {AUTHOR} · {EMAIL} · {SITE}",
            text_color="#6b8299",
            font=ctk.CTkFont(size=11),
        )
        foot.pack(pady=(0, 8))

    # ----- navigation -----
    def open_site(self) -> None:
        webbrowser.open(SITE)

    def open_tutorial(self) -> None:
        for p in [ROOT / "website" / "tutorial.html", ROOT / "docs" / "TUTORIAL.md"]:
            if p.is_file():
                webbrowser.open(p.resolve().as_uri())
                return
        messagebox.showinfo(APP_NAME, "Tutorial em website/tutorial.html")

    def open_github(self) -> None:
        url = "https://github.com/elevbit-ai/OpSDigitaisDados"
        cfg = ROOT / ".git" / "config"
        if cfg.is_file():
            text = cfg.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                if "url =" in line and "github.com" in line:
                    u = line.split("url =", 1)[1].strip().replace(".git", "")
                    if u.startswith("git@"):
                        u = u.replace("git@github.com:", "https://github.com/")
                    url = u
                    break
        webbrowser.open(url)

    # ----- users -----
    def refresh_stats(self) -> None:
        s = self.db.stats()
        self.stats_label.configure(
            text=f"Usuários: {s['users']}  ·  Digitais: {s['fingerprints']}  ·  Auditoria: {s['audit_events']}"
        )

    def refresh_users(self) -> None:
        for w in self.user_list.winfo_children():
            w.destroy()
        users = self.db.list_users(self.search_var.get())
        for u in users:
            label = f"{u.full_name}  ({u.fingerprint_count} dig.)"
            b = ctk.CTkButton(
                self.user_list,
                text=label,
                anchor="w",
                fg_color="#132838" if u.id != self.selected_user_id else "#1d4e89",
                command=lambda uid=u.id: self.select_user(uid),
            )
            b.pack(fill="x", pady=2)

    def clear_form(self) -> None:
        self.selected_user_id = None
        for key, widget in self.fields.items():
            if key == "notes":
                widget.delete("1.0", "end")
            else:
                widget.delete(0, "end")
        self._set_fp_info("Formulário limpo. Preencha e clique em Salvar.")
        self.refresh_users()

    def select_user(self, user_id: int) -> None:
        user = self.db.get_user(user_id)
        if not user:
            return
        self.selected_user_id = user_id
        for key, widget in self.fields.items():
            val = getattr(user, key)
            if key == "notes":
                widget.delete("1.0", "end")
                widget.insert("1.0", val)
            else:
                widget.delete(0, "end")
                widget.insert(0, val)
        self._show_user_fps(user_id)
        self.refresh_users()

    def _get_form(self) -> dict[str, str]:
        data = {}
        for key, widget in self.fields.items():
            if key == "notes":
                data[key] = widget.get("1.0", "end").strip()
            else:
                data[key] = widget.get().strip()
        return data

    def save_user(self) -> None:
        data = self._get_form()
        if not data["full_name"]:
            messagebox.showwarning(APP_NAME, "Nome completo é obrigatório.")
            return
        if self.selected_user_id:
            self.db.update_user(self.selected_user_id, **data)
            messagebox.showinfo(APP_NAME, "Usuário atualizado.")
        else:
            uid = self.db.add_user(**data)
            self.selected_user_id = uid
            messagebox.showinfo(APP_NAME, f"Usuário criado (ID {uid}).")
        self.refresh_users()
        self.refresh_stats()
        if self.selected_user_id:
            self._show_user_fps(self.selected_user_id)

    def delete_user(self) -> None:
        if not self.selected_user_id:
            messagebox.showwarning(APP_NAME, "Selecione um usuário.")
            return
        if not messagebox.askyesno(APP_NAME, "Excluir usuário e todas as digitais?"):
            return
        self.db.delete_user(self.selected_user_id)
        self.clear_form()
        self.refresh_users()
        self.refresh_stats()

    def _set_fp_info(self, text: str) -> None:
        self.fp_info.configure(state="normal")
        self.fp_info.delete("1.0", "end")
        self.fp_info.insert("1.0", text)
        self.fp_info.configure(state="disabled")

    def _show_user_fps(self, user_id: int) -> None:
        fps = self.db.list_fingerprints(user_id)
        if not fps:
            self._set_fp_info("Nenhuma impressão digital cadastrada para este usuário.")
            return
        lines = [f"Digitais do usuário #{user_id}:", ""]
        for f in fps:
            lines.append(
                f"• ID {f['id']} · {f['finger_label']} · qualidade {f['quality']:.1f} · "
                f"pontos {f['keypoints']} · {f['enrolled_at']}"
            )
        self._set_fp_info("\n".join(lines))

    # ----- fingerprint -----
    def _show_preview(self, path: Path) -> None:
        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((320, 280), Image.Resampling.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=self.preview_photo, text="")
        except Exception as exc:
            self.preview_label.configure(image=None, text=f"Pré-visualização indisponível\n{exc}")

    def load_enroll_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Imagem da impressão digital",
            filetypes=[("Imagens", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.webp"), ("Todos", "*.*")],
        )
        if not path:
            return
        self.enroll_image_path = Path(path)
        self._show_preview(self.enroll_image_path)

    def enroll_fingerprint(self) -> None:
        if not self.selected_user_id:
            messagebox.showwarning(APP_NAME, "Selecione ou salve um usuário primeiro.")
            return
        if not self.enroll_image_path or not self.enroll_image_path.is_file():
            messagebox.showwarning(APP_NAME, "Carregue a imagem da digital.")
            return
        try:
            tmpl = extract_template(self.enroll_image_path)
            preview = self.previews_dir / f"user{self.selected_user_id}_{self.finger_var.get()}_{tmpl.keypoints}.png"
            save_preview_copy(self.enroll_image_path, preview)
            fp_id = self.db.add_fingerprint(
                user_id=self.selected_user_id,
                template=tmpl.to_bytes(),
                finger_label=self.finger_var.get(),
                preview_path=str(preview),
                quality=tmpl.quality,
                keypoints=tmpl.keypoints,
            )
            self.refresh_users()
            self.refresh_stats()
            self._show_user_fps(self.selected_user_id)
            messagebox.showinfo(
                APP_NAME,
                f"Digital registrada (ID {fp_id}).\n"
                f"Qualidade: {tmpl.quality:.1f}\nPontos-chave: {tmpl.keypoints}",
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Falha no registro da digital:\n{exc}")

    def load_verify_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Digital para verificação",
            filetypes=[("Imagens", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.webp"), ("Todos", "*.*")],
        )
        if not path:
            return
        self.verify_image_path = Path(path)
        self._show_preview(self.verify_image_path)

    def verify_fingerprint(self) -> None:
        if not self.verify_image_path or not self.verify_image_path.is_file():
            messagebox.showwarning(APP_NAME, "Carregue uma digital para verificar.")
            return
        gallery = self.db.all_templates()
        if not gallery:
            messagebox.showwarning(APP_NAME, "Nenhuma digital no banco interno.")
            return
        try:
            result = identify(self.verify_image_path, gallery, threshold=MATCH_THRESHOLD)
            self.db.log(
                "fingerprint_verify",
                f"score={result['score'] if result else 0}; match={result['matched'] if result else False}",
            )
            self.refresh_stats()
            if result and result["matched"]:
                messagebox.showinfo(
                    APP_NAME,
                    f"IDENTIFICADO\n\n"
                    f"Usuário: {result['full_name']}\n"
                    f"ID usuário: {result['user_id']}\n"
                    f"ID digital: {result['fp_id']}\n"
                    f"Score: {result['score']}% (limite {MATCH_THRESHOLD})",
                )
                self.select_user(result["user_id"])
            else:
                best = result["score"] if result else 0
                messagebox.showwarning(
                    APP_NAME,
                    f"Não identificado.\nMelhor score: {best}% (limite {MATCH_THRESHOLD}).",
                )
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Falha na verificação:\n{exc}")

    # ----- export / import -----
    def export_all(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Download / exportar tudo",
            defaultextension=".zip",
            filetypes=[("Pacote OpS", "*.zip")],
            initialfile=f"OpS_Digitais_Dados_backup.zip",
        )
        if not path:
            return
        try:
            out = export_package(self.db, self.data_dir, Path(path), AUTHOR)
            self.refresh_stats()
            messagebox.showinfo(APP_NAME, f"Pacote exportado:\n{out}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Erro ao exportar:\n{exc}")

    def import_all(self) -> None:
        path = filedialog.askopenfilename(
            title="Upload / importar pacote",
            filetypes=[("Pacote OpS", "*.zip"), ("Todos", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            APP_NAME,
            "Importar substitui o banco local atual (backup .bak será criado). Continuar?",
        ):
            return
        try:
            info = import_package(self.db, self.data_dir, Path(path))
            self.selected_user_id = None
            self.clear_form()
            self.refresh_users()
            self.refresh_stats()
            s = info["stats"]
            messagebox.showinfo(
                APP_NAME,
                f"Importação concluída.\nUsuários: {s['users']}\nDigitais: {s['fingerprints']}",
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Erro ao importar:\n{exc}")


def main() -> None:
    app = OpSApp()
    app.mainloop()


if __name__ == "__main__":
    main()
