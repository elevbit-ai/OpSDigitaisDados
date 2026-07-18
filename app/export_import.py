"""
Export / import full internal database package for OpS Digitais Dados.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from database import Database, utc_now


MANIFEST_NAME = "manifest.json"
DB_NAME = "ops_digitais_dados.db"
PREVIEWS = "previews"


def export_package(db: Database, data_dir: Path, zip_path: Path, author: str) -> Path:
    """Create a ZIP with SQLite DB + preview images + manifest."""
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    data_dir = Path(data_dir)

    stats = db.stats()
    manifest = {
        "app": "OpS Digitais Dados",
        "author": author,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "stats": stats,
        "format_version": 1,
        "contents": [DB_NAME, PREVIEWS + "/", MANIFEST_NAME],
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(db.db_path, arcname=DB_NAME)
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        previews_dir = data_dir / PREVIEWS
        if previews_dir.is_dir():
            for p in previews_dir.rglob("*"):
                if p.is_file():
                    zf.write(p, arcname=str(Path(PREVIEWS) / p.relative_to(previews_dir)))

    db.log("export", f"file={zip_path.name}; users={stats['users']}; fps={stats['fingerprints']}")
    return zip_path


def import_package(db: Database, data_dir: Path, zip_path: Path) -> dict:
    """
    Replace local DB and previews with package contents.
    Creates a .bak of current DB first.
    """
    zip_path = Path(zip_path)
    data_dir = Path(data_dir)
    if not zip_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if DB_NAME not in names:
            raise ValueError("Pacote inválido: falta ops_digitais_dados.db")

        # Backup current DB
        if db.db_path.is_file():
            bak = db.db_path.with_suffix(db.db_path.suffix + f".bak_{datetime.now():%Y%m%d_%H%M%S}")
            shutil.copy2(db.db_path, bak)

        # Extract DB
        tmp_db = data_dir / "_import_tmp.db"
        with zf.open(DB_NAME) as src, open(tmp_db, "wb") as dst:
            shutil.copyfileobj(src, dst)

        # Extract previews
        previews_dir = data_dir / PREVIEWS
        if previews_dir.exists():
            shutil.rmtree(previews_dir)
        previews_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            if name.startswith(PREVIEWS + "/") and not name.endswith("/"):
                target = data_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        # Replace live DB
        shutil.move(str(tmp_db), str(db.db_path))

        manifest = {}
        if MANIFEST_NAME in names:
            manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))

    # Re-open schema ensure
    db._init_schema()
    stats = db.stats()
    db.log("import", f"file={zip_path.name}; users={stats['users']}; fps={stats['fingerprints']}")
    return {"manifest": manifest, "stats": stats}
