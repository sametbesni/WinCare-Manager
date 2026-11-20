from app.paths import get_resource_path


def load_stylesheet() -> str:
    # get_resource_path hem kaynak koddan hem de PyInstaller EXE'den çalışır.
    return get_resource_path("ui/styles/theme.qss").read_text(encoding="utf-8")
